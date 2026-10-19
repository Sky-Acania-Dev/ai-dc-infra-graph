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

    def test_full_inventory_profile_openings_and_aggregate_membership(self):
        from backend.services.routing_test_profile import configure_hall_test
        from backend.services.routing_inventory_review import inventory_review_context
        data = routing.initialize_lbb01(self.session); uid = data['layout']['uid']
        for number, col, category in ((801, 0, 'T0-FE-v1a'), (802, 1, 'HD-GB3g'), (811, 9, 'HD-GB3g'), (812, 8, 'HD-GB3g')):
            self.session.add(db.Cabinet(uid=f'full-cab-{number}', project_uid='LBB01', building_uid='LBB01:A', room_uid='LBB01:A:DH1-1', cabinet_id=str(number), source_col=col, category=category))
        self.session.flush()
        for number in (801, 811):
            self.session.add(db.Port(uid=f'full-port-{number}', project_uid='LBB01', building_uid='LBB01:A', room_uid='LBB01:A:DH1-1', cabinet_uid=f'full-cab-{number}', port_name='P1'))
        self.session.flush()
        for index in range(3):
            self.session.add(db.Cable(uid=f'full-cable-{index}', project_uid='LBB01', building_uid='LBB01:A', a_port_uid='full-port-801' if index % 2 else 'full-port-811', z_port_uid='full-port-811' if index % 2 else 'full-port-801', cable_type='LC', construction_phase='Management & Ethernet'))
        self.session.flush()
        setup = configure_hall_test(self.session, uid)
        self.assertEqual(setup['created_opening_count'], 160)
        self.assertEqual(configure_hall_test(self.session, uid)['created_opening_count'], 0)
        self.session.expire_all()
        review, planner = inventory_review_context(self.session, uid)
        self.assertEqual((review['inventory_cable_count'], review['routed_cable_count'], len(review['groups'])), (3, 3, 1))
        self.assertEqual(review['groups'][0]['policy'], 'FE_OUTER_TOP')
        self.assertEqual(review['groups'][0]['route']['vertical_transition_count'], 2)
        self.assertFalse(any(e['edge_type'] == 'PASSAGE' and e['tier'] == 3 and e['passage_code'] in ('NORTH', 'SOUTH') for e in planner.edges.values()))
        from backend.schemas.routing_manual import ManualBatchInput
        from backend.services.routing_manual_routes import update_manual_batch
        group = review['groups'][0]
        chain = [review['planning_segments'][i]['id'] for i in group['route']['edge_indices']]
        request = ManualBatchInput(scope='hall',topology_revision=review['topology_revision'],groups=[dict(group_uid=group['uid'],expected_version=None,segment_ids=chain,start_tier=3,end_tier=3)])
        saved = update_manual_batch(self.session,uid,request,'full-hall-technician')['review']
        self.assertEqual(saved['manual_group_count'],1)
        self.assertEqual((saved['groups'][0]['route_source'],saved['groups'][0]['manual_status']),('MANUAL','VALID'))

    def test_inventory_count_query_bounds_parallel_memory_without_leaking_settings(self):
        from backend.services.routing_inventory_review import inventory_counts
        data = routing.initialize_lbb01(self.session)
        layout = routing.get_layout(self.session, data['layout']['uid'])
        self.session.execute(text('SET LOCAL max_parallel_workers_per_gather = 4'))
        savepoint = self.session.begin_nested()
        self.assertEqual(inventory_counts(self.session, layout), [])
        self.assertEqual(self.session.scalar(text('SHOW max_parallel_workers_per_gather')), '0')
        savepoint.rollback()
        self.assertEqual(self.session.scalar(text('SHOW max_parallel_workers_per_gather')), '4')

    def test_manual_tier_routes_persist_and_are_not_replaced_by_defaults(self):
        from backend.services.routing_cable_review import cable_review
        from backend.services.routing_manual_routes import initialize_test_tiers, update_manual_batch, RoutingRouteConflict
        from backend.schemas.routing_manual import ManualBatchInput
        from backend.persistence.postgresql.routing_models import RoutingManualCableRoute
        data = routing.initialize_lbb01(self.session); uid = data['layout']['uid']
        for number in list(range(1, 21)) + list(range(801, 821)):
            offset = (number - 1) % 20
            self.session.add(db.Cabinet(uid=f'pilot-cab-{number}', project_uid='LBB01', building_uid='LBB01:A',
                room_uid='LBB01:A:DH1-1', cabinet_id=f'{number:03d}', source_col=offset if offset < 10 else 19-offset))
        self.session.flush()
        for number in (801, 811):
            self.session.add(db.Port(uid=f'pilot-port-{number}', project_uid='LBB01', building_uid='LBB01:A', room_uid='LBB01:A:DH1-1', cabinet_uid=f'pilot-cab-{number}', port_name='P1'))
        self.session.flush()
        for index, cable_type in enumerate(('LC', 'CAT6')):
            self.session.add(db.Cable(uid=f'pilot-cable-{index}', project_uid='LBB01', building_uid='LBB01:A',
                a_port_uid='pilot-port-801', z_port_uid='pilot-port-811', cable_type=cable_type))
        self.session.flush()
        self.assertTrue(all(g['route'] is None for g in cable_review(self.session, uid)['groups']))
        setup = initialize_test_tiers(self.session, uid)
        self.assertGreater(setup['created_tier_count'], 0)
        self.assertEqual(initialize_test_tiers(self.session, uid)['created_tier_count'], 0)
        review = setup['review']
        payload = ManualBatchInput(topology_revision=review['topology_revision'], groups=[dict(group_uid=g['uid'], expected_version=None,
            segment_ids=g['route']['load_ids'], start_tier=1, end_tier=1) for g in review['groups']])
        saved = update_manual_batch(self.session, uid, payload, 'postgres-tech')['review']
        self.assertEqual(saved['manual_group_count'], 2)
        self.session.expire_all()
        again = cable_review(self.session, uid)
        self.assertEqual(again['groups'], saved['groups'])
        self.assertTrue(all(g['tier'] == 1 and g['route']['vertical_transition_count'] == 0 for g in again['groups']))
        from sqlalchemy import select
        rows = self.session.scalars(select(RoutingManualCableRoute)).all()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(all(l['tier'] == 1 for l in r.legs) for r in rows))
        with self.assertRaises(RoutingRouteConflict): update_manual_batch(self.session, uid, payload, 'stale-tech')
        # Project-scoped inventory replacement must not delete manual intent or fail on retired identities.
        versions = {r.uid: r.version for r in rows}
        ingestion = ingest_cutsheet_rows([{'A_CABINET': '801', 'A_RACK_UNIT': '1', 'A_DEVICE_MODEL': 'sw', 'A_PORT_NAME': '1',
            'A_CONNECTOR': 'LC', 'Z_CABINET': '811', 'Z_RACK_UNIT': '1', 'Z_DEVICE_MODEL': 'sw', 'Z_PORT_NAME': '1',
            'Z_CONNECTOR': 'LC', 'CABLE_TYPE': 'LC', 'GROUP': 'Replacement', 'DATA_HALL': 'DH1-1'}], project_uid='LBB01')
        database = build_topology_database_from_results(ingestion, OverheadIngestionResult(project_uid='LBB01', summary=OverheadIngestionSummary(cabinets=0, data_halls=0, unknown_category_cabinets=0)))
        replace_project_topology(self.session, database, version_name='manual-route-reimport')
        self.session.expire_all()
        self.assertEqual({r.uid: r.version for r in self.session.scalars(select(RoutingManualCableRoute))}, versions)

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

    def test_actual_cable_pilot_is_read_only_and_uses_inventory_references(self):
        from backend.services.routing_cable_review import cable_review
        data = routing.initialize_lbb01(self.session)
        uid = data['layout']['uid']
        for n in [*range(1, 22), *range(801, 821)]:
            col = (n - 1) % 10 if ((n - 1) // 10) % 2 == 0 else 9 - (n - 1) % 10
            self.session.add(db.Cabinet(uid=f'pilot:{n}', project_uid='LBB01', building_uid='LBB01:A', room_uid='LBB01:A:DH1-1', cabinet_id=f'{n:03d}', source_col=col))
        self.session.flush()
        for n in [*range(1, 22), *range(801, 821)]:
            self.session.add(db.Port(uid=f'pilot-port:{n}', project_uid='LBB01', building_uid='LBB01:A', room_uid='LBB01:A:DH1-1', cabinet_uid=f'pilot:{n}', port_name='P1'))
        self.session.flush()
        for index, (a, b, cable_type) in enumerate(((1, 2, 'LC-TO-LC SMF'), (2, 1, 'LC-TO-LC SMF'), (1, 11, 'CAT6a'), (1, 801, 'MPO12-SMF'), (1, 1, 'CAT6a'), (1, 21, 'LC-TO-LC SMF'))):
            self.session.add(db.Cable(uid=f'pilot-cable:{index}', project_uid='LBB01', building_uid='LBB01:A', a_port_uid=f'pilot-port:{a}', z_port_uid=f'pilot-port:{b}', cable_type=cable_type))
        self.session.flush()
        from backend.services.routing_manual_routes import initialize_test_tiers
        initialize_test_tiers(self.session, uid)
        before = routing.snapshot(self.session, uid)
        result = cable_review(self.session, uid)
        self.assertEqual((result['inventory_cable_count'], result['same_cabinet_count'], result['routed_cable_count']), (5, 1, 4))
        self.assertEqual(result['unrouted_cable_count'], 0)
        self.assertEqual({g['route']['method'] for g in result['groups']}, {'SAME_ROW', 'ASTAR'})
        self.assertEqual({c['uid'] for c in result['cables']}, {f'pilot-cable:{i}' for i in range(4)})
        self.assertEqual({c['cable_class'] for c in result['cables']}, {'LC', 'CAT6', 'MPO'})
        self.assertTrue(all(g['tier'] == 1 for g in result['groups']))
        self.assertEqual(before, routing.snapshot(self.session, uid))
        self.assertEqual(result, cable_review(self.session, uid))

    def test_section_direction_persistence_and_central_validation(self):
        data = routing.initialize_lbb01(self.session)
        uid = data['layout']['uid']
        self.assertEqual(data['layout']['longitudinal_direction'], 'EAST')
        north = next(b['uid'] for b in data['bands'] if b['code'] == 'NORTH')
        item = routing.save_resource(self.session, uid, 'segment-annotations', {'passage_band_uid': north,
            'start_station_in': 0, 'end_station_in': 108, 'section_inner_direction': 'SOUTH'})
        self.session.expire_all()
        self.assertEqual(routing.resolved_layout(self.session, uid)['segment_annotations'][0]['section_inner_direction'], 'SOUTH')
        # Direction revision also supports a populated downgrade/upgrade.
        command.downgrade(self.alembic, 'd84e30b6f219')
        command.upgrade(self.alembic, 'head')
        self.session.expire_all()
        self.assertIsNone(routing.resolved_layout(self.session, uid)['segment_annotations'][0]['section_inner_direction'])

    def test_bundle_and_group_membership_uses_actual_cable_ids(self):
        from datetime import datetime, timezone
        from backend.services.routing_cables import placement_cables
        data = routing.initialize_lbb01(self.session)
        uid = data['layout']['uid']
        north = next(b['uid'] for b in data['bands'] if b['code'] == 'NORTH')
        routing.save_resource(self.session, uid, 'passage-tiers', {'passage_band_uid': north, 'tier': 1, 'pathway_type': 'BASKET_TRAY'})
        parent = routing.save_resource(self.session, uid, 'segment-annotations', {'passage_band_uid': north, 'start_station_in': 0, 'end_station_in': 108})
        for number in ('021', '031'):
            self.session.add(db.Cabinet(uid=f'cab-{number}', project_uid='LBB01', building_uid='LBB01:A', room_uid='LBB01:A:DH1-1', cabinet_id=number))
        self.session.flush()
        for number in ('021', '031'):
            self.session.add(db.Port(uid=f'port-{number}', project_uid='LBB01', building_uid='LBB01:A', room_uid='LBB01:A:DH1-1', cabinet_uid=f'cab-{number}', port_name=f'P-{number}'))
        self.session.flush()
        for index, cable_type in enumerate(('LC', 'LC', 'CAT6', 'LC')):
            self.session.add(db.Cable(uid=f'actual-{index}', project_uid='LBB01', building_uid='LBB01:A', a_port_uid='port-021', z_port_uid='port-031', cable_type=cable_type, deleted_at=datetime.now(timezone.utc) if index == 3 else None))
        self.session.add(db.CableBundle(uid='bundle-a', scoped_uid='LBB01:A:bundle-a', project_uid='LBB01', building_uid='LBB01:A', name='Actual bundle'))
        self.session.add(db.EntityGroup(uid='group-a', project_uid='LBB01', name='Actual group', entity_type='bundle'))
        self.session.flush()
        self.session.add_all([db.CableBundleCable(cable_bundle_uid='bundle-a', cable_uid=f'actual-{i}') for i in (0, 1, 3)])
        self.session.add_all([db.EntityGroupMember(group_uid='group-a', entity_type='bundle', entity_uid='bundle-a'),
                              db.EntityGroupMember(group_uid='group-a', entity_type='cable', entity_uid='actual-0'),
                              db.EntityGroupMember(group_uid='group-a', entity_type='cable', entity_uid='actual-2')])
        self.session.flush()
        bundle = routing.save_resource(self.session, uid, 'bundle-placements', {'segment_annotation_uid': parent['uid'], 'tier': 1, 'source_kind': 'BUNDLE', 'source_uid': 'bundle-a'})
        group = routing.save_resource(self.session, uid, 'bundle-placements', {'segment_annotation_uid': parent['uid'], 'tier': 1, 'position': 2, 'source_kind': 'GROUP', 'source_uid': 'group-a'})
        manual = routing.save_resource(self.session, uid, 'bundle-placements', {'segment_annotation_uid': parent['uid'], 'tier': 1, 'position': 3, 'label': 'LC x 100 021-031'})
        actual = placement_cables(self.session, uid, bundle['uid'])
        self.assertEqual([c['uid'] for c in actual['cables']], ['actual-0', 'actual-1'])
        self.assertEqual(actual['summary'], [{'cable_type': 'LC', 'source_cabinet_id': '021', 'destination_cabinet_id': '031', 'count': 2}])
        self.assertEqual(actual['cables'][0]['source_port_name'], 'P-021')
        self.assertEqual([c['uid'] for c in placement_cables(self.session, uid, group['uid'])['cables']], ['actual-0', 'actual-1', 'actual-2'])
        self.assertEqual(placement_cables(self.session, uid, manual['uid'])['cables'], [])
        with self.assertRaises(routing.RoutingNotFound):
            placement_cables(self.session, 'another-layout', bundle['uid'])
        self.session.get(db.CableBundle, 'bundle-a').deleted_at = datetime.now(timezone.utc)
        self.session.flush()
        self.assertFalse(placement_cables(self.session, uid, bundle['uid'])['source_available'])
        self.assertEqual([c['uid'] for c in placement_cables(self.session, uid, group['uid'])['cables']], ['actual-0', 'actual-2'])


if __name__ == '__main__':
    unittest.main()
