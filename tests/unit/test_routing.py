import copy
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql import routing_models as routing_db
from backend.schemas.routing import GraphEdge, GraphNode, RoutingGraph, VerticalTransitionInput, BandInput
from backend.services import routing_configuration as config
from backend.services.routing_geometry import resolve_geometry, format_inches
from backend.services.routing_graph import derive_graph
from backend.services.routing_pathfinding import preview_route, NoRoutingPath


@compiles(JSONB, 'sqlite')
def sqlite_jsonb(element, compiler, **kw):
    return 'JSON'


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        event.listen(self.engine, 'connect', lambda connection, _: connection.execute('PRAGMA foreign_keys=ON'))
        tables = [db.Project.__table__, db.Building.__table__, db.Room.__table__, db.Cabinet.__table__]
        tables += [t for t in db.Base.metadata.sorted_tables if t.name.startswith('routing_')]
        db.Base.metadata.create_all(self.engine, tables=tables)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)
        self.session = self.factory()
        self.session.add(db.Project(uid='LBB01'))
        self.session.flush()
        self.session.add(db.Building(uid='LBB01:A', project_uid='LBB01', building_id='A'))
        self.session.flush()
        self.session.add_all([db.Room(uid=f'LBB01:A:DH1-{i}', project_uid='LBB01', building_uid='LBB01:A', room_id=f'DH1-{i}') for i in range(1, 6)])
        self.session.flush()
        self.data = config.initialize_lbb01(self.session)
        self.uid = self.data['layout']['uid']

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def save(self, resource, values, uid=None):
        return config.save_resource(self.session, self.uid, resource, values, uid)

    def data_now(self):
        return config.resolved_layout(self.session, self.uid)

    def configure_tiers(self, tiers=(1, 2, 3), cross_tiers=(1, 2, 3)):
        for band in self.data['bands']:
            if band['kind'] == 'PASSAGE':
                for tier in tiers:
                    self.session.add(routing_db.RoutingPassageTier(uid=f"pt:{band['uid']}:{tier}", routing_layout_uid=self.uid,
                                                                  passage_band_uid=band['uid'], tier=tier, pathway_type='LADDER_RACK'))
        # Cover row and gap routes without assuming every route has every tier.
        for route in self.data['cross_routes']:
            for tier in cross_tiers:
                self.session.add(routing_db.RoutingCrossRouteTier(uid=f"ct:{route['uid']}:{tier}", routing_layout_uid=self.uid,
                                                                  cross_route_uid=route['uid'], tier=tier, pathway_type='BASKET_TRAY'))
        self.session.flush()
        config.validate_layout(self.session, self.uid)

    def north(self):
        return next(b for b in self.data['bands'] if b['code'] == 'NORTH')['uid']

    def passage_id(self, tier, station=0):
        return f'passage:{self.north()}:station:{station}:tier:{tier}'

    def test_initializer_idempotent_and_confirmed_rows(self):
        again = config.initialize_lbb01(self.session)
        self.assertEqual(self.data, again)
        self.assertEqual(len(again['sections']), 5)
        self.assertEqual(len(again['row_pairs']), 80)
        self.assertEqual(len(again['cabinet_rows']), 160)
        self.assertEqual(len(again['cross_routes']), 164)
        self.assertEqual(len([r for r in again['cross_routes'] if r['kind'] == 'SECTION_GAP']), 4)
        self.assertEqual(again['passage_tiers'], [])
        self.assertEqual(again['cross_route_tiers'], [])
        self.assertEqual(again['vertical_transitions'], [])
        fields = {b['uid']: b['code'] for b in again['bands']}
        for row in again['geometry']['cabinet_rows']:
            self.assertEqual(row['cabinet_number_end'] - row['cabinet_number_start'] + 1, 10)
            self.assertEqual(row['cabinet_number_start'] >= 801, fields[row['row_field_band_uid']] == 'NORTH_FIELD')

    def test_module_and_alternating_row_centers(self):
        layout = self.data['layout']
        self.assertEqual([layout[k] for k in ('cabinet_row_depth_in', 'hot_aisle_clear_in', 'cold_aisle_clear_in', 'row_pair_module_in')], [24, 96, 120, 264])
        self.assertEqual(24 + 96 + 24 + 120, 264)
        rows = [r for r in self.data['geometry']['cabinet_rows'] if r['cabinet_number_start'] <= 160]
        centers = sorted(r['center_in'] for r in rows)
        self.assertEqual([b - a for a, b in zip(centers, centers[1:])], [120, 144] * 7 + [120])
        for pair in self.data['geometry']['row_pairs']:
            self.assertEqual(pair['hot_aisle_end_in'] - pair['hot_aisle_start_in'], 96)

    def test_transverse_dimensions_and_formatter(self):
        geometry = self.data['geometry']
        self.assertEqual(geometry['total_width_in'], 788)
        bands = sorted(geometry['bands'], key=lambda b: b['ordinal'])
        self.assertEqual([b['start_in'] for b in bands], [0, 34, 370, 394, 754])
        self.assertEqual([b['center_in'] for b in bands if b['kind'] == 'PASSAGE'], [17, 382, 771])
        for value, formatted in [(24, '2\'-0"'), (34, '2\'-10"'), (96, '8\'-0"'), (120, '10\'-0"'), (264, '22\'-0"'), (336, '28\'-0"'), (360, '30\'-0"'), (788, '65\'-8"')]:
            self.assertEqual(format_inches(value), formatted)
        self.assertTrue(all(r['width_in'] == 24 for r in geometry['cross_routes']))

    def test_sections_parallel_sides_and_empty_sections(self):
        geometry = self.data['geometry']
        self.assertEqual(geometry['module_end_in'], 40 * 264 + 4 * 216)
        self.assertEqual(len(geometry['gaps']), 4)
        self.assertTrue(all(g['end_in'] - g['start_in'] == 216 for g in geometry['gaps']))
        data = copy.deepcopy(self.data)
        data['row_pairs'] = []
        data['cabinet_rows'] = []
        data['cross_routes'] = [r for r in data['cross_routes'] if r['kind'] == 'SECTION_GAP']
        empty = resolve_geometry(data)
        self.assertEqual([g['center_in'] for g in empty['gaps']], [108, 324, 540, 756])
        self.assertEqual(empty['module_end_in'], 864)

    def test_cold_routes_are_adjacent_not_hot(self):
        rows = {r['uid']: r for r in self.data['geometry']['cabinet_rows']}
        for route in self.data['geometry']['cross_routes']:
            if route['kind'] != 'CABINET_COLD_AISLE':
                continue
            row = rows[route['cabinet_row_uid']]
            if row['position_in_pair'] == 'A':
                self.assertEqual(route['end_in'], row['start_in'])
            else:
                self.assertEqual(route['start_in'], row['end_in'])
            self.assertNotEqual(route['station_in'], row['center_in'])
        self.assertEqual(len(rows), len([r for r in self.data['cross_routes'] if r['cabinet_row_uid']]))

    def test_manual_station_is_preserved_and_derived_moves(self):
        gaps = sorted((r for r in self.data['geometry']['cross_routes'] if r['kind'] == 'SECTION_GAP'), key=lambda r: r['station_in'])
        self.save('cross-routes', {'station_source': 'FIELD_MEASURED', 'manual_station_in': gaps[1]['station_in'] + 1}, gaps[1]['uid'])
        self.session.get(routing_db.RoutingLayout, self.uid).section_extra_gap_in += 2
        self.session.flush()
        updated = self.data_now()['geometry']['cross_routes']
        self.assertEqual(next(r for r in updated if r['uid'] == gaps[0]['uid'])['station_in'], gaps[0]['station_in'] + 1)
        self.assertEqual(next(r for r in updated if r['uid'] == gaps[1]['uid'])['station_in'], gaps[1]['station_in'] + 1)

    def test_schema_vertical_validation_and_strict_inches(self):
        for low, high in ((1, 2), (2, 3)):
            VerticalTransitionInput(passage_band_uid='n', station_in=0, lower_tier=low, upper_tier=high)
        for low, high in ((1, 3), (0, 1), (3, 4)):
            with self.assertRaises(ValidationError):
                VerticalTransitionInput(passage_band_uid='n', station_in=0, lower_tier=low, upper_tier=high)
        for width in (34.0, '34', 0, -2, 35):
            with self.assertRaises(ValidationError):
                BandInput(ordinal=0, kind='PASSAGE', code='NORTH', width_in=width)

    def test_no_tiers_no_graph(self):
        self.assertEqual(derive_graph(self.data).nodes, [])
        self.assertEqual(derive_graph(self.data).edges, [])

    def test_configurable_dimensions_and_initializer_preserves_configuration(self):
        band = next(b for b in self.data['bands'] if b['code'] == 'NORTH')
        self.save('bands', {'width_in': 36}, band['uid'])
        data = config.initialize_lbb01(self.session)
        self.assertEqual(next(b for b in data['geometry']['bands'] if b['code'] == 'NORTH')['center_in'], 18)
        self.assertEqual(data['geometry']['total_width_in'], 790)
        config.update_layout(self.session, self.uid, {'hot_aisle_clear_in': 98})
        self.assertEqual(self.data_now()['layout']['row_pair_module_in'], 266)
        with self.assertRaises(config.RoutingConfigurationError):
            config.update_layout(self.session, self.uid, {'hot_aisle_clear_in': '98'})

    def test_hot_side_manual_placement_rejected(self):
        route = next(r for r in self.data['geometry']['cross_routes'] if r['cabinet_row_uid'] and r['station_in'] == 108)
        with self.assertRaisesRegex(config.RoutingConfigurationError, 'envelope'):
            with self.session.begin_nested():
                self.save('cross-routes', {'station_source': 'MANUAL', 'manual_station_in': 192}, route['uid'])

    def test_duplicate_pair_position_and_tier_constraints(self):
        pair = self.data['row_pairs'][0]
        with self.assertRaises(IntegrityError):
            with self.session.begin_nested():
                self.save('row-pairs', {key: pair[key] for key in ('routing_section_uid', 'row_field_band_uid', 'ordinal_in_section')})
        row = self.data['cabinet_rows'][0]
        with self.assertRaises(IntegrityError):
            with self.session.begin_nested():
                self.save('cabinet-rows', {'row_pair_uid': row['row_pair_uid'], 'position_in_pair': row['position_in_pair'], 'name': 'Duplicate'})
        route = self.data['cross_routes'][0]
        self.save('cross-route-tiers', {'cross_route_uid': route['uid'], 'tier': 1, 'pathway_type': 'LADDER_RACK'})
        with self.assertRaises(IntegrityError):
            with self.session.begin_nested():
                self.save('cross-route-tiers', {'cross_route_uid': route['uid'], 'tier': 1, 'pathway_type': 'BASKET_TRAY'})

    def test_cross_layout_references_and_row_field_opening_rejected(self):
        self.session.add(db.Room(uid='LBB01:A:DH2', project_uid='LBB01', building_uid='LBB01:A', room_id='DH2'))
        self.session.flush()
        other = config.create_layout(self.session, {'room_uid': 'LBB01:A:DH2', 'physical_hall_code': 'DH2'})
        with self.assertRaisesRegex(config.RoutingConfigurationError, 'this layout'):
            with self.session.begin_nested():
                config.save_resource(self.session, other.uid, 'passage-tiers', {'passage_band_uid': self.north(), 'tier': 1, 'pathway_type': 'LADDER_RACK'})
        field = next(b for b in self.data['bands'] if b['kind'] == 'ROW_FIELD')
        with self.assertRaisesRegex(config.RoutingConfigurationError, 'PASSAGE band'):
            with self.session.begin_nested():
                self.save('vertical-transitions', {'passage_band_uid': field['uid'], 'station_in': 100, 'lower_tier': 1, 'upper_tier': 2})

    def test_pair_and_row_crud_maintains_association_and_cascade(self):
        section = next(s for s in self.data['sections'] if s['ordinal'] == 1)
        field = next(b for b in self.data['bands'] if b['code'] == 'NORTH_FIELD')
        pair = self.save('row-pairs', {'routing_section_uid': section['uid'], 'row_field_band_uid': field['uid'], 'ordinal_in_section': 9})
        row = self.save('cabinet-rows', {'row_pair_uid': pair['uid'], 'position_in_pair': 'A', 'name': 'Configured spare row'})
        route = next(r for r in self.data_now()['cross_routes'] if r['cabinet_row_uid'] == row['uid'])
        self.assertEqual(route['kind'], 'CABINET_COLD_AISLE')
        config.delete_resource(self.session, self.uid, 'row-pairs', pair['uid'])
        self.assertFalse(any(r['uid'] == row['uid'] for r in self.data_now()['cabinet_rows']))
        self.assertFalse(any(r['uid'] == route['uid'] for r in self.data_now()['cross_routes']))

    def test_graph_lengths_order_junctions_determinism_and_continuity(self):
        self.configure_tiers(tiers=(1,), cross_tiers=(1,))
        data = self.data_now()
        graph = derive_graph(data)
        self.assertEqual(graph, derive_graph(data))
        reverse = copy.deepcopy(data)
        for key in config.RESOURCES:
            reverse[key.replace('-', '_')].reverse()
        self.assertEqual(graph, derive_graph(reverse))
        self.assertEqual({e.planar_length_in for e in graph.edges if e.edge_type == 'CROSS_ROUTE'}, {365, 389})
        self.assertEqual(len([e for e in graph.edges if e.edge_type == 'CROSS_ROUTE']), 164 * 2)
        self.assertTrue(all(e.planar_length_in == 0 for e in graph.edges if e.edge_type == 'JUNCTION'))
        nodes = {n.id: n for n in graph.nodes}
        for edge in graph.edges:
            if edge.edge_type == 'PASSAGE':
                self.assertLess(nodes[edge.source_node_id].x_in, nodes[edge.target_node_id].x_in)
                self.assertEqual(edge.planar_length_in, nodes[edge.target_node_id].x_in - nodes[edge.source_node_id].x_in)
        for band in (b for b in data['bands'] if b['kind'] == 'PASSAGE'):
            start = f"passage:{band['uid']}:station:0:tier:1"
            end = f"passage:{band['uid']}:station:{data['geometry']['hall_length_in']}:tier:1"
            result = preview_route(graph, data, start, end)
            self.assertEqual(result.planar_length_in, data['geometry']['hall_length_in'])
            self.assertEqual(len(result.steps), 1)

    def test_missing_middle_tier_does_not_invent_connection(self):
        self.configure_tiers(tiers=(1,), cross_tiers=(2,))
        graph = derive_graph(self.data_now())
        self.assertFalse(any(e.edge_type in ('CROSS_ROUTE', 'JUNCTION') for e in graph.edges))
        data = self.data_now()
        data['cross_route_tiers'] = [{**t, 'tier': 1} for t in data['cross_route_tiers']]
        central = next(b for b in data['bands'] if b['code'] == 'CENTRAL')['uid']
        data['passage_tiers'] = [t for t in data['passage_tiers'] if t['passage_band_uid'] != central]
        graph = derive_graph(data)
        self.assertFalse(any(e.edge_type == 'CROSS_ROUTE' for e in graph.edges))

    def test_openings_are_required_and_distinct(self):
        self.configure_tiers(tiers=(1, 2, 3), cross_tiers=())
        data = self.data_now()
        with self.assertRaises(NoRoutingPath):
            preview_route(derive_graph(data), data, self.passage_id(1), self.passage_id(2))
        first = self.save('vertical-transitions', {'passage_band_uid': self.north(), 'station_in': 100, 'lower_tier': 1, 'upper_tier': 2, 'label': 'VT-N-01'})
        data = self.data_now()
        result = preview_route(derive_graph(data), data, self.passage_id(1), self.passage_id(2))
        self.assertEqual(result.vertical_transition_count, 1)
        self.assertEqual(result.planar_length_in, 200)
        self.assertEqual(result.length_label, 'Planar pathway length')
        self.assertEqual(result.vertical_opening_labels, ['VT-N-01'])
        self.assertTrue(any('Tier 1 to Tier 2' in step for step in result.steps))
        self.assertTrue(all(e.planar_length_in == 0 for e in result.edges if e.edge_type == 'VERTICAL'))
        with self.assertRaises(NoRoutingPath):
            preview_route(derive_graph(data), data, self.passage_id(1), self.passage_id(3))
        self.save('vertical-transitions', {'passage_band_uid': self.north(), 'station_in': 100, 'lower_tier': 2, 'upper_tier': 3, 'label': 'VT-N-02'})
        data = self.data_now()
        self.assertEqual(len([e for e in derive_graph(data).edges if e.edge_type == 'VERTICAL']), 2)
        result = preview_route(derive_graph(data), data, self.passage_id(3), self.passage_id(1))
        self.assertEqual(result.vertical_transition_count, 2)
        self.save('vertical-transitions', {'enabled': False}, first['uid'])
        data = self.data_now()
        with self.assertRaises(NoRoutingPath):
            preview_route(derive_graph(data), data, self.passage_id(1), self.passage_id(2))

    def test_disabled_row_removes_only_its_pathways(self):
        self.configure_tiers(tiers=(1,), cross_tiers=(1,))
        row = self.data['cabinet_rows'][0]
        route = next(r for r in self.data['cross_routes'] if r['cabinet_row_uid'] == row['uid'])
        self.save('cabinet-rows', {'enabled': False}, row['uid'])
        self.assertFalse(any(e.cross_route_uid == route['uid'] for e in derive_graph(self.data_now()).edges))

    def test_api_crud_errors_permissions_and_preview(self):
        self.session.commit()
        with patch('backend.api.routing.session_factory', return_value=self.factory):
            client = TestClient(app)
            base = f'/routing/layouts/{self.uid}'
            self.assertEqual(client.get(base).status_code, 200)
            self.assertEqual(client.get('/routing/layouts', params={'project_uid': 'OTHER'}).json(), [])
            self.assertEqual(client.post('/routing/initialize-lbb01', json={}).json()['layout']['uid'], self.uid)
            request = {'passage_band_uid': self.north(), 'tier': 1, 'pathway_type': 'LADDER_RACK'}
            response = client.post(base + '/passage-tiers', json=request)
            self.assertEqual(response.status_code, 200, response.text)
            uid = response.json()['uid']
            self.assertEqual(client.post(base + '/passage-tiers', json=request).status_code, 409)
            self.assertEqual(client.patch(base + '/passage-tiers/' + uid, json={'enabled': False}).status_code, 200)
            self.assertEqual(client.delete(base + '/passage-tiers/' + uid).status_code, 204)
            self.assertEqual(client.get(base + '/passage-tiers/' + uid).status_code, 404)
            self.assertEqual(client.post(base + '/passage-tiers', json=request, headers={'x-user-role': 'viewer'}).status_code, 403)
            self.assertEqual(client.post(base + '/passage-tiers', json={**request, 'tier': 4}).status_code, 422)
            field = next(b for b in self.data['bands'] if b['kind'] == 'ROW_FIELD')
            self.assertEqual(client.post(base + '/passage-tiers', json={**request, 'passage_band_uid': field['uid']}).status_code, 422)
            self.assertEqual(client.post(base + '/route-preview', json={'start_node_id': 'missing', 'end_node_id': 'missing'}).status_code, 422)
            self.assertEqual(client.patch(base + '/cabinet-rows/' + self.data['cabinet_rows'][0]['uid'], json={'row_pair_uid': 'another-layout'}).status_code, 422)
            self.assertEqual(client.delete(base + '/sections/' + self.data['sections'][0]['uid']).status_code, 422)
            # A failed request rolls back fully; the scaffold remains usable.
            self.assertEqual(len(client.get(base).json()['sections']), 5)
            self.assertEqual(client.get('/health').json(), {'status': 'ok'})

    def test_api_successful_preview_and_opening_crud(self):
        self.session.commit()
        with patch('backend.api.routing.session_factory', return_value=self.factory):
            client = TestClient(app)
            base = f'/routing/layouts/{self.uid}'
            for tier in (1, 2):
                response = client.post(base + '/passage-tiers', json={'passage_band_uid': self.north(), 'tier': tier, 'pathway_type': 'LADDER_RACK'})
                self.assertEqual(response.status_code, 200)
            response = client.post(base + '/vertical-transitions', json={'passage_band_uid': self.north(), 'station_in': 100, 'lower_tier': 1, 'upper_tier': 2, 'label': 'API-VT'})
            self.assertEqual(response.status_code, 200, response.text)
            opening = response.json()['uid']
            request = {'start_node_id': self.passage_id(1), 'end_node_id': self.passage_id(2)}
            preview = client.post(base + '/route-preview', json=request)
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertEqual(preview.json()['planar_length_in'], 200)
            self.assertEqual(preview.json()['vertical_transition_count'], 1)
            self.assertEqual(client.patch(base + '/vertical-transitions/' + opening, json={'enabled': False}).status_code, 200)
            self.assertEqual(client.post(base + '/route-preview', json=request).status_code, 422)
            self.assertEqual(client.patch(base + '/vertical-transitions/' + opening, json={'enabled': True, 'label': 'Edited opening'}).status_code, 200)
            self.assertEqual(client.post(base + '/route-preview', json=request).json()['vertical_opening_labels'], ['Edited opening'])
            self.assertEqual(client.delete(base + '/vertical-transitions/' + opening).status_code, 204)
            self.assertEqual(client.post(base + '/route-preview', json=request).status_code, 422)


class PathfindingPriorityTests(unittest.TestCase):
    def graph(self, specifications):
        ids = sorted({n for spec in specifications for n in spec[1:3]})
        nodes = [GraphNode(id=n, node_type='PASSAGE_STATION', x_in=0, y_in=17, station_in=0, tier=1,
                           passage_code='NORTH', passage_band_uid='north') for n in ids]
        edges = [GraphEdge(id=uid, source_node_id=a, target_node_id=b, planar_length_in=length,
                           edge_type=kind, tier=1, passage_code='NORTH', vertical_transition_uid='vt' if kind == 'VERTICAL' else None)
                 for uid, a, b, length, kind in specifications]
        return RoutingGraph(nodes=nodes, edges=edges)

    def run_route(self, specifications):
        data = {'cross_routes': [], 'cabinet_rows': [], 'sections': [], 'vertical_transitions': [{'uid': 'vt', 'label': 'VT'}]}
        return preview_route(self.graph(specifications), data, 'a', 'z')

    def test_fewer_vertical_before_shorter_planar(self):
        result = self.run_route([('long', 'a', 'z', 1000, 'PASSAGE'), ('v1', 'a', 'b', 0, 'VERTICAL'), ('short', 'b', 'c', 1, 'PASSAGE'), ('v2', 'c', 'z', 0, 'VERTICAL')])
        self.assertEqual([e.id for e in result.edges], ['long'])

    def test_planar_before_edge_count(self):
        result = self.run_route([('long', 'a', 'z', 100, 'PASSAGE'), ('short1', 'a', 'b', 1, 'PASSAGE'), ('short2', 'b', 'z', 1, 'PASSAGE')])
        self.assertEqual(result.planar_length_in, 2)

    def test_edge_count_before_stable_id(self):
        result = self.run_route([('z-direct', 'a', 'z', 2, 'PASSAGE'), ('a-short1', 'a', 'b', 1, 'PASSAGE'), ('a-short2', 'b', 'z', 1, 'PASSAGE')])
        self.assertEqual([e.id for e in result.edges], ['z-direct'])

    def test_stable_id_tie_break(self):
        specifications = [('b1', 'a', 'b', 1, 'PASSAGE'), ('b2', 'b', 'z', 1, 'PASSAGE'), ('a1', 'a', 'c', 1, 'PASSAGE'), ('a2', 'c', 'z', 1, 'PASSAGE')]
        self.assertEqual([e.id for e in self.run_route(specifications).edges], ['a1', 'a2'])
        self.assertEqual(self.run_route(specifications), self.run_route(list(reversed(specifications))))


if __name__ == '__main__':
    unittest.main()
