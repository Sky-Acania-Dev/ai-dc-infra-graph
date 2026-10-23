"""Versioned ordering of atomic rack-pair/type units inside a bundle box.

SPAN is a default. START/END are complete endpoint overrides, not implicit merges.
This service never writes cable membership, manual routes or generated graph data.
"""
from collections import Counter
from hashlib import sha256
import json
from uuid import uuid4
from sqlalchemy import select
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql import routing_models as routing
from backend.services import routing_configuration as config
from backend.services.routing_content_units import resolve_unit, unit_identity, content_reference
from backend.services.routing_manual_routes import RoutingRouteConflict


class ContentsContext:
    def __init__(self, session, layout_uid, placement_uid):
        self.session, self.layout = session, config.get_layout(session, layout_uid)
        self.placement = session.get(routing.RoutingBundlePlacement, placement_uid)
        if self.placement is None or self.placement.routing_layout_uid != layout_uid:
            raise config.RoutingNotFound('Bundle placement was not found in this layout.')
        self.rows = list(session.scalars(select(routing.RoutingBundleContents).where(
            routing.RoutingBundleContents.bundle_placement_uid == placement_uid).order_by(routing.RoutingBundleContents.section_end)))
        self.cache, self.parent_error, self.parent_members = {}, None, None
        if self.placement.source_kind != 'MANUAL':
            from backend.services.routing_sections import resolve_source
            from backend.services.routing_cables import placement_member_query
            if not resolve_source(session, self.layout, config.record(self.placement))[1]:
                self.parent_error = 'The parent bundle/group reference is unavailable.'
                self.parent_members = set()
            else:
                room = session.get(db.Room, self.layout.room_uid)
                query = placement_member_query(session, self.layout, self.placement)
                self.parent_members = set(session.scalars(select(db.Cable.uid).where(db.Cable.uid.in_(query),
                    db.Cable.project_uid == room.project_uid, db.Cable.building_uid == room.building_uid, db.Cable.deleted_at.is_(None))))

    def resolve(self, unit):
        selector={k: unit.get(k) for k in ('kind', 'cable_uids', 'source_cabinet_uid', 'destination_cabinet_uid', 'cable_type')}
        if selector['cable_uids'] is not None:selector['cable_uids']=sorted(selector['cable_uids'])
        key = json.dumps(selector, sort_keys=True)
        if key not in self.cache:
            try:
                value, info, members = resolve_unit(self.session, self.layout, unit)
                error = self.parent_error
                if self.parent_members is not None and not members <= self.parent_members:
                    error = 'A content unit includes cables outside the parent bundle/group membership.'
                self.cache[key] = value, info, members, error
            except config.RoutingConfigurationError as exc:
                self.cache[key] = dict(unit), dict(unit_uid=unit_identity(self.layout.uid, unit), cable_count=None,
                    resolved_label=unit.get('label') or 'Unavailable cable unit', review_group_uid=None), set(), str(exc)
        value, info, members, error = self.cache[key]
        return {**unit, **{k: value.get(k) for k in ('source_cabinet_uid', 'destination_cabinet_uid')}}, {**info, 'resolved_label':unit.get('label') or info['resolved_label']}, members, error

    def version(self):
        membership = []
        for row in self.rows:
            for unit in row.units:
                _, info, members, error = self.resolve(unit)
                membership.append([row.section_end, info['unit_uid'], sorted(members), error])
        annotation = self.session.get(routing.RoutingSegmentAnnotation, self.placement.segment_annotation_uid)
        payload = [config.record(self.placement), config.record(annotation), self.layout.longitudinal_direction,
                   [config.record(row) for row in self.rows], membership,
                   None if self.parent_members is None else sorted(self.parent_members), self.parent_error]
        return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _view(context, section_end):
    selected = next((r for r in context.rows if r.section_end == section_end), None)
    if selected is None and section_end != 'SPAN':
        selected = next((r for r in context.rows if r.section_end == 'SPAN'), None)
    columns, rows = (selected.grid_columns, selected.grid_rows) if selected else (12, 8)
    cells, units, errors, used = [[0]*columns for _ in range(rows)], [], [], set()
    if context.parent_error:errors.append(context.parent_error)
    for unit in sorted(selected.units if selected else [], key=lambda u:(u['layer'],u['position'],unit_identity(context.layout.uid,u))):
        value, info, members, error = context.resolve(unit)
        if used & members:errors.append('Content units duplicate actual cable membership.')
        used.update(members)
        if error:errors.append(error)
        ordinal = len(units)+1
        units.append({**value, **info, 'ordinal':ordinal, 'membership_status':'STALE' if error else 'AVAILABLE', 'error':error})
        for y in range(unit['layer']-1,unit['layer']-1+unit['slot_height']):
            for x in range(unit['position']-1,unit['position']-1+unit['slot_width']):
                cells[y][x] = ordinal
    unassigned = None if context.parent_members is None else len(context.parent_members-used)
    data = config.resolved_layout(context.session, context.layout.uid)
    from backend.services.routing_section_order import group_positions, rack_positions
    positions=rack_positions(data)
    for unit in units:
        if unit['kind']=='RACK_PAIR':unit.update(group_positions(data,unit,positions))
    return dict(bundle_placement_uid=context.placement.uid, parent_enabled=context.placement.enabled, requested_end=section_end,
        defined_end=selected.section_end if selected else None, inherited=bool(selected and selected.section_end!=section_end),
        version=context.version(), grid_columns=columns, grid_rows=rows, cells=cells, units=units,
        reference=content_reference(data,context.placement), assigned_cable_count=len(used), unassigned_cable_count=unassigned,
        coverage_scope='EXPLICIT_UNITS' if context.parent_members is None else 'PARENT_MEMBERSHIP',
        status='STALE' if errors else 'UNCONFIGURED' if selected is None else 'PARTIAL' if unassigned else 'CONFIGURED',
        errors=sorted(set(errors)), notes=selected.notes if selected else None,
        physical_packing_verified=False, route_assignments_changed=False)


def get_contents(session, layout_uid, placement_uid, section_end='SPAN'):
    return _view(ContentsContext(session, layout_uid, placement_uid), section_end)


def write_contents(session, layout_uid, placement_uid, section_end, request, *, remove=False):
    session.scalar(select(routing.RoutingLayout).where(routing.RoutingLayout.uid==layout_uid).with_for_update())
    context = ContentsContext(session, layout_uid, placement_uid)
    expected = request if remove else request.expected_version
    if context.version() != expected:
        raise RoutingRouteConflict('Bundle contents or inventory changed. Reload the sectional contents before saving.')
    row = next((r for r in context.rows if r.section_end==section_end),None)
    if remove:
        if row is not None:session.delete(row)
    else:
        if context.parent_error:raise config.RoutingConfigurationError(context.parent_error)
        units, used, identities = [], set(), set()
        for unit in request.units:
            value, info, members, error = context.resolve(unit.model_dump())
            if error:raise config.RoutingConfigurationError(error)
            if info['unit_uid'] in identities or used & members:
                raise config.RoutingConfigurationError('A cable may belong to only one atomic unit in this sectional arrangement.')
            identities.add(info['unit_uid']); used.update(members); units.append(value)
        units.sort(key=lambda u:(u['layer'],u['position'],unit_identity(layout_uid,u)))
        row = row or routing.RoutingBundleContents(uid=str(uuid4()),routing_layout_uid=layout_uid,bundle_placement_uid=placement_uid,section_end=section_end)
        row.grid_columns,row.grid_rows,row.units,row.notes = request.grid_columns,request.grid_rows,units,request.notes
        session.add(row)
    session.flush()
    return get_contents(session,layout_uid,placement_uid,section_end)


def unit_cables(session, layout_uid, placement_uid, section_end, unit_uid):
    context = ContentsContext(session,layout_uid,placement_uid)
    view = _view(context,section_end)
    unit = next((u for u in view['units'] if u['unit_uid']==unit_uid),None)
    if unit is None:raise config.RoutingNotFound('The atomic unit is not in this endpoint arrangement.')
    _,_,members,error = context.resolve(unit)
    if error:raise config.RoutingConfigurationError(error)
    from backend.services.routing_cables import inventory_cables
    return dict(unit_uid=unit_uid,cable_count=len(members),cables=inventory_cables(session,context.layout,members=sorted(members)))


def manual_content_members(session, layout, placement):
    context = ContentsContext(session,layout.uid,placement.uid)
    result = set()
    for row in context.rows:
        for unit in row.units:
            _,_,members,_ = context.resolve(unit)
            result.update(members)
    return sorted(result)


def connection_unit_order(session, layout_uid, connection_uid):
    config.get_layout(session,layout_uid)
    connection = session.get(routing.RoutingBundleConnection,connection_uid)
    if connection is None or connection.routing_layout_uid!=layout_uid:
        raise config.RoutingNotFound('Bundle connection was not found in this layout.')
    sides, indexed = {}, {}
    for side in ('from','to'):
        context = ContentsContext(session,layout_uid,getattr(connection,side+'_placement_uid'))
        view = _view(context,getattr(connection,side+'_end')); sides[side] = view
        indexed[side] = {}
        for unit in view['units']:
            _,_,members,error=context.resolve(unit)
            if not error:indexed[side].update((c,unit['unit_uid']) for c in members)
    links = Counter((indexed['from'][c],indexed['to'][c]) for c in indexed['from'].keys() & indexed['to'].keys())
    return dict(connection_uid=connection_uid,enabled=connection.enabled,from_section=sides['from'],to_section=sides['to'],
        links=[dict(from_unit_uid=a,to_unit_uid=b,cable_count=count) for (a,b),count in sorted(links.items())],
        from_unmatched_cable_count=len(indexed['from'].keys()-indexed['to'].keys()),
        to_unmatched_cable_count=len(indexed['to'].keys()-indexed['from'].keys()),
        geometry_status='ORDINAL_ONLY', physical_geometry_generated=False, route_assignments_changed=False)
