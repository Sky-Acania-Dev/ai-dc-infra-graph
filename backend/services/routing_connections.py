"""Explicit bundle continuation and cabinet takeoffs on stable domain spans."""
from backend.services.routing_spans import span_geometry, node_id


def connection_points(data, geometry, connection):
    placements = {p['uid']: p for p in data['bundle_placements']}
    parents = {a['uid']: a for a in data['segment_annotations']}
    points, node_ids, endpoints = [], [], []
    for side in ('from', 'to'):
        placement = placements[connection[f'{side}_placement_uid']]
        span = parents[placement['segment_annotation_uid']]
        point = span_geometry(geometry, span)[connection[f'{side}_end'].lower()]
        points.append(point)
        node_ids.append(node_id(point, placement['tier']))
        endpoints.append({'placement_uid': placement['uid'], 'end': connection[f'{side}_end'], 'tier': placement['tier'],
                          'x_in': point[0], 'y_in': point[1], 'passage_band_uid': point[2]})
    return {'node_ids': node_ids, 'points': points, 'endpoints': endpoints}


def validate_connections(data, geometry):
    placements = {p['uid']: p for p in data['bundle_placements']}
    parents = {a['uid']: a for a in data['segment_annotations']}
    passages = {(p['passage_band_uid'], p['tier']) for p in data['passage_tiers'] if p['enabled']}
    routes = {r['uid']: r for r in geometry['cross_routes']}
    cross_tiers = {(p['cross_route_uid'], p['tier']) for p in data['cross_route_tiers'] if p['enabled']}
    openings = {v['uid']: v for v in data['vertical_transitions']}
    seen = set()
    for connection in data.get('bundle_connections', []):
        if not connection['enabled']:
            continue
        a, b = (placements[connection[f'{side}_placement_uid']] for side in ('from', 'to'))
        if not a['enabled'] or not b['enabled']:
            raise ValueError('An enabled bundle connection requires both placements to be enabled.')
        if (a['source_kind'], a['source_uid']) != (b['source_kind'], b['source_uid']):
            raise ValueError('Bundle connections must continue the same referenced bundle or group.')
        points = connection_points(data, geometry, connection)['points']
        if points[0][:2] != points[1][:2]:
            raise ValueError('Connected bundle span endpoints must meet at the same physical junction.')
        for placement, point in zip((a, b), points):
            parent = parents[placement['segment_annotation_uid']]
            if (point[2], placement['tier']) not in passages or (parent['cross_route_uid'] and not routes[parent['cross_route_uid']]['effective_enabled']):
                raise ValueError('Bundle connections require enabled pathways at their junction endpoints.')
        if a['tier'] != b['tier']:
            opening = openings.get(connection['vertical_transition_uid'])
            if not opening or not opening['enabled'] or opening['passage_band_uid'] != points[0][2] or opening['station_in'] != points[0][0] or {opening['lower_tier'], opening['upper_tier']} != {a['tier'], b['tier']}:
                raise ValueError('A tier-changing bundle connection requires the matching explicit adjacent-tier opening.')
        elif connection['vertical_transition_uid']:
            raise ValueError('A same-tier bundle connection must not reference a vertical opening.')
        identity = tuple(sorted(((a['uid'], connection['from_end']), (b['uid'], connection['to_end']))))
        if identity in seen:
            raise ValueError('This bundle endpoint connection already exists.')
        seen.add(identity)
    for attachment in data.get('cabinet_attachments', []):
        parent = parents[attachment['segment_annotation_uid']]
        if attachment['offset_in'] > span_geometry(geometry, parent)['length_in']:
            raise ValueError('Cabinet attachment offset is outside its pathway span.')
        if attachment['tier'] is not None and parent['tier'] not in (None, attachment['tier']):
            raise ValueError('Cabinet attachment tier must match its pathway span tier.')
        if attachment['enabled'] and (not parent['usable'] or parent['cross_route_uid'] and not routes[parent['cross_route_uid']]['effective_enabled']):
            raise ValueError('An enabled cabinet attachment requires a usable enabled pathway.')
        if attachment['enabled'] and attachment['tier'] is not None:
            configured = (parent['passage_band_uid'], attachment['tier']) in passages if parent['passage_band_uid'] else (parent['cross_route_uid'], attachment['tier']) in cross_tiers
            if not configured:
                raise ValueError('The attachment tier must be explicitly configured and enabled, or left unknown.')


def resolve_connections(data, geometry):
    for connection in data.get('bundle_connections', []):
        value = connection_points(data, geometry, connection)
        connection['from_node_id'], connection['to_node_id'] = value['node_ids']
        connection['endpoints'] = value['endpoints']
    parents = {a['uid']: a for a in data['segment_annotations']}
    for attachment in data.get('cabinet_attachments', []):
        span = span_geometry(geometry, parents[attachment['segment_annotation_uid']])
        a, b = span['start'], span['end']
        offset = attachment['offset_in']
        attachment['x_in'] = a[0] + (offset if b[0] > a[0] else 0)
        attachment['y_in'] = a[1] + (offset if b[1] > a[1] else 0)
