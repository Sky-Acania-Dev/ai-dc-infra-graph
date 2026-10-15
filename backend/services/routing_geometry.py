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
                    rows.append({**row, 'section_uid': section['uid'], 'row_field_band_uid': field['uid'], 'start_in': row_start,
                                 'end_in': row_start + depth, 'center_in': row_start + depth // 2})
        x = start + max(field_counts, default=0) * layout['row_pair_module_in']
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
    gap_map = {g['after_section_uid']: g for g in gaps}
    routes = []
    for route in sorted(data['cross_routes'], key=lambda r: r['uid']):
        row = row_map.get(route['cabinet_row_uid'])
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
                       'effective_enabled': route['enabled'] and (row is None or row['enabled'])})
    return {'bands': bands, 'sections': sections, 'gaps': gaps, 'row_pairs': pairs, 'cabinet_rows': rows,
            'cold_aisles': cold_aisles, 'cross_routes': routes, 'total_width_in': y,
            'module_end_in': x, 'hall_length_in': x + (cold if pairs else 0)}
