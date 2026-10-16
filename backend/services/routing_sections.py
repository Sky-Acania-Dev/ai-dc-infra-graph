"""Tier elevation and ordinal bundle-section validation; no cable sizing or fill policy."""
from sqlalchemy import select
from backend.persistence.postgresql.models import CableBundle, EntityGroup, Room


def placement_sources(session, layout):
    room = session.get(Room, layout.room_uid)
    bundles = session.scalars(select(CableBundle).where(CableBundle.building_uid == room.building_uid).order_by(CableBundle.name, CableBundle.uid))
    groups = session.scalars(select(EntityGroup).where(EntityGroup.project_uid == room.project_uid, EntityGroup.entity_type.in_(('cable', 'bundle'))).order_by(EntityGroup.name, EntityGroup.uid))
    return ([{'kind': 'BUNDLE', 'uid': b.uid, 'name': b.name or b.uid} for b in bundles]
            + [{'kind': 'GROUP', 'uid': g.uid, 'name': g.name} for g in groups])


def resolve_source(session, layout, placement):
    if placement['source_kind'] == 'MANUAL':
        return placement['label'], True
    room = session.get(Room, layout.room_uid)
    model = CableBundle if placement['source_kind'] == 'BUNDLE' else EntityGroup
    row = session.get(model, placement['source_uid'])
    valid = row is not None and row.project_uid == room.project_uid
    if valid and model is CableBundle:
        valid = row.building_uid == room.building_uid
    if valid and model is EntityGroup:
        valid = row.entity_type in ('cable', 'bundle')
    return (placement['label'] or (row.name if valid else placement['source_uid']), valid)


def validate_sections(data):
    annotations = {a['uid']: a for a in data['segment_annotations']}
    tiers = {}
    for kind, records, key in (('passage', data['passage_tiers'], 'passage_band_uid'), ('cross', data['cross_route_tiers'], 'cross_route_uid')):
        for record in records:
            tiers[(kind, record[key], record['tier'])] = record
        owners = {record[key] for record in records}
        for owner in owners:
            known = sorted((r['tier'], r['elevation_in']) for r in records if r[key] == owner and r['enabled'] and r['elevation_in'] is not None)
            if any(b[1] <= a[1] for a, b in zip(known, known[1:])):
                raise ValueError('Higher tier numbers must have greater known elevations above finished floor on the same route.')
    seen = set()
    for placement in data['bundle_placements']:
        parent = annotations[placement['segment_annotation_uid']]
        kind = 'passage' if parent['passage_band_uid'] else 'cross'
        owner = parent['passage_band_uid'] or parent['cross_route_uid']
        tier = tiers.get((kind, owner, placement['tier']))
        if placement['enabled'] and (tier is None or not tier['enabled'] or not parent['usable']):
            raise ValueError('An enabled bundle placement requires a usable segment and an explicitly enabled pathway tier.')
        if parent['tier'] is not None and parent['tier'] != placement['tier']:
            raise ValueError('Bundle tier must match the segment marking tier.')
        if not placement['enabled']:
            continue
        # Identical physical spans may be represented by aligned north/south routes.
        selector = (parent['passage_band_uid'], parent['cross_route_uid'], parent['start_station_in'], parent['end_station_in'],
                    parent['from_passage_band_uid'], parent['to_passage_band_uid'], placement['tier'], placement['layer'], placement['position'])
        if selector in seen:
            raise ValueError('Two enabled bundles cannot occupy the same sectional slot.')
        seen.add(selector)
