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


if __name__ == '__main__':
    unittest.main()
