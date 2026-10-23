from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.main import app
from backend.persistence.postgresql import models as db
from backend.services import routing_configuration as config
from backend.services.routing_bundle_contents import get_contents, write_contents, unit_cables, connection_unit_order
from backend.services.routing_cables import placement_cables
from backend.services.routing_graph import derive_graph
from backend.services.routing_manual_routes import RoutingRouteConflict
from backend.schemas.routing_bundle_contents import BundleContentsInput
from tests.unit import test_routing as base


class BundleContentsTests(unittest.TestCase):
    tearDown=base.RoutingTests.tearDown
    save=base.RoutingTests.save
    data_now=base.RoutingTests.data_now
    north=base.RoutingTests.north

    def setUp(self):
        base.RoutingTests.setUp(self)
        db.Base.metadata.create_all(self.engine)
        for number in (1,11,21,31):
            self.session.add(db.Cabinet(uid=f'cab{number}',project_uid='LBB01',building_uid='LBB01:A',room_uid='LBB01:A:DH1-1',cabinet_id=f'{number:03d}'))
        self.session.flush()
        for number in (1,11,21,31):
            self.session.add(db.Port(uid=f'port{number}',project_uid='LBB01',building_uid='LBB01:A',room_uid='LBB01:A:DH1-1',cabinet_uid=f'cab{number}',port_name='P1'))
        self.session.flush()
        for uid,a,z,kind in [('c1',1,11,'MPO12-SMF'),('c2',11,1,'MPO12-SMF'),('c3',21,31,'LC-TO-LC SMF')]:
            self.session.add(db.Cable(uid=uid,project_uid='LBB01',building_uid='LBB01:A',room_uid='LBB01:A:DH1-1',a_port_uid=f'port{a}',z_port_uid=f'port{z}',cable_type=kind))
        self.session.flush()
        self.save('passage-tiers',dict(passage_band_uid=self.north(),tier=1,pathway_type='BASKET_TRAY'))
        span=self.save('segment-annotations',dict(passage_band_uid=self.north(),start_station_in=0,end_station_in=108,tier=1))
        self.placement=self.save('bundle-placements',dict(segment_annotation_uid=span['uid'],tier=1,label='Ordered group',layer=None,position=None,slot_width=None,slot_height=None,offset_across_in=0,offset_up_in=0,occupied_width_in=12,occupied_height_in=4))
        self.pair=dict(kind='RACK_PAIR',source_cabinet_uid='cab1',destination_cabinet_uid='cab11',cable_type='MPO12-SMF',layer=1,position=1,slot_width=3)
        self.single=dict(kind='CABLE_LIST',cable_uids=['c3'],layer=1,position=4)

    def view(self,end='SPAN',uid=None):
        return get_contents(self.session,self.uid,uid or self.placement['uid'],end)

    def put(self,units,end='SPAN',uid=None,**values):
        view=self.view(end,uid)
        return write_contents(self.session,self.uid,uid or self.placement['uid'],end,BundleContentsInput(expected_version=view['version'],units=units,**values))

    def test_logical_units_multi_cell_boxes_and_atomic_swaps(self):
        initial=self.view()
        self.assertEqual((initial['status'],initial['grid_columns'],initial['grid_rows']),('UNCONFIGURED',12,8))
        graph_before=derive_graph(self.data_now()).model_dump()
        view=self.put([self.pair,self.single])
        self.assertEqual(view['assigned_cable_count'],3)
        self.assertEqual(view['cells'][0][:5],[1,1,1,2,0])
        self.assertEqual([u['cable_count'] for u in view['units']],[2,1])
        self.assertEqual(view['reference']['column_1_direction'],'SOUTH')
        self.assertTrue(view['reference']['column_1_is_inner'])
        self.assertFalse(view['physical_packing_verified'])
        ids={u['kind']:u['unit_uid'] for u in view['units']}
        swapped=self.put([{**self.single,'position':1},{**self.pair,'position':2}])
        self.assertEqual(swapped['cells'][0][:5],[1,2,2,2,0])
        self.assertEqual(ids,{u['kind']:u['unit_uid'] for u in swapped['units']})
        self.assertTrue(all('units' not in summary for summary in self.data_now()['bundle_contents']))
        self.assertEqual(graph_before,derive_graph(self.data_now()).model_dump())
        self.assertEqual({c['uid'] for c in placement_cables(self.session,self.uid,self.placement['uid'])['cables']},{'c1','c2','c3'})

    def test_endpoint_overrides_and_connection_continuity_use_actual_members(self):
        self.put([self.pair,self.single])
        self.assertTrue(self.view('END')['inherited'])
        end=self.put([{**self.pair,'position':6},self.single],'END')
        self.assertEqual(end['defined_end'],'END')
        self.assertEqual(self.view('START')['defined_end'],'SPAN')
        span=self.save('segment-annotations',dict(passage_band_uid=self.north(),start_station_in=108,end_station_in=276,tier=1))
        other=self.save('bundle-placements',dict(segment_annotation_uid=span['uid'],tier=1,label='Ordered group'))
        self.put([self.single,{**self.pair,'position':7}],uid=other['uid'])
        connection=self.save('bundle-connections',dict(from_placement_uid=self.placement['uid'],from_end='END',to_placement_uid=other['uid'],to_end='START'))
        links=connection_unit_order(self.session,self.uid,connection['uid'])
        self.assertEqual(sorted(item['cable_count'] for item in links['links']),[1,2])
        self.assertEqual(links['from_unmatched_cable_count'],0)
        self.assertEqual(links['geometry_status'],'ORDINAL_ONLY')
        self.assertTrue(all(item['from_unit_uid']==item['to_unit_uid'] for item in links['links']))
        # A rack-pair unit can split into explicit sub-units at the other endpoint.
        self.put([dict(kind='CABLE_LIST',cable_uids=['c1'],layer=1,position=1),
                  dict(kind='CABLE_LIST',cable_uids=['c2'],layer=1,position=2),self.single],uid=other['uid'])
        split=connection_unit_order(self.session,self.uid,connection['uid'])
        self.assertEqual(sorted(item['cable_count'] for item in split['links']),[1,1,1])
        self.assertEqual(len({item['from_unit_uid'] for item in split['links']}),2)
        self.assertEqual((split['from_unmatched_cable_count'],split['to_unmatched_cable_count']),(0,0))
        write_contents(self.session,self.uid,self.placement['uid'],'END',self.view('END')['version'],remove=True)
        self.assertTrue(self.view('END')['inherited'])

    def test_overlap_bounds_strict_grid_values_and_duplicate_members_are_rejected(self):
        for units in ([self.pair,{**self.single,'position':3}],[{**self.pair,'position':12}], [{**self.pair,'layer':0}], [{**self.single,'position':1.5}]):
            with self.assertRaises(ValidationError):BundleContentsInput(expected_version='v',units=units)
        self.put([self.pair])
        before=self.view()
        for units in ([self.pair,{**self.pair,'source_cabinet_uid':'cab11','destination_cabinet_uid':'cab1','position':6}],
                      [self.pair,dict(kind='CABLE_LIST',cable_uids=['c1'],layer=1,position=6)]):
            with self.assertRaises(config.RoutingConfigurationError),self.session.begin_nested():self.put(units)
        self.assertEqual(before,self.view())

    def test_actual_parent_membership_is_unchanged_and_subsets_are_enforced(self):
        self.session.add(db.EntityGroup(uid='group',project_uid='LBB01',entity_type='cable',name='Subset'))
        self.session.flush()
        for uid in ('c1','c3'):self.session.add(db.EntityGroupMember(group_uid='group',entity_type='cable',entity_uid=uid,sequence=1))
        self.session.flush()
        self.save('bundle-placements',dict(source_kind='GROUP',source_uid='group'),self.placement['uid'])
        with self.assertRaises(config.RoutingConfigurationError),self.session.begin_nested():self.put([self.pair])
        result=self.put([dict(kind='CABLE_LIST',cable_uids=['c1'],layer=1,position=1)])
        self.assertEqual((result['assigned_cable_count'],result['unassigned_cable_count'],result['status']),(1,1,'PARTIAL'))
        self.assertEqual({m.entity_uid for m in self.session.query(db.EntityGroupMember).all()},{'c1','c3'})
        with self.assertRaises(config.RoutingConfigurationError),self.session.begin_nested():
            self.save('bundle-placements',dict(source_kind='MANUAL',source_uid=None,label='Changed source'),self.placement['uid'])

    def test_stale_inventory_tokens_and_retired_single_cable_positions(self):
        result=self.put([self.single])
        self.session.get(db.Cable,'c3').deleted_at=datetime.now(timezone.utc);self.session.flush()
        view=self.view()
        self.assertEqual(view['status'],'STALE')
        self.assertEqual(view['units'][0]['position'],4)
        self.assertIsNone(view['units'][0]['cable_count'])
        self.assertNotEqual(result['version'],view['version'])
        with self.assertRaises(RoutingRouteConflict):
            write_contents(self.session,self.uid,self.placement['uid'],'SPAN',BundleContentsInput(expected_version=result['version'],units=[]))
        cleared=self.put([])
        self.assertEqual(cleared['units'],[])

    def test_lazy_cable_details_contain_only_the_selected_atomic_unit(self):
        view=self.put([self.pair,self.single])
        pair=next(u for u in view['units'] if u['kind']=='RACK_PAIR')
        self.assertIsNone(pair['cable_uids'])
        result=unit_cables(self.session,self.uid,self.placement['uid'],'SPAN',pair['unit_uid'])
        self.assertEqual({c['uid'] for c in result['cables']},{'c1','c2'})

    def test_rack_pair_unit_identity_survives_cabinet_label_sort_changes(self):
        view=self.put([self.pair]);identity=view['units'][0]['unit_uid']
        self.session.get(db.Cabinet,'cab1').cabinet_id='999';self.session.flush()
        self.assertEqual(self.view()['units'][0]['unit_uid'],identity)

    def test_an_explicit_list_stays_one_unit_and_keeps_its_actual_members(self):
        unit=dict(kind='CABLE_LIST',cable_uids=['c1','c3'],layer=1,position=1)
        view=self.put([unit])
        self.assertEqual((len(view['units']),view['units'][0]['cable_count']),(1,2))
        self.assertEqual(sum(bool(cell) for row in view['cells'] for cell in row),1)
        identity=view['units'][0]['unit_uid']
        reordered=self.put([{**unit,'cable_uids':['c3','c1']}])
        self.assertEqual(reordered['units'][0]['unit_uid'],identity)
        self.assertEqual(reordered['units'][0]['cable_uids'],['c3','c1'])
        result=unit_cables(self.session,self.uid,self.placement['uid'],'SPAN',identity)
        self.assertEqual({c['uid'] for c in result['cables']},{'c1','c3'})
        for invalid in ([],['c1','c1']):
            with self.assertRaises(ValidationError):BundleContentsInput(expected_version='v',units=[{**unit,'cable_uids':invalid}])

    def test_existing_bundle_references_keep_membership_and_central_has_no_inner_side(self):
        self.session.add(db.CableBundle(uid='bundle',scoped_uid='LBB01:A:bundle',project_uid='LBB01',building_uid='LBB01:A',name='Existing actual bundle'))
        self.session.flush()
        for cable in ('c1','c2'):self.session.add(db.CableBundleCable(cable_bundle_uid='bundle',cable_uid=cable,sequence=1))
        self.session.flush()
        self.save('bundle-placements',dict(source_kind='BUNDLE',source_uid='bundle'),self.placement['uid'])
        self.assertEqual(self.put([self.pair])['assigned_cable_count'],2)
        self.assertEqual(self.session.query(db.CableBundleCable).count(),2)
        central=next(b['uid'] for b in self.data['bands'] if b['code']=='CENTRAL')
        self.save('passage-tiers',dict(passage_band_uid=central,tier=1,pathway_type='BASKET_TRAY'))
        span=self.save('segment-annotations',dict(passage_band_uid=central,start_station_in=0,end_station_in=108,tier=1))
        other=self.save('bundle-placements',dict(segment_annotation_uid=span['uid'],tier=1,label='Central box'))
        reference=self.view(uid=other['uid'])['reference']
        self.assertEqual((reference['column_1_direction'],reference['column_1_is_inner']),('NORTH',False))

    def test_explicit_lists_reject_cables_with_outside_hall_endpoints(self):
        self.session.add(db.Room(uid='other-hall',project_uid='LBB01',building_uid='LBB01:A',room_id='DH2'))
        self.session.flush()
        self.session.get(db.Cabinet,'cab21').room_uid='other-hall';self.session.flush()
        with self.assertRaises(config.RoutingConfigurationError),self.session.begin_nested():self.put([self.single])

    def test_api_permissions_versions_and_invalid_selectors(self):
        self.session.commit()
        with patch('backend.api.routing.session_factory',return_value=self.factory):
            client=TestClient(app);path=f'/routing/layouts/{self.uid}/bundle-placements/{self.placement["uid"]}/contents'
            initial=client.get(path,headers={'x-user-role':'viewer'})
            self.assertEqual(initial.status_code,200)
            request=dict(expected_version=initial.json()['version'],units=[self.pair,self.single])
            self.assertEqual(client.put(path,json=request,headers={'x-user-role':'viewer'}).status_code,403)
            saved=client.put(path,json=request);self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(client.put(path,json=request).status_code,409)
            self.assertEqual(client.get(path,params={'section_end':'MIDDLE'}).status_code,422)
            self.assertEqual(client.get(path.replace(self.placement['uid'],'missing')).status_code,404)
            invalid={**request,'expected_version':saved.json()['version'],'units':[{**self.single,'cable_uids':['foreign-or-missing']}]}
            self.assertEqual(client.put(path,json=invalid).status_code,422)
            self.assertEqual(client.delete(path,params={'expected_version':'stale'}).status_code,409)
            self.assertEqual(client.delete(path,params={'expected_version':saved.json()['version']}).status_code,204)


if __name__=='__main__':unittest.main()
