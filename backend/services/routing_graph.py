"""Deterministic rectilinear graph. No persisted or implicit tier connectivity."""
from __future__ import annotations

from backend.schemas.routing import GraphEdge, GraphNode, RoutingGraph
from backend.services.routing_geometry import resolve_geometry


def derive_graph(data: dict) -> RoutingGraph:
    geometry = resolve_geometry(data)
    bands = [b for b in geometry['bands'] if b['kind'] == 'PASSAGE']
    passage_tiers = {(p['passage_band_uid'], p['tier']): p for p in data['passage_tiers'] if p['enabled']}
    routes = {r['uid']: r for r in geometry['cross_routes'] if r['effective_enabled']}
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    stations: dict[tuple[str, int], set[int]] = {key: {0, geometry['hall_length_in']} for key in passage_tiers}

    def passage_node(band: dict, station: int, tier: int) -> str:
        uid = f"passage:{band['uid']}:station:{station}:tier:{tier}"
        if uid not in nodes:
            nodes[uid] = GraphNode(id=uid, node_type='PASSAGE_STATION', x_in=station, y_in=band['center_in'],
                                  station_in=station, tier=tier, passage_code=band['code'], passage_band_uid=band['uid'])
        stations[(band['uid'], tier)].add(station)
        return uid

    for rt in sorted(data['cross_route_tiers'], key=lambda r: r['uid']):
        route = routes.get(rt['cross_route_uid'])
        if not rt['enabled'] or route is None:
            continue
        previous = None
        for band in bands:
            # A missing middle passage must not become a NORTH-to-SOUTH shortcut.
            if (band['uid'], rt['tier']) not in passage_tiers:
                previous = None
                continue
            nid = f"cross:{route['uid']}:passage:{band['uid']}:tier:{rt['tier']}"
            nodes[nid] = GraphNode(id=nid, node_type='CROSS_PASSAGE_INTERSECTION', x_in=route['station_in'],
                                  y_in=band['center_in'], station_in=route['station_in'], tier=rt['tier'],
                                  passage_code=band['code'], passage_band_uid=band['uid'], cross_route_uid=route['uid'],
                                  cross_route_kind=route['kind'], cabinet_row_uid=route['cabinet_row_uid'], label=route['label'])
            pid = passage_node(band, route['station_in'], rt['tier'])
            eid = f"junction:{nid}"
            edges[eid] = GraphEdge(id=eid, edge_type='JUNCTION', source_node_id=nid, target_node_id=pid,
                                  tier=rt['tier'], passage_code=band['code'], cross_route_uid=route['uid'],
                                  cross_route_kind=route['kind'], cabinet_row_uid=route['cabinet_row_uid'])
            if previous:
                eid = f"cross:{route['uid']}:tier:{rt['tier']}:{previous['uid']}:{band['uid']}"
                edges[eid] = GraphEdge(id=eid, edge_type='CROSS_ROUTE', source_node_id=previous['node_id'], target_node_id=nid,
                                      tier=rt['tier'], planar_length_in=band['center_in'] - previous['center_in'],
                                      width_in=route['width_in'],
                                      pathway_type=rt['pathway_type'], cross_route_uid=route['uid'], cross_route_kind=route['kind'],
                                      cabinet_row_uid=route['cabinet_row_uid'])
            previous = {**band, 'node_id': nid}

    for vt in sorted(data['vertical_transitions'], key=lambda v: v['uid']):
        if not vt['enabled']:
            continue
        band = next(b for b in bands if b['uid'] == vt['passage_band_uid'])
        if any((band['uid'], t) not in passage_tiers for t in (vt['lower_tier'], vt['upper_tier'])):
            continue
        source = passage_node(band, vt['station_in'], vt['lower_tier'])
        target = passage_node(band, vt['station_in'], vt['upper_tier'])
        for nid in (source, target):
            nodes[nid].vertical_transition_uids.append(vt['uid'])
        eid = f"vertical:{vt['uid']}"
        edges[eid] = GraphEdge(id=eid, edge_type='VERTICAL', source_node_id=source, target_node_id=target,
                              lower_tier=vt['lower_tier'], upper_tier=vt['upper_tier'], passage_code=band['code'],
                              vertical_transition_uid=vt['uid'])

    band_map = {b['uid']: b for b in bands}
    for (band_uid, tier), station_set in sorted(stations.items()):
        band = band_map[band_uid]
        ordered = sorted(station_set)
        ids = [passage_node(band, s, tier) for s in ordered]
        for i in range(len(ids) - 1):
            eid = f"passage:{band_uid}:tier:{tier}:{ordered[i]}:{ordered[i + 1]}"
            edges[eid] = GraphEdge(id=eid, edge_type='PASSAGE', source_node_id=ids[i], target_node_id=ids[i + 1],
                                  tier=tier, planar_length_in=ordered[i + 1] - ordered[i], passage_code=band['code'],
                                  width_in=band['width_in'],
                                  pathway_type=passage_tiers[(band_uid, tier)]['pathway_type'])
    return RoutingGraph(nodes=sorted(nodes.values(), key=lambda n: n.id), edges=sorted(edges.values(), key=lambda e: e.id))
