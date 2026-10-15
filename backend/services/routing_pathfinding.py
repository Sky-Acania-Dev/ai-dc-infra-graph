from __future__ import annotations

import heapq

from backend.schemas.routing import RoutePreview, RoutingGraph
from backend.services.routing_geometry import format_inches


class NoRoutingPath(ValueError):
    pass


def preview_route(graph: RoutingGraph, data: dict, start: str, end: str) -> RoutePreview:
    nodes = {n.id: n for n in graph.nodes}
    if start not in nodes or end not in nodes:
        raise NoRoutingPath('The selected node is unavailable. Reload the graph and select configured pathway nodes.')
    adjacency = {nid: [] for nid in nodes}
    edges = {e.id: e for e in graph.edges}
    for edge in graph.edges:
        if not edge.usable:
            continue
        adjacency[edge.source_node_id].append((edge.target_node_id, edge))
        adjacency[edge.target_node_id].append((edge.source_node_id, edge))
    # Stable edge-ID sequence is the final lexicographic tie breaker.
    initial = (0, 0, 0, ())
    best, previous = {start: initial}, {}
    queue = [(initial, start)]
    while queue:
        cost, nid = heapq.heappop(queue)
        if best.get(nid) != cost:
            continue
        if nid == end:
            break
        for target, edge in sorted(adjacency[nid], key=lambda item: item[1].id):
            candidate = (cost[0] + int(edge.edge_type == 'VERTICAL'), cost[1] + edge.planar_length_in,
                         cost[2] + 1, cost[3] + (edge.id,))
            if target not in best or candidate < best[target]:
                best[target] = candidate
                previous[target] = (nid, edge.id)
                heapq.heappush(queue, (candidate, target))
    if end not in best:
        raise NoRoutingPath('No configured pathway connects these nodes. Check enabled tiers and explicit adjacent-tier openings.')
    node_ids, edge_ids = [end], []
    while node_ids[-1] != start:
        before, eid = previous[node_ids[-1]]
        node_ids.append(before)
        edge_ids.append(eid)
    ordered_nodes = [nodes[nid] for nid in reversed(node_ids)]
    ordered_edges = [edges[eid] for eid in reversed(edge_ids)]
    steps, openings = route_steps(ordered_nodes, ordered_edges, data)
    return RoutePreview(nodes=ordered_nodes, edges=ordered_edges, vertical_transition_count=best[end][0],
                        planar_length_in=best[end][1], steps=steps, vertical_opening_labels=openings)


def route_steps(nodes, edges, data: dict) -> tuple[list[str], list[str]]:
    routes = {r['uid']: r for r in data['cross_routes']}
    rows = {r['uid']: r for r in data['cabinet_rows']}
    sections = {s['uid']: s for s in data['sections']}
    transitions = {v['uid']: v for v in data['vertical_transitions']}

    def cross_label(uid):
        route = routes[uid]
        if route['kind'] == 'SECTION_GAP':
            ordinal = sections[route['section_boundary_after_section_uid']]['ordinal']
            return route['label'] or f'Section {ordinal}-{ordinal + 1} gap route'
        return route['label'] or f"Row {rows[route['cabinet_row_uid']]['name']} cold-aisle route"

    def destination(node):
        if node.vertical_transition_uids:
            return ' / '.join(transitions[uid]['label'] or uid for uid in node.vertical_transition_uids)
        if node.cross_route_uid:
            return cross_label(node.cross_route_uid)
        # A passage node may be the separate representation of an intersection.
        matching = next((r for r in data.get('geometry', {}).get('cross_routes', []) if r['station_in'] == node.station_in), None)
        return cross_label(matching['uid']) if matching else f'station {format_inches(node.station_in)}'

    groups = []
    for i, edge in enumerate(edges):
        if edge.edge_type == 'JUNCTION':
            continue
        key = (edge.edge_type, edge.tier, edge.cross_route_uid, edge.passage_code)
        if groups and edge.edge_type != 'VERTICAL' and groups[-1]['key'] == key:
            groups[-1]['end'] = nodes[i + 1]
        else:
            groups.append({'key': key, 'edge': edge, 'start': nodes[i], 'end': nodes[i + 1]})
    steps, openings = [], []
    for index, group in enumerate(groups):
        edge, a, b = (group[k] for k in ('edge', 'start', 'end'))
        if edge.edge_type == 'VERTICAL':
            opening = transitions[edge.vertical_transition_uid]
            label = opening['label'] or opening['uid']
            openings.append(label)
            steps.append(f'Use {label} on {a.passage_code} from Tier {a.tier} to Tier {b.tier}.')
        elif edge.edge_type == 'CROSS_ROUTE':
            label = cross_label(edge.cross_route_uid)
            if edge.cross_route_kind == 'SECTION_GAP':
                steps.append(f'Use the section-gap cross-route ({label}) on Tier {edge.tier} from {a.passage_code} to {b.passage_code}.')
            else:
                steps.append(f'Follow {label} on Tier {edge.tier} from {a.passage_code} to {b.passage_code}.')
        else:
            next_group = groups[index + 1] if index + 1 < len(groups) else None
            if next_group and next_group['edge'].edge_type == 'VERTICAL':
                opening = transitions[next_group['edge'].vertical_transition_uid]
                target = opening['label'] or opening['uid']
            elif next_group and next_group['edge'].edge_type == 'CROSS_ROUTE':
                target = cross_label(next_group['edge'].cross_route_uid)
            else:
                target = destination(b)
            steps.append(f'Follow {edge.passage_code} passage on Tier {edge.tier} to {target}.')
    return steps, openings
