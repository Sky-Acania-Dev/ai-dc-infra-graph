"""Deterministic rectilinear graph. No persisted or implicit tier connectivity."""
from __future__ import annotations

from backend.schemas.routing import GraphEdge, GraphNode, RoutingGraph
from backend.services.routing_geometry import resolve_geometry, passage_span_label
from backend.services.routing_elevations import tier_elevation


def derive_graph(data: dict, *, junction_statistics=True) -> RoutingGraph:
    geometry = resolve_geometry(data)
    bands = [b for b in geometry['bands'] if b['kind'] == 'PASSAGE']
    passage_tiers = {(p['passage_band_uid'], p['tier']): p for p in data['passage_tiers'] if p['enabled']}
    routes = {r['uid']: r for r in geometry['cross_routes'] if r['effective_enabled']}
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    stations: dict[tuple[str, int], set[int]] = {key: {0, geometry['hall_length_in']} for key in passage_tiers}
    row_openings = {(v.get('cross_route_uid'), v['passage_band_uid'], v['upper_tier']): v
                    for v in data['vertical_transitions'] if v['enabled'] and v.get('cross_route_uid')
                    and (v['passage_band_uid'], v['lower_tier']) in passage_tiers}
    # Domain interval endpoints split the generated passage without storing edges.
    for item in data.get('segment_annotations', []):
        if item['passage_band_uid']:
            for (band_uid, tier), station_set in stations.items():
                if band_uid == item['passage_band_uid'] and item['tier'] in (None, tier):
                    station_set.update((item['start_station_in'], item['end_station_in']))
    for item in data.get('junction_areas', []):
        if item['enabled'] and item.get('station_in') is not None and (item['passage_band_uid'], item['tier']) in stations:
            stations[(item['passage_band_uid'], item['tier'])].add(item['station_in'])

    def passage_node(band: dict, station: int, tier: int, landing: str | None = None) -> str:
        uid = f"cross:{landing}:passage:{band['uid']}:tier:{tier}" if landing else f"passage:{band['uid']}:station:{station}:tier:{tier}"
        if uid not in nodes:
            nodes[uid] = GraphNode(id=uid, node_type='PASSAGE_STATION', x_in=station, y_in=band['center_in'],
                                  station_in=station, tier=tier, passage_code=band['code'], passage_band_uid=band['uid'],
                                  roles=['ENDPOINT'] if station in (0, geometry['hall_length_in']) else [])
        if not landing:
            stations[(band['uid'], tier)].add(station)
        return uid

    for rt in sorted(data['cross_route_tiers'], key=lambda r: r['uid']):
        route = routes.get(rt['cross_route_uid'])
        if not rt['enabled'] or route is None:
            continue
        previous = None
        for band in bands:
            if band['uid'] not in route['passage_band_uids']:
                previous = None
                continue
            # A missing middle passage must not become a NORTH-to-SOUTH shortcut.
            landing = (band['uid'], rt['tier']) not in passage_tiers
            if landing and (route['uid'], band['uid'], rt['tier']) not in row_openings:
                previous = None
                continue
            nid = passage_node(band, route['station_in'], rt['tier'], route['uid'] if landing else None)
            node = nodes[nid]
            node.node_type = 'JUNCTION'
            node.roles.append('JUNCTION')
            node.cross_route_uids.append(route['uid'])
            if route['cabinet_row_uid']:
                node.cabinet_row_uids.append(route['cabinet_row_uid'])
            # Singular fields remain the first deterministic association for existing clients.
            if node.cross_route_uid is None:
                node.cross_route_uid, node.cross_route_kind = route['uid'], route['kind']
                node.cabinet_row_uid, node.label = route['cabinet_row_uid'], route['display_label']
            if previous:
                eid = f"cross:{route['uid']}:tier:{rt['tier']}:{previous['uid']}:{band['uid']}"
                edges[eid] = GraphEdge(id=eid, edge_type='CROSS_ROUTE', source_node_id=previous['node_id'], target_node_id=nid,
                                      tier=rt['tier'], planar_length_in=band['center_in'] - previous['center_in'],
                                      width_in=route['width_in'],
                                      elevation_in=tier_elevation(data['layout'], rt), label=route['display_label'],
                                      pathway_type=rt['pathway_type'], cross_route_uid=route['uid'], cross_route_kind=route['kind'],
                                      cabinet_row_uid=route['cabinet_row_uid'])
            previous = {**band, 'node_id': nid}

    for vt in sorted(data['vertical_transitions'], key=lambda v: v['uid']):
        if not vt['enabled']:
            continue
        band = next(b for b in bands if b['uid'] == vt['passage_band_uid'])
        route = routes.get(vt.get('cross_route_uid'))
        if vt.get('cross_route_uid'):
            target = f"cross:{vt['cross_route_uid']}:passage:{band['uid']}:tier:{vt['upper_tier']}"
            # When both tiers are passages the upper intersection already has its passage ID.
            if (band['uid'], vt['upper_tier']) in passage_tiers and route:
                target = f"passage:{band['uid']}:station:{route['station_in']}:tier:{vt['upper_tier']}"
            if not route or target not in nodes or (band['uid'], vt['lower_tier']) not in passage_tiers:
                continue
            source = passage_node(band, route['station_in'], vt['lower_tier'])
        else:
            if any((band['uid'], t) not in passage_tiers for t in (vt['lower_tier'], vt['upper_tier'])):
                continue
            source = passage_node(band, vt['station_in'], vt['lower_tier'])
            target = passage_node(band, vt['station_in'], vt['upper_tier'])
        for nid in (source, target):
            nodes[nid].vertical_transition_uids.append(vt['uid'])
            nodes[nid].roles.append('TIER_OPENING')
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
                                  elevation_in=tier_elevation(data['layout'], passage_tiers[(band_uid, tier)]),
                                  label=passage_span_label(geometry, band_uid, ordered[i], ordered[i + 1]),
                                  pathway_type=passage_tiers[(band_uid, tier)]['pathway_type'])
    from backend.services.routing_annotations import apply_annotations
    apply_annotations(data, geometry, nodes, edges)
    from backend.services.routing_connections import connection_points
    for connection in data.get('bundle_connections', []):
        if connection['enabled']:
            for nid in connection_points(data, geometry, connection)['node_ids']:
                if nid in nodes:
                    nodes[nid].bundle_connection_uids.append(connection['uid'])
    for node in nodes.values():
        node.roles = sorted(set(node.roles)) or ['STATION']
        node.cross_route_uids = sorted(set(node.cross_route_uids))
        node.cabinet_row_uids = sorted(set(node.cabinet_row_uids))
        node.bundle_connection_uids.sort()
    result = RoutingGraph(nodes=sorted(nodes.values(), key=lambda n: n.id), edges=sorted(edges.values(), key=lambda e: e.id))
    if junction_statistics:
        from backend.services.routing_junction_geometry import saved_junction, area_key
        configured = {area_key(a, geometry) for a in data.get('junction_areas', []) if a['enabled']}
        for node in result.nodes:
            if node.bundle_connection_uids or (node.passage_band_uid, node.station_in, node.tier) in configured:
                stats = saved_junction(data, geometry, node, result)['statistics']
                for field in ('cable_intersection_point_count', 'bundle_pair_crossing_count', 'intersection_count_status'):
                    setattr(node, field, stats[field])
    return result
