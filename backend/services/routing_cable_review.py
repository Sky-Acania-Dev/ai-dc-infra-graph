"""Read-only real-cable pilot for the first two rows on each LBB01 DH1 side."""
from collections import Counter
from uuid import NAMESPACE_URL, uuid5

from backend.persistence.postgresql.models import Room
from backend.services.routing_configuration import get_layout, resolved_layout, RoutingConfigurationError
from backend.services.routing_cables import inventory_cables, inventory_cable_class
from backend.services.routing_planning import ReviewPlanner


def review_scope(data):
    section = next(s for s in data['geometry']['sections'] if s['ordinal'] == 1)
    return sorted((c for c in data['cabinets'] if c['data_hall_id'] == section['data_hall_id'] and c['cabinet_id'].isdigit()
        and (1 <= int(c['cabinet_id']) <= 20 or 801 <= int(c['cabinet_id']) <= 820)), key=lambda c: int(c['cabinet_id']))


def build_cable_review(data, cables):
    cabinets = review_scope(data)
    names = {c['cabinet_uid']: c['cabinet_id'] for c in cabinets}
    cables = sorted((c for c in cables if c['source_cabinet_uid'] in names and c['destination_cabinet_uid'] in names), key=lambda c: c['uid'])
    planner = ReviewPlanner(data, names)
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
        if (a, b) not in cache: cache[(a, b)] = planner.route(a, b)
        route = cache[(a, b)]
        group = dict(uid=uid, source_cabinet_uid=a, destination_cabinet_uid=b, source_cabinet_id=names[a], destination_cabinet_id=names[b],
            cable_type=cable_type, cable_class=inventory_cable_class(cable_type), cable_uids=ids, count=len(ids), tier=None,
            route=route, reason=None if route else 'No enabled plan route or authoritative cabinet column mapping.')
        groups.append(group)
        if not route: continue
        for eid in route['load_ids']:
            edge = planner.edges[eid]
            load = loads.setdefault(eid, dict(id=eid, segment_id=edge['segment_id'], source=planner.nodes[edge['source']], target=planner.nodes[edge['target']],
                planar_length_in=edge['planar_length_in'], group_uids=[], cable_classes=[], cable_count=0))
            load['group_uids'].append(uid); load['cable_count'] += len(ids)
            if group['cable_class'] and group['cable_class'] not in load['cable_classes']: load['cable_classes'].append(group['cable_class'])
    routed = sum(g['count'] for g in groups if g['route'])
    return dict(label='Actual cable review · racks 001–020 / 801–820', provisional=True, tier=None, algorithm='Direct same-row / A* cross-row',
        cabinet_uids=list(names), inventory_cable_count=len(cables), same_cabinet_count=local, routed_cable_count=routed,
        unrouted_cable_count=len(cables)-local-routed, cable_types=dict(Counter(c['cable_type'] for c in cables)),
        groups=groups, loads=sorted(loads.values(), key=lambda x: x['id']),
        cables=[c for c in cables if c['source_cabinet_uid'] != c['destination_cabinet_uid']],
        notes='Read-only draft paths. Tiers, cable drops and sectional packing are unassigned. Cabinet attachment positions are schematic. Planar pathway length is not cable length.')


def cable_review(session, layout_uid):
    layout = get_layout(session, layout_uid)
    room = session.get(Room, layout.room_uid)
    if room.project_uid != 'LBB01' or layout.physical_hall_code != 'DH1':
        raise RoutingConfigurationError('This pilot is limited to LBB01 DH1.')
    data = resolved_layout(session, layout_uid)
    cabinets = review_scope(data)
    if len(cabinets) != 40:
        raise RoutingConfigurationError('Map all 40 cabinets in racks 001–020 and 801–820 in Section 1 before running this pilot.')
    return build_cable_review(data, inventory_cables(session, layout, cabinet_uids=[c['cabinet_uid'] for c in cabinets]))
