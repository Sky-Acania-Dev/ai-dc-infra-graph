import copy
import unittest
from sqlalchemy import select
from tests.unit import test_routing_review as review_support
from backend.persistence.postgresql import routing_models as db
from backend.services import routing_configuration as config
from backend.services.routing_graph import derive_graph
from backend.services.routing_planning import ReviewPlanner
from backend.services.routing_test_profile import configure_hall_test
from backend.services.routing_inventory_review import build_inventory_review, InventoryPolicy


class InventoryReviewTests(unittest.TestCase):
    def setUp(self):
        self.support = review_support.CableReviewTests(); self.support.setUp()
        self.addCleanup(self.support.doCleanups)
        self.case = self.support.case
        configure_hall_test(self.case.session, self.case.uid)
        data = self.case.data_now()
        # Keep test inventory fixtures; resolved geometry carries the same stable domain IDs.
        self.data = data
        self.data['cabinets'] = copy.deepcopy(self.support.data['cabinets'])
        rows = {r['uid']: r for r in self.support.data['geometry']['cabinet_rows']}
        for row in data['geometry']['cabinet_rows']:
            row['existing_cabinet_uids'] = rows[row['uid']]['existing_cabinet_uids']
        for c in self.data['cabinets']:
            c['category'] = 'T0-FE-v1a' if c['cabinet_id'] in ('001', '801') else 'HD-GB3g'
        self.planner = ReviewPlanner(data, [c['cabinet_uid'] for c in data['cabinets']])

    def test_setup_is_idempotent_and_outer_passages_have_only_two_tiers(self):
        result = configure_hall_test(self.case.session, self.case.uid)
        self.assertEqual((result['created_tier_count'], result['created_opening_count']), (0, 0))
        outer = {b['uid'] for b in self.data['bands'] if b['code'] in ('NORTH', 'SOUTH')}
        self.assertEqual(len(self.data['vertical_transitions']), 160)
        self.assertFalse(any(t['tier'] == 3 and t['enabled'] and t['passage_band_uid'] in outer for t in self.data['passage_tiers']))
        heights = {t['tier']: t['effective_elevation_in'] for t in self.data['passage_tiers'] if t['passage_band_uid'] in outer}
        self.assertEqual(heights, {1: 98, 2: 116})

    def test_explicit_row_end_opening_has_landing_but_no_longitudinal_tier_three(self):
        graph = derive_graph(self.data)
        self.assertFalse(any(e.edge_type == 'PASSAGE' and e.tier == 3 and e.passage_code in ('NORTH', 'SOUTH') for e in graph.edges))
        policy = InventoryPolicy(self.data, self.planner)
        route = policy.route('cab:801', 'cab:811', 'FE_OUTER_TOP', 3)
        self.assertIsNotNone(route)
        self.assertEqual(route['vertical_transition_count'], 2)
        self.assertEqual((route['points'][0]['tier'], route['points'][-1]['tier']), (3, 3))
        for eid in route['load_ids']:
            edge = self.planner.edges[eid]
            if edge['edge_type'] == 'PASSAGE': self.assertEqual((edge['passage_code'], edge['tier']), ('NORTH', 2))
            if edge['edge_type'] == 'VERTICAL': self.assertEqual(edge['planar_length_in'], 0)
        without = copy.deepcopy(self.data); without['vertical_transitions'] = []
        p = ReviewPlanner(without, ['cab:801', 'cab:811'])
        self.assertIsNone(InventoryPolicy(without, p).route('cab:801', 'cab:811', 'FE_OUTER_TOP', 3))
        across = policy.route('cab:001','cab:801','FE_OUTER_TOP',3)
        self.assertIsNotNone(across)
        self.assertEqual(across['vertical_transition_count'],2)
        gap_uids = {r['uid'] for r in self.data['cross_routes'] if r['kind'] == 'SECTION_GAP'}
        self.assertTrue(any(self.planner.edges[e]['cross_route_uid'] in gap_uids for e in across['load_ids']))
        self.assertFalse(any(self.planner.edges[e]['edge_type'] == 'PASSAGE' and self.planner.edges[e]['passage_code'] == 'CENTRAL' for e in across['load_ids']))

    def test_opening_station_follows_row_and_incompatible_end_rejected(self):
        opening = self.data['vertical_transitions'][0]
        model = self.case.session.get(db.RoutingVerticalTransition, opening['uid'])
        model.station_in = 999999
        self.case.session.flush()
        config.validate_layout(self.case.session, self.case.uid)
        resolved = self.case.data_now()
        actual = next(v for v in resolved['vertical_transitions'] if v['uid'] == opening['uid'])
        route = next(r for r in resolved['geometry']['cross_routes'] if r['uid'] == opening['cross_route_uid'])
        self.assertEqual(actual['station_in'], route['station_in'])
        model.passage_band_uid = next(b['uid'] for b in self.data['bands'] if b['code'] == 'CENTRAL')
        self.case.session.flush()
        with self.assertRaises(config.RoutingConfigurationError): config.validate_layout(self.case.session, self.case.uid)

    def test_policy_uses_phase_roles_and_preserves_manual_assignments(self):
        from backend.services.routing_cables import inventory_cable_class
        self.assertEqual(inventory_cable_class('MTP'),'MPO')
        def item(a, b, kind, phase, count=10): return dict(a=f'cab:{a:03d}', b=f'cab:{b:03d}', cable_type=kind, phase=phase, count=count)
        counts = [item(801, 802, 'LC-TO-LC SMF', 'Management & Ethernet'), item(801, 802, 'MPO12 2x2', 'RoCE'),
            item(801, 811, 'LC-TO-LC SMF', 'Management & Ethernet'), item(1, 1, 'LC', 'Management & Ethernet'),
            item(1, 9999, 'LC', 'Management & Ethernet'), item(802, 812, 'RJ12', 'Management & Ethernet')]
        result = build_inventory_review(self.data, counts, planner=self.planner)
        self.assertEqual((result['routed_cable_count'], result['same_cabinet_count'], result['unmapped_cable_count'], result['unrouted_cable_count']), (30, 10, 10, 20))
        tiers = {g['policy']: g['start_tier'] for g in result['groups']}
        self.assertEqual(tiers['SAME_ROW_DATA'], 2); self.assertEqual(tiers['SAME_ROW_ROCE'], 1); self.assertEqual(tiers['FE_OUTER_TOP'], 3)
        self.assertEqual(InventoryPolicy(self.data,self.planner).classify('cab:801','cab:802','MPO12-SMF',{'Management & Ethernet'})[:2], ('SAME_ROW_DATA',2))
        self.assertEqual(result['encoding'], 'indexed-v1'); self.assertEqual(result['cables'], [])
        other = build_inventory_review(self.data, list(reversed(counts)), planner=self.planner)
        for key in ('groups', 'loads', 'topology_revision'): self.assertEqual(result[key], other[key])
        from backend.services.routing_manual_paths import chain_legs
        route = self.planner.route('cab:801', 'cab:811', 1, 1)
        legs = chain_legs(self.planner, [(p['x_in'], p['y_in'], p['tier']) for p in route['points']], route['load_ids'])
        manual = dict(source_cabinet_uid='cab:801', destination_cabinet_uid='cab:811', cable_type='LC-TO-LC SMF', legs=legs,
            start_tier=1, end_tier=1, version='keep', revision=1, notes='', updated_by='tester')
        result = build_inventory_review(self.data, counts, [manual], self.planner)
        group = next(g for g in result['groups'] if g['destination_cabinet_uid'] == 'cab:811')
        self.assertEqual((group['route_source'], group['start_tier'], group['manual_version']), ('MANUAL', 1, 'keep'))

    def test_roce_t0_t1_exits_t0_row_at_nearest_passage(self):
        lookup = {c['cabinet_uid']: c for c in self.data['cabinets']}
        lookup['cab:801']['category'], lookup['cab:811']['category'] = 'T0-RO-v1a', 'T1-RO-v1a'
        policy = InventoryPolicy(self.data, self.planner)
        self.assertEqual(policy.classify('cab:801', 'cab:811', 'MPO12-SMF', {'RoCE'})[:2], ('ROCE_T0_T1', 1))
        route = policy.route('cab:801', 'cab:811', 'ROCE_T0_T1', 1)
        self.assertTrue(all(p['tier'] == 1 for p in route['points']))
        first_passage = next(p for p in route['points'] if p.get('passage_code'))
        start = route['points'][0]
        distances = {abs(start['y_in']-y): y for y in (17, 382)}
        self.assertEqual(first_passage['y_in'], distances[min(distances)])


if __name__ == '__main__': unittest.main()
