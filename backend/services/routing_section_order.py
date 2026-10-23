"""Shared actual-group sectional arrangements; reads and drafts never save routes.

Ordinal cells project into a schematic window, not measured cable dimensions.
"""
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select
from backend.persistence.postgresql import routing_models as db
from backend.schemas.routing import BundlePlacementInput
from backend.schemas.routing_bundle_contents import BundleContentsInput
from backend.services import routing_configuration as config
from backend.services.routing_bundle_contents import get_contents, write_contents
from backend.services.routing_content_units import unit_identity
from backend.services.routing_spans import span_geometry
from backend.services.routing_manual_routes import RoutingRouteConflict

SPAN_KEYS = ('passage_band_uid', 'cross_route_uid', 'start_station_in', 'end_station_in', 'from_passage_band_uid', 'to_passage_band_uid')


def span_key(span):
    return [span.get(k) for k in SPAN_KEYS] + [span.get('tier')]


def container_uid(layout_uid, span):
    return 'section-order:' + str(uuid5(NAMESPACE_URL, layout_uid + json.dumps(span_key(span))))


def covering_annotation(data,span):
    for item in data['segment_annotations']:
        if item['tier'] not in (None,span['tier']):continue
        if span['passage_band_uid']:
            matches=item['passage_band_uid']==span['passage_band_uid'] and item['start_station_in']<=span['start_station_in'] and item['end_station_in']>=span['end_station_in']
        else:
            matches=item['cross_route_uid']==span['cross_route_uid'] and item['from_passage_band_uid']==span['from_passage_band_uid'] and item['to_passage_band_uid']==span['to_passage_band_uid']
        if matches:return item
    return None


def edge_span(graph, edge):
    nodes = {n.id: n for n in graph.nodes}
    a, b = nodes[edge.source_node_id], nodes[edge.target_node_id]
    return dict(passage_band_uid=a.passage_band_uid if edge.edge_type == 'PASSAGE' else None,
        cross_route_uid=edge.cross_route_uid if edge.edge_type == 'CROSS_ROUTE' else None,
        start_station_in=min(a.x_in,b.x_in) if edge.edge_type == 'PASSAGE' else None,
        end_station_in=max(a.x_in,b.x_in) if edge.edge_type == 'PASSAGE' else None,
        from_passage_band_uid=a.passage_band_uid if a.y_in < b.y_in else b.passage_band_uid if edge.edge_type == 'CROSS_ROUTE' else None,
        to_passage_band_uid=b.passage_band_uid if a.y_in < b.y_in else a.passage_band_uid if edge.edge_type == 'CROSS_ROUTE' else None,
        tier=edge.tier)


def rack_positions(data):
    from backend.services.routing_planning import cabinet_review_attachments
    rows={r['uid']:r for r in data['geometry']['cabinet_rows']}
    # Reuse the authoritative serpentine mapping; missing racks leave holes.
    mapped=cabinet_review_attachments(data,[c['cabinet_uid'] for c in data.get('cabinets',[])])
    return {uid:(a['row_position'],rows[a['row_uid']]['display_name']) for uid,a in mapped.items()}


def group_positions(data, group, positions=None):
    result = {};positions=positions if positions is not None else rack_positions(data)
    for end in ('source','destination'):
        result[end+'_rack_position'],result[end+'_row']=positions.get(group[end+'_cabinet_uid'],(None,None))
    return result


def span_groups(data, review, span):
    shape = span_geometry(data['geometry'],span)
    a,b = shape['start'],shape['end']
    def matches(edge):
        p,q = edge['source'],edge['target']
        if edge['tier'] != span['tier'] or edge['edge_type']=='VERTICAL':return False
        if span['passage_band_uid']:
            return p['y_in']==q['y_in']==a[1] and max(min(p['x_in'],q['x_in']),a[0]) < min(max(p['x_in'],q['x_in']),b[0])
        return p['x_in']==q['x_in']==a[0] and max(min(p['y_in'],q['y_in']),min(a[1],b[1])) < min(max(p['y_in'],q['y_in']),max(a[1],b[1]))
    groups = set()
    for load in review['loads']:
        edge = review['planning_segments'][load['edge_index']] if 'edge_index' in load else load
        if matches(edge):
            groups.update(review['groups'][i]['uid'] for i in load['group_indices']) if 'group_indices' in load else groups.update(load['group_uids'])
    return [g for g in review['groups'] if g['uid'] in groups]


def default_units(data, groups):
    units=[];positions=rack_positions(data)
    for group in groups:
        value=dict(kind='RACK_PAIR',source_cabinet_uid=group['source_cabinet_uid'],destination_cabinet_uid=group['destination_cabinet_uid'],
            cable_type=group['cable_type'],label=None,slot_width=1,slot_height=1,**group_positions(data,group,positions))
        value.update(unit_uid=unit_identity(data['layout']['uid'],value),review_group_uid=group['uid'],cable_count=group['count'],
            cable_class=group['cable_class'],resolved_label=f"{group['source_cabinet_id']} ↔ {group['destination_cabinet_id']} · {group['cable_type']} × {group['count']}",membership_status='AVAILABLE')
        units.append(value)
    units.sort(key=lambda u:(u['source_rack_position'] or 1000,u['destination_rack_position'] or 1000,u['unit_uid']))
    columns=max(12,min(64,(len(units)+7)//8))
    rows=max(8,(len(units)+columns-1)//columns)
    if rows>64:raise config.RoutingConfigurationError('This section exceeds the 64 × 64 editor limit. Split the outer bundle first.')
    for index,unit in enumerate(units):unit.update(layer=index//columns+1,position=index%columns+1)
    return columns,rows,units


def section_order(session, data, review, span, section_end='SPAN', draft=None):
    if span.get('tier') is None:raise config.RoutingConfigurationError('Choose an explicit tier for a sectional arrangement.')
    # The span must be physically valid, enabled and in this layout.
    from backend.services.routing_annotations import validate_annotations
    try:validate_annotations({**data,'segment_annotations':[span]},data['geometry'])
    except (ValueError,KeyError,StopIteration) as exc:raise config.RoutingConfigurationError('Section must reference a valid enabled pathway span.') from exc
    owner=span['passage_band_uid'] or span['cross_route_uid']
    tiers=data['passage_tiers'] if span['passage_band_uid'] else data['cross_route_tiers']
    if not any((t.get('passage_band_uid') or t.get('cross_route_uid'))==owner and t['tier']==span['tier'] and t['enabled'] for t in tiers):
        raise config.RoutingConfigurationError('This pathway tier is not enabled.')
    parent=covering_annotation(data,span)
    if parent and not parent['usable']:raise config.RoutingConfigurationError('This segment is marked unusable.')
    if span['cross_route_uid'] and not next(r['effective_enabled'] for r in data['geometry']['cross_routes'] if r['uid']==span['cross_route_uid']):
        raise config.RoutingConfigurationError('This cabinet/section-gap route is disabled.')
    groups=span_groups(data,review,span)
    columns,rows,defaults=default_units(data,groups)
    uid=container_uid(data['layout']['uid'],span)
    placement=session.get(db.RoutingBundlePlacement,uid)
    saved=get_contents(session,data['layout']['uid'],uid,section_end) if placement else None
    version=sha256(json.dumps([span_key(span),section_end,data['layout']['longitudinal_direction'],parent,review['topology_revision'],[(g['uid'],g['count']) for g in groups],saved['version'] if saved else None],sort_keys=True,default=str).encode()).hexdigest()
    current=saved if saved and saved['defined_end'] else dict(grid_columns=columns,grid_rows=rows,units=defaults,status='DEFAULT',defined_end=None,inherited=False,errors=[])
    if draft:
        if draft.expected_version!=version:raise RoutingRouteConflict('The section or routed inventory changed. Reload its ordering before saving.')
        # Resolve actual selectors through the same membership validation as saved contents.
        from backend.services.routing_content_units import resolve_unit
        layout=config.get_layout(session,data['layout']['uid'])
        allowed={g['uid'] for g in groups};units=[];seen=set();identities=set()
        explicit=any(u.kind=='CABLE_LIST' for u in draft.units)
        for unit in draft.units:
            if not explicit:
                group=next((g for g in groups if {g['source_cabinet_uid'],g['destination_cabinet_uid']}=={unit.source_cabinet_uid,unit.destination_cabinet_uid} and g['cable_type']==unit.cable_type),None)
                if group is None:raise config.RoutingConfigurationError('The rack-pair/type unit does not use this segment on this tier.')
                identity=unit_identity(data['layout']['uid'],unit.model_dump())
                if identity in identities:raise config.RoutingConfigurationError('A cable may occur in only one ordered unit.')
                identities.add(identity)
                units.append({**unit.model_dump(), 'unit_uid':identity,'review_group_uid':group['uid'],'cable_count':group['count'],
                    'resolved_label':unit.label or f"{group['source_cabinet_id']} ↔ {group['destination_cabinet_id']} · {group['cable_type']} × {group['count']}", 'membership_status':'AVAILABLE'})
                continue
            value,info,members=resolve_unit(session,layout,unit.model_dump())
            if seen & members:raise config.RoutingConfigurationError('A cable may occur in only one ordered unit.')
            seen.update(members)
            if unit.kind=='RACK_PAIR' and info['review_group_uid'] not in allowed:
                raise config.RoutingConfigurationError('The rack-pair/type unit does not use this segment on this tier.')
            if unit.kind=='CABLE_LIST':
                # Explicit members must belong to a group actually traversing this span.
                from backend.persistence.postgresql import models as inventory
                from sqlalchemy.orm import aliased
                a,z=aliased(inventory.Port),aliased(inventory.Port)
                pairs={(*sorted((g['source_cabinet_uid'],g['destination_cabinet_uid'])),g['cable_type']) for g in groups}
                refs=session.execute(select(a.cabinet_uid,z.cabinet_uid,inventory.Cable.cable_type).select_from(a).join(inventory.Cable,inventory.Cable.a_port_uid==a.uid).join(z,z.uid==inventory.Cable.z_port_uid).where(inventory.Cable.uid.in_(members)))
                if any((*sorted((a,b)),kind) not in pairs for a,b,kind in refs):raise config.RoutingConfigurationError('Listed cables must use this segment on this tier.')
            group=next((g for g in groups if g['uid']==info['review_group_uid']),None)
            units.append({**value,**info,'cable_class':group['cable_class'] if group else None,**(group_positions(data,group) if group else {})})
        current=dict(grid_columns=draft.grid_columns,grid_rows=draft.grid_rows,units=units,status='DRAFT',defined_end=section_end,inherited=False,errors=[])
    # Enrich saved rack-pair selectors with current rack positions and route metadata.
    positions=rack_positions(data)
    for unit in current['units']:
        group=next((g for g in groups if g['uid']==unit.get('review_group_uid')),None)
        if group:unit.update(group_positions(data,group,positions),cable_class=group['cable_class'])
        elif unit['kind']=='CABLE_LIST':
            from backend.persistence.postgresql import models as inventory
            from sqlalchemy.orm import aliased
            a,z=aliased(inventory.Port),aliased(inventory.Port)
            refs=session.execute(select(inventory.Cable.uid,a.cabinet_uid,z.cabinet_uid,inventory.Cable.cable_type).select_from(inventory.Cable)
                .join(a,a.uid==inventory.Cable.a_port_uid).join(z,z.uid==inventory.Cable.z_port_uid).where(inventory.Cable.uid.in_(unit['cable_uids'])))
            grouped={}
            for cable_uid,auid,zuid,kind in refs:
                match=next((g for g in groups if {auid,zuid}=={g['source_cabinet_uid'],g['destination_cabinet_uid']} and kind==g['cable_type']),None)
                if match:grouped.setdefault(match['uid'],[]).append(cable_uid)
            unit['group_memberships']=[dict(group_uid=k,cable_uids=sorted(v),count=len(v)) for k,v in sorted(grouped.items())]
            if len(grouped)==1:
                group=next(g for g in groups if g['uid'] in grouped)
                unit.update(group_positions(data,group,positions),cable_class=group['cable_class'],review_group_uid=group['uid'])
    covered={}
    for unit in current['units']:
        if unit['kind']=='RACK_PAIR' and unit.get('review_group_uid'):
            covered[unit['review_group_uid']]=unit.get('cable_count') or 0
        else:
            for member in unit.get('group_memberships',[]):covered[member['group_uid']]=covered.get(member['group_uid'],0)+member['count']
    missing=sum(max(0,g['count']-covered.get(g['uid'],0)) for g in groups)
    if missing:
        current['errors']=[*current.get('errors',[]),f'{missing} routed cable(s) have no ordered unit in this arrangement. Restore generated order or assign them explicitly.']
        if current['status']!='STALE':current['status']='PARTIAL'
    shape=span_geometry(data['geometry'],span)
    code=next((b['code'] for b in data['bands'] if b['uid']==span['passage_band_uid']),None)
    row=next((r for r in data['geometry']['cabinet_rows'] if r['uid']==next((c['cabinet_row_uid'] for c in data['cross_routes'] if c['uid']==span['cross_route_uid']),None)),None)
    inner='SOUTH' if code=='NORTH' else 'NORTH' if code=='SOUTH' else None if code else data['layout']['longitudinal_direction'] if row and row['position_in_pair']=='A' else {'EAST':'WEST','WEST':'EAST'}.get(data['layout']['longitudinal_direction']) if row else None
    inner=(parent or {}).get('section_inner_direction') or inner
    return {**current,'span':span,'section_end':section_end,'version':version,'bundle_placement_uid':uid if placement else None,
        'width_in':shape['width_in'],'reference':dict(column_1_direction=inner or ('NORTH' if code else 'WEST'),column_1_is_inner=inner is not None),
        'group_count':len(groups),'cable_count':sum(g['count'] for g in groups),'physical_packing_verified':False,'route_assignments_changed':False}


def save_section_order(session,data,review,span,end,request):
    session.scalar(select(db.RoutingLayout).where(db.RoutingLayout.uid==data['layout']['uid']).with_for_update())
    section_order(session,data,review,span,end,request)  # Validate everything before creating records.
    uid=container_uid(data['layout']['uid'],span)
    placement=session.get(db.RoutingBundlePlacement,uid)
    if placement is None:
        parent=covering_annotation(data,span)
        parent=parent or config.save_resource(session,data['layout']['uid'],'segment-annotations',span)
        values=BundlePlacementInput(segment_annotation_uid=parent['uid'],tier=span['tier'],is_section_container=True,
            layer=None,position=None,slot_width=None,slot_height=None,label='Actual cable group order').model_dump()
        placement=db.RoutingBundlePlacement(uid=uid,routing_layout_uid=data['layout']['uid'],**values)
        session.add(placement);session.flush()
        config.validate_layout(session,data['layout']['uid'])
    saved=get_contents(session,data['layout']['uid'],uid,end)
    write_contents(session,data['layout']['uid'],uid,end,request.model_copy(update={'expected_version':saved['version']}))
    return section_order(session,config.resolved_layout(session,data['layout']['uid']),review,span,end)
