"""Tier elevation and ordinal bundle-section validation; no cable sizing or fill policy."""
from sqlalchemy import select
from backend.persistence.postgresql.models import CableBundle, EntityGroup, Room
from backend.schemas.routing import BundlePlacementInput
from backend.services.routing_spans import span_geometry
from backend.services.routing_elevations import tier_elevation


def placement_sources(session, layout):
    room = session.get(Room, layout.room_uid)
    bundles = session.scalars(select(CableBundle).where(CableBundle.building_uid == room.building_uid, CableBundle.deleted_at.is_(None)).order_by(CableBundle.name, CableBundle.uid))
    groups = session.scalars(select(EntityGroup).where(EntityGroup.project_uid == room.project_uid, EntityGroup.entity_type.in_(('cable', 'bundle')), EntityGroup.deleted_at.is_(None)).order_by(EntityGroup.name, EntityGroup.uid))
    return ([{'kind': 'BUNDLE', 'uid': b.uid, 'name': b.name or b.uid} for b in bundles]
            + [{'kind': 'GROUP', 'uid': g.uid, 'name': g.name} for g in groups])


def resolve_source(session, layout, placement):
    if placement['source_kind'] == 'MANUAL':
        return placement['label'], True
    room = session.get(Room, layout.room_uid)
    model = CableBundle if placement['source_kind'] == 'BUNDLE' else EntityGroup
    row = session.get(model, placement['source_uid'])
    valid = row is not None and row.deleted_at is None and row.project_uid == room.project_uid
    if valid and model is CableBundle:
        valid = row.building_uid == room.building_uid
    if valid and model is EntityGroup:
        valid = row.entity_type in ('cable', 'bundle')
    return (placement['label'] or (row.name if valid else placement['source_uid']), valid)


def validate_sections(data, geometry):
    annotations = {a['uid']: a for a in data['segment_annotations']}
    bands = {b['uid']: b for b in data['bands']}
    if any(a.get('section_inner_direction') and bands.get(a['passage_band_uid'], {}).get('code') == 'CENTRAL' for a in annotations.values()):
        raise ValueError('CENTRAL has NORTH/SOUTH section sides, without an inner side.')
    tiers = {}
    for kind, records, key in (('passage', data['passage_tiers'], 'passage_band_uid'), ('cross', data['cross_route_tiers'], 'cross_route_uid')):
        for record in records:
            tiers[(kind, record[key], record['tier'])] = record
        owners = {record[key] for record in records}
        for owner in owners:
            known = sorted((r['tier'], tier_elevation(data['layout'], r)) for r in records if r[key] == owner and r['enabled'] and tier_elevation(data['layout'], r) is not None)
            if any(b[1] <= a[1] for a, b in zip(known, known[1:])):
                raise ValueError('Higher tier numbers must have greater known elevations above finished floor on the same route.')
    seen = set()
    rectangles = {}
    for placement in data['bundle_placements']:
        BundlePlacementInput.model_validate({k: placement[k] for k in BundlePlacementInput.model_fields if k in placement})
        parent = annotations[placement['segment_annotation_uid']]
        kind = 'passage' if parent['passage_band_uid'] else 'cross'
        owner = parent['passage_band_uid'] or parent['cross_route_uid']
        tier = tiers.get((kind, owner, placement['tier']))
        if placement['enabled'] and (tier is None or not tier['enabled'] or not parent['usable']):
            raise ValueError('An enabled bundle placement requires a usable segment and an explicitly enabled pathway tier.')
        if parent['tier'] is not None and parent['tier'] != placement['tier']:
            raise ValueError('Bundle tier must match the segment marking tier.')
        if placement['layer'] is not None and (placement['position'] + placement['slot_width'] - 1 > parent['grid_columns'] or placement['layer'] + placement['slot_height'] - 1 > parent['grid_rows']):
            raise ValueError('Bundle grid footprint is outside the configured section grid.')
        if placement['offset_across_in'] is not None:
            if placement['offset_across_in'] + placement['occupied_width_in'] > span_geometry(geometry, parent)['width_in']:
                raise ValueError('Bundle rectangle extends beyond the pathway width.')
            if parent['section_height_in'] is not None and placement['offset_up_in'] + placement['occupied_height_in'] > parent['section_height_in']:
                raise ValueError('Bundle rectangle extends beyond the configured section height.')
        if not placement['enabled']:
            continue
        selector = (parent['passage_band_uid'], parent['cross_route_uid'], parent['start_station_in'], parent['end_station_in'],
                    parent['from_passage_band_uid'], parent['to_passage_band_uid'], placement['tier'])
        if placement['layer'] is not None:
            for layer in range(placement['layer'], placement['layer'] + placement['slot_height']):
                for position in range(placement['position'], placement['position'] + placement['slot_width']):
                    cell = (*selector, layer, position)
                    if cell in seen:
                        raise ValueError('Enabled bundle grid footprints overlap.')
                    seen.add(cell)
        if placement['offset_across_in'] is not None:
            box = tuple(placement[k] for k in ('offset_across_in', 'offset_up_in', 'occupied_width_in', 'occupied_height_in'))
            for x, y, w, h in rectangles.get(selector, []):
                if box[0] < x + w and x < box[0] + box[2] and box[1] < y + h and y < box[1] + box[3]:
                    raise ValueError('Enabled bundle sectional rectangles overlap.')
            rectangles.setdefault(selector, []).append(box)


def resolve_sections(data, geometry):
    """Integer arrays are projections, never a second persisted source of occupancy."""
    result = []
    for parent in data['segment_annotations']:
        placements = sorted((p for p in data['bundle_placements'] if p['segment_annotation_uid'] == parent['uid'] and p['enabled'] and not p.get('is_section_container')), key=lambda p: p['uid'])
        owner_tiers = (p['tier'] for p in data['passage_tiers'] if p['passage_band_uid'] == parent['passage_band_uid']) if parent['passage_band_uid'] else (p['tier'] for p in data['cross_route_tiers'] if p['cross_route_uid'] == parent['cross_route_uid'])
        tiers = {parent['tier']} if parent['tier'] is not None else set(owner_tiers) | {p['tier'] for p in placements}
        for tier in sorted(tiers):
            cells = [[0] * parent['grid_columns'] for _ in range(parent['grid_rows'])]
            occupants, boxes = [], []
            for value, p in enumerate((p for p in placements if p['tier'] == tier), 1):
                occupants.append({'value': value, 'placement_uid': p['uid']})
                if p['layer'] is not None:
                    for row in range(p['layer'] - 1, p['layer'] - 1 + p['slot_height']):
                        for col in range(p['position'] - 1, p['position'] - 1 + p['slot_width']):
                            cells[row][col] = value
                if p['offset_across_in'] is not None:
                    boxes.append({k: p[k] for k in ('uid', 'offset_across_in', 'offset_up_in', 'occupied_width_in', 'occupied_height_in')})
            result.append({'segment_annotation_uid': parent['uid'], 'tier': tier, 'grid_columns': parent['grid_columns'],
                'grid_rows': parent['grid_rows'], 'cells': cells, 'occupants': occupants, 'rectangles': boxes,
                'width_in': span_geometry(geometry, parent)['width_in'], 'height_in': parent['section_height_in']})
    return result
