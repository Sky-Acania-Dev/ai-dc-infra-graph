"""Read-only actual-group junction audit, normally run against an isolated DB copy."""
import json
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from sqlalchemy import select, text
from backend.persistence.postgresql.session import session_factory
from backend.persistence.postgresql.routing_models import RoutingManualCableRoute
from backend.services.routing_configuration import find_layout, record, resolved_layout
from backend.services.routing_graph import derive_graph
from backend.services.routing_inventory_review import inventory_review_context
from backend.services.routing_junction_geometry import saved_junction
from backend.services.routing_junction_inventory import actual_junction


def digest(value):return sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def audit():
    with session_factory()(autoflush=False) as session,session.begin():
        session.execute(text('SET TRANSACTION READ ONLY'))
        layout=find_layout(session,'LBB01','A','DH1')
        before=[record(r) for r in session.scalars(select(RoutingManualCableRoute).where(RoutingManualCableRoute.routing_layout_uid==layout.uid).order_by(RoutingManualCableRoute.uid))]
        data=resolved_layout(session,layout.uid);graph=derive_graph(data)
        start=perf_counter();review,_=inventory_review_context(session,layout.uid);build=perf_counter()-start
        fingerprint=digest(review)
        outputs=[]
        candidates=[]
        for passage in ('NORTH','CENTRAL','SOUTH'):
            candidates.extend(sorted((n for n in graph.nodes if n.passage_code==passage and n.tier==1 and n.node_type=='JUNCTION'),key=lambda n:n.station_in)[:3])
        for node in candidates:
            passage=node.passage_code
            start=perf_counter()
            preview=actual_junction(saved_junction(data,data['geometry'],node,graph),review,node,longitudinal_direction=data['layout']['longitudinal_direction'])
            summary={k:preview['statistics'][k] for k in ('cable_intersection_point_count','bundle_pair_crossing_count','unresolved_movement_count','intersection_count_status')}
            summary.update(node_id=node.id,passage=passage,tier=node.tier,movement_count=len(preview['movements']),manual_movement_count=sum(m['route_source']=='MANUAL' for m in preview['movements']),seconds=round(perf_counter()-start,3),bytes=len(json.dumps(preview)))
            assert all(m.get('group_uid') in {g['uid'] for g in review['groups']} for m in preview['movements'])
            outputs.append(summary)
            Path(f'tmp/junction-{passage.lower()}-{node.station_in}-actual.json').write_text(json.dumps(preview,indent=2),encoding='utf-8')
        after=[record(r) for r in session.scalars(select(RoutingManualCableRoute).where(RoutingManualCableRoute.routing_layout_uid==layout.uid).order_by(RoutingManualCableRoute.uid))]
        assert before==after,'Manual assignments were modified'
        assert fingerprint==digest(review),'Preview mutated the default/manual route inventory'
        result=dict(layout_uid=layout.uid,database_revision=session.scalar(text('SELECT version_num FROM alembic_version')),actual_cable_count=review['inventory_cable_count'],actual_group_count=len(review['groups']),manual_route_count=len(before),manual_routes_sha256=digest(before),review_build_seconds=round(build,3),nodes=outputs,preserved_manual_routes=True,preserved_review=True)
        Path('tmp/junction-actual-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))


if __name__=='__main__':audit()
