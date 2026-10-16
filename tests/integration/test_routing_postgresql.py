"""Opt-in, isolated-schema migration and persistence checks on real PostgreSQL."""
import os
import unittest
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from backend.ingest.cutsheet import ingest_cutsheet_rows
from backend.ingest.overhead import OverheadIngestionResult, OverheadIngestionSummary
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.config import database_url
from backend.persistence.postgresql.importer import replace_project_topology
from backend.services.topology_database_builder import build_topology_database_from_results
from backend.services import routing_configuration as routing
from backend.services.routing_graph import derive_graph
from backend.services.routing_pathfinding import preview_route


@unittest.skipUnless(os.environ.get('RUN_ROUTING_POSTGRESQL_TESTS') == '1', 'set RUN_ROUTING_POSTGRESQL_TESTS=1')
class RoutingPostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(database_url())
        cls.connection = cls.engine.connect()
        cls.schema = 'routing_test_' + uuid4().hex
        cls.addClassCleanup(cls.tearDownClass)
        cls.connection.execute(text(f'CREATE SCHEMA {cls.schema}'))
        cls.connection.execute(text(f'SET search_path TO {cls.schema}'))
        cls.connection.commit()
        cls.alembic = Config('alembic.ini')
        cls.alembic.attributes['connection'] = cls.connection
        command.upgrade(cls.alembic, 'head')
        cls.connection.commit()
        # Additive revision can be reversed without removing existing topology.
        command.downgrade(cls.alembic, '4d8f1b2c9a73')
        cls.connection.commit()
        assert 'rooms' in inspect(cls.connection).get_table_names()
        assert 'routing_layouts' not in inspect(cls.connection).get_table_names()
        cls.connection.commit()
        command.upgrade(cls.alembic, 'head')
        cls.connection.commit()

    @classmethod
    def tearDownClass(cls):
        if cls.connection.closed:
            return
        cls.connection.rollback()
        cls.connection.execute(text('SET search_path TO public'))
        # Only the generated test schema is removed.
        cls.connection.execute(text(f'DROP SCHEMA {cls.schema} CASCADE'))
        cls.connection.commit()
        cls.connection.close()
        cls.engine.dispose()

    def setUp(self):
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, autoflush=False)
        self.session.add(db.Project(uid='LBB01'))
        self.session.flush()
        self.session.add(db.Building(uid='LBB01:A', project_uid='LBB01', building_id='A'))
        self.session.flush()
        self.session.add_all([db.Room(uid=f'LBB01:A:DH1-{i}', project_uid='LBB01', building_uid='LBB01:A', room_id=f'DH1-{i}') for i in range(1, 6)])
        self.session.flush()

    def tearDown(self):
        self.session.close()
        self.transaction.rollback()

    def test_initializer_graph_and_persistence(self):
        data = routing.initialize_lbb01(self.session)
        self.assertEqual(data, routing.initialize_lbb01(self.session))
        uid = data['layout']['uid']
        for band in (b for b in data['bands'] if b['kind'] == 'PASSAGE'):
            routing.save_resource(self.session, uid, 'passage-tiers', {'passage_band_uid': band['uid'], 'tier': 1, 'pathway_type': 'LADDER_RACK'})
        for route in (r for r in data['cross_routes'] if r['kind'] == 'SECTION_GAP'):
            routing.save_resource(self.session, uid, 'cross-route-tiers', {'cross_route_uid': route['uid'], 'tier': 1, 'pathway_type': 'BASKET_TRAY'})
        resolved = routing.resolved_layout(self.session, uid)
        graph = derive_graph(resolved)
        self.assertEqual(graph, derive_graph(resolved))
        north = next(b for b in data['bands'] if b['code'] == 'NORTH')['uid']
        result = preview_route(graph, resolved, f'passage:{north}:station:0:tier:1',
                               f"passage:{north}:station:{resolved['geometry']['hall_length_in']}:tier:1")
        self.assertEqual(result.planar_length_in, 11544)
        self.assertEqual(result.vertical_transition_count, 0)
        self.assertEqual(len(resolved['geometry']['gaps']), 4)

    def test_reimport_retains_routing_and_existing_rooms(self):
        before = routing.initialize_lbb01(self.session)
        database = build_topology_database_from_results(
            cutsheet_result=ingest_cutsheet_rows([], project_uid='LBB01'),
            overhead_result=OverheadIngestionResult(summary=OverheadIngestionSummary(cabinets=0, data_halls=0, unknown_category_cabinets=0), cabinets=[]),
            project_uid='LBB01',
        )
        replace_project_topology(self.session, database)
        self.session.flush()
        self.session.expire_all()
        after = routing.resolved_layout(self.session, before['layout']['uid'])
        self.assertEqual(before['geometry'], after['geometry'])
        self.assertEqual(len(after['sections']), 5)

    def test_manual_segment_marking_persistence(self):
        data = routing.initialize_lbb01(self.session)
        uid = data['layout']['uid']
        self.assertEqual(data['segment_annotations'], [])
        north = next(b['uid'] for b in data['bands'] if b['code'] == 'NORTH')
        item = routing.save_resource(self.session, uid, 'segment-annotations', {
            'passage_band_uid': north, 'start_station_in': 0, 'end_station_in': 120,
            'usable': False, 'cable_classes': ['LC', 'MPO'], 'notes': 'Manual marking'})
        self.session.expire_all()
        actual = routing.resolved_layout(self.session, uid)['segment_annotations'][0]
        self.assertEqual(actual['cable_classes'], ['LC', 'MPO'])
        self.assertFalse(actual['usable'])
        routing.delete_resource(self.session, uid, 'segment-annotations', item['uid'])
        self.assertEqual(routing.resolved_layout(self.session, uid)['segment_annotations'], [])

    def test_elevation_and_bundle_section_persistence(self):
        data = routing.initialize_lbb01(self.session)
        uid = data['layout']['uid']
        north = next(b['uid'] for b in data['bands'] if b['code'] == 'NORTH')
        tier = routing.save_resource(self.session, uid, 'passage-tiers', {'passage_band_uid': north, 'tier': 1,
            'pathway_type': 'LADDER_RACK', 'elevation_in': 121})
        parent = routing.save_resource(self.session, uid, 'segment-annotations', {'passage_band_uid': north, 'start_station_in': 108,
            'end_station_in': 276, 'section_reference': 'Inner toward CENTRAL'})
        routing.save_resource(self.session, uid, 'bundle-placements', {'segment_annotation_uid': parent['uid'], 'tier': 1,
            'layer': 2, 'position': 3, 'label': 'LC-G1', 'cable_class': 'LC'})
        self.session.expire_all()
        resolved = routing.resolved_layout(self.session, uid)
        self.assertEqual(resolved['passage_tiers'][0]['elevation_in'], 121)
        self.assertEqual((resolved['bundle_placements'][0]['layer'], resolved['bundle_placements'][0]['position']), (2, 3))
        routing.save_resource(self.session, uid, 'passage-tiers', {'elevation_in': None}, tier['uid'])
        self.assertIsNone(routing.resolved_layout(self.session, uid)['passage_tiers'][0]['elevation_in'])

    def test_multi_cell_rectangles_connections_and_upgrade_preservation(self):
        data = routing.initialize_lbb01(self.session)
        uid = data['layout']['uid']
        north = next(b['uid'] for b in data['bands'] if b['code'] == 'NORTH')
        routing.save_resource(self.session, uid, 'passage-tiers', {'passage_band_uid': north, 'tier': 1, 'pathway_type': 'LADDER_RACK'})
        parent = routing.save_resource(self.session, uid, 'segment-annotations', {'passage_band_uid': north, 'start_station_in': 0, 'end_station_in': 108, 'grid_columns': 20, 'grid_rows': 10})
        old = routing.save_resource(self.session, uid, 'bundle-placements', {'segment_annotation_uid': parent['uid'], 'tier': 1, 'layer': 9, 'position': 15, 'label': 'Legacy G1'})
        # A populated round trip preserves every legacy slot, expanding defaults as needed.
        command.downgrade(self.alembic, 'b5f63c9e0214')
        command.upgrade(self.alembic, 'head')
        self.session.expire_all()
        resolved = routing.resolved_layout(self.session, uid)
        self.assertEqual((resolved['segment_annotations'][0]['grid_columns'], resolved['segment_annotations'][0]['grid_rows']), (15, 9))
        self.assertEqual((resolved['bundle_placements'][0]['position'], resolved['bundle_placements'][0]['slot_width']), (15, 1))
        routing.save_resource(self.session, uid, 'bundle-placements', {'position': 1, 'layer': 1, 'slot_width': 3, 'slot_height': 2, 'offset_across_in': 0, 'offset_up_in': 0, 'occupied_width_in': 6, 'occupied_height_in': 2}, old['uid'])
        other = routing.save_resource(self.session, uid, 'segment-annotations', {'passage_band_uid': north, 'start_station_in': 108, 'end_station_in': 276})
        new = routing.save_resource(self.session, uid, 'bundle-placements', {'segment_annotation_uid': other['uid'], 'tier': 1, 'label': 'Legacy G1', 'layer': None, 'position': None, 'slot_width': None, 'slot_height': None, 'offset_across_in': 0, 'offset_up_in': 0, 'occupied_width_in': 4, 'occupied_height_in': 2})
        connection = routing.save_resource(self.session, uid, 'bundle-connections', {'from_placement_uid': old['uid'], 'from_end': 'END', 'to_placement_uid': new['uid'], 'to_end': 'START'})
        self.session.expire_all()
        resolved = routing.resolved_layout(self.session, uid)
        section = next(s for s in resolved['section_occupations'] if s['segment_annotation_uid'] == parent['uid'])
        self.assertEqual(sum(v > 0 for row in section['cells'] for v in row), 6)
        self.assertEqual(section['rectangles'][0]['occupied_width_in'], 6)
        self.assertEqual(resolved['bundle_connections'][0]['uid'], connection['uid'])
        self.assertEqual(len(derive_graph(resolved).nodes), len({(n.x_in, n.y_in, n.tier) for n in derive_graph(resolved).nodes}))

    def test_measured_elevation_downgrade_preserves_effective_values(self):
        data = routing.initialize_lbb01(self.session)
        uid = data['layout']['uid']
        north = next(b['uid'] for b in data['bands'] if b['code'] == 'NORTH')
        routing.save_resource(self.session, uid, 'passage-tiers', {'passage_band_uid': north, 'tier': 1, 'pathway_type': 'BASKET_TRAY'})
        routing.save_resource(self.session, uid, 'passage-tiers', {'passage_band_uid': north, 'tier': 3, 'pathway_type': 'LADDER_RACK', 'elevation_reference': 'NORTH_SOUTH_TOP'})
        command.downgrade(self.alembic, 'c73a91de4826')
        command.upgrade(self.alembic, 'head')
        self.session.expire_all()
        resolved = routing.resolved_layout(self.session, uid)
        self.assertEqual({p['effective_elevation_in'] for p in resolved['passage_tiers']}, {98, 116})
        self.assertTrue(all(p['elevation_reference'] is None for p in resolved['passage_tiers']))


if __name__ == '__main__':
    unittest.main()
