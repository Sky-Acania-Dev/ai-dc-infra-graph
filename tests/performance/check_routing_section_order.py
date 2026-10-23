"""End-to-end actual inventory ordering audit, rolled back on a test copy only."""
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from backend.main import app
from backend.persistence.postgresql.session import create_postgresql_engine
from backend.persistence.postgresql.routing_models import RoutingBundleContents, RoutingBundlePlacement
from backend.services import routing_configuration as config
from backend.services.routing_junction_cache import junction_review
from backend.services.routing_graph import derive_graph
from tests.performance.check_routing_bundle_contents import fingerprint


def audit():
    engine=create_postgresql_engine()
    if not (engine.url.database or '').startswith('junction_test_'):raise RuntimeError('Use an isolated junction_test_* database only.')
    start=perf_counter()
    with engine.connect() as connection:
        transaction=connection.begin();factory=sessionmaker(bind=connection,autoflush=False,expire_on_commit=False,join_transaction_mode='create_savepoint')
        try:
            with factory() as session:
                before=fingerprint(session);contents_before=list(session.scalars(select(RoutingBundleContents.uid)));placements_before=list(session.scalars(select(RoutingBundlePlacement.uid)))
                uid=config.find_layout(session,'LBB01','A','DH1').uid;data=config.resolved_layout(session,uid);review=junction_review(session,uid,data)
                node=next(n for n in derive_graph(data).nodes if n.passage_code=='SOUTH' and n.station_in==276 and n.tier==1)
            with patch('backend.api.routing.session_factory',return_value=factory),patch('backend.services.routing_junction_cache.junction_review',return_value=review),TestClient(app) as client:
                base=f'/routing/layouts/{uid}'
                first=client.get(base+'/junction-preview',params={'node_id':node.id,'actual_groups':True});assert first.status_code==200,first.text
                first=first.json();section=first['sections']['EAST']
                ordered=sorted(section['units'],key=lambda u:(-(u.get('destination_rack_position') or 0),u['unit_uid']))
                units=[{**{k:u[k] for k in ('kind','source_cabinet_uid','destination_cabinet_uid','cable_type','slot_width','slot_height')},'position':i%section['grid_columns']+1,'layer':i//section['grid_columns']+1} for i,u in enumerate(ordered)]
                payload=dict(span=section['span'],section_end=section['section_end'],contents=dict(expected_version=section['version'],grid_columns=section['grid_columns'],grid_rows=section['grid_rows'],units=units))
                started=perf_counter();draft=client.post(base+'/junction-preview',json=dict(node_id=node.id,overrides=[payload]));draft_seconds=perf_counter()-started
                assert draft.status_code==200,draft.text
                draft=draft.json();assert draft['statistics']['unresolved_movement_count']==0
                assert draft['statistics']['cable_intersection_point_count']!=first['statistics']['cable_intersection_point_count']
                with factory() as session:assert list(session.scalars(select(RoutingBundleContents.uid)))==contents_before
                assert client.put(base+'/section-order',json=payload,headers={'x-user-role':'viewer'}).status_code==403
                saved=client.put(base+'/section-order',json=payload);assert saved.status_code==200,saved.text
                assert client.put(base+'/section-order',json=payload).status_code==409
                after=client.get(base+'/junction-preview',params={'node_id':node.id,'actual_groups':True});assert after.status_code==200,after.text
                after=after.json();assert after['statistics']==draft['statistics']
                other_end='START' if section['section_end']=='END' else 'END'
                other=client.post(base+'/section-order/preview',json=dict(span=section['span'],section_end=other_end));assert other.status_code==200,other.text
                assert other.json()['status']=='DEFAULT'
                invalid=json.loads(json.dumps(payload));invalid['contents']['expected_version']=saved.json()['version'];invalid['contents']['units'][0]['position']=0
                assert client.put(base+'/section-order',json=invalid).status_code==422
                result=dict(actual_cable_count=review['inventory_cable_count'],actual_group_count=len(review['groups']),junction_movements=len(first['movements']),
                    edited_units=len(units),intersection_points_before=first['statistics']['cable_intersection_point_count'],intersection_points_after=draft['statistics']['cable_intersection_point_count'],
                    draft_seconds=round(draft_seconds,3),save_reload_matches_preview=True,opposite_end_unchanged=True,stale_save_rejected=True,invalid_save_rejected=True,manual_routes_sha256=before)
        finally:transaction.rollback()
    with Session(engine) as session:
        assert fingerprint(session)==before
        assert list(session.scalars(select(RoutingBundleContents.uid)))==contents_before
        assert list(session.scalars(select(RoutingBundlePlacement.uid)))==placements_before
    result.update(rolled_back=True,manual_routes_unchanged=True,seconds=round(perf_counter()-start,3))
    Path('tmp/routing-section-order-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':audit()
