"""Read actual cable membership through existing bundles/groups, never type guesses."""
from collections import Counter

from sqlalchemy import select, union
from sqlalchemy.orm import aliased

from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.routing_models import RoutingBundlePlacement
from backend.services.routing_configuration import RoutingNotFound, get_layout, record
from backend.services.routing_sections import resolve_source


def inventory_cable_class(cable_type):
    value = cable_type.upper()
    return 'CAT6' if value.startswith('CAT6') else 'LC' if value.startswith('LC-') or value == 'LC' else 'MPO' if value.startswith(('MPO', 'MTP')) else None


def placement_cables(session, layout_uid, placement_uid):
    layout = get_layout(session, layout_uid)
    placement = session.get(RoutingBundlePlacement, placement_uid)
    if placement is None or placement.routing_layout_uid != layout_uid:
        raise RoutingNotFound('Bundle placement was not found in this layout.')
    label, available = resolve_source(session, layout, record(placement))
    result = {'placement_uid': placement_uid, 'label': label, 'source_available': available, 'cables': [], 'summary': []}
    if not available or placement.source_kind == 'MANUAL':
        return result
    room = session.get(db.Room, layout.room_uid)
    if placement.source_kind == 'BUNDLE':
        members = select(db.CableBundleCable.cable_uid).where(db.CableBundleCable.cable_bundle_uid == placement.source_uid)
    else:
        group = session.get(db.EntityGroup, placement.source_uid)
        direct = select(db.EntityGroupMember.entity_uid).where(db.EntityGroupMember.group_uid == group.uid, db.EntityGroupMember.entity_type == 'cable')
        bundles = select(db.EntityGroupMember.entity_uid).where(db.EntityGroupMember.group_uid == group.uid, db.EntityGroupMember.entity_type == 'bundle')
        indirect = select(db.CableBundleCable.cable_uid).join(db.CableBundle, db.CableBundle.uid == db.CableBundleCable.cable_bundle_uid).where(
            db.CableBundleCable.cable_bundle_uid.in_(bundles), db.CableBundle.project_uid == room.project_uid,
            db.CableBundle.building_uid == room.building_uid, db.CableBundle.deleted_at.is_(None))
        members = union(direct, indirect)
    result['cables'] = inventory_cables(session, layout, members=members)
    counts = Counter((c['cable_type'], c['source_cabinet_id'], c['destination_cabinet_id']) for c in result['cables'])
    result['summary'] = [{'cable_type': key[0], 'source_cabinet_id': key[1], 'destination_cabinet_id': key[2], 'count': count}
                         for key, count in sorted(counts.items(), key=lambda item: tuple(v or '' for v in item[0]))]
    return result


def inventory_cables(session, layout, *, members=None, cabinet_uids=None):
    room = session.get(db.Room, layout.room_uid)
    a_port, z_port = aliased(db.Port), aliased(db.Port)
    a_cab, z_cab = aliased(db.Cabinet), aliased(db.Cabinet)
    query = (select(db.Cable, a_port, z_port, a_cab, z_cab)
             .outerjoin(a_port, a_port.uid == db.Cable.a_port_uid).outerjoin(z_port, z_port.uid == db.Cable.z_port_uid)
             .outerjoin(a_cab, a_cab.uid == a_port.cabinet_uid).outerjoin(z_cab, z_cab.uid == z_port.cabinet_uid)
             .where(db.Cable.project_uid == room.project_uid,
                    db.Cable.building_uid == room.building_uid, db.Cable.deleted_at.is_(None)).order_by(db.Cable.uid))
    if members is not None:
        query = query.where(db.Cable.uid.in_(members))
    if cabinet_uids is not None:
        query = query.where(a_port.cabinet_uid.in_(cabinet_uids), z_port.cabinet_uid.in_(cabinet_uids))
    result = []
    for cable, a, z, cabinet_a, cabinet_z in session.execute(query):
        result.append({'uid': cable.uid, 'cable_type': cable.cable_type, 'cable_class': inventory_cable_class(cable.cable_type), 'cable_group': cable.cable_group,
            'source_cabinet_uid': cabinet_a.uid if cabinet_a else None, 'source_cabinet_id': cabinet_a.cabinet_id if cabinet_a else None,
            'destination_cabinet_uid': cabinet_z.uid if cabinet_z else None, 'destination_cabinet_id': cabinet_z.cabinet_id if cabinet_z else None,
            'source_port_uid': cable.a_port_uid, 'source_port_name': a.port_name if a else None,
            'destination_port_uid': cable.z_port_uid, 'destination_port_name': z.port_name if z else None,
            'source_label': cable.a_label_text, 'destination_label': cable.z_label_text, 'notes': cable.note})
    return result
