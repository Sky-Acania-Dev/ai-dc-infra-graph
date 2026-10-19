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
from backend.services.routing_geometry import resolve_geometry
from backend.services.routing_manual_paths import chain_legs, validate_chain


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

    def node_policy(self, extra_station=0):
        self.data['cabinets'][next(i for i,c in enumerate(self.data['cabinets']) if c['cabinet_uid']=='cab:802')]['category'] = 'T0-RO-v1a'
        if extra_station:
            uid = self.planner.attachments['cab:811']['cross_route_uid']
            station = next(r['station_in'] for r in self.data['geometry']['cross_routes'] if r['uid']==uid)
            route = next(r for r in self.data['cross_routes'] if r['uid']==uid)
            route.update(station_source='MANUAL',manual_station_in=station+extra_station)
            existing={r['uid']:r['existing_cabinet_uids'] for r in self.data['geometry']['cabinet_rows']}
            self.data['geometry'] = resolve_geometry(self.data)
            for row in self.data['geometry']['cabinet_rows']:
                row['existing_cabinet_uids']=existing[row['uid']]
        self.planner = ReviewPlanner(self.data, [c['cabinet_uid'] for c in self.data['cabinets']])
        return InventoryPolicy(self.data,self.planner)

    def test_t0_node_policy_is_limited_to_cross_row_roce_mpo_and_known_node_categories(self):
        policy = self.node_policy()
        for kind in ('MPO12 2x2','MPO12 4x4','MTP'):
            self.assertEqual(policy.classify('cab:802','cab:811',kind,{'RoCE'})[:2],('ROCE_T0_NODE',1))
            self.assertEqual(policy.classify('cab:811','cab:802',kind,{'RoCE'})[:2],('ROCE_T0_NODE',1))
        self.assertEqual(policy.classify('cab:802','cab:803','MPO12 2x2',{'RoCE'})[0],'SAME_ROW_ROCE')
        for kind,phases in [('CAT6',{'RoCE'}),('MPO12 2x2',{'Management & Ethernet'}),('MPO12 2x2',{'RoCE','Management & Ethernet'})]:
            self.assertEqual(policy.classify('cab:802','cab:811',kind,phases)[0],'UNSUPPORTED')
        policy.cabinets['cab:811']['category']='VR-NVL72-v2'
        self.assertEqual(policy.classify('cab:802','cab:811','MPO12 4x4',{'RoCE'})[0],'ROCE_T0_NODE')
        policy.cabinets['cab:811']['category']='RES'
        self.assertEqual(policy.classify('cab:802','cab:811','MPO12 2x2',{'RoCE'})[0],'UNSUPPORTED')

    def test_t0_node_uses_central_within_ten_percent_but_keeps_shorter_outer_route_beyond_it(self):
        original=copy.deepcopy(self.data)
        # Integer slot centers give exactly 616/560 inches at this boundary.
        for extra,prefer_central in ((0,False),(54,False),(55,True),(300,True)):
            self.data=copy.deepcopy(original)
            policy=self.node_policy(extra)
            start,end=self.planner.endpoint('cab:802'),self.planner.endpoint('cab:811')
            shortest=self.planner.shortest(start,end,allow_edge=lambda e:e['edge_type']!='VERTICAL' and e['tier']==1)
            route=policy.route('cab:802','cab:811','ROCE_T0_NODE',1)
            passages={self.planner.edges[e]['passage_code'] for e in route['load_ids'] if self.planner.edges[e]['edge_type']=='PASSAGE'}
            self.assertEqual(passages,{'CENTRAL'} if prefer_central else {'NORTH'})
            self.assertLessEqual(route['planar_length_in']*100,shortest['planar_length_in']*110)
            if prefer_central:self.assertGreater(route['planar_length_in'],shortest['planar_length_in'])
            self.assertEqual(route['vertical_transition_count'],0)
            self.assertTrue(all(p['tier']==1 for p in route['points']))
            self.assertTrue(validate_chain(self.planner,'cab:802','cab:811',route['load_ids'],complete=True)[1])
            self.assertEqual(route,policy.route('cab:802','cab:811','ROCE_T0_NODE',1))

    def test_t0_node_falls_back_when_central_is_disabled_and_never_uses_an_upper_tier(self):
        self.node_policy(300)
        central=next(b['uid'] for b in self.data['bands'] if b['code']=='CENTRAL')
        self.data['segment_annotations'].append(dict(uid='blocked-central',passage_band_uid=central,cross_route_uid=None,
            start_station_in=0,end_station_in=self.data['geometry']['hall_length_in'],from_passage_band_uid=None,to_passage_band_uid=None,
            tier=1,usable=False,cable_classes=[]))
        planner=ReviewPlanner(self.data,[c['cabinet_uid'] for c in self.data['cabinets']])
        route=InventoryPolicy(self.data,planner).route('cab:802','cab:811','ROCE_T0_NODE',1)
        self.assertIsNotNone(route)
        self.assertTrue(all(p['tier']==1 for p in route['points']))
        for t in self.data['cross_route_tiers']:
            if t['tier']==1:t['enabled']=False
        planner=ReviewPlanner(self.data,[c['cabinet_uid'] for c in self.data['cabinets']])
        self.assertIsNone(InventoryPolicy(self.data,planner).route('cab:802','cab:811','ROCE_T0_NODE',1))

    def test_t0_node_default_never_overwrites_a_manual_higher_tier_route(self):
        self.node_policy()
        route=self.planner.route('cab:802','cab:811',2,2)
        points=[(p['x_in'],p['y_in'],p['tier']) for p in route['points']]
        manual=dict(source_cabinet_uid='cab:802',destination_cabinet_uid='cab:811',cable_type='MPO12 2x2',
            legs=chain_legs(self.planner,points,route['load_ids']),start_tier=2,end_tier=2,version='preserve',revision=4,notes='Manual',updated_by='tech')
        counts=[dict(a='cab:802',b='cab:811',cable_type='MPO12 2x2',phase='RoCE',count=144)]
        review=build_inventory_review(self.data,counts,[manual],self.planner)
        group=review['groups'][0]
        self.assertEqual((group['policy'],group['route_source'],group['manual_version'],group['manual_revision']),('ROCE_T0_NODE','MANUAL','preserve',4))
        self.assertEqual((group['start_tier'],group['end_tier']), (2,2))
        self.assertEqual(review['routed_cable_count'],144)


if __name__ == '__main__': unittest.main()
