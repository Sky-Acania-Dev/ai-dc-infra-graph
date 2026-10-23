"""Ordinal sectional cells projected into schematic junction curves."""
from copy import deepcopy
from math import hypot
from backend.schemas.routing import SegmentAnnotationInput
from backend.services.routing_section_order import section_order, edge_span, span_key
from backend.services.routing_junction_geometry import DIRECTIONS, resolve_movement
from backend.services.routing_junction_intersections import intersection_statistics


def schematic_movement(uid,tier,a,b,**meta):
    na,nb=DIRECTIONS[a['direction']],DIRECTIONS[b['direction']]
    dot=na[0]*nb[0]+na[1]*nb[1]
    if dot==0:
        corner=[b['point'][0],a['point'][1]] if na[0] else [a['point'][0],b['point'][1]]
        da=hypot(a['point'][0]-corner[0],a['point'][1]-corner[1]);db=hypot(b['point'][0]-corner[0],b['point'][1]-corner[1])
        radius=min(da,db)*.85
        # Different unit footprints at each end use a thin centerline proposal.
        a,b=deepcopy(a),deepcopy(b)
        a['occupation']['occupied_width_in']=b['occupation']['occupied_width_in']=min(a['occupation']['occupied_width_in'],b['occupation']['occupied_width_in'])
        return resolve_movement(uid,tier,a,b,da-radius,db-radius,**meta)
    if dot!=-1:return resolve_movement(uid,tier,a,b,**meta)
    start,end=a['point'],b['point'];t=(-na[0],-na[1]);delta=(end[0]-start[0],end[1]-start[1]);length=delta[0]*t[0]+delta[1]*t[1]
    p=(-t[1],t[0]);offset=delta[0]*p[0]+delta[1]*p[1]
    if abs(offset)<1e-7:return resolve_movement(uid,tier,a,b,**meta)
    if offset<0:p=(-p[0],-p[1])
    distance=abs(offset);radius=min(length,distance)/2
    # S transition: two tangent quarter arcs and optional straight middle run.
    def add(point,along=0,across=0):return [point[0]+t[0]*along+p[0]*across,point[1]+t[1]*along+p[1]*across]
    lead=(length-2*radius)/2
    u=add(start,lead);v=add(u,radius,radius);w=add(v,across=distance-2*radius);z=add(w,radius,radius)
    sweep=int(t[0]*p[1]-t[1]*p[0]>0)
    primitives=[dict(kind='LINE',start=start,end=u),dict(kind='ARC',start=u,end=v,center=add(u,across=radius),radius=radius,sweep=sweep),
        dict(kind='LINE',start=v,end=w),dict(kind='ARC',start=w,end=z,center=add(w,radius),radius=radius,sweep=1-sweep),dict(kind='LINE',start=z,end=end)]
    path=f'M {start[0]} {start[1]} L {u[0]} {u[1]} A {radius} {radius} 0 0 {sweep} {v[0]} {v[1]} L {w[0]} {w[1]} A {radius} {radius} 0 0 {1-sweep} {z[0]} {z[1]} L {end[0]} {end[1]}'
    return dict(uid=uid,tier=tier,from_port=a,to_port=b,geometry_status='RESOLVED',path=path,primitives=primitives,
        checks=['Schematic ordinal projection; physical bundle sizes and minimum bend radius are unverified.'],**meta)


def project_port(port,section,unit,area,inside_box=False):
    result=deepcopy(port);columns,rows=section['grid_columns'],section['grid_rows']
    width=port['width_in'];sw=unit.get('slot_width',1);sh=unit.get('slot_height',1)
    outer=port['occupation']
    box_width=outer.get('occupied_width_in') if inside_box else None
    box_offset=outer.get('offset_across_in') if inside_box else None
    if inside_box and box_width is None and outer.get('position') is not None:
        box_width=(outer.get('slot_width') or 1)*width/(port.get('grid_columns') or 12)
        box_offset=(outer['position']-1)*width/(port.get('grid_columns') or 12)
    box_width=box_width if box_width is not None else width
    offset=(box_offset or 0)+(unit['position']-1)*box_width/columns;bw=sw*box_width/columns
    center=width/2-offset-bw/2
    reference=section['reference']['column_1_direction']
    if reference in ('NORTH','WEST'):center=-center
    direction=port['direction']
    result.update(point=[area['bounds'][direction.lower()+'_in'],center] if direction in ('WEST','EAST') else [center,area['bounds'][direction.lower()+'_in']],
        grid_columns=columns,grid_rows=rows,placement_uid=section.get('bundle_placement_uid'),unit_uid=unit['unit_uid'],section_end=section['section_end'],
        occupation=dict(offset_across_in=offset,offset_up_in=(outer.get('offset_up_in') or 0)+(unit['layer']-1)*(outer.get('occupied_height_in') or rows)/rows if inside_box else unit['layer']-1,occupied_width_in=bw*.55,occupied_height_in=sh*.7,
            layer=unit['layer'],position=unit['position'],slot_width=sw,slot_height=sh),ordinal_projection=True)
    return result


def ordered_saved_junction(session,data,result):
    """Expand configured parent connections using their actual unit memberships."""
    from backend.services.routing_bundle_contents import connection_unit_order
    result=deepcopy(result);movements=[];used=False
    for movement in result['movements']:
        if not movement.get('from_port') or not movement.get('to_port') or movement['from_port']['placement_tier']!=movement['to_port']['placement_tier']:
            movements.append(movement);continue
        order=connection_unit_order(session,data['layout']['uid'],movement['uid'])
        a,b=order['from_section'],order['to_section']
        if not a['defined_end'] and not b['defined_end']:movements.append(movement);continue
        used=True
        for link in order['links']:
            ua=next(u for u in a['units'] if u['unit_uid']==link['from_unit_uid']);ub=next(u for u in b['units'] if u['unit_uid']==link['to_unit_uid'])
            sa={**a,'section_end':a['requested_end']};sb={**b,'section_end':b['requested_end']}
            pa=project_port(movement['from_port'],sa,ua,result['area'],True);pb=project_port(movement['to_port'],sb,ub,result['area'],True)
            uid=movement['uid']+':'+ua['unit_uid']+':'+ub['unit_uid']
            try:
                child=schematic_movement(uid,movement['tier'],pa,pb,label=ua['resolved_label'],group_uid=ua.get('review_group_uid'),
                    cable_count=link['cable_count'],cable_class=movement['cable_class'],parent_connection_uid=movement['uid'],provenance='ORDINAL_PROJECTION')
            except ValueError as exc:child={**movement,'uid':uid,'path':None,'primitives':[],'geometry_status':'UNKNOWN','checks':[str(exc)]}
            movements.append(child)
        if a['status']=='STALE' or b['status']=='STALE' or order['from_unmatched_cable_count'] or order['to_unmatched_cable_count'] or not order['links']:
            movements.append({**movement,'uid':movement['uid']+':unmatched','path':None,'primitives':[],'geometry_status':'UNKNOWN','checks':['Cable membership is missing an ordered continuation at one end.']})
    if used:
        crossing_orders=[]
        for order in result.get('crossing_orders',[]):
            above=[m['uid'] for m in movements if m.get('parent_connection_uid',m['uid'])==order['above_connection_uid']]
            below=[m['uid'] for m in movements if m.get('parent_connection_uid',m['uid'])==order['below_connection_uid']]
            crossing_orders.extend({**order,'above_connection_uid':a,'below_connection_uid':b} for a in above for b in below)
        result.update(movements=movements,crossing_orders=crossing_orders,statistics=intersection_statistics(movements,estimated=True),scope='CONFIGURED_UNITS_SCHEMATIC')
    return result


def ordered_actual_junction(session,data,review,node,graph,result,overrides=()):
    from backend.services.routing_configuration import RoutingConfigurationError
    result=deepcopy(result);sections={};edges={e.id:e for e in graph.edges};used=set()
    for port in result['area']['ports']:
        span=SegmentAnnotationInput(**edge_span(graph,edges[port['edge_id']])).model_dump()
        shape_start=span['start_station_in'] if span['passage_band_uid'] else data['geometry']['bands'][0]['center_in']
        end=('START' if node.station_in==shape_start else 'END') if span['passage_band_uid'] else ('START' if node.passage_band_uid==span['from_passage_band_uid'] else 'END')
        matches=[(index,o) for index,o in enumerate(overrides) if span_key(o.span.model_dump())==span_key(span) and o.section_end==end]
        if len(matches)>1:raise RoutingConfigurationError('Only one draft arrangement may override each connected end.')
        override=matches[0][1] if matches else None
        if matches:used.add(matches[0][0])
        sections[port['direction']]=section_order(session,data,review,span,end,override.contents if override else None)
    if len(used)!=len(overrides):raise RoutingConfigurationError('Every draft override must reference a connected end of this junction.')
    movements=[]
    def parts(section,group_uid):
        result=[]
        for unit in section['units']:
            if unit.get('membership_status')=='STALE':continue
            if unit['kind']=='RACK_PAIR' and unit.get('review_group_uid')==group_uid:result.append((unit,None,unit['cable_count']))
            if unit['kind']=='CABLE_LIST':
                for member in unit.get('group_memberships',[]):
                    if member['group_uid']==group_uid:result.append((unit,set(member['cable_uids']),member['count']))
        return result
    for movement in result['movements']:
        a,b=movement.get('from_port'),movement.get('to_port')
        if not a or not b:movements.append(movement);continue
        sa,sb=sections[a['direction']],sections[b['direction']]
        aa,bb=parts(sa,movement['group_uid']),parts(sb,movement['group_uid'])
        if not aa or not bb:
            movement.update(path=None,primitives=[],geometry_status='UNKNOWN',checks=['This group has no ordered unit at one of the connected ends.'])
            movements.append(movement);continue
        assigned=0
        for ua,idsa,counta in aa:
            for ub,idsb,countb in bb:
                count=len(idsa&idsb) if idsa is not None and idsb is not None else counta if idsa is not None else countb if idsb is not None else movement['cable_count']
                if not count:continue
                assigned+=count
                pa,pb=project_port(a,sa,ua,result['area']),project_port(b,sb,ub,result['area'])
                uid=movement['uid'] if len(aa)==len(bb)==1 else movement['uid']+':'+ua['unit_uid']+':'+ub['unit_uid']
                meta={k:movement[k] for k in ('group_uid','label','cable_class','route_source','provenance') if k in movement}
                meta['cable_count']=count
                try:resolved=schematic_movement(uid,node.tier,pa,pb,**meta)
                except ValueError as exc:resolved={**movement,'uid':uid,'from_port':pa,'to_port':pb,'path':None,'primitives':[],'geometry_status':'UNKNOWN','checks':[str(exc)]}
                movements.append(resolved)
        if assigned<movement['cable_count']:
            movements.append({**movement,'uid':movement['uid']+':unassigned','cable_count':movement['cable_count']-assigned,'path':None,'primitives':[],'geometry_status':'UNKNOWN','checks':['Some actual cables lack an ordered unit at one end.']})
    result.update(movements=movements,sections=sections,statistics=intersection_statistics(movements,estimated=True),
        notes='Actual cable groups and unchanged routes. Saved sectional order or rack-position defaults; all curves are schematic ordinal projections.')
    return result
