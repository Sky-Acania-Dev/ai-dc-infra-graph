"""Bounded, revision-checked cache of read-only group-route metadata for inspectors."""
from collections import OrderedDict
from hashlib import sha256
import json
from threading import Lock
from time import monotonic

from sqlalchemy import func, select
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.routing_models import RoutingManualCableRoute

_cache = OrderedDict()
_lock = Lock()


def junction_review(session, layout_uid, data):
    from backend.services.routing_cable_review import review_context
    from backend.services.routing_configuration import record
    room=session.get(db.Room,data['layout']['room_uid'])
    versions=[]
    for model in (db.Cable,db.Port):
        versions.append(tuple(session.execute(select(func.count(),func.max(model.updated_at),func.max(model.deleted_at)).where(model.project_uid==room.project_uid,model.building_uid==room.building_uid)).one()))
    manuals=[record(r) for r in session.scalars(select(RoutingManualCableRoute).where(RoutingManualCableRoute.routing_layout_uid==layout_uid).order_by(RoutingManualCableRoute.uid))]
    # Local packing edits cannot change route legs. Keep the expensive inventory
    # grouping cache warm while a technician edits only sectional order.
    routing_data={k:v for k,v in data.items() if k not in ('bundle_contents','bundle_placements','bundle_connections','section_occupations','junction_areas','junction_crossings','cabinet_attachments')}
    routing_data['segment_annotations']=[{k:a.get(k) for k in ('passage_band_uid','cross_route_uid','start_station_in','end_station_in','from_passage_band_uid','to_passage_band_uid','tier','usable')} for a in data.get('segment_annotations',[])]
    bind=session.get_bind();url=getattr(bind,'url',None) or bind.engine.url
    key=sha256(json.dumps([str(url),routing_data,versions,manuals],sort_keys=True,default=str).encode()).hexdigest()
    # Builders are serialized so concurrent requests do not repeat the full SQL
    # grouping pass. This cache never contains individual cable rows or writes.
    with _lock:
        entry=_cache.get(key)
        if entry and monotonic()-entry[0]<30:
            _cache.move_to_end(key)
            return entry[1]
        result=review_context(session,layout_uid,'hall')[0]
        _cache[key]=(monotonic(),result)
        while len(_cache)>2:_cache.popitem(last=False)
        return result
