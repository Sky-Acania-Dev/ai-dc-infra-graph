"""Read-only junction display proposals referencing actual routed cable groups.

Route legs (including every saved manual route) are read verbatim. Only local
occupation/turn suggestions are schematic; nothing is persisted by this module.
"""
from copy import deepcopy

from backend.services.routing_junction_geometry import DIRECTIONS, resolve_movement
from backend.services.routing_junction_intersections import intersection_statistics


def at_node(point, node):
    return (point['x_in'], point['y_in'], point['tier']) == (node.x_in, node.y_in, node.tier)


def actual_junction(result, review, node, *, longitudinal_direction='EAST'):
    result = deepcopy(result)
    area, movements = result['area'], []
    sign = -1 if longitudinal_direction == 'WEST' else 1
    for group in sorted(review['groups'], key=lambda g: g['uid']):
        route = group.get('route')
        if not route:
            continue
        if 'edge_indices' in route:
            points = [route['start']]
            for index in route['edge_indices']:
                segment = review['planning_segments'][index]
                other = segment['target'] if segment['source']['node_id'] == points[-1]['node_id'] else segment['source']
                points.append(other)
        else:
            points = route['points']
        # Planning nodes already include passage intersections. Ignore takeoff
        # endpoints and repeated zero-length points without inventing drops.
        for index in range(1, len(points)-1):
            if not at_node(points[index], node):
                continue
            previous, following = points[index-1], points[index+1]
            if previous['tier'] != node.tier or following['tier'] != node.tier:
                movements.append(dict(uid=group['uid']+f':{index}', group_uid=group['uid'], tier=node.tier,
                    label=f"{group['source_cabinet_id']} ↔ {group['destination_cabinet_id']} · {group['cable_type']} × {group['count']}",
                    cable_class=group['cable_class'], cable_count=group['count'], route_source=group['route_source'],
                    geometry_status='UNKNOWN', path=None, primitives=[], from_port=None, to_port=None,
                    checks=['Tier-opening traversal has no modeled vertical cable curve.'], provenance='SCHEMATIC'))
                continue
            def direction(point):
                dx, dy = sign*(point['x_in']-node.x_in), point['y_in']-node.y_in
                return ('EAST' if dx > 0 else 'WEST') if dx else ('SOUTH' if dy > 0 else 'NORTH') if dy else None
            incoming, outgoing = direction(previous), direction(following)
            if not incoming or not outgoing:
                continue
            ordinal = len(movements)
            height = 0 if group['cable_class'] in ('CAT6', 'CROSS_SECTION_CAT6') else 4 if group['cable_class'] in ('LC', 'CROSS_SECTION_LC') else 2
            def port(code):
                width = area['passage_width_in'] if code in ('WEST', 'EAST') else area['cross_route_width_in']
                lanes = max(1, min(10, (width-4)//2))
                offset = 2 + 2*(ordinal % lanes)
                # Both endpoints share a schematic lane. This is NOT measured packing.
                center = width/2-offset-1
                context=next((p for p in area.get('ports',[]) if p['direction']==code),None)
                inner=context.get('inner_direction') if context else 'SOUTH' if code in ('WEST','EAST') and area['passage_code']=='NORTH' else 'NORTH' if code in ('WEST','EAST') and area['passage_code']=='SOUTH' else 'EAST' if code in ('NORTH','SOUTH') else None
                if inner in ('NORTH','WEST') or inner is None:
                    center = -center
                return dict(direction=code, width_in=width, inner_direction=inner, placement_uid=None,placement_tier=node.tier,grid_columns=12,grid_rows=8,
                    point=[area['bounds'][code.lower()+'_in'], center] if code in ('WEST','EAST') else [center,area['bounds'][code.lower()+'_in']],
                    occupation=dict(offset_across_in=offset,offset_up_in=height,occupied_width_in=2,occupied_height_in=1,
                                    layer=height+1,position=ordinal%12+1,slot_width=1,slot_height=1), label=code)
            a, b = port(incoming), port(outgoing)
            na, nb = DIRECTIONS[incoming], DIRECTIONS[outgoing]
            turn_a = turn_b = None
            if na[0]*nb[0]+na[1]*nb[1] == 0:
                corner = [b['point'][0],a['point'][1]] if na[0] else [a['point'][0],b['point'][1]]
                da = abs(a['point'][0]-corner[0])+abs(a['point'][1]-corner[1])
                db = abs(b['point'][0]-corner[0])+abs(b['point'][1]-corner[1])
                radius = min(da,db)-1
                turn_a, turn_b = int(da-radius), int(db-radius)
            try:
                movement = resolve_movement(group['uid']+f':{index}',node.tier,a,b,turn_a,turn_b,
                    group_uid=group['uid'],label=f"{group['source_cabinet_id']} ↔ {group['destination_cabinet_id']} · {group['cable_type']} × {group['count']}",
                    cable_class=group['cable_class'],cable_count=group['count'],route_source=group['route_source'],provenance='SCHEMATIC')
            except ValueError as exc:
                movement = dict(uid=group['uid']+f':{index}',tier=node.tier,group_uid=group['uid'],label=str(exc),cable_class=group['cable_class'],cable_count=group['count'],route_source=group['route_source'],from_port=a,to_port=b,geometry_status='UNKNOWN',path=None,primitives=[],checks=[str(exc)],provenance='SCHEMATIC')
            movements.append(movement)
    result.update(movements=movements,statistics=intersection_statistics(movements,estimated=True),scope='ACTUAL_GROUPS_SCHEMATIC',
        topology_revision=review['topology_revision'],notes='Actual cable group memberships and route legs; display-only 2 × 1 in occupation suggestions. No saved route or placement is modified.')
    return result
