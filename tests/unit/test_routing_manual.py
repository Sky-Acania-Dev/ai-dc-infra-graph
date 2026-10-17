import copy
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.main import app
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.routing_models import RoutingManualCableRoute
from backend.services.routing_cable_review import build_cable_review
from backend.services.routing_configuration import RoutingConfigurationError
from backend.services.routing_manual_paths import manual_preview, validate_chain, chain_legs, resolve_legs, topology_revision
from backend.services.routing_planning import ReviewPlanner
from tests.unit import test_routing_review as review_support


class ManualRouteTests(unittest.TestCase):
    def setUp(self):
        fixture = review_support.CableReviewTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.case, self.data = fixture, fixture.case, fixture.data
        self.cables = [fixture.cable('lc', 801, 811), fixture.cable('cat', 801, 811, 'CAT6'), fixture.cable('other', 1, 2)]
        self.review = build_cable_review(self.data, self.cables)
        self.group = next(g for g in self.review['groups'] if g['cable_type'] == 'LC-TO-LC SMF' and g['source_cabinet_uid'] == 'cab:801')
        self.planner = ReviewPlanner(self.data, [c['cabinet_uid'] for c in self.data['cabinets']])

    def detour(self):
        initial = manual_preview(self.planner, self.group, [])
        north = next(b['uid'] for b in self.data['bands'] if b['code'] == 'NORTH')
        first = next(c for c in initial['next_chains'] if c['points'][-1]['passage_band_uid'] == north)
        next_preview = manual_preview(self.planner, self.group, first['load_ids'])
        return first['load_ids'] + next_preview['suggestion']['load_ids']

    def test_prefix_click_continuation_and_complete_manual_chain(self):
        initial = manual_preview(self.planner, self.group, [])
        self.assertFalse(initial['complete']); self.assertEqual(len(initial['next_chains']), 2)
        self.assertTrue(any(len(c['load_ids']) > 1 for c in initial['next_chains']))
        first = initial['next_chains'][0]['load_ids']
        response = manual_preview(self.planner, self.group, first)
        self.assertEqual(response['prefix']['points'][-1], response['suggestion']['points'][0])
        ids = self.detour(); complete = manual_preview(self.planner, self.group, ids)
        self.assertTrue(complete['complete']); self.assertIsNone(complete['suggestion']); self.assertEqual(complete['next_chains'], [])
        self.assertGreater(complete['prefix']['planar_length_in'], self.group['route']['planar_length_in'])

    def test_reject_disconnected_unknown_backtracking_and_incomplete_chains(self):
        ids = self.group['route']['load_ids']
        for bad in (['missing'], [ids[-1]], [ids[0], ids[0]]):
            with self.assertRaises(RoutingConfigurationError): validate_chain(self.planner, 'cab:801', 'cab:811', bad)
        with self.assertRaises(RoutingConfigurationError): validate_chain(self.planner, 'cab:801', 'cab:811', ids[:-1], complete=True)

    def test_domain_intervals_survive_subdivision_and_invalid_manual_never_falls_back(self):
        ids = self.detour(); points, _ = validate_chain(self.planner, 'cab:801', 'cab:811', ids, True)
        legs = chain_legs(self.planner, points, ids)
        self.assertLess(len(legs), len(ids))
        self.assertFalse(any('guide:' in str(leg) for leg in legs))
        manual = dict(source_cabinet_uid='cab:801', destination_cabinet_uid='cab:811', cable_type=self.group['cable_type'],
                      legs=legs, version='manual-v1', revision=1, notes='Use north', updated_by='tech')
        result = build_cable_review(self.data, self.cables, [manual])
        saved = next(g for g in result['groups'] if g['uid'] == self.group['uid'])
        self.assertEqual(saved['route']['method'], 'MANUAL'); self.assertEqual(saved['route']['load_ids'], ids)
        self.assertEqual(saved['manual_version'], 'manual-v1')
        self.assertEqual(next(g for g in result['groups'] if g['cable_type'] == 'CAT6')['route_source'], 'DEFAULT')
        north_leg = next(l for l in legs if l['passage_band_uid'])
        changed = copy.deepcopy(self.data)
        changed['segment_annotations'].append(dict(passage_band_uid=north_leg['passage_band_uid'], cross_route_uid=None,
            uid='split', tier=1, cable_classes=[], start_station_in=180, end_station_in=190, from_passage_band_uid=None, to_passage_band_uid=None, usable=True))
        planner = ReviewPlanner(changed, [c['cabinet_uid'] for c in changed['cabinets']])
        self.assertEqual(resolve_legs(planner, 'cab:801', 'cab:811', legs)['planar_length_in'], saved['route']['planar_length_in'])
        self.assertNotEqual(topology_revision(planner), topology_revision(self.planner))
        changed['segment_annotations'][-1]['usable'] = False
        invalid = next(g for g in build_cable_review(changed, self.cables, [manual])['groups'] if g['uid'] == self.group['uid'])
        self.assertEqual(invalid['manual_status'], 'INVALID'); self.assertIsNone(invalid['route'])
        self.assertEqual(invalid['route_source'], 'MANUAL'); self.assertIn('A* has not replaced', invalid['reason'])

    def test_same_row_manual_detour_is_allowed_and_suggestions_do_not_revisit_prefix(self):
        group = next(g for g in self.review['groups'] if g['source_cabinet_uid'] == 'cab:001')
        first = next(c for c in manual_preview(self.planner, group, [])['next_chains'] if c['points'][-1]['y_in'] == 771)
        response = manual_preview(self.planner, group, first['load_ids'])
        ids = first['load_ids'] + response['suggestion']['load_ids']
        points, complete = validate_chain(self.planner, 'cab:001', 'cab:002', ids, True)
        self.assertTrue(complete); self.assertEqual(len(points), len(set(points)))
        self.assertGreater(response['suggestion']['planar_length_in'], group['route']['planar_length_in'])

    def add_tier(self, tier):
        for key in ('cross_route_tiers', 'passage_tiers'):
            for row in list(self.data[key]):
                if row['tier'] == 1:
                    self.data[key].append({**row, 'uid': row['uid'] + f'-{tier}', 'tier': tier, 'elevation_in': None, 'elevation_reference': None, 'effective_elevation_in': None})

    def opening(self, lower, upper, code='NORTH', station=108):
        return dict(uid=f'hole-{code}-{station}-{lower}-{upper}', passage_band_uid=next(b['uid'] for b in self.data['bands'] if b['code'] == code),
                    station_in=station, lower_tier=lower, upper_tier=upper, enabled=True, label='Test opening', notes=None)

    def test_tiers_require_explicit_openings_and_vertical_legs_survive_persistence(self):
        self.add_tier(2); self.add_tier(3)
        planner = ReviewPlanner(self.data, self.planner.attachments)
        response = manual_preview(planner, self.group, [], 1, 2)
        self.assertIsNone(response['suggestion'])
        self.data['vertical_transitions'].append(self.opening(1, 2))
        planner = ReviewPlanner(self.data, self.planner.attachments)
        response = manual_preview(planner, self.group, [], 1, 2)
        self.assertEqual(response['suggestion']['vertical_transition_count'], 1)
        self.assertIsNone(manual_preview(planner, self.group, [], 1, 3)['suggestion'])
        self.data['vertical_transitions'].append(self.opening(2, 3))
        planner = ReviewPlanner(self.data, self.planner.attachments)
        route = manual_preview(planner, self.group, [], 1, 3)['suggestion']
        points, _ = validate_chain(planner, 'cab:801', 'cab:811', route['load_ids'], True, 1, 3)
        legs = chain_legs(planner, points, route['load_ids'])
        holes = [l for l in legs if l.get('vertical_transition_uid')]
        self.assertEqual(len(holes), 2)
        self.assertEqual(route['vertical_transition_count'], 2)
        self.assertTrue(all(e['planar_length_in'] == 0 for e in planner.edges.values() if e['edge_type'] == 'VERTICAL'))
        self.assertEqual(resolve_legs(planner, 'cab:801', 'cab:811', legs, 1, 3), {**route, 'method': 'MANUAL'})
        self.data['vertical_transitions'][0]['enabled'] = False
        with self.assertRaises(RoutingConfigurationError): resolve_legs(ReviewPlanner(self.data, self.planner.attachments), 'cab:801', 'cab:811', legs, 1, 3)

    def test_astar_prioritizes_fewer_tier_changes_and_never_invents_tiers(self):
        empty = copy.deepcopy(self.data); empty['passage_tiers'] = []; empty['cross_route_tiers'] = []
        self.assertIsNone(ReviewPlanner(empty, self.planner.attachments).route('cab:801', 'cab:811'))
        self.add_tier(2)
        central = next(b['uid'] for b in self.data['bands'] if b['code'] == 'CENTRAL')
        self.data['segment_annotations'].append(dict(uid='block-t1', passage_band_uid=central, cross_route_uid=None,
            from_passage_band_uid=None, to_passage_band_uid=None, start_station_in=108, end_station_in=276, tier=1, usable=False, cable_classes=[]))
        self.data['vertical_transitions'] += [self.opening(1, 2, 'CENTRAL', station) for station in (108, 276)]
        planner = ReviewPlanner(self.data, self.planner.attachments)
        route = planner.route('cab:801', 'cab:811')
        self.assertEqual(route['vertical_transition_count'], 0)
        self.assertGreater(route['planar_length_in'], self.group['route']['planar_length_in'])

    def test_batch_api_atomicity_versioning_permissions_manual_precedence_and_reset(self):
        for c in self.data['cabinets']:
            self.case.session.add(db.Cabinet(uid=c['cabinet_uid'], project_uid='LBB01', building_uid='LBB01:A',
                room_uid='LBB01:A:DH1-1', cabinet_id=c['cabinet_id']))
        self.case.session.commit()
        base = f'/routing/layouts/{self.case.uid}'
        with patch('backend.api.routing.session_factory', return_value=self.case.factory), \
             patch('backend.services.routing_cable_review.resolved_layout', return_value=self.data), \
             patch('backend.services.routing_cable_review.inventory_cables', return_value=self.cables):
            client = TestClient(app)
            rev = self.review['topology_revision']
            preview = client.post(base + '/manual-route-preview', json={'group_uid': self.group['uid'], 'prefix_segment_ids': []})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(client.post(base + '/manual-route-preview', json={'group_uid': 'foreign', 'prefix_segment_ids': []}).status_code, 404)
            self.assertEqual(client.post(base + '/manual-route-preview', json={'group_uid': self.group['uid'], 'topology_revision': 'old'}).status_code, 409)
            ids = self.detour()
            targets = [g for g in self.review['groups'] if g['source_cabinet_uid'] == 'cab:801']
            payload = {'topology_revision': rev, 'groups': [{'group_uid': g['uid'], 'expected_version': None, 'segment_ids': ids} for g in targets], 'notes': 'North pattern'}
            self.assertEqual(client.post(base + '/manual-routes/batch', json=payload, headers={'x-user-role': 'viewer'}).status_code, 403)
            bad = copy.deepcopy(payload); bad['groups'][1]['segment_ids'] = ids[:-1]
            self.assertEqual(client.post(base + '/manual-routes/batch', json=bad).status_code, 422)
            self.assertEqual(client.get(base + '/cable-review').json()['manual_group_count'], 0)
            response = client.post(base + '/manual-routes/batch', json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            groups = response.json()['review']['groups']; manual = [g for g in groups if g['route_source'] == 'MANUAL']
            self.assertEqual(len(manual), 2); self.assertTrue(all(g['route']['load_ids'] == ids for g in manual))
            self.assertEqual(client.post(base + '/manual-routes/batch', json=payload).status_code, 409)
            stored = client.get(base + '/manual-routes')
            self.assertEqual(stored.status_code, 200); self.assertEqual(len(stored.json()), 2)
            self.assertTrue(all('guide:' not in str(row['legs']) and 'takeoff:' not in str(row['legs']) for row in stored.json()))
            replacement = {'topology_revision': rev, 'groups': [dict(group_uid=g['uid'], expected_version=g['manual_version'],
                segment_ids=self.group['route']['load_ids']) for g in manual], 'notes': 'Explicit technician revision'}
            edited = client.post(base + '/manual-routes/batch', json=replacement, headers={'x-user-role': 'manager', 'x-user-uid': 'tech-two'})
            self.assertEqual(edited.status_code, 200, edited.text)
            manual = [g for g in edited.json()['review']['groups'] if g['route_source'] == 'MANUAL']
            self.assertTrue(all(g['manual_revision'] == 2 and g['manual_updated_by'] == 'tech-two' for g in manual))
            self.assertEqual(client.post(base + '/manual-routes/batch', json=replacement).status_code, 409)
            after = client.get(base + '/cable-review').json()
            self.assertEqual([g['route'] for g in after['groups'] if g['route_source'] == 'MANUAL'], [g['route'] for g in manual])
            reset = {'topology_revision': rev, 'groups': [{'group_uid': g['uid'], 'expected_version': g['manual_version'], 'segment_ids': []} for g in manual]}
            response = client.post(base + '/manual-routes/reset', json=reset)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['review']['manual_group_count'], 0)
            # Old editor tokens cannot recreate/overwrite after explicit reset.
            payload['groups'] = [dict(group_uid=g['uid'], expected_version=g['manual_version'], segment_ids=ids) for g in manual]
            self.assertEqual(client.post(base + '/manual-routes/batch', json=payload).status_code, 409)
        self.assertEqual(self.case.session.scalars(select(RoutingManualCableRoute)).all(), [])


if __name__ == '__main__': unittest.main()
