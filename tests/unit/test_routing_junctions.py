import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.schemas.routing import BundleConnectionInput, JunctionAreaInput
from backend.services import routing_configuration as config
from backend.services.routing_graph import derive_graph
from backend.services.routing_junction_geometry import resolve_movement, saved_junction, validate_junctions
from backend.services.routing_junction_intersections import intersection_statistics
from backend.services.routing_junction_inventory import actual_junction
from tests.unit import test_routing as base_tests


def line(uid, a, b, tier=1):
    return dict(uid=uid,tier=tier,geometry_status='RESOLVED',primitives=[dict(kind='LINE',start=a,end=b)])


class JunctionGeometryTests(unittest.TestCase):
    def test_exact_fixture_counts_and_traversal_reversal(self):
        fixture=json.loads(Path('docs/architecture/fixtures/routing_junction_multi_bundle.json').read_text())
        movements=[]
        for m in fixture['movements']:
            def port(p):
                across=(12 if p['port']=='SOUTH' else 17)-p['offset_across_in']-p['occupied_width_in']/2
                return dict(direction=p['port'],point=[across,17] if p['port']=='SOUTH' else [-12 if p['port']=='WEST' else 12,across],occupation=p)
            movements.append(resolve_movement(m['uid'],1,port(m['from']),port(m['to']),m['from_turn_start_in'],m['to_turn_start_in']))
        result=intersection_statistics(movements)
        self.assertEqual((result['cable_intersection_point_count'],result['bundle_pair_crossing_count']),(7,7))
        self.assertEqual(result['intersection_count_status'],'EXACT')
        self.assertEqual(result,intersection_statistics(list(reversed(movements))))
        self.assertEqual(sum('DEMO-A' in p['movement_uids'] for p in result['points']),4)
        self.assertEqual(fixture['expected_node_statistics']['cable_intersection_point_count'],result['cable_intersection_point_count'])

    def test_crossing_rules_unknown_overlap_tiers_and_endpoints(self):
        a=line('a',[-10,0],[10,0]);b=line('b',[0,-10],[0,10]);c=line('c',[-10,-10],[10,10])
        result=intersection_statistics([a,b,c])
        self.assertEqual((result['cable_intersection_point_count'],result['bundle_pair_crossing_count']),(1,3))
        self.assertEqual(intersection_statistics([a,line('b',[10,0],[10,5])])['cable_intersection_point_count'],0)
        self.assertEqual(intersection_statistics([a,line('b',[0,-10],[0,10],2)])['cable_intersection_point_count'],0)
        self.assertEqual(intersection_statistics([a,b,line('c2',[-10,0],[10,0],2),line('d2',[0,-10],[0,10],2)])['cable_intersection_point_count'],2)
        overlap=intersection_statistics([a,line('d',[-5,0],[5,0])])
        self.assertEqual(overlap['cable_intersection_point_count'],0)
        self.assertEqual(len(overlap['overlapping_movement_pairs']),1)
        self.assertIsNone(intersection_statistics([dict(uid='unknown',tier=1,geometry_status='UNKNOWN',primitives=[])])['cable_intersection_point_count'])
        self.assertEqual(intersection_statistics([])['cable_intersection_point_count'],0)

    def test_two_crossings_of_same_pair_and_tangency(self):
        arc=dict(kind='ARC',start=[-1,0],end=[1,0],center=[0,0],radius=1,sweep=1)
        # Use two disconnected line primitives solely to exercise pair/location deduplication.
        a=dict(uid='a',tier=1,geometry_status='RESOLVED',primitives=[dict(kind='LINE',start=[-3,-2],end=[-3,2]),dict(kind='LINE',start=[3,-2],end=[3,2])])
        result=intersection_statistics([a,line('b',[-5,0],[5,0])])
        self.assertEqual(result['bundle_pair_crossing_count'],2)
        curved=dict(uid='curve',tier=1,geometry_status='RESOLVED',primitives=[arc])
        self.assertEqual(intersection_statistics([curved,line('t',[-3,-1],[3,-1])])['cable_intersection_point_count'],0)

    def test_turn_starts_require_pair_integer_inches(self):
        base=dict(from_placement_uid='a',to_placement_uid='b',from_end='END',to_end='START')
        for patch_values in ({'from_turn_start_in':1},{'from_turn_start_in':-1,'to_turn_start_in':1},{'from_turn_start_in':1.5,'to_turn_start_in':1}):
            with self.assertRaises(ValidationError):BundleConnectionInput(**base,**patch_values)
        with self.assertRaises(ValidationError):JunctionAreaInput(passage_band_uid='a',tier=1)

    def test_grid_only_straight_movement_rejects_turn_parameters(self):
        a=dict(direction='WEST',point=None,occupation={})
        b=dict(direction='EAST',point=None,occupation={})
        with self.assertRaisesRegex(ValueError,'Straight movements'):
            resolve_movement('straight',1,a,b,1,1)
        self.assertEqual(resolve_movement('straight',1,a,b)['geometry_status'],'UNKNOWN')

    def test_actual_preview_reads_routes_without_mutating_membership_or_manual_legs(self):
        class Node:
            x_in=0;y_in=0;tier=1
        point=lambda x,y:dict(node_id=f'{x}:{y}',x_in=x,y_in=y,tier=1)
        route=dict(points=[point(-100,0),point(0,0),point(0,100)],load_ids=['one','two'],segment_ids=['west','south'])
        review=dict(topology_revision='revision',groups=[dict(uid='actual-group',source_cabinet_id='801',destination_cabinet_id='811',cable_type='LC',cable_class='LC',count=16,route_source='MANUAL',manual_version='preserve',route=route)])
        before=copy.deepcopy(review)
        base=dict(area=dict(bounds=dict(west_in=-12,east_in=12,north_in=-17,south_in=17),passage_width_in=34,cross_route_width_in=24,passage_code='NORTH'),crossing_orders=[])
        result=actual_junction(base,review,Node())
        self.assertEqual(review,before)
        self.assertEqual(result['movements'][0]['group_uid'],'actual-group')
        self.assertEqual(result['movements'][0]['route_source'],'MANUAL')
        self.assertEqual(result['scope'],'ACTUAL_GROUPS_SCHEMATIC')
        self.assertEqual(result['statistics']['intersection_count_status'],'ESTIMATED')


class JunctionPersistenceTests(unittest.TestCase):
    setUp=base_tests.RoutingTests.setUp
    tearDown=base_tests.RoutingTests.tearDown
    save=base_tests.RoutingTests.save
    data_now=base_tests.RoutingTests.data_now
    north=base_tests.RoutingTests.north

    def setup_turn(self):
        route=next(r for r in self.data['geometry']['cross_routes'] if r['cabinet_row_uid'] and r['start_y_in']==17)
        north,central=self.north(),next(b['uid'] for b in self.data['bands'] if b['code']=='CENTRAL')
        for band in (north,central):self.save('passage-tiers',dict(passage_band_uid=band,tier=1,pathway_type='BASKET_TRAY'))
        self.save('cross-route-tiers',dict(cross_route_uid=route['uid'],tier=1,pathway_type='BASKET_TRAY'))
        station=route['station_in']
        a=self.save('segment-annotations',dict(passage_band_uid=north,start_station_in=0,end_station_in=station,tier=1))
        b=self.save('segment-annotations',dict(cross_route_uid=route['uid'],from_passage_band_uid=north,to_passage_band_uid=central,tier=1))
        common=dict(tier=1,layer=None,position=None,slot_width=None,slot_height=None,offset_up_in=0,occupied_width_in=4,occupied_height_in=1,label='Same LC bundle',cable_class='LC')
        pa=self.save('bundle-placements',dict(segment_annotation_uid=a['uid'],offset_across_in=15,**common))
        pb=self.save('bundle-placements',dict(segment_annotation_uid=b['uid'],offset_across_in=10,**common))
        c=self.save('bundle-connections',dict(from_placement_uid=pa['uid'],from_end='END',to_placement_uid=pb['uid'],to_end='START',from_turn_start_in=2,to_turn_start_in=7))
        return route,c

    def test_saved_turn_area_graph_metrics_and_legacy_unknown(self):
        route,c=self.setup_turn()
        self.save('junction-areas',dict(passage_band_uid=self.north(),cross_route_uid=route['uid'],tier=1))
        data=self.data_now();graph=derive_graph(data)
        node=next(n for n in graph.nodes if c['uid'] in n.bundle_connection_uids)
        view=saved_junction(data,data['geometry'],node,graph)
        self.assertEqual(view['movements'][0]['centerline_radius_in'],10)
        self.assertEqual(node.cable_intersection_point_count,0)
        self.assertEqual(node.intersection_count_status,'EXACT')
        self.save('bundle-connections',dict(from_turn_start_in=None,to_turn_start_in=None),c['uid'])
        node=next(n for n in derive_graph(self.data_now()).nodes if c['uid'] in n.bundle_connection_uids)
        self.assertIsNone(node.cable_intersection_point_count)
        with self.assertRaises(config.RoutingConfigurationError),self.session.begin_nested():
            self.save('bundle-connections',dict(from_turn_start_in=2,to_turn_start_in=6),c['uid'])

    def test_working_area_validation_and_api_permissions(self):
        route,c=self.setup_turn()
        field=next(b['uid'] for b in self.data['bands'] if b['kind']=='ROW_FIELD')
        for values in (dict(passage_band_uid=field,station_in=100,tier=1),dict(passage_band_uid=self.north(),cross_route_uid=route['uid'],tier=1,north_extension_in=2)):
            with self.assertRaises(config.RoutingConfigurationError),self.session.begin_nested():self.save('junction-areas',values)
        self.session.commit()
        with patch('backend.api.routing.session_factory',return_value=self.factory):
            client=TestClient(app);base=f'/routing/layouts/{self.uid}'
            node=next(n for n in derive_graph(self.data_now()).nodes if c['uid'] in n.bundle_connection_uids)
            response=client.get(base+'/junction-preview',params={'node_id':node.id})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['movements'][0]['centerline_radius_in'],10)
            self.assertEqual(client.get(base+'/junction-preview',params={'node_id':'missing'}).status_code,404)
            self.assertEqual(client.post(base+'/junction-areas',json=dict(passage_band_uid=self.north(),cross_route_uid=route['uid'],tier=1),headers={'x-user-role':'viewer'}).status_code,403)

    def test_area_extensions_preserve_saved_turn_locations_and_radius(self):
        route,c=self.setup_turn()
        area=self.save('junction-areas',dict(passage_band_uid=self.north(),cross_route_uid=route['uid'],tier=1,west_extension_in=4,south_extension_in=4))
        current=next(item for item in self.data_now()['bundle_connections'] if item['uid']==c['uid'])
        self.assertEqual((current['from_turn_start_in'],current['to_turn_start_in']),(6,11))
        data=self.data_now();graph=derive_graph(data);node=next(n for n in graph.nodes if c['uid'] in n.bundle_connection_uids)
        self.assertEqual(saved_junction(data,data['geometry'],node,graph)['movements'][0]['centerline_radius_in'],10)
        self.save('junction-areas',dict(west_extension_in=0,south_extension_in=0),area['uid'])
        current=next(item for item in self.data_now()['bundle_connections'] if item['uid']==c['uid'])
        self.assertEqual((current['from_turn_start_in'],current['to_turn_start_in']),(2,7))
        self.save('bundle-connections',{'junction_area_uid':area['uid']},c['uid'])
        config.delete_resource(self.session,self.uid,'junction-areas',area['uid'])
        current=next(item for item in self.data_now()['bundle_connections'] if item['uid']==c['uid'])
        self.assertIsNone(current['junction_area_uid'])
        self.assertEqual((current['from_turn_start_in'],current['to_turn_start_in']),(2,7))

    def test_crossing_orders_validate_clearance_and_reject_cycles(self):
        _,first=self.setup_turn()
        data=self.data_now()
        # Separate persisted placements/connections sharing the same junction.
        connections=[first]
        for height in (4,8):
            endpoints=[]
            for side in ('from','to'):
                original=next(p for p in data['bundle_placements'] if p['uid']==first[side+'_placement_uid'])
                values={k:original[k] for k in config.RESOURCES['bundle-placements'][1].model_fields}
                endpoints.append(self.save('bundle-placements',{**values,'offset_up_in':height})['uid'])
            connections.append(self.save('bundle-connections',dict(from_placement_uid=endpoints[0],from_end='END',to_placement_uid=endpoints[1],to_end='START',from_turn_start_in=2,to_turn_start_in=7)))
        self.save('junction-crossings',dict(above_connection_uid=connections[1]['uid'],below_connection_uid=connections[0]['uid'],clearance_in=2))
        with self.assertRaisesRegex(config.RoutingConfigurationError,'endpoint heights'),self.session.begin_nested():
            self.save('junction-crossings',dict(above_connection_uid=connections[0]['uid'],below_connection_uid=connections[1]['uid']))
        data=self.data_now()
        for p in data['bundle_placements']:p['offset_up_in']=None
        data['junction_crossings']=[dict(uid=f'order{i}',above_connection_uid=connections[i]['uid'],below_connection_uid=connections[(i+1)%3]['uid'],clearance_in=None,enabled=True) for i in range(3)]
        with self.assertRaisesRegex(ValueError,'cycle'):
            validate_junctions(data,data['geometry'],derive_graph(data,junction_statistics=False))


class JunctionCacheTests(unittest.TestCase):
    def test_metadata_cache_invalidates_on_manual_route_inventory_and_geometry_changes(self):
        from types import SimpleNamespace
        from backend.services import routing_junction_cache as cache
        from backend.persistence.postgresql.routing_models import RoutingManualCableRoute
        route=RoutingManualCableRoute(uid='manual',routing_layout_uid='layout',source_cabinet_uid='801',destination_cabinet_uid='811',cable_type='LC',start_tier=1,end_tier=1,legs=[],revision=1,version='v1',updated_by='test',notes='')
        class Session:
            version=1
            def get(self,*args):return SimpleNamespace(project_uid='LBB01',building_uid='LBB01:A')
            def get_bind(self):return SimpleNamespace(url='test-junction-cache')
            def execute(self,*args):return SimpleNamespace(one=lambda:(self.version,None,None))
            def scalars(self,*args):return [route]
        session=Session();data={'layout':{'room_uid':'hall'}}
        cache._cache.clear()
        with patch('backend.services.routing_cable_review.review_context',side_effect=lambda *args:({'version':route.version},None)) as build:
            cache.junction_review(session,'layout',data);cache.junction_review(session,'layout',data)
            self.assertEqual(build.call_count,1)
            route.version='v2'
            self.assertEqual(cache.junction_review(session,'layout',data)['version'],'v2')
            self.assertEqual(build.call_count,2)
            session.version=2;cache.junction_review(session,'layout',data)
            self.assertEqual(build.call_count,3)
            cache.junction_review(session,'layout',{**data,'new_geometry':True})
            self.assertEqual(build.call_count,4)
            self.assertLessEqual(len(cache._cache),2)
        cache._cache.clear()


if __name__=='__main__':unittest.main()
