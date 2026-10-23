"""Actual-group API validation in one rolled-back transaction on a test DB copy."""
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from backend.main import app
from backend.persistence.postgresql.session import create_postgresql_engine
from backend.persistence.postgresql.routing_models import RoutingBundleContents, RoutingManualCableRoute
from backend.schemas.routing_bundle_contents import ContentUnitInput
from backend.services import routing_configuration as config
from backend.services.routing_content_units import resolve_unit
from backend.services.routing_graph import derive_graph
from backend.services.routing_inventory_review import inventory_review_context
from backend.services.routing_junction_geometry import saved_junction
from backend.services.routing_junction_inventory import actual_junction


def fingerprint(session):
    rows=[config.record(r) for r in session.scalars(select(RoutingManualCableRoute).order_by(RoutingManualCableRoute.uid))]
    return sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()


def audit():
    engine=create_postgresql_engine()
    if not (engine.url.database or '').startswith('junction_test_'):
        raise RuntimeError('Run only against a disposable junction_test_* database copy.')
    start=perf_counter()
    with engine.connect() as connection:
        transaction=connection.begin()
        factory=sessionmaker(bind=connection,autoflush=False,expire_on_commit=False,join_transaction_mode='create_savepoint')
        try:
            with factory() as session,session.begin():
                before=fingerprint(session)
                contents_before=[config.record(r) for r in session.scalars(select(RoutingBundleContents).order_by(RoutingBundleContents.uid))]
                layout=config.find_layout(session,'LBB01','A','DH1');uid=layout.uid
                data=config.resolved_layout(session,uid);graph=derive_graph(data)
                review,_=inventory_review_context(session,uid)
                node=next(n for n in graph.nodes if n.passage_code=='SOUTH' and n.station_in==276 and n.tier==1)
                preview=actual_junction(saved_junction(data,data['geometry'],node,graph),review,node,longitudinal_direction=data['layout']['longitudinal_direction'])
                group_ids={m['group_uid'] for m in preview['movements'] if m['from_port'] and m['to_port'] and 'EAST' in (m['from_port']['direction'],m['to_port']['direction'])}
                groups=[g for g in review['groups'] if g['uid'] in group_ids and g['count']>=3][:3]
                assert len(groups)==3
                units=[];members=[]
                for index,group in enumerate(groups):
                    unit=ContentUnitInput(kind='RACK_PAIR',source_cabinet_uid=group['source_cabinet_uid'],destination_cabinet_uid=group['destination_cabinet_uid'],cable_type=group['cable_type'],layer=1,position=1+index*2,slot_width=2).model_dump()
                    _,_,actual=resolve_unit(session,layout,unit);members.append(sorted(actual));units.append(unit)
                units=units[:2]+[dict(kind='CABLE_LIST',cable_uids=members[2][:2],layer=1,position=5),dict(kind='CABLE_LIST',cable_uids=members[2][2:3],layer=1,position=6)]
                span=config.save_resource(session,uid,'segment-annotations',dict(passage_band_uid=node.passage_band_uid,start_station_in=108,end_station_in=276,tier=1))
                cross=config.save_resource(session,uid,'segment-annotations',dict(cross_route_uid=node.cross_route_uid,from_passage_band_uid=next(b['uid'] for b in data['bands'] if b['code']=='CENTRAL'),to_passage_band_uid=node.passage_band_uid,tier=1))
                a=config.save_resource(session,uid,'bundle-placements',dict(segment_annotation_uid=span['uid'],tier=1,label='Rollback-only actual packing'))
                b=config.save_resource(session,uid,'bundle-placements',dict(segment_annotation_uid=cross['uid'],tier=1,label='Rollback-only actual packing'))
                link=config.save_resource(session,uid,'bundle-connections',dict(from_placement_uid=a['uid'],from_end='END',to_placement_uid=b['uid'],to_end='END'))
            base=f'/routing/layouts/{uid}/bundle-placements/'
            with patch('backend.api.routing.session_factory',return_value=factory):
                client=TestClient(app)
                get=lambda placement,end='SPAN':client.get(base+placement+'/contents',params={'section_end':end})
                for placement in (a['uid'],b['uid']):
                    response=client.put(base+placement+'/contents',json=dict(expected_version=get(placement).json()['version'],units=units))
                    assert response.status_code==200,response.text
                response=client.put(base+a['uid']+'/contents',params={'section_end':'END'},json=dict(expected_version=get(a['uid'],'END').json()['version'],units=[{**u,'position':14-u['position']-u.get('slot_width',1)} for u in units]))
                assert response.status_code==200,response.text
                contents=response.json();assert len(contents['units'])==4 and all(u['layer']==1 for u in contents['units'])
                continuity=client.get(f'/routing/layouts/{uid}/bundle-connections/{link["uid"]}/unit-order')
                assert continuity.status_code==200,continuity.text
                assert len(continuity.json()['links'])==4
                assert sum(v['cable_count'] for v in continuity.json()['links'])==contents['assigned_cable_count']
                current=get(a['uid']).json()
                invalid=client.put(base+a['uid']+'/contents',json=dict(expected_version=current['version'],units=units+[dict(kind='CABLE_LIST',cable_uids=members[0][:1],layer=2,position=1)]))
                assert invalid.status_code==422,invalid.text
                assert get(a['uid']).json()['version']==current['version']
                explicit=next(u for u in contents['units'] if u['kind']=='CABLE_LIST' and u['cable_count']==2)
                cables=client.get(base+a['uid']+'/contents/units/'+explicit['unit_uid']+'/cables',params={'section_end':'END'})
                assert cables.status_code==200 and len(cables.json()['cables'])==2,cables.text
                result=dict(actual_cable_count=review['inventory_cable_count'],actual_group_count=len(review['groups']),atomic_units=4,
                    explicit_list_sizes=[1,2],assigned_cable_count=contents['assigned_cable_count'],layers_used=1,continuity_links=4,
                    duplicate_members_rejected=True,manual_routes_sha256=before)
                client.close()
            with factory() as session:
                assert fingerprint(session)==before,'Manual routes changed'
        finally:
            transaction.rollback()
    with Session(engine) as session:
        assert fingerprint(session)==before
        assert [config.record(r) for r in session.scalars(select(RoutingBundleContents).order_by(RoutingBundleContents.uid))]==contents_before
    result.update(rolled_back=True,manual_routes_unchanged=True,seconds=round(perf_counter()-start,3))
    Path('tmp/routing-bundle-contents-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':audit()
