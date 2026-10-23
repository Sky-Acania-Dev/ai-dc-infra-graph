"""Domain-anchored junction working areas and bundle movement geometry.

Inputs are integer inches. Derived arc coordinates are local inch values, never
frontend pixels; these optional curves never change graph route lengths.
"""
from math import cos, hypot, pi, sin, atan2

from backend.services.routing_connections import connection_points
from backend.services.routing_spans import span_geometry
from backend.services.routing_junction_intersections import intersection_statistics
from backend.services.routing_elevations import tier_elevation

DIRECTIONS = {'WEST': (-1, 0), 'EAST': (1, 0), 'NORTH': (0, -1), 'SOUTH': (0, 1)}
OPPOSITE = {'WEST': 'EAST', 'EAST': 'WEST', 'NORTH': 'SOUTH', 'SOUTH': 'NORTH'}


def area_station(area, geometry):
    return next(r['station_in'] for r in geometry['cross_routes'] if r['uid'] == area['cross_route_uid']) if area.get('cross_route_uid') else area['station_in']


def area_key(area, geometry):
    return area['passage_band_uid'], area_station(area, geometry), area['tier']


def node_area(data, geometry, node, graph):
    east = data['layout'].get('longitudinal_direction') != 'WEST'
    sign = 1 if east else -1
    record = next((a for a in data.get('junction_areas', []) if a['enabled'] and area_key(a, geometry) == (node.passage_band_uid, node.station_in, node.tier)), None)
    adjacent = [e for e in graph.edges if node.id in (e.source_node_id, e.target_node_id) and e.edge_type != 'VERTICAL' and e.tier == node.tier]
    by_id = {n.id: n for n in graph.nodes}
    band = next(b for b in geometry['bands'] if b['uid']==node.passage_band_uid)
    ports = []
    for edge in adjacent:
        other = by_id[edge.target_node_id if edge.source_node_id == node.id else edge.source_node_id]
        delta = (sign*(other.x_in-node.x_in), other.y_in-node.y_in)
        direction = ('EAST' if delta[0] > 0 else 'WEST') if delta[0] else ('SOUTH' if delta[1] > 0 else 'NORTH')
        route=next((r for r in geometry['cross_routes'] if r['uid']==edge.cross_route_uid),None)
        row=next((r for r in geometry['cabinet_rows'] if route and r['uid']==route['cabinet_row_uid']),None)
        inner=('EAST' if sign==1 else 'WEST') if row and row['position_in_pair']=='A' else ('WEST' if sign==1 else 'EAST') if row else None
        if edge.edge_type=='PASSAGE':inner='SOUTH' if band['code']=='NORTH' else 'NORTH' if band['code']=='SOUTH' else None
        ports.append(dict(uid=edge.id, direction=direction, width_in=edge.width_in, label=edge.label or edge.edge_type,inner_direction=inner,
                          edge_id=edge.id, cross_route_uid=edge.cross_route_uid, passage_band_uid=node.passage_band_uid if edge.edge_type == 'PASSAGE' else None))
    bands = {b['uid']: b for b in geometry['bands']}
    wp = bands[node.passage_band_uid]['width_in']
    wc = max((p['width_in'] for p in ports if p['direction'] in ('NORTH', 'SOUTH')), default=wp)
    bounds = dict(west_in=-wc/2, east_in=wc/2, north_in=-wp/2, south_in=wp/2)
    for direction in ('west', 'east', 'north', 'south'):
        extension = record.get(f'{direction}_extension_in', 0) if record else 0
        bounds[f'{direction}_in'] += extension * (-1 if direction in ('west', 'north') else 1)
    core = dict(x_in=-wc/2,y_in=-wp/2,width_in=wc,height_in=wp)
    rectangles=[core]
    display_rectangles=[core]
    for port in ports:
        direction=port['direction'];extra=abs(bounds[direction.lower()+'_in'])-(wc/2 if direction in ('WEST','EAST') else wp/2)
        for length,target in ((extra,rectangles),(extra+10,display_rectangles)):
            if length<=0:continue
            if direction in ('WEST','EAST'):
                target.append(dict(x_in=-wc/2-length if direction=='WEST' else wc/2,y_in=-port['width_in']/2,width_in=length,height_in=port['width_in']))
            else:
                target.append(dict(x_in=-port['width_in']/2,y_in=-wp/2-length if direction=='NORTH' else wp/2,width_in=port['width_in'],height_in=length))
    # Ports are distinct domain spans, even when they share a physical direction.
    tier_record=next((t for t in data['passage_tiers'] if t['passage_band_uid']==node.passage_band_uid and t['tier']==node.tier and t['enabled']),None)
    if tier_record is None:
        tier_record=next((t for t in data['cross_route_tiers'] if t['cross_route_uid'] in node.cross_route_uids and t['tier']==node.tier and t['enabled']),None)
    return dict(uid=record['uid'] if record else f'junction:{node.id}', node_id=node.id, tier=node.tier,
                label=(record or {}).get('label') or f'{node.passage_code} · {node.label or "station"}',
                passage_band_uid=node.passage_band_uid, passage_code=node.passage_code, station_in=node.station_in,
                x_in=node.x_in, y_in=node.y_in, bounds=bounds, passage_width_in=wp, cross_route_width_in=wc,
                usable_height_in=(record or {}).get('usable_height_in'), provenance=(record or {}).get('provenance', 'SCHEMATIC'),
                configured=record is not None, ports=sorted(ports, key=lambda p: (p['direction'], p['uid'])), notes=(record or {}).get('notes'),elevation_in=tier_elevation(data['layout'],tier_record) if tier_record else None,
                tray_rectangles=rectangles,display_tray_rectangles=display_rectangles)


def placement_port(data, geometry, area, placement, span, end):
    shape = span_geometry(geometry, span)
    point, other = shape[end.lower()], shape['end' if end == 'START' else 'start']
    sign = -1 if data['layout'].get('longitudinal_direction') == 'WEST' else 1
    delta = (sign*(other[0]-point[0]), other[1]-point[1])
    direction = ('EAST' if delta[0] > 0 else 'WEST') if delta[0] else ('SOUTH' if delta[1] > 0 else 'NORTH')
    inner = span.get('section_inner_direction')
    if span['passage_band_uid']:
        code = area['passage_code']
        inner = inner or ('SOUTH' if code == 'NORTH' else 'NORTH' if code == 'SOUTH' else None)
        start_direction = inner or 'NORTH'
    else:
        route = next(r for r in geometry['cross_routes'] if r['uid'] == span['cross_route_uid'])
        row = next((r for r in geometry['cabinet_rows'] if r['uid'] == route['cabinet_row_uid']), None)
        inner = inner or (('EAST' if sign == 1 else 'WEST') if row and row['position_in_pair'] == 'A' else ('WEST' if sign == 1 else 'EAST') if row else None)
        start_direction = inner or 'WEST'
    width = placement.get('occupied_width_in')
    across = None if width is None else shape['width_in']/2-placement['offset_across_in']-width/2
    if across is not None and start_direction in ('NORTH', 'WEST'):
        across = -across
    bounds = area['bounds']
    port_point = None if across is None else ([bounds[direction.lower()+'_in'], across] if direction in ('WEST', 'EAST') else [across, bounds[direction.lower()+'_in']])
    return dict(placement_uid=placement['uid'], placement_tier=placement['tier'], end=end, direction=direction, point=port_point,
                width_in=shape['width_in'], inner_direction=inner, occupation={k: placement.get(k) for k in
                ('offset_across_in', 'offset_up_in', 'occupied_width_in', 'occupied_height_in', 'layer', 'position', 'slot_width', 'slot_height')},
                grid_columns=span.get('grid_columns',12),grid_rows=span.get('grid_rows',8),segment_annotation_uid=span['uid'], label=span.get('section_reference') or direction)


def resolve_movement(uid, tier, a, b, from_inset=None, to_inset=None, **metadata):
    result = dict(uid=uid, tier=tier, from_port=a, to_port=b, geometry_status='UNKNOWN', primitives=[], path=None,
                  from_turn_start_in=from_inset, to_turn_start_in=to_inset, checks=[], **metadata)
    na, nb = DIRECTIONS[a['direction']], DIRECTIONS[b['direction']]
    dot = na[0]*nb[0]+na[1]*nb[1]
    if dot == -1 and (from_inset is not None or to_inset is not None):
        raise ValueError('Straight movements must leave turn-start distances unset.')
    if a['point'] is None or b['point'] is None:
        result['checks'].append('Physical occupation rectangles are not configured at both endpoints.')
        return result
    if a['occupation']['occupied_width_in'] != b['occupation']['occupied_width_in']:
        result['checks'].append('Changing bundle widths needs an explicit transition; no constant-width curve assumed.')
        return result
    start, end = a['point'], b['point']
    if dot == -1:
        axis = 1 if na[0] else 0
        if abs(start[axis]-end[axis]) > 1e-7:
            result['checks'].append('Offset straight runs need an explicitly designed S transition.')
            return result
        primitives = [dict(kind='LINE', start=start, end=end)]
        path = f'M {start[0]} {start[1]} L {end[0]} {end[1]}'
        result['centerline_radius_in'] = None
    elif dot == 0:
        if from_inset is None or to_inset is None:
            result['checks'].append('Set both turn-start distances for this 90-degree movement.')
            return result
        corner = [end[0], start[1]] if na[0] else [start[0], end[1]]
        r = hypot(start[0]-corner[0], start[1]-corner[1])-from_inset
        rb = hypot(end[0]-corner[0], end[1]-corner[1])-to_inset
        if r <= 0 or abs(r-rb) > 1e-7:
            raise ValueError('Turn-start positions must give the same positive circular radius at both ends.')
        if r <= a['occupation']['occupied_width_in']/2:
            raise ValueError('The bundle inner envelope radius must remain positive.')
        p = [corner[0]+na[0]*r, corner[1]+na[1]*r]
        q = [corner[0]+nb[0]*r, corner[1]+nb[1]*r]
        center = [p[0]+nb[0]*r, p[1]+nb[1]*r]
        sweep = 1 if (-na[0])*nb[1]-(-na[1])*nb[0] > 0 else 0
        arc = dict(kind='ARC', start=p, end=q, center=center, radius=r, sweep=sweep)
        primitives = [dict(kind='LINE', start=start, end=p), arc, dict(kind='LINE', start=q, end=end)]
        path = f'M {start[0]} {start[1]} L {p[0]} {p[1]} A {r} {r} 0 0 {sweep} {q[0]} {q[1]} L {end[0]} {end[1]}'
        result.update(centerline_radius_in=r, inner_envelope_radius_in=r-a['occupation']['occupied_width_in']/2)
    else:
        result['checks'].append('U-turn geometry is not configured.')
        return result
    result.update(geometry_status='RESOLVED', primitives=primitives, path=path)
    start_context=[start[0]+na[0]*10,start[1]+na[1]*10]
    end_context=[end[0]+nb[0]*10,end[1]+nb[1]*10]
    result['display_path']=f'M {start_context[0]} {start_context[1]} L {start[0]} {start[1]} '+path.split(' ',3)[3]+f' L {end_context[0]} {end_context[1]}'
    result['checks'].append('Cable-specific minimum bend radius and supports are not verified.')
    if a['occupation'].get('offset_up_in') != b['occupation'].get('offset_up_in'):
        result['checks'].append('Different endpoint heights: local vertical travel remains unchecked.')
    return result


def check_envelope(area,movement):
    if movement['geometry_status']!='RESOLVED':return
    half=movement['from_port']['occupation']['occupied_width_in']/2
    def inside(point):
        return any(r['x_in']-1e-7<=point[0]<=r['x_in']+r['width_in']+1e-7 and r['y_in']-1e-7<=point[1]<=r['y_in']+r['height_in']+1e-7 for r in area['tray_rectangles'])
    for primitive in movement['primitives']:
        if primitive['kind']=='ARC':
            center=primitive['center'];angle=atan2(primitive['start'][1]-center[1],primitive['start'][0]-center[0])
            points=[(center[0]+radius*cos(angle+(1 if primitive['sweep'] else -1)*pi/2*i/64),center[1]+radius*sin(angle+(1 if primitive['sweep'] else -1)*pi/2*i/64)) for radius in (primitive['radius']-half,primitive['radius']+half) for i in range(65)]
        else:
            a,b=primitive['start'],primitive['end'];length=hypot(b[0]-a[0],b[1]-a[1])
            normal=((b[1]-a[1])/length*half,-(b[0]-a[0])/length*half) if length else (0,0)
            points=[(p[0]+s*normal[0],p[1]+s*normal[1]) for p in (a,b) for s in (-1,1)]
        if not all(inside(p) for p in points):
            raise ValueError('Bundle turn envelope extends outside the square tray working area.')
    for port in (movement['from_port'],movement['to_port']):
        occupation=port['occupation']
        if area['usable_height_in'] is not None and occupation['offset_up_in']+occupation['occupied_height_in']>area['usable_height_in']:
            raise ValueError('Bundle occupation exceeds the configured junction usable height.')


def saved_junction(data, geometry, node, graph):
    area = node_area(data, geometry, node, graph)
    placements = {p['uid']: p for p in data.get('bundle_placements', [])}
    parents = {p['uid']: p for p in data.get('segment_annotations', [])}
    movements = []
    for c in data.get('bundle_connections', []):
        if not c['enabled']:
            continue
        endpoints = connection_points(data, geometry, c)
        if node.id not in endpoints['node_ids']:
            continue
        pa, pb = placements[c['from_placement_uid']], placements[c['to_placement_uid']]
        a, b = (placement_port(data, geometry, area, p, parents[p['segment_annotation_uid']], c[side+'_end']) for side, p in (('from', pa), ('to', pb)))
        if pa['tier'] != pb['tier']:
            movement = dict(uid=c['uid'], tier=node.tier, from_port=a, to_port=b, geometry_status='UNKNOWN', primitives=[], path=None,
                            checks=['Explicit tier opening; a planar turn does not describe vertical travel.'], label=pa.get('resolved_label') or pa.get('label') or pa['source_uid'], cable_class=pa['cable_class'], source_kind=pa['source_kind'], source_uid=pa['source_uid'])
        else:
            movement = resolve_movement(c['uid'], node.tier, a, b, c.get('from_turn_start_in'), c.get('to_turn_start_in'),
                label=pa.get('resolved_label') or pa.get('label') or pa['source_uid'], cable_class=pa['cable_class'], source_kind=pa['source_kind'], source_uid=pa['source_uid'], provenance='MANUAL')
            check_envelope(area,movement)
        movements.append(movement)
    stats = intersection_statistics(movements)
    return dict(area=area, movements=movements, statistics=stats, scope='CONFIGURED_MOVEMENTS',
                crossing_orders=[c for c in data.get('junction_crossings', []) if c['enabled'] and {c['above_connection_uid'], c['below_connection_uid']} <= {m['uid'] for m in movements}])


def validate_junctions(data, geometry, graph):
    seen = set()
    for area in data.get('junction_areas', []):
        if not area['enabled']:
            continue
        key = area_key(area, geometry)
        if key[1]>geometry['hall_length_in']:
            raise ValueError('Junction station is outside the hall.')
        if key in seen:
            raise ValueError('Only one enabled working area may occupy a physical junction and tier.')
        seen.add(key)
        node = next((n for n in graph.nodes if (n.passage_band_uid, n.station_in, n.tier) == key), None)
        if node is None:
            raise ValueError('A junction working area requires a configured passage/cross-route node at this tier.')
        resolved = node_area(data, geometry, node, graph)
        for direction in DIRECTIONS:
            if area[direction.lower()+'_extension_in'] and not any(p['direction'] == direction for p in resolved['ports']):
                raise ValueError('A working-area extension requires an existing tray arm in that direction.')
    connections = {c['uid']: c for c in data.get('bundle_connections', [])}
    for c in connections.values():
        if not c['enabled']:
            continue
        endpoints = connection_points(data, geometry, c)
        if c.get('junction_area_uid'):
            area = next(a for a in data['junction_areas'] if a['uid'] == c['junction_area_uid'])
            key = area_key(area, geometry)
            if not area['enabled'] or not any((e['passage_band_uid'], e['x_in'], e['tier']) == key for e in endpoints['endpoints']):
                raise ValueError('Connection and working area must share the same physical junction/tier.')
        # Resolving validates explicit radii while leaving legacy unknown geometry usable.
        for nid in set(endpoints['node_ids']):
            node = next((n for n in graph.nodes if n.id == nid), None)
            if node:
                saved_junction(data, geometry, node, graph)
    orders = {}
    placements={p['uid']:p for p in data['bundle_placements']}
    for order in data.get('junction_crossings', []):
        if not order['enabled']:
            continue
        a, b = connections[order['above_connection_uid']], connections[order['below_connection_uid']]
        aa, bb = connection_points(data, geometry, a), connection_points(data, geometry, b)
        if not a['enabled'] or not b['enabled'] or len(set(aa['node_ids']+bb['node_ids'])) != 1:
            raise ValueError('Crossing order requires two enabled same-tier movements at the same junction.')
        upper=[placements[a[side+'_placement_uid']] for side in ('from','to')]
        lower=[placements[b[side+'_placement_uid']] for side in ('from','to')]
        if all(p.get('offset_up_in') is not None for p in upper+lower):
            required=max(p['offset_up_in']+p['occupied_height_in'] for p in lower)+(order.get('clearance_in') or 0)
            if min(p['offset_up_in'] for p in upper)<required:
                raise ValueError('Crossing order/clearance contradicts the saved endpoint heights; no unmodeled crossover hump is assumed.')
        orders.setdefault(a['uid'], set()).add(b['uid'])
    def visit(uid, path):
        if uid in path:
            raise ValueError('Junction crossing order cannot contain an above/below cycle.')
        for other in orders.get(uid, ()):
            visit(other, path | {uid})
    for uid in orders:
        visit(uid, set())


def preserve_turn_positions(before,after,area_uid):
    """Changing a port boundary must not silently move a saved tangent point."""
    from backend.services.routing_geometry import resolve_geometry
    from backend.services.routing_graph import derive_graph
    geometry=resolve_geometry(after)
    area=next((a for a in after['junction_areas'] if a['uid']==area_uid),None) or next(a for a in before['junction_areas'] if a['uid']==area_uid)
    key=area_key(area,geometry)
    new_graph=derive_graph(after,junction_statistics=False)
    new_node=next((n for n in new_graph.nodes if (n.passage_band_uid,n.station_in,n.tier)==key),None)
    old_geometry=resolve_geometry(before)
    old_graph=derive_graph(before,junction_statistics=False)
    old_node=next((n for n in old_graph.nodes if (n.passage_band_uid,n.station_in,n.tier)==key),None)
    if new_node is None or old_node is None:return {}
    old_area=node_area(before,old_geometry,old_node,old_graph)
    new_area=node_area(after,geometry,new_node,new_graph)
    placements={p['uid']:p for p in before['bundle_placements']}
    spans={p['uid']:p for p in before['segment_annotations']}
    changes={}
    for connection in before['bundle_connections']:
        if connection.get('from_turn_start_in') is None:continue
        if old_node.id not in connection_points(before,old_geometry,connection)['node_ids']:continue
        starts=[]
        for side in ('from','to'):
            placement=placements[connection[side+'_placement_uid']]
            port=placement_port(before,old_geometry,old_area,placement,spans[placement['segment_annotation_uid']],connection[side+'_end'])
            direction=port['direction'].lower()+'_in'
            delta=abs(new_area['bounds'][direction])-abs(old_area['bounds'][direction])
            value=connection[side+'_turn_start_in']+delta
            if value<0:raise ValueError('The new working area would exclude a saved turn-start point. Extend the area or explicitly revise the turn first.')
            starts.append(int(value))
        changes[connection['uid']]=starts
    return changes
