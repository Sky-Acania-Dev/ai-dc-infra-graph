"""Integer-inch schematic geometry, independent of SVG and graph topology.

The final B row faces a trailing cold aisle. Its context extends beyond the
last module, without changing section offsets or the four extra gap stations.
"""
from __future__ import annotations


def format_inches(value: int) -> str:
    return f"{value // 12}'-{value % 12}\""


def resolve_geometry(data: dict) -> dict:
    layout = data['layout']
    bands = []
    y = 0
    for band in sorted(data['bands'], key=lambda b: (b['ordinal'], b['uid'])):
        bands.append({**band, 'start_in': y, 'end_in': y + band['width_in'], 'center_in': y + band['width_in'] // 2})
        y += band['width_in']
    sections, gaps, pairs, rows, cold_aisles = [], [], [], [], []
    x = 0
    row_base = 0
    depth, cold, hot = (layout[k] for k in ('cabinet_row_depth_in', 'cold_aisle_clear_in', 'hot_aisle_clear_in'))
    ordered_sections = sorted(data['sections'], key=lambda s: (s['ordinal'], s['uid']))
    for index, section in enumerate(ordered_sections):
        start = x
        field_counts = []
        for field in (b for b in bands if b['kind'] == 'ROW_FIELD'):
            field_pairs = sorted((p for p in data['row_pairs'] if p['routing_section_uid'] == section['uid'] and p['row_field_band_uid'] == field['uid']), key=lambda p: (p['ordinal_in_section'], p['uid']))
            field_counts.append(len(field_pairs))
            for slot, pair in enumerate(field_pairs):
                pair_x = start + slot * layout['row_pair_module_in']
                a_start, b_start = pair_x + cold, pair_x + cold + depth + hot
                pairs.append({**pair, 'start_in': pair_x, 'end_in': pair_x + layout['row_pair_module_in'],
                              'hot_aisle_start_in': a_start + depth, 'hot_aisle_end_in': b_start})
                cold_aisles.append({'start_in': pair_x, 'end_in': pair_x + cold, 'section_uid': section['uid'], 'row_field_band_uid': field['uid']})
                for row in sorted((r for r in data['cabinet_rows'] if r['row_pair_uid'] == pair['uid']), key=lambda r: r['position_in_pair']):
                    row_start = a_start if row['position_in_pair'] == 'A' else b_start
                    number = row_base + slot * 2 + (1 if row['position_in_pair'] == 'A' else 2)
                    rows.append({**row, 'row_number': number, 'display_name': f'Row {number}', 'section_uid': section['uid'], 'row_field_band_uid': field['uid'], 'start_in': row_start,
                                 'end_in': row_start + depth, 'center_in': row_start + depth // 2})
        x = start + max(field_counts, default=0) * layout['row_pair_module_in']
        row_base += max(field_counts, default=0) * 2
        sections.append({**section, 'start_in': start, 'end_in': x})
        if index < len(ordered_sections) - 1:
            end = x + layout['section_extra_gap_in']
            gaps.append({'after_section_uid': section['uid'], 'before_section_uid': ordered_sections[index + 1]['uid'],
                         'start_in': x, 'end_in': end, 'center_in': x + layout['section_extra_gap_in'] // 2})
            x = end
    if pairs:
        for field in (b for b in bands if b['kind'] == 'ROW_FIELD'):
            cold_aisles.append({'start_in': x, 'end_in': x + cold, 'section_uid': ordered_sections[-1]['uid'], 'row_field_band_uid': field['uid']})
    row_map = {r['uid']: r for r in rows}
    band_map = {b['uid']: b for b in bands}
    passages = [b for b in bands if b['kind'] == 'PASSAGE']
    gap_map = {g['after_section_uid']: g for g in gaps}
    routes = []
    for route in sorted(data['cross_routes'], key=lambda r: r['uid']):
        row = row_map.get(route['cabinet_row_uid'])
        field = band_map[row['row_field_band_uid']] if row else None
        route_passages = passages if field is None else [b for b in passages if abs(b['ordinal'] - field['ordinal']) == 1]
        if route['station_source'] != 'DERIVED':
            station = route['manual_station_in']
        elif route['kind'] == 'SECTION_GAP':
            station = gap_map[route['section_boundary_after_section_uid']]['center_in']
        elif row['position_in_pair'] == 'A':
            station = row['start_in'] - row['cold_route_face_offset_in'] - route['width_in'] // 2
        else:
            station = row['end_in'] + row['cold_route_face_offset_in'] + route['width_in'] // 2
        routes.append({**route, 'station_in': station, 'start_in': station - route['width_in'] // 2,
                       'end_in': station + route['width_in'] // 2,
                       'passage_band_uids': [b['uid'] for b in route_passages],
                       'start_y_in': route_passages[0]['center_in'], 'end_y_in': route_passages[-1]['center_in'],
                       'display_label': row['display_name'] if row else f"Section {next(s['ordinal'] for s in sections if s['uid'] == route['section_boundary_after_section_uid'])}-{next(s['ordinal'] for s in sections if s['uid'] == route['section_boundary_after_section_uid']) + 1} gap",
                       'effective_enabled': route['enabled'] and (row is None or row['enabled'])})
    geometry = {'bands': bands, 'sections': sections, 'gaps': gaps, 'row_pairs': pairs, 'cabinet_rows': rows,
            'cold_aisles': cold_aisles, 'cross_routes': routes, 'total_width_in': y,
            'module_end_in': x, 'hall_length_in': x + (cold if pairs else 0)}
    geometry['station_labels'] = station_labels(data, geometry)
    return geometry


def station_labels(data, geometry):
    rows = {r['uid']: r for r in geometry['cabinet_rows']}
    result = []
    for band in (b for b in geometry['bands'] if b['kind'] == 'PASSAGE'):
        stations = {0, geometry['hall_length_in']}
        stations.update(r['station_in'] for r in geometry['cross_routes'] if r['effective_enabled'] and band['uid'] in r['passage_band_uids'])
        stations.update(v['station_in'] for v in data['vertical_transitions'] if v['passage_band_uid'] == band['uid'] and v['enabled'])
        for marking in data.get('segment_annotations', []):
            if marking['passage_band_uid'] == band['uid']:
                stations.update((marking['start_station_in'], marking['end_station_in']))
        for station in sorted(stations):
            matching = [r for r in geometry['cross_routes'] if r['station_in'] == station and r['effective_enabled'] and band['uid'] in r['passage_band_uids']]
            gap = next((r for r in matching if r['kind'] == 'SECTION_GAP'), None)
            row_numbers = sorted({rows[r['cabinet_row_uid']]['row_number'] for r in matching if r['cabinet_row_uid']})
            opening = next((v for v in data['vertical_transitions'] if v['enabled'] and v['passage_band_uid'] == band['uid'] and v['station_in'] == station), None)
            if gap:
                token = gap['display_label']
            elif row_numbers:
                token = '/'.join(f'R{n}' for n in row_numbers)
            elif opening:
                token = opening['label'] or f'Opening @{format_inches(station)}'
            else:
                token = 'Start' if station == 0 else 'End' if station == geometry['hall_length_in'] else f'@{format_inches(station)}'
            result.append({'passage_band_uid': band['uid'], 'station_in': station, 'token': token})
    return result


def passage_span_label(geometry, band_uid, start, end):
    code = next(b['code'] for b in geometry['bands'] if b['uid'] == band_uid).title()
    tokens = {s['station_in']: s['token'] for s in geometry['station_labels'] if s['passage_band_uid'] == band_uid}
    a, b = tokens.get(start, f'@{format_inches(start)}'), tokens.get(end, f'@{format_inches(end)}')
    if a.startswith('R') and a[1:].isdigit() and b.startswith('R') and b[1:].isdigit():
        return f'{code} {a}–{b[1:]}'
    return f'{code} {a}–{b}'
