"""Configuration persistence, scaffold maintenance and domain validation."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.persistence.postgresql.models import Room, Cabinet
from backend.persistence.postgresql import routing_models as db
from backend.schemas import routing as schema
from backend.services.routing_geometry import resolve_geometry

RESOURCES = {
    'sections': (db.RoutingSection, schema.SectionInput),
    'bands': (db.RoutingBand, schema.BandInput),
    'row-pairs': (db.RoutingRowPair, schema.RowPairInput),
    'cabinet-rows': (db.RoutingCabinetRow, schema.CabinetRowInput),
    'cross-routes': (db.RoutingCrossRoute, schema.CrossRouteInput),
    'cross-route-tiers': (db.RoutingCrossRouteTier, schema.CrossRouteTierInput),
    'passage-tiers': (db.RoutingPassageTier, schema.PassageTierInput),
    'vertical-transitions': (db.RoutingVerticalTransition, schema.VerticalTransitionInput),
    'segment-annotations': (db.RoutingSegmentAnnotation, schema.SegmentAnnotationInput),
    'bundle-placements': (db.RoutingBundlePlacement, schema.BundlePlacementInput),
    'bundle-connections': (db.RoutingBundleConnection, schema.BundleConnectionInput),
    'cabinet-attachments': (db.RoutingCabinetAttachment, schema.CabinetAttachmentInput),
}


class RoutingConfigurationError(ValueError):
    pass


class RoutingNotFound(RoutingConfigurationError):
    pass


def record(row) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def get_layout(session: Session, uid: str):
    layout = session.get(db.RoutingLayout, uid)
    if layout is None:
        raise RoutingNotFound('Routing layout was not found.')
    return layout


def snapshot(session: Session, uid: str) -> dict:
    result = {'layout': record(get_layout(session, uid))}
    for resource, (model, _) in RESOURCES.items():
        result[resource.replace('-', '_')] = [record(row) for row in session.scalars(
            select(model).where(model.routing_layout_uid == uid).order_by(model.uid))]
    return result


def resolved_layout(session: Session, uid: str) -> dict:
    result = snapshot(session, uid)
    result['geometry'] = resolve_geometry(result)
    from backend.services.routing_elevations import resolve_elevations
    resolve_elevations(result)
    from backend.services.routing_sections import resolve_source, resolve_sections
    for placement in result['bundle_placements']:
        placement['resolved_label'], placement['source_available'] = resolve_source(session, get_layout(session, uid), placement)
    result['section_occupations'] = resolve_sections(result, result['geometry'])
    from backend.services.routing_connections import resolve_connections
    resolve_connections(result, result['geometry'])
    anchor = session.get(Room, result['layout']['room_uid'])
    rooms = {r.uid: r for r in session.scalars(select(Room).where(Room.building_uid == anchor.building_uid, Room.deleted_at.is_(None)))}
    sections = {s['uid']: s for s in result['sections']}
    room_uids = {s['room_uid'] or anchor.uid for s in result['sections']} & rooms.keys()
    cabinets = list(session.scalars(select(Cabinet).where(Cabinet.room_uid.in_(room_uids), Cabinet.deleted_at.is_(None))))
    cabinet_ids = {c.uid for c in cabinets}
    for attachment in result['cabinet_attachments']:
        attachment['cabinet_available'] = attachment['cabinet_uid'] in cabinet_ids
    linked = {}
    for section in result['geometry']['sections']:
        room = rooms.get(section['room_uid'])
        section['data_hall_id'] = room.room_id if room else None
    for row in result['geometry']['cabinet_rows']:
        room_uid = sections[row['section_uid']]['room_uid'] or anchor.uid
        matches = [c for c in cabinets if c.room_uid == room_uid and row['cabinet_number_start'] is not None
                   and c.cabinet_id.isdigit() and row['cabinet_number_start'] <= int(c.cabinet_id) <= row['cabinet_number_end']]
        row['existing_cabinet_uids'] = sorted(c.uid for c in matches)
        linked.update((c.uid, c) for c in matches)
    # Read the existing inventory; these are presentation records, not duplicate Cabinets.
    result['cabinets'] = [dict(cabinet_uid=c.uid, cabinet_id=c.cabinet_id, data_hall_id=rooms[c.room_uid].room_id,
                               category=c.category, cabinet_group=c.cabinet_group, source_row=c.source_row,
                               source_col=c.source_col) for c in sorted(linked.values(), key=lambda c: c.uid)]
    return result


def resource_type(resource: str):
    if resource not in RESOURCES:
        raise RoutingNotFound('Unknown routing resource.')
    return RESOURCES[resource]


def find_layout(session: Session, project_uid: str, building_id: str, hall_code: str):
    return session.scalar(select(db.RoutingLayout).join(Room, Room.uid == db.RoutingLayout.room_uid).where(
        Room.project_uid == project_uid, Room.building_uid == f'{project_uid}:{building_id}',
        db.RoutingLayout.physical_hall_code == hall_code))


def maintain_scaffold(session: Session, layout) -> None:
    """Create missing defaults only. Never rewrite configured widths or stations."""
    sections = {s.ordinal: s for s in session.scalars(select(db.RoutingSection).where(db.RoutingSection.routing_layout_uid == layout.uid))}
    room = session.get(Room, layout.room_uid)
    for ordinal in range(1, 6):
        if ordinal not in sections:
            existing = session.scalar(select(Room).where(Room.building_uid == room.building_uid,
                                                        Room.room_id == f'{layout.physical_hall_code}-{ordinal}'))
            section = db.RoutingSection(uid=str(uuid4()), routing_layout_uid=layout.uid, ordinal=ordinal,
                                        name=f'Section {ordinal}', room_uid=existing.uid if existing else None)
            session.add(section)
            sections[ordinal] = section
    session.flush()
    existing_bands = set(session.scalars(select(db.RoutingBand.code).where(db.RoutingBand.routing_layout_uid == layout.uid)))
    for ordinal, (code, width) in enumerate((('NORTH', 34), ('NORTH_FIELD', 336), ('CENTRAL', 24), ('SOUTH_FIELD', 360), ('SOUTH', 34))):
        if code not in existing_bands:
            session.add(db.RoutingBand(uid=str(uuid4()), routing_layout_uid=layout.uid, ordinal=ordinal,
                                      kind='ROW_FIELD' if code.endswith('_FIELD') else 'PASSAGE', code=code, width_in=width))
    for ordinal in range(1, 5):
        section = sections[ordinal]
        route = session.scalar(select(db.RoutingCrossRoute).where(db.RoutingCrossRoute.section_boundary_after_section_uid == section.uid))
        if route is None:
            session.add(db.RoutingCrossRoute(uid=str(uuid4()), routing_layout_uid=layout.uid, kind='SECTION_GAP',
                                            section_boundary_after_section_uid=section.uid, width_in=layout.default_cross_route_width_in,
                                            label=f'Section {ordinal}-{ordinal + 1} gap route'))
    session.flush()


def create_layout(session: Session, payload: dict):
    values = schema.LayoutInput.model_validate(payload).model_dump()
    room = session.get(Room, values['room_uid'])
    if room is None or room.deleted_at is not None or room.room_type != 'data_hall':
        raise RoutingConfigurationError('Select an existing active data-hall Room.')
    if find_layout(session, room.project_uid, room.building_uid.split(':')[-1], values['physical_hall_code']):
        raise RoutingConfigurationError('This physical hall already has a routing layout.')
    layout = db.RoutingLayout(uid=str(uuid4()), **values)
    session.add(layout)
    session.flush()
    maintain_scaffold(session, layout)
    validate_layout(session, layout.uid)
    return layout


def initialize_lbb01(session: Session, building_id: str = 'A'):
    # Existing Room is the authoritative hall anchor. Lock it to serialize repeat initialization.
    room = session.scalar(select(Room).where(Room.project_uid == 'LBB01', Room.building_uid == f'LBB01:{building_id}',
                                             Room.room_id.in_(('DH1', 'DH1-1')), Room.deleted_at.is_(None))
                          .order_by(Room.room_id).with_for_update())
    if room is None:
        raise RoutingConfigurationError('Import the LBB01 DH1 rooms first. Initialization requires an existing DH1 or DH1-1 Room.')
    layout = find_layout(session, 'LBB01', building_id, 'DH1')
    if layout is None:
        measured = {'bottom_basket_elevation_in': 98, 'north_south_top_elevation_in': 116, 'longitudinal_direction': 'EAST'} if building_id == 'A' else {}
        layout = create_layout(session, {'room_uid': room.uid, **measured})
        initialize_confirmed_rows(session, layout)
    else:
        maintain_scaffold(session, layout)
    return resolved_layout(session, layout.uid)


def initialize_confirmed_rows(session: Session, layout) -> None:
    """Confirmed 10 racks/row, 16 rows/section/side, aligned north/south slots."""
    sections = list(session.scalars(select(db.RoutingSection).where(db.RoutingSection.routing_layout_uid == layout.uid).order_by(db.RoutingSection.ordinal)))
    fields = list(session.scalars(select(db.RoutingBand).where(db.RoutingBand.routing_layout_uid == layout.uid, db.RoutingBand.kind == 'ROW_FIELD')))
    for section in sections:
        for field in fields:
            base = (800 if field.code == 'NORTH_FIELD' else 0) + (section.ordinal - 1) * 160
            for ordinal in range(1, 9):
                pair = db.RoutingRowPair(uid=str(uuid4()), routing_layout_uid=layout.uid, routing_section_uid=section.uid,
                                        row_field_band_uid=field.uid, ordinal_in_section=ordinal, name=f'{field.code} pair {ordinal}')
                session.add(pair)
                session.flush()
                for position, delta in (('A', 0), ('B', 10)):
                    first = base + (ordinal - 1) * 20 + delta + 1
                    row = db.RoutingCabinetRow(uid=str(uuid4()), routing_layout_uid=layout.uid, row_pair_uid=pair.uid,
                                              position_in_pair=position, name=f'Rack {first}-{first + 9}',
                                              cabinet_number_start=first, cabinet_number_end=first + 9,
                                              existing_row_reference=f'LBB01 OVERHEAD racks {first}-{first + 9}')
                    session.add(row)
                    session.flush()
                    session.add(db.RoutingCrossRoute(uid=str(uuid4()), routing_layout_uid=layout.uid,
                                                    kind='CABINET_COLD_AISLE', cabinet_row_uid=row.uid,
                                                    width_in=layout.default_cross_route_width_in))
    session.flush()
    validate_layout(session, layout.uid)


def update_layout(session: Session, uid: str, patch: dict):
    layout = get_layout(session, uid)
    if any(k in patch for k in ('room_uid', 'physical_hall_code')):
        raise RoutingConfigurationError('The hall association cannot be changed after creation.')
    current = {key: getattr(layout, key) for key in schema.LayoutInput.model_fields}
    if 'row_pair_module_in' not in patch and any(key in patch for key in ('cabinet_row_depth_in', 'hot_aisle_clear_in', 'cold_aisle_clear_in')):
        dimensions = {**current, **patch}
        if any(type(dimensions[key]) is not int for key in ('cabinet_row_depth_in', 'hot_aisle_clear_in', 'cold_aisle_clear_in')):
            raise RoutingConfigurationError('Row and aisle dimensions must be integer inches.')
        patch = {**patch, 'row_pair_module_in': 2 * dimensions['cabinet_row_depth_in'] + dimensions['hot_aisle_clear_in'] + dimensions['cold_aisle_clear_in']}
    values = schema.LayoutInput.model_validate({**current, **patch}).model_dump()
    for key, value in values.items():
        setattr(layout, key, value)
    session.flush()
    validate_layout(session, uid)
    return record(layout)


def save_resource(session: Session, layout_uid: str, resource: str, payload: dict, uid: str | None = None) -> dict:
    layout = get_layout(session, layout_uid)
    # Serialize span edits with other configuration edits in this layout.
    session.scalar(select(db.RoutingLayout).where(db.RoutingLayout.uid == layout_uid).with_for_update())
    model, input_type = resource_type(resource)
    existing = session.get(model, uid) if uid else None
    if uid and (existing is None or existing.routing_layout_uid != layout_uid):
        raise RoutingNotFound('Routing record was not found in this layout.')
    if existing:
        values = {key: getattr(existing, key) for key in input_type.model_fields}
        values.update(payload)
    else:
        values = payload
    if resource in ('passage-tiers', 'cross-route-tiers') and existing is None and values.get('tier') == 1 and values.get('pathway_type') == 'BASKET_TRAY' and 'elevation_in' not in values and 'elevation_reference' not in values and layout.bottom_basket_elevation_in is not None:
        values = {**values, 'elevation_reference': 'BOTTOM_BASKET'}
    values = input_type.model_validate(values).model_dump()
    if resource == 'cross-routes' and existing and any(values[k] != getattr(existing, k) for k in ('kind', 'cabinet_row_uid', 'section_boundary_after_section_uid')):
        raise RoutingConfigurationError('Cross-route association cannot be changed. Edit its associated row instead.')
    original_source = (existing.source_kind, existing.source_uid) if existing is not None and resource == 'bundle-placements' else None
    original_cabinet = existing.cabinet_uid if existing is not None and resource == 'cabinet-attachments' else None
    row = existing or model(uid=str(uuid4()), routing_layout_uid=layout_uid)
    for key, value in values.items():
        setattr(row, key, value)
    # Validate references before flush so bad associations return useful domain errors.
    for field, target in (('routing_section_uid', db.RoutingSection), ('row_field_band_uid', db.RoutingBand), ('row_pair_uid', db.RoutingRowPair),
                          ('cabinet_row_uid', db.RoutingCabinetRow), ('section_boundary_after_section_uid', db.RoutingSection),
                          ('cross_route_uid', db.RoutingCrossRoute), ('passage_band_uid', db.RoutingBand),
                          ('from_passage_band_uid', db.RoutingBand), ('to_passage_band_uid', db.RoutingBand),
                          ('segment_annotation_uid', db.RoutingSegmentAnnotation), ('from_placement_uid', db.RoutingBundlePlacement),
                          ('to_placement_uid', db.RoutingBundlePlacement), ('vertical_transition_uid', db.RoutingVerticalTransition)):
        if values.get(field):
            referenced = session.get(target, values[field])
            if referenced is None or referenced.routing_layout_uid != layout_uid:
                raise RoutingConfigurationError(f'{field} must reference a record in this layout.')
    if resource == 'bundle-placements':
        parent = session.get(db.RoutingSegmentAnnotation, values['segment_annotation_uid'])
        if parent is None or parent.routing_layout_uid != layout_uid:
            raise RoutingConfigurationError('Bundle placement must reference a segment marking in this layout.')
        from backend.services.routing_sections import resolve_source
        retired_disable = not values['enabled'] and original_source == (values['source_kind'], values['source_uid'])
        if not resolve_source(session, layout, values)[1] and not retired_disable:
            raise RoutingConfigurationError('Choose an existing bundle in this building or cable/bundle group in this project.')
    if values.get('room_uid'):
        room, anchor = session.get(Room, values['room_uid']), session.get(Room, layout.room_uid)
        if room is None or room.building_uid != anchor.building_uid:
            raise RoutingConfigurationError('Section Room must be in the same building as its layout.')
    if resource == 'cabinet-attachments':
        cabinet = session.get(Cabinet, values['cabinet_uid'])
        rooms = {s.room_uid or layout.room_uid for s in session.scalars(select(db.RoutingSection).where(db.RoutingSection.routing_layout_uid == layout_uid))}
        available = cabinet is not None and cabinet.deleted_at is None and cabinet.room_uid in rooms
        if not available and not (original_cabinet == values['cabinet_uid'] and not values['enabled']):
            raise RoutingConfigurationError('Select an existing cabinet in this physical hall.')
    session.add(row)
    session.flush()
    if resource == 'cabinet-rows' and existing is None:
        session.add(db.RoutingCrossRoute(uid=str(uuid4()), routing_layout_uid=layout_uid, kind='CABINET_COLD_AISLE',
                                        cabinet_row_uid=row.uid, width_in=layout.default_cross_route_width_in))
        session.flush()
    validate_layout(session, layout_uid)
    return record(row)


def delete_resource(session: Session, layout_uid: str, resource: str, uid: str) -> None:
    get_layout(session, layout_uid)
    model, _ = resource_type(resource)
    row = session.get(model, uid)
    if row is None or row.routing_layout_uid != layout_uid:
        raise RoutingNotFound('Routing record was not found in this layout.')
    if resource in ('sections', 'bands', 'cross-routes'):
        raise RoutingConfigurationError('Required hall geometry/routes cannot be deleted. Disable a cross route or delete its cabinet row/pair.')
    session.delete(row)
    session.flush()
    validate_layout(session, layout_uid)


def validate_layout(session: Session, uid: str) -> None:
    data = snapshot(session, uid)
    if sorted(s['ordinal'] for s in data['sections']) != list(range(1, 6)):
        raise RoutingConfigurationError('V1 layouts require five sections.')
    if len(data['bands']) != 5:
        raise RoutingConfigurationError('V1 layouts require five ordered transverse bands.')
    boundary_uids = {s['uid'] for s in data['sections'] if s['ordinal'] < 5}
    if {r['section_boundary_after_section_uid'] for r in data['cross_routes'] if r['kind'] == 'SECTION_GAP'} != boundary_uids:
        raise RoutingConfigurationError('Each of the four section boundaries requires one gap route.')
    geometry = resolve_geometry(data)
    from backend.services.routing_annotations import validate_annotations
    try:
        validate_annotations(data, geometry)
        from backend.services.routing_sections import validate_sections
        from backend.services.routing_elevations import validate_elevations
        validate_elevations(data)
        validate_sections(data, geometry)
        from backend.services.routing_connections import validate_connections
        validate_connections(data, geometry)
    except ValueError as exc:
        raise RoutingConfigurationError(str(exc)) from exc
    bands = {b['uid']: b for b in data['bands']}
    for pair in data['row_pairs']:
        if bands[pair['row_field_band_uid']]['kind'] != 'ROW_FIELD':
            raise RoutingConfigurationError('Cabinet row pairs require a NORTH_FIELD or SOUTH_FIELD band.')
    tiers = {(p['passage_band_uid'], p['tier']) for p in data['passage_tiers'] if p['enabled']}
    for pathway in data['passage_tiers'] + data['vertical_transitions']:
        if bands[pathway['passage_band_uid']]['kind'] != 'PASSAGE':
            raise RoutingConfigurationError('Passage tiers and openings require a NORTH, CENTRAL or SOUTH PASSAGE band.')
    for opening in data['vertical_transitions']:
        if opening['station_in'] > geometry['hall_length_in']:
            raise RoutingConfigurationError('Opening station is outside the schematic hall. Configure row pairs first.')
        if opening['enabled'] and any((opening['passage_band_uid'], t) not in tiers for t in (opening['lower_tier'], opening['upper_tier'])):
            raise RoutingConfigurationError('An enabled opening requires both adjacent passage tiers to be enabled.')
    rows = {r['uid']: r for r in geometry['cabinet_rows']}
    for row in rows.values():
        if row['cabinet_number_start'] is not None and row['cabinet_number_end'] - row['cabinet_number_start'] + 1 != data['layout']['cabinets_per_row']:
            raise RoutingConfigurationError('Cabinet range must match the configured cabinets per row.')
    gaps = {g['after_section_uid']: g for g in geometry['gaps']}
    for route in geometry['cross_routes']:
        if route['kind'] == 'SECTION_GAP':
            gap = gaps.get(route['section_boundary_after_section_uid'])
            if gap is None:
                raise RoutingConfigurationError('A section-gap route must follow Section 1, 2, 3 or 4.')
            low, high = gap['start_in'], gap['end_in']
        else:
            row = rows[route['cabinet_row_uid']]
            if row['position_in_pair'] == 'A':
                low, high = row['start_in'] - data['layout']['cold_aisle_clear_in'], row['start_in']
            else:
                low, high = row['end_in'], row['end_in'] + data['layout']['cold_aisle_clear_in']
        if route['start_in'] < low or route['end_in'] > high:
            raise RoutingConfigurationError('The cross-route envelope must stay in its cold aisle or extra section gap.')
