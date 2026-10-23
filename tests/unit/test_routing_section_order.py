"""Actual memberships, independent ends and draft-only crossing changes."""
import copy
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.main import app
from backend.persistence.postgresql import routing_models as db
from backend.schemas.routing import SegmentAnnotationInput
from backend.schemas.routing_bundle_contents import BundleContentsInput
from backend.schemas.routing_section_order import SectionOrderRequest
from backend.services import routing_configuration as config
from backend.services.routing_content_units import resolve_unit
from backend.services.routing_graph import derive_graph
from backend.services.routing_junction_geometry import saved_junction
from backend.services.routing_junction_inventory import actual_junction
from backend.services.routing_ordered_junction import ordered_actual_junction, ordered_saved_junction, schematic_movement
from backend.services.routing_junction_intersections import intersection_statistics
from backend.services.routing_section_order import section_order, save_section_order, group_positions
from backend.services.routing_manual_routes import RoutingRouteConflict
from tests.unit import test_routing_bundle_contents as contents_support


class SectionOrderTests(unittest.TestCase):
    def setUp(self):
        self.support=contents_support.BundleContentsTests();self.support.setUp();self.addCleanup(self.support.tearDown)
        self.session,self.uid=self.support.session,self.support.uid
        data=self.support.data_now();north=self.support.north()
        central=next(b['uid'] for b in data['bands'] if b['code']=='CENTRAL')
        route=next(r for r in data['geometry']['cross_routes'] if north in r['passage_band_uids'] and r['station_in']==108)
        self.support.save('passage-tiers',dict(passage_band_uid=central,tier=1,pathway_type='BASKET_TRAY'))
        self.support.save('cross-route-tiers',dict(cross_route_uid=route['uid'],tier=1,pathway_type='BASKET_TRAY'))
        self.data=self.support.data_now();self.graph=derive_graph(self.data)
        self.node=next(n for n in self.graph.nodes if n.passage_code=='NORTH' and n.station_in==108)
        nodes={n.id:n for n in self.graph.nodes}
        cross=next(e for e in self.graph.edges if e.edge_type=='CROSS_ROUTE' and self.node.id in (e.source_node_id,e.target_node_id))
        passage=next(e for e in self.graph.edges if e.edge_type=='PASSAGE' and nodes[e.source_node_id].station_in==0 and e.target_node_id==self.node.id)
        point=lambda n:dict(node_id=n.id,x_in=n.x_in,y_in=n.y_in,tier=n.tier,passage_band_uid=n.passage_band_uid)
        segments=[dict(id=e.id,tier=1,edge_type=e.edge_type,source=point(nodes[e.source_node_id]),target=point(nodes[e.target_node_id])) for e in (passage,cross)]
        groups=[]
        for a,b,kind in [('cab1','cab11','MPO12-SMF'),('cab21','cab31','LC-TO-LC SMF')]:
            _,info,_=resolve_unit(self.session,config.get_layout(self.session,self.uid),dict(kind='RACK_PAIR',source_cabinet_uid=a,destination_cabinet_uid=b,cable_type=kind))
            groups.append(dict(uid=info['review_group_uid'],source_cabinet_uid=a,destination_cabinet_uid=b,source_cabinet_id=a,destination_cabinet_id=b,cable_type=kind,cable_class='MPO',count=info['cable_count'],route_source='MANUAL',route=dict(start=segments[0]['source'],edge_indices=[0,1])))
        self.review=dict(groups=groups,loads=[dict(edge_index=i,group_indices=[0,1]) for i in (0,1)],planning_segments=segments,topology_revision='unchanged-route-legs')
        self.original=actual_junction(saved_junction(self.data,self.data['geometry'],self.node,self.graph),self.review,self.node)

    def preview(self,overrides=()):
        return ordered_actual_junction(self.session,self.data,self.review,self.node,self.graph,self.original,overrides)

    def request(self,section,reverse=False):
        units=[{k:u[k] for k in ('kind','source_cabinet_uid','destination_cabinet_uid','cable_type','layer','position','slot_width','slot_height')} for u in section['units']]
        if reverse:
            for index,u in enumerate(reversed(units)):u['position']=index+1
        return BundleContentsInput(expected_version=section['version'],grid_columns=section['grid_columns'],grid_rows=section['grid_rows'],units=units)

    def test_preview_defaults_are_shared_and_read_only_and_flipping_changes_crossings(self):
        before=copy.deepcopy(self.review);baseline=self.preview()
        section=baseline['sections']['WEST']
        override=SectionOrderRequest(span=section['span'],section_end=section['section_end'],contents=self.request(section,True))
        changed=self.preview([override])
        self.assertNotEqual(baseline['statistics']['cable_intersection_point_count'],changed['statistics']['cable_intersection_point_count'])
        self.assertEqual(changed['statistics']['unresolved_movement_count'],0)
        self.assertEqual(self.session.query(db.RoutingBundleContents).count(),0)
        self.assertEqual(self.review,before)
        with self.assertRaises(config.RoutingConfigurationError):self.preview([override,override])
        with self.assertRaises(config.RoutingConfigurationError):self.preview([override.model_copy(update={'section_end':'SPAN'})])

    def test_save_endpoint_is_versioned_and_other_end_keeps_its_default(self):
        section=self.preview()['sections']['WEST'];end=section['section_end'];request=self.request(section,True)
        saved=save_section_order(self.session,self.data,self.review,section['span'],end,request)
        self.assertEqual(saved['status'],'CONFIGURED')
        placement=self.session.get(db.RoutingBundlePlacement,saved['bundle_placement_uid'])
        self.assertTrue(placement.is_section_container);self.assertIsNone(placement.occupied_width_in)
        self.assertEqual(self.session.query(db.RoutingManualCableRoute).count(),0)
        self.data=self.support.data_now()
        other=section_order(self.session,self.data,self.review,section['span'],'START' if end=='END' else 'END')
        self.assertEqual(other['status'],'DEFAULT')
        with self.assertRaises(RoutingRouteConflict):save_section_order(self.session,self.data,self.review,section['span'],end,request)
        reread=section_order(self.session,self.data,self.review,section['span'],end)
        self.assertEqual([u['unit_uid'] for u in reread['units']],list(reversed([u['unit_uid'] for u in section['units']])))

    def test_explicit_subsets_split_movements_and_unassigned_members_stay_unknown(self):
        baseline=self.preview();section=baseline['sections']['WEST']
        # Both MPO cables remain referenced individually in one list unit.
        request=BundleContentsInput(expected_version=section['version'],units=[dict(kind='CABLE_LIST',cable_uids=['c1','c2'],layer=1,position=1)])
        changed=self.preview([SectionOrderRequest(span=section['span'],section_end=section['section_end'],contents=request)])
        routed=[m for m in changed['movements'] if m['geometry_status']=='RESOLVED']
        self.assertEqual(sum(m['cable_count'] for m in routed),2)
        self.assertEqual(changed['statistics']['unresolved_movement_count'],1)
        self.assertIsNone(changed['statistics']['cable_intersection_point_count'])

    def test_actual_section_api_permissions_and_preview_never_write(self):
        section=self.preview()['sections']['WEST'];payload=SectionOrderRequest(span=section['span'],section_end=section['section_end'],contents=self.request(section)).model_dump()
        self.session.commit()
        with patch('backend.api.routing.session_factory',return_value=self.support.factory),patch('backend.services.routing_junction_cache.junction_review',return_value=self.review):
            client=TestClient(app);base=f'/routing/layouts/{self.uid}'
            self.assertEqual(client.post(base+'/section-order/preview',json=payload).status_code,200)
            self.assertEqual(client.put(base+'/section-order',json=payload,headers={'x-user-role':'viewer'}).status_code,403)
            response=client.put(base+'/section-order',json=payload);self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(client.put(base+'/section-order',json=payload).status_code,409)
            detail=client.post(base+'/unit-cables',json=dict(kind='CABLE_LIST',cable_uids=['c1'],layer=1,position=1))
            self.assertEqual(detail.status_code,200,detail.text)
            self.assertEqual([c['uid'] for c in detail.json()['cables']],['c1'])

    def test_relative_positions_follow_authoritative_columns_not_rack_numbers(self):
        data=copy.deepcopy(self.data)
        row=data['geometry']['cabinet_rows'][0];row['existing_cabinet_uids']=['cab1','cab11'];row.update(cabinet_number_start=1,cabinet_number_end=10)
        for cabinet in data['cabinets']:
            if cabinet['cabinet_uid']=='cab1':cabinet['source_col']=9
            if cabinet['cabinet_uid']=='cab11':cabinet.update(source_col=1,cabinet_id='009')
        positions=group_positions(data,dict(source_cabinet_uid='cab1',destination_cabinet_uid='cab11'))
        self.assertEqual((positions['source_rack_position'],positions['destination_rack_position']),(10,2))

    def test_saved_bundle_connections_expand_into_actual_ordered_units(self):
        baseline=self.preview();span=baseline['sections']['SOUTH']['span']
        annotation=self.support.save('segment-annotations',span)
        other=self.support.save('bundle-placements',dict(segment_annotation_uid=annotation['uid'],tier=1,label='Nested actual units',
            layer=None,position=None,slot_width=None,slot_height=None,offset_across_in=0,offset_up_in=0,occupied_width_in=12,occupied_height_in=4))
        self.support.put([self.support.pair,self.support.single])
        self.support.put([self.support.pair,self.support.single],uid=other['uid'])
        connection=self.support.save('bundle-connections',dict(from_placement_uid=self.support.placement['uid'],from_end='END',to_placement_uid=other['uid'],to_end='START'))
        data=self.support.data_now();before=copy.deepcopy(data);graph=derive_graph(data)
        result=ordered_saved_junction(self.session,data,saved_junction(data,data['geometry'],self.node,graph))
        self.assertEqual(len(result['movements']),2)
        self.assertEqual(sum(m['cable_count'] for m in result['movements']),3)
        self.assertTrue(all(m['parent_connection_uid']==connection['uid'] for m in result['movements']))
        self.assertEqual(result['statistics']['unresolved_movement_count'],0)
        self.assertEqual(data,before)

    def test_offset_straight_runs_get_schematic_tangent_s_curves(self):
        def port(direction,point):return dict(direction=direction,point=point,occupation=dict(occupied_width_in=1,offset_up_in=0))
        a=schematic_movement('a',1,port('WEST',[-12,-6]),port('EAST',[12,6]))
        b=schematic_movement('b',1,port('WEST',[-12,0]),port('EAST',[12,0]))
        self.assertEqual(len([p for p in a['primitives'] if p['kind']=='ARC']),2)
        self.assertEqual(intersection_statistics([a,b],estimated=True)['cable_intersection_point_count'],1)
