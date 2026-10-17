"""Manual prefix validation, domain intervals, and A* continuation. No persistence."""
from hashlib import sha256
import json

from backend.services.routing_configuration import RoutingConfigurationError


def topology_revision(planner):
    payload = [(e['id'], e['planar_length_in']) for e in sorted(planner.edges.values(), key=lambda e: e['id'])]
    payload += [(uid, a['point']) for uid, a in sorted(planner.attachments.items())]
    return sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()


def planning_segments(planner):
    return [dict(id=e['id'], segment_id=e['segment_id'], source=planner.nodes[e['source']], target=planner.nodes[e['target']],
                 planar_length_in=e['planar_length_in'], label=planner.span_by_id[e['segment_id']]['label'],
                 edge_type=e['edge_type'], tier=e['tier'], lower_tier=e['lower_tier'], upper_tier=e['upper_tier'],
                 vertical_transition_uid=e['vertical_transition_uid'], pathway_type=e['pathway_type'], width_in=e['width_in'])
            for e in sorted(planner.edges.values(), key=lambda e: e['id'])]


def validate_chain(planner, source, destination, ids, complete=False, start_tier=1, end_tier=1):
    a, b = planner.endpoint(source, start_tier), planner.endpoint(destination, end_tier)
    if a not in planner.nodes or b not in planner.nodes:
        raise RoutingConfigurationError('The cabinet endpoints need enabled pathways on their selected tiers and valid cabinet ordering.')
    points, visited = [a], {a}
    for eid in ids:
        edge = planner.edges.get(eid)
        if not edge:
            raise RoutingConfigurationError('The chain contains an unavailable or disabled segment. Refresh the routing map.')
        current = points[-1]
        if current == b:
            raise RoutingConfigurationError('The chain cannot continue beyond its destination.')
        if current not in (edge['source'], edge['target']):
            raise RoutingConfigurationError('Route segments must form a connected, ordered chain from the source cabinet.')
        target = edge['target'] if current == edge['source'] else edge['source']
        if target in visited:
            raise RoutingConfigurationError('Route chains cannot loop or backtrack. Use Undo to change direction.')
        points.append(target); visited.add(target)
    reached = points[-1] == b
    if complete and not reached:
        raise RoutingConfigurationError('Complete the route to the destination cabinet before saving.')
    return points, reached


def next_chains(planner, points, destination):
    """Collapse degree-two cabinet stations into one click, stopping at actual junctions."""
    start, visited = points[-1], set(points)
    if start == destination:
        return []
    result = []
    for target, eid in sorted(planner.adjacency[start], key=lambda item: item[1]):
        if target in visited:
            continue
        chain_points, ids = [start, target], [eid]
        while chain_points[-1] != destination and len(planner.adjacency[chain_points[-1]]) == 2 and not any(planner.edges[e]['edge_type'] == 'VERTICAL' for _, e in planner.adjacency[chain_points[-1]]):
            choices = [(p, e) for p, e in planner.adjacency[chain_points[-1]] if p != chain_points[-2] and p not in visited and p not in chain_points]
            if not choices:
                break
            p, e = choices[0]; chain_points.append(p); ids.append(e)
        route = planner.result(chain_points, ids, 'MANUAL')
        route['id'] = sha256('|'.join(ids).encode()).hexdigest()[:20]
        route['label'] = planner.span_by_id[planner.edges[ids[0]]['segment_id']]['label']
        result.append(route)
    return result


def manual_preview(planner, group, ids, start_tier=1, end_tier=1):
    points, complete = validate_chain(planner, group['source_cabinet_uid'], group['destination_cabinet_uid'], ids, start_tier=start_tier, end_tier=end_tier)
    destination = planner.endpoint(group['destination_cabinet_uid'], end_tier)
    suggestion = None if complete else planner.shortest(points[-1], destination, points[:-1])
    return dict(group_uid=group['uid'], topology_revision=topology_revision(planner), complete=complete,
                prefix=planner.result(points, ids, 'MANUAL'), suggestion=suggestion,
                next_chains=next_chains(planner, points, destination), destination=planner.nodes[destination], start_tier=start_tier, end_tier=end_tier)


def chain_legs(planner, points, ids):
    """Persist pathway owners and directed integer-inch intervals, never generated edge IDs."""
    legs = []
    for a, b, eid in zip(points, points[1:], ids):
        edge = planner.edges[eid]
        if edge['edge_type'] == 'VERTICAL':
            legs.append(dict(vertical_transition_uid=edge['vertical_transition_uid'], from_tier=a[2], to_tier=b[2]))
            continue
        span = planner.span_by_id[planner.edges[eid]['segment_id']]
        passage = span['passage_band_uid']
        leg = dict(passage_band_uid=passage, cross_route_uid=span['cross_route_uid'], tier=a[2], start_in=a[0 if passage else 1], end_in=b[0 if passage else 1])
        if legs and all(legs[-1].get(k) == leg[k] for k in ('passage_band_uid', 'cross_route_uid', 'tier')) and legs[-1]['end_in'] == leg['start_in']:
            legs[-1]['end_in'] = leg['end_in']
        else:
            legs.append(leg)
    return legs


def resolve_legs(planner, source, destination, legs, start_tier=1, end_tier=1):
    """Rebuild a saved chain after harmless graph subdivisions; never reroute invalid intent."""
    ids = []
    for leg in legs:
        if leg.get('vertical_transition_uid'):
            matches = [e for e in planner.edges.values() if e['edge_type'] == 'VERTICAL' and e['vertical_transition_uid'] == leg['vertical_transition_uid']
                       and {e['source'][2], e['target'][2]} == {leg['from_tier'], leg['to_tier']}]
            if len(matches) != 1:
                raise RoutingConfigurationError('A saved tier change requires an enabled adjacent-tier opening. A* has not replaced this manual route.')
            ids.append(matches[0]['id']); continue
        passage, cross = leg.get('passage_band_uid'), leg.get('cross_route_uid')
        if bool(passage) == bool(cross) or leg['start_in'] == leg['end_in']:
            raise RoutingConfigurationError('The saved manual pathway interval is invalid.')
        axis, start, end = (0 if passage else 1), leg['start_in'], leg['end_in']
        forward, choices = end > start, {}
        for edge in planner.edges.values():
            if edge['edge_type'] == 'VERTICAL' or edge['tier'] != leg['tier']:
                continue
            span = planner.span_by_id[edge['segment_id']]
            if span['passage_band_uid'] != passage or span['cross_route_uid'] != cross:
                continue
            a, b = edge['source'], edge['target']
            if not forward: a, b = b, a
            if min(start, end) <= a[axis] <= max(start, end) and min(start, end) <= b[axis] <= max(start, end):
                choices[a[axis]] = (b[axis], edge['id'])
        current = start
        while current != end:
            if current not in choices:
                raise RoutingConfigurationError('A saved manual route is no longer connected or usable. Edit it explicitly; A* has not replaced it.')
            current, eid = choices[current]; ids.append(eid)
    points, _ = validate_chain(planner, source, destination, ids, complete=True, start_tier=start_tier, end_tier=end_tier)
    return planner.result(points, ids, 'MANUAL')
