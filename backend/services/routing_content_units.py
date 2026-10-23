"""Actual cable-unit membership and the bundle-local sectional reference frame."""
import json
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import or_, select
from sqlalchemy.orm import aliased
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.routing_models import RoutingSection
from backend.services.routing_configuration import RoutingConfigurationError


def content_scope(session, layout):
    room = session.get(db.Room, layout.room_uid)
    rooms = {s.room_uid or layout.room_uid for s in session.scalars(select(RoutingSection).where(RoutingSection.routing_layout_uid == layout.uid))}
    return room, rooms


def unit_identity(layout_uid, unit):
    key = ['CABLE_LIST', sorted(unit['cable_uids'])] if unit['kind'] == 'CABLE_LIST' else ['RACK_PAIR', *sorted((unit['source_cabinet_uid'], unit['destination_cabinet_uid'])), unit['cable_type']]
    return 'content-unit:' + str(uuid5(NAMESPACE_URL, layout_uid + ':' + json.dumps(key, separators=(',', ':'))))


def resolve_unit(session, layout, unit):
    """Return canonical selector, display metadata and real cable IDs on demand."""
    room, rooms = content_scope(session, layout)
    value = dict(unit)
    a, z = aliased(db.Port), aliased(db.Port)
    ca, cz = aliased(db.Cabinet), aliased(db.Cabinet)
    query = (select(db.Cable.uid).join(a, a.uid == db.Cable.a_port_uid).join(z, z.uid == db.Cable.z_port_uid)
             .join(ca,ca.uid==a.cabinet_uid).join(cz,cz.uid==z.cabinet_uid)
             .where(db.Cable.project_uid == room.project_uid, db.Cable.building_uid == room.building_uid, db.Cable.deleted_at.is_(None),
                    a.deleted_at.is_(None), z.deleted_at.is_(None), a.project_uid == room.project_uid, z.project_uid == room.project_uid,
                    a.building_uid == room.building_uid, z.building_uid == room.building_uid,
                    ca.deleted_at.is_(None),cz.deleted_at.is_(None),ca.room_uid.in_(rooms),cz.room_uid.in_(rooms),
                    ca.project_uid==room.project_uid,cz.project_uid==room.project_uid,ca.building_uid==room.building_uid,cz.building_uid==room.building_uid))
    if unit['kind'] == 'CABLE_LIST':
        query = query.where(db.Cable.uid.in_(unit['cable_uids']))
        label = unit.get('label') or (unit['cable_uids'][0] if len(unit['cable_uids'])==1 else f"{len(unit['cable_uids'])} explicitly selected cables")
        review_uid = None
    else:
        cabinets = [session.get(db.Cabinet, unit[k]) for k in ('source_cabinet_uid', 'destination_cabinet_uid')]
        if all(cabinets):
            cabinets.sort(key=lambda c: (0, int(c.cabinet_id), c.uid) if c.cabinet_id.isdigit() else (1, c.cabinet_id, c.uid))
            value.update(source_cabinet_uid=cabinets[0].uid, destination_cabinet_uid=cabinets[1].uid)
        auid, zuid = value['source_cabinet_uid'], value['destination_cabinet_uid']
        query = query.where(db.Cable.cable_type == unit['cable_type'], or_(
            (a.cabinet_uid == auid) & (z.cabinet_uid == zuid), (a.cabinet_uid == zuid) & (z.cabinet_uid == auid)))
        label = unit.get('label') or f"{cabinets[0].cabinet_id} ↔ {cabinets[1].cabinet_id} · {unit['cable_type']}" if all(cabinets) else unit.get('label') or 'Unavailable rack pair'
        review_uid = 'review-group:' + str(uuid5(NAMESPACE_URL, f"{layout.uid}:{auid}:{zuid}:{unit['cable_type']}"))
        if any(c is None or c.deleted_at is not None or c.room_uid not in rooms or (c.project_uid, c.building_uid) != (room.project_uid, room.building_uid) for c in cabinets):
            raise RoutingConfigurationError('Both unit endpoints must be active cabinets in this routing hall.')
    members = set(session.scalars(query))
    if unit['kind']=='CABLE_LIST' and members != set(unit['cable_uids']):
        raise RoutingConfigurationError('Every listed cable must be active and have active endpoints in this routing hall/building.')
    if not members:
        raise RoutingConfigurationError('The unit has no active cables matching its actual reference.')
    identity = unit_identity(layout.uid, value)
    return value, dict(unit_uid=identity, resolved_label=label, cable_count=len(members), review_group_uid=review_uid), members


def content_reference(data, placement):
    parent = next(a for a in data['segment_annotations'] if a['uid'] == placement.segment_annotation_uid)
    if parent['passage_band_uid']:
        code = next(b['code'] for b in data['bands'] if b['uid'] == parent['passage_band_uid'])
        inner = None if code == 'CENTRAL' else parent.get('section_inner_direction') or ('SOUTH' if code == 'NORTH' else 'NORTH')
        direction = inner or 'NORTH'
    else:
        route = next(r for r in data['geometry']['cross_routes'] if r['uid'] == parent['cross_route_uid'])
        row = next((r for r in data['geometry']['cabinet_rows'] if r['uid'] == route['cabinet_row_uid']), None)
        longitudinal = data['layout'].get('longitudinal_direction')
        opposite = {'EAST': 'WEST', 'WEST': 'EAST'}
        inner = parent.get('section_inner_direction') or (longitudinal if row and row['position_in_pair'] == 'A' else opposite.get(longitudinal) if row else None)
        direction = inner or 'WEST'
    return dict(column_1_direction=direction, column_1_is_inner=inner is not None,
                layer_1='BOTTOM_OF_BUNDLE_BOX', coordinate_units='ORDINAL_CELLS', physical_packing_verified=False)
