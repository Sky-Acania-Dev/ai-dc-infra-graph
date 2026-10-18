"""Read-only real-cable pilot for the first two rows on each LBB01 DH1 side."""
from collections import Counter
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select

from backend.persistence.postgresql.models import Room
from backend.services.routing_configuration import get_layout, resolved_layout, RoutingConfigurationError
from backend.services.routing_cables import inventory_cables, inventory_cable_class
from backend.services.routing_planning import ReviewPlanner
from backend.persistence.postgresql.routing_models import RoutingManualCableRoute
from backend.services.routing_configuration import record
from backend.services.routing_manual_paths import resolve_legs, planning_segments, topology_revision


def review_scope(data):
    section = next(s for s in data['geometry']['sections'] if s['ordinal'] == 1)
    return sorted((c for c in data['cabinets'] if c['data_hall_id'] == section['data_hall_id'] and c['cabinet_id'].isdigit()
        and (1 <= int(c['cabinet_id']) <= 20 or 801 <= int(c['cabinet_id']) <= 820)), key=lambda c: int(c['cabinet_id']))


def build_cable_review(data, cables, manual_routes=(), planner=None):
    cabinets = review_scope(data)
    names = {c['cabinet_uid']: c['cabinet_id'] for c in cabinets}
    cables = sorted((c for c in cables if c['source_cabinet_uid'] in names and c['destination_cabinet_uid'] in names), key=lambda c: c['uid'])
    planner = planner or ReviewPlanner(data, names)
    manuals = {(r['source_cabinet_uid'], r['destination_cabinet_uid'], r['cable_type']): r for r in manual_routes}
    grouped, local = {}, 0
    for cable in cables:
        a, b = cable['source_cabinet_uid'], cable['destination_cabinet_uid']
        if a == b:
            local += 1
            continue
        a, b = sorted((a, b), key=lambda uid: (int(names[uid]), uid))
        grouped.setdefault((a, b, cable['cable_type']), []).append(cable['uid'])
    groups, loads, cache = [], {}, {}
    for (a, b, cable_type), ids in sorted(grouped.items()):
        uid = 'review-group:' + str(uuid5(NAMESPACE_URL, f"{data['layout']['uid']}:{a}:{b}:{cable_type}"))
        manual = manuals.get((a, b, cable_type))
        reason = None
        if manual:
            try:
                route = resolve_legs(planner, a, b, manual['legs'], manual.get('start_tier', 1), manual.get('end_tier', 1))
            except RoutingConfigurationError as exc:
                route, reason = None, str(exc)
        else:
            if (a, b) not in cache: cache[(a, b)] = planner.route(a, b)
            route = cache[(a, b)]
        group = dict(uid=uid, source_cabinet_uid=a, destination_cabinet_uid=b, source_cabinet_id=names[a], destination_cabinet_id=names[b],
            cable_type=cable_type, cable_class=inventory_cable_class(cable_type), cable_uids=ids, count=len(ids),
            tier=route['points'][0]['tier'] if route and len({p['tier'] for p in route['points']}) == 1 else None,
            start_tier=manual.get('start_tier', 1) if manual else 1, end_tier=manual.get('end_tier', 1) if manual else 1,
            route=route, reason=reason or (None if route else 'No enabled plan route or authoritative cabinet column mapping.'),
            route_source='MANUAL' if manual else 'DEFAULT', manual_status=('VALID' if route else 'INVALID') if manual else None,
            manual_version=manual['version'] if manual else None, manual_revision=manual['revision'] if manual else 0,
            manual_notes=manual['notes'] if manual else '', manual_updated_by=manual['updated_by'] if manual else None)
        groups.append(group)
        if not route: continue
        for eid in route['load_ids']:
            edge = planner.edges[eid]
            load = loads.setdefault(eid, dict(id=eid, segment_id=edge['segment_id'], source=planner.nodes[edge['source']], target=planner.nodes[edge['target']],
                tier=edge['tier'], edge_type=edge['edge_type'], lower_tier=edge['lower_tier'], upper_tier=edge['upper_tier'],
                planar_length_in=edge['planar_length_in'], group_uids=[], cable_classes=[], cable_count=0))
            load['group_uids'].append(uid); load['cable_count'] += len(ids)
            if group['cable_class'] and group['cable_class'] not in load['cable_classes']: load['cable_classes'].append(group['cable_class'])
    routed = sum(g['count'] for g in groups if g['route'])
    return dict(label='Actual cable review · racks 001–020 / 801–820', provisional=True, tier=None, algorithm='Direct same-row / A* cross-row',
        cabinet_uids=list(names), inventory_cable_count=len(cables), same_cabinet_count=local, routed_cable_count=routed,
        unrouted_cable_count=len(cables)-local-routed, cable_types=dict(Counter(c['cable_type'] for c in cables)),
        groups=groups, loads=sorted(loads.values(), key=lambda x: x['id']),
        cables=[c for c in cables if c['source_cabinet_uid'] != c['destination_cabinet_uid']],
        planning_segments=planning_segments(planner), topology_revision=topology_revision(planner),
        manual_group_count=sum(g['route_source'] == 'MANUAL' for g in groups),
        notes='Manual routes take precedence over defaults. Tier changes require explicit openings. Cabinet takeoffs and sectional packing remain schematic. Planar pathway length excludes vertical travel, drops and slack.')


def review_context(session, layout_uid, scope='pilot'):
    if scope == 'hall':
        from backend.services.routing_inventory_review import inventory_review_context
        return inventory_review_context(session, layout_uid)
    layout = get_layout(session, layout_uid)
    room = session.get(Room, layout.room_uid)
    if room.project_uid != 'LBB01' or layout.physical_hall_code != 'DH1':
        raise RoutingConfigurationError('This pilot is limited to LBB01 DH1.')
    data = resolved_layout(session, layout_uid)
    cabinets = review_scope(data)
    if len(cabinets) != 40:
        raise RoutingConfigurationError('Map all 40 cabinets in racks 001–020 and 801–820 in Section 1 before running this pilot.')
    planner = ReviewPlanner(data, [c['cabinet_uid'] for c in cabinets])
    manual = [record(r) for r in session.scalars(select(RoutingManualCableRoute).where(RoutingManualCableRoute.routing_layout_uid == layout_uid))]
    review = build_cable_review(data, inventory_cables(session, layout, cabinet_uids=[c['cabinet_uid'] for c in cabinets]), manual, planner)
    return review, planner


def cable_review(session, layout_uid, scope='pilot'):
    return review_context(session, layout_uid, scope)[0]
