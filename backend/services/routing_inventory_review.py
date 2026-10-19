"""Full inventory stress preview: SQL counts, tier policies, compact graph references.

Defaults are calculated on read. They never write cable assignments or bundle packing.
"""
from collections import Counter
from hashlib import sha256
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.routing_models import RoutingManualCableRoute
from backend.services.routing_cables import inventory_cable_class
from backend.services.routing_configuration import get_layout, record, resolved_layout, RoutingConfigurationError
from backend.services.routing_manual_paths import planning_segments, resolve_legs, topology_revision
from backend.services.routing_planning import ReviewPlanner

T0_NODE_CENTRAL_EXTRA_PERCENT = 10
ROCE_NODE_CATEGORY_PREFIXES = ('HD-GB3', 'VR-NVL72')


def inventory_counts(session, layout):
    """Group in PostgreSQL; do not materialize hundreds of thousands of Cable objects."""
    if session.get_bind().dialect.name == 'postgresql':
        # Concurrent parallel hash joins can exhaust Docker's default 64-MiB /dev/shm.
        # Keep this large read serial within each request; users can still read concurrently.
        # SET LOCAL is transaction-scoped and cannot leak through the connection pool.
        session.execute(select(func.set_config('max_parallel_workers_per_gather', '0', True)))
    room = session.get(db.Room, layout.room_uid)
    a, z = aliased(db.Port), aliased(db.Port)
    query = (select(a.cabinet_uid, z.cabinet_uid, db.Cable.cable_type, db.Cable.construction_phase, func.count())
        .select_from(db.Cable).outerjoin(a, a.uid == db.Cable.a_port_uid).outerjoin(z, z.uid == db.Cable.z_port_uid)
        .where(db.Cable.project_uid == room.project_uid, db.Cable.building_uid == room.building_uid, db.Cable.deleted_at.is_(None))
        .group_by(a.cabinet_uid, z.cabinet_uid, db.Cable.cable_type, db.Cable.construction_phase))
    return [dict(a=a, b=b, cable_type=kind, phase=phase, count=count) for a, b, kind, phase, count in session.execute(query)]


class InventoryPolicy:
    def __init__(self, data, planner):
        self.planner, self.data, self.cache = planner, data, {}
        self.cabinets = {c['cabinet_uid']: c for c in data['cabinets']}
        self.rows = {r['uid']: r for r in data['geometry']['cabinet_rows']}
        self.route_kinds = {r['uid']: r['kind'] for r in data['cross_routes']}
        self.routes = {r['uid']: r for r in data['geometry']['cross_routes']}
        self.bands = {b['uid']: b for b in data['geometry']['bands']}

    def outer_fe_route(self, a, b):
        """Both cabinet routes must exit outward; cross-hall travel uses a gap route."""
        planner = self.planner
        endpoints = []
        for uid in (a,b):
            attachment = planner.attachments.get(uid)
            if not attachment:
                return None
            route = self.routes[attachment['cross_route_uid']]
            band = next((self.bands[bid] for bid in route['passage_band_uids'] if self.bands[bid]['code'] in ('NORTH','SOUTH')), None)
            if not band:
                return None
            upper = route['station_in'], band['center_in'], 3
            lower = *upper[:2], 2
            opening = next((eid for target,eid in planner.adjacency.get(upper,[]) if target == lower and planner.edges[eid]['edge_type'] == 'VERTICAL'), None)
            prefix = planner.shortest(planner.endpoint(uid,3), upper,
                allow_edge=lambda e: e['edge_type'] == 'CROSS_ROUTE' and e['tier'] == 3 and e['cross_route_uid'] == route['uid'])
            if not opening or not prefix:
                return None
            endpoints.append((prefix,opening,lower))
        source, destination = endpoints
        middle = planner.shortest(source[2],destination[2],allow_edge=lambda e: e['tier'] == 2 and (
            e['edge_type'] == 'PASSAGE' and e['passage_code'] in ('NORTH','SOUTH')
            or e['edge_type'] == 'CROSS_ROUTE' and self.route_kinds.get(e['cross_route_uid']) == 'SECTION_GAP'))
        if middle is None:
            return None
        ids = source[0]['load_ids'] + [source[1]] + middle['load_ids'] + [destination[1]] + list(reversed(destination[0]['load_ids']))
        points = [(p['x_in'],p['y_in'],p['tier']) for p in source[0]['points']]
        points += [(p['x_in'],p['y_in'],p['tier']) for p in middle['points']]
        points += [(p['x_in'],p['y_in'],p['tier']) for p in reversed(destination[0]['points'])]
        return planner.result(points,ids,'ASTAR')

    def classify(self, a, b, kind, phases):
        pa, pb = self.planner.attachments.get(a), self.planner.attachments.get(b)
        if not pa or not pb:
            return 'UNMAPPED', 1, 'Authoritative cabinet column or row mapping is missing.'
        if len(phases) != 1:
            return 'UNSUPPORTED', 1, 'Mixed construction phases require a manual route.'
        roce = next(iter(phases)) == 'RoCE'
        same = pa['row_uid'] == pb['row_uid']
        categories = [self.cabinets[uid]['category'].upper() for uid in (a, b)]
        if same and roce:
            return 'SAME_ROW_ROCE', 1, None
        if same and (inventory_cable_class(kind) in ('LC', 'CAT6') or kind.upper().startswith('Y')
                     or not roce and inventory_cable_class(kind) == 'MPO' and any('-FE-' in c for c in categories)):
            return 'SAME_ROW_DATA', 2, None
        if not same and not roce and any('-FE-' in c for c in categories):
            return 'FE_OUTER_TOP', 3, None
        levels = {c.split('-RO-', 1)[0] for c in categories if '-RO-' in c}
        if not same and roce and inventory_cable_class(kind) == 'MPO' and any(c.startswith('T0-RO-') for c in categories) and any(c.startswith(ROCE_NODE_CATEGORY_PREFIXES) for c in categories):
            return 'ROCE_T0_NODE', 1, None
        if not same and roce and levels == {'T0', 'T1'}:
            return 'ROCE_T0_T1', 1, None
        if not same and roce and levels == {'T1', 'T2'}:
            # A stable test distribution across the permitted layers, without capacity assumptions.
            tier = 2 + (sha256(f'{a}:{b}'.encode()).digest()[0] % 2)
            return 'ROCE_T1_T2', tier, None
        return 'UNSUPPORTED', 1, 'No test policy matches this phase, rack role and cable type; assign a manual route.'

    def bottom_node_route(self, a, b):
        """Prefer a CENTRAL longitudinal route within the confirmed 10% length allowance."""
        planner = self.planner
        start, end = planner.endpoint(a, 1), planner.endpoint(b, 1)
        bottom = lambda edge: edge['edge_type'] != 'VERTICAL' and edge['tier'] == 1
        shortest = planner.shortest(start, end, allow_edge=bottom)
        if shortest is None:
            return None
        central = planner.shortest(start, end, allow_edge=lambda edge: bottom(edge) and (
            edge['edge_type'] != 'PASSAGE' or edge['passage_code'] == 'CENTRAL'))
        # All arithmetic is integer inches, including the percentage boundary.
        if central and central['planar_length_in'] * 100 <= shortest['planar_length_in'] * (100 + T0_NODE_CENTRAL_EXTRA_PERCENT):
            return central
        return shortest

    def route(self, a, b, policy, tier):
        key = a, b, policy, tier
        if key in self.cache:
            return self.cache[key]
        planner = self.planner
        if policy.startswith('SAME_ROW'):
            route = planner.route(a, b, tier, tier)
        elif policy == 'FE_OUTER_TOP':
            route = self.outer_fe_route(a,b)
        elif policy == 'ROCE_T0_NODE':
            route = self.bottom_node_route(a,b)
        else:
            def allowed(edge):
                if policy == 'ROCE_T0_T1':
                    return edge['edge_type'] != 'VERTICAL' and edge['tier'] == 1
                # T1-T2 traffic may use mid/top and explicit upper-tier openings, never bottom.
                return edge['lower_tier'] == 2 if edge['edge_type'] == 'VERTICAL' else edge['tier'] in (2, 3)
            start, end = planner.endpoint(a, tier), planner.endpoint(b, tier)
            if policy == 'ROCE_T0_T1' and start in planner.nodes and end in planner.nodes:
                # Exit the T0 row first; this takes precedence over overall shortest distance.
                reverse = self.cabinets[b]['category'].upper().startswith('T0-RO-')
                source, target = (end, start) if reverse else (start, end)
                row_uid = planner.attachments[b if reverse else a]['cross_route_uid']
                endpoints = sorted(p for p, n in planner.nodes.items() if n.get('passage_code') and p[0] == source[0] and p[2] == 1)
                options = []
                for exit_point in endpoints:
                    prefix = planner.shortest(source, exit_point, allow_edge=lambda e: allowed(e) and e['cross_route_uid'] == row_uid)
                    if not prefix:
                        continue
                    remainder = planner.shortest(exit_point, target, forbidden=[(p['x_in'], p['y_in'], p['tier']) for p in prefix['points'][:-1]], allow_edge=allowed)
                    if remainder:
                        points = prefix['points'][:-1] + remainder['points']
                        ids = prefix['load_ids'] + remainder['load_ids']
                        options.append((prefix['planar_length_in'], remainder['planar_length_in'], tuple(ids), points, ids))
                if options:
                    _, _, _, points, ids = min(options, key=lambda o: o[:3])
                    keys = [(p['x_in'], p['y_in'], p['tier']) for p in points]
                    route = planner.result(list(reversed(keys)) if reverse else keys, list(reversed(ids)) if reverse else ids, 'ASTAR')
                else:
                    route = None
            else:
                route = planner.shortest(start, end, allow_edge=allowed)
        self.cache[key] = route
        return route


def build_inventory_review(data, counts, manual_routes=(), planner=None):
    started = perf_counter()
    cabinets = {c['cabinet_uid']: c for c in data['cabinets']}
    planner = planner or ReviewPlanner(data, cabinets)
    policy = InventoryPolicy(data, planner)
    grouped, local, unmapped, total = {}, 0, 0, 0
    types = Counter()
    for row in counts:
        a, b, count = row['a'], row['b'], row['count']
        total += count
        types[row['cable_type']] += count
        if a is None or b is None or a not in cabinets or b not in cabinets:
            unmapped += count
            continue
        if a == b:
            local += count
            continue
        a, b = sorted((a, b), key=lambda uid: (int(cabinets[uid]['cabinet_id']), uid))
        item = grouped.setdefault((a, b, row['cable_type']), dict(count=0, phases=set()))
        item['count'] += count
        item['phases'].add(row['phase'])
    manuals = {(r['source_cabinet_uid'], r['destination_cabinet_uid'], r['cable_type']): r for r in manual_routes}
    groups, loads = [], {}
    for (a, b, kind), item in sorted(grouped.items()):
        uid = 'review-group:' + str(uuid5(NAMESPACE_URL, f"{data['layout']['uid']}:{a}:{b}:{kind}"))
        rule, tier, reason = policy.classify(a, b, kind, item['phases'])
        manual = manuals.get((a, b, kind))
        if manual:
            try:
                route = resolve_legs(planner, a, b, manual['legs'], manual['start_tier'], manual['end_tier'])
                reason = None
            except RoutingConfigurationError as exc:
                route, reason = None, str(exc)
        else:
            route = policy.route(a, b, rule, tier) if not reason else None
            if not reason and route is None:
                reason = 'No complete enabled route satisfies this test policy and its physical openings.'
        cable_class = inventory_cable_class(kind)
        if cable_class == 'MPO' and rule == 'ROCE_T1_T2':
            cable_class = 'MPO_TRUNK_T2_T1_RO'
        elif cable_class in ('LC', 'CAT6') and cabinets[a]['data_hall_id'] != cabinets[b]['data_hall_id']:
            cable_class = 'CROSS_SECTION_' + cable_class
        group = dict(uid=uid, source_cabinet_uid=a, destination_cabinet_uid=b, source_cabinet_id=cabinets[a]['cabinet_id'], destination_cabinet_id=cabinets[b]['cabinet_id'],
            cable_type=kind, cable_class=cable_class, cable_uids=[], count=item['count'], policy=rule,
            occupation_hint='INNER' if rule == 'FE_OUTER_TOP' and not manual else None,
            tier=route['points'][0]['tier'] if route and len({p['tier'] for p in route['points']}) == 1 else None,
            start_tier=manual['start_tier'] if manual else tier, end_tier=manual['end_tier'] if manual else tier,
            route=route, reason=reason, route_source='MANUAL' if manual else 'DEFAULT',
            manual_status=('VALID' if route else 'INVALID') if manual else None,
            manual_version=manual['version'] if manual else None, manual_revision=manual['revision'] if manual else 0,
            manual_notes=manual['notes'] if manual else '', manual_updated_by=manual['updated_by'] if manual else None)
        groups.append(group)
        if route:
            for eid in route['load_ids']:
                load = loads.setdefault(eid, dict(group_uids=[], cable_classes=[], cable_count=0))
                load['group_uids'].append(uid)
                load['cable_count'] += item['count']
                if group['cable_class'] and group['cable_class'] not in load['cable_classes']:
                    load['cable_classes'].append(group['cable_class'])
    routed = sum(g['count'] for g in groups if g['route'])
    reasons = Counter()
    for g in groups:
        if not g['route']:
            reasons[g['reason']] += g['count']
    segments = planning_segments(planner)
    # Encode paths and memberships once by table index. The client hydrates shared graph objects.
    edge_index = {e['id']: i for i, e in enumerate(segments)}
    group_index = {g['uid']: i for i, g in enumerate(groups)}
    for group in groups:
        route = group['route']
        if route:
            group['route'] = {k: v for k, v in route.items() if k not in ('points', 'load_ids', 'segment_ids')}
            group['route'].update(start=route['points'][0], edge_indices=[edge_index[e] for e in route['load_ids']])
    encoded_loads = [dict(edge_index=edge_index[eid], group_indices=[group_index[uid] for uid in load['group_uids']],
        cable_classes=load['cable_classes'], cable_count=load['cable_count']) for eid, load in sorted(loads.items())]
    return dict(encoding='indexed-v1', scope='hall', label='Actual cable review · all five DH1 sections', provisional=True, tier=None,
        algorithm='Tier policy defaults / A* · manual assignments preserved', cabinet_uids=sorted(cabinets), inventory_cable_count=total,
        same_cabinet_count=local, unmapped_cable_count=unmapped, routed_cable_count=routed, unrouted_cable_count=total-local-routed,
        cable_types=dict(types), groups=groups, loads=encoded_loads, cables=[], planning_segments=segments, topology_revision=topology_revision(planner),
        manual_group_count=sum(g['route_source'] == 'MANUAL' for g in groups), unrouted_reasons=dict(reasons),
        policy_counts=dict(Counter({rule: sum(g['count'] for g in groups if g['policy'] == rule) for rule in sorted({g['policy'] for g in groups})})),
        build_ms=round((perf_counter()-started)*1000),
        notes='Test defaults only; manual routes take precedence. Cross-row T0–node RoCE MPO stays on Tier 1; CENTRAL longitudinal travel is preferred when no more than 10% longer than the shortest enabled bottom-tier route. FE uses outer passages and INNER packing intent, with no measured bundle footprint. T1–T2 RoCE is stably distributed over mid/top. Gap routes use two test layers. Cable members load on demand. Elevations are AFF; planar pathway length excludes vertical travel, cabinet drops and slack.' )


def inventory_review_context(session, layout_uid):
    layout = get_layout(session, layout_uid)
    if session.get(db.Room, layout.room_uid).project_uid != 'LBB01' or layout.physical_hall_code != 'DH1':
        raise RoutingConfigurationError('The inventory test is limited to LBB01 DH1.')
    started = perf_counter()
    data = resolved_layout(session, layout_uid)
    planner = ReviewPlanner(data, [c['cabinet_uid'] for c in data['cabinets']])
    manuals = [record(r) for r in session.scalars(select(RoutingManualCableRoute).where(RoutingManualCableRoute.routing_layout_uid == layout_uid))]
    review = build_inventory_review(data, inventory_counts(session, layout), manuals, planner)
    review['build_ms'] = round((perf_counter()-started)*1000)
    return review, planner
