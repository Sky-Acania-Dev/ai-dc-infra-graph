"""Real inventory membership, draft routing and row-side isolation."""
import copy
import unittest
import networkx as nx

from tests.unit import test_routing as routing_test_support
from backend.services.routing_cable_review import build_cable_review
from backend.services.routing_planning import ReviewPlanner
from backend.services.routing_graph import derive_graph
from backend.services.routing_pathfinding import preview_route, NoRoutingPath


class CableReviewTests(unittest.TestCase):
    def setUp(self):
        self.case = routing_test_support.RoutingTests(); self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.case.configure_tiers((1,), (1,))
        self.data = self.case.data_now()
        self.data['cabinets'] = []
        for row in self.data['geometry']['cabinet_rows']:
            start, end = row['cabinet_number_start'], row['cabinet_number_end']
            if start not in (1, 11, 801, 811): continue
            row['existing_cabinet_uids'] = []
            for number in range(start, end + 1):
                uid = f'cab:{number:03d}'
                row['existing_cabinet_uids'].append(uid)
                self.data['cabinets'].append(dict(cabinet_uid=uid, cabinet_id=f'{number:03d}', data_hall_id='DH1-1',
                    source_col=number-start if row['position_in_pair'] == 'A' else end-number))

    def cable(self, uid, a, b, kind='LC-TO-LC SMF'):
        return dict(uid=uid, source_cabinet_uid=f'cab:{a:03d}', destination_cabinet_uid=f'cab:{b:03d}', cable_type=kind)

    def test_scope_membership_local_cables_and_same_row_direct_route(self):
        cables = [self.cable('a', 1, 2), self.cable('b', 2, 1), self.cable('local', 1, 1), self.cable('outside', 1, 21)]
        before = copy.deepcopy(self.data)
        result = build_cable_review(self.data, cables)
        self.assertEqual((result['inventory_cable_count'], result['same_cabinet_count'], result['routed_cable_count']), (3, 1, 2))
        self.assertEqual(len(result['groups']), 1)
        group = result['groups'][0]
        self.assertEqual(group['cable_uids'], ['a', 'b'])
        self.assertEqual(group['route']['method'], 'SAME_ROW')
        self.assertTrue(all(p['x_in'] == group['route']['points'][0]['x_in'] for p in group['route']['points']))
        self.assertTrue(all('guide:cross:' in uid for uid in group['route']['segment_ids']))
        self.assertEqual(group['tier'], 1)
        self.assertEqual(result, build_cable_review(self.data, list(reversed(cables))))
        self.assertEqual(self.data, before)

    def test_astar_is_shortest_and_longitudinal_travel_uses_passages_only(self):
        planner = ReviewPlanner(self.data, [c['cabinet_uid'] for c in self.data['cabinets']])
        reference = nx.Graph()
        for e in planner.edges.values(): reference.add_edge(e['source'], e['target'], weight=e['planar_length_in'])
        for a, b in ((1, 11), (1, 801), (3, 817)):
            result = planner.route(f'cab:{a:03d}', f'cab:{b:03d}')
            self.assertEqual(result['method'], 'ASTAR')
            start = planner.attachments[f'cab:{a:03d}']['point']; end = planner.attachments[f'cab:{b:03d}']['point']
            self.assertEqual(result['planar_length_in'], nx.shortest_path_length(reference, start, end, weight='weight'))
            for x, y in zip(result['points'], result['points'][1:]):
                if x['x_in'] != y['x_in']:
                    self.assertIn(x['y_in'], (17, 382, 771)); self.assertEqual(x['y_in'], y['y_in'])

    def test_disabled_route_or_missing_column_mapping_does_not_invent_a_path(self):
        for route in self.data['geometry']['cross_routes']:
            if route['cabinet_row_uid'] == next(r['uid'] for r in self.data['geometry']['cabinet_rows'] if r['cabinet_number_start'] == 1):
                route['effective_enabled'] = False
        result = build_cable_review(self.data, [self.cable('a', 1, 2)])
        self.assertEqual(result['unrouted_cable_count'], 1); self.assertEqual(result['loads'], [])
        for c in self.data['cabinets']: c['source_col'] = None
        result = build_cable_review(self.data, [self.cable('b', 811, 812)])
        self.assertEqual(result['unrouted_cable_count'], 1)

    def test_manual_obstruction_cannot_be_bypassed_by_unassigned_tier(self):
        planner = ReviewPlanner(self.data, ['cab:001', 'cab:002'])
        span = next(s for s in planner.spans if s['cross_route_uid'] == planner.attachments['cab:001']['cross_route_uid'])
        self.data['segment_annotations'] = [{k: v for k, v in span.items() if k in ('passage_band_uid', 'cross_route_uid', 'start_station_in', 'end_station_in', 'from_passage_band_uid', 'to_passage_band_uid')} | {'uid': 'blocked', 'tier': 1, 'usable': False, 'cable_classes': []}]
        self.assertIsNone(ReviewPlanner(self.data, ['cab:001', 'cab:002']).route('cab:001', 'cab:002'))

    def test_configured_north_route_never_creates_south_side_edges(self):
        case = self.case
        from backend.persistence.postgresql.routing_models import RoutingCrossRouteTier
        from sqlalchemy import delete
        case.session.execute(delete(RoutingCrossRouteTier)); case.session.flush()
        north_row = next(r for r in case.data['geometry']['cabinet_rows'] if r['cabinet_number_start'] == 801)
        route = next(r for r in case.data['cross_routes'] if r['cabinet_row_uid'] == north_row['uid'])
        case.save('cross-route-tiers', {'cross_route_uid': route['uid'], 'tier': 1, 'pathway_type': 'LADDER_RACK'})
        data = case.data_now(); graph = derive_graph(data); nodes = {n.id: n for n in graph.nodes}
        crosses = [e for e in graph.edges if e.edge_type == 'CROSS_ROUTE']
        self.assertEqual([(nodes[e.source_node_id].passage_code, nodes[e.target_node_id].passage_code) for e in crosses], [('NORTH', 'CENTRAL')])
        south = next(n for n in graph.nodes if n.passage_code == 'SOUTH')
        with self.assertRaises(NoRoutingPath): preview_route(graph, data, crosses[0].source_node_id, south.id)


if __name__ == '__main__': unittest.main()
