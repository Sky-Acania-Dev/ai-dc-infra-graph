"""Manual span markings survive graph regeneration; cable classes describe design intent."""
from backend.schemas.routing import SegmentAnnotationInput


def validate_annotations(data: dict, geometry: dict) -> None:
    bands = {b['uid']: b for b in geometry['bands']}
    route_stations = {r['uid']: r['station_in'] for r in geometry['cross_routes']}
    seen = []
    for item in data.get('segment_annotations', []):
        SegmentAnnotationInput.model_validate({k: item[k] for k in SegmentAnnotationInput.model_fields})
        for field in ('passage_band_uid', 'from_passage_band_uid', 'to_passage_band_uid'):
            if item[field] and (item[field] not in bands or bands[item[field]]['kind'] != 'PASSAGE'):
                raise ValueError('Segment markings require NORTH, CENTRAL or SOUTH passages.')
        if item['passage_band_uid']:
            if item['end_station_in'] > geometry['hall_length_in']:
                raise ValueError('Segment marking is outside the schematic hall.')
        elif bands[item['to_passage_band_uid']]['ordinal'] - bands[item['from_passage_band_uid']]['ordinal'] != 2:
            raise ValueError('Cross-route markings must follow NORTH-CENTRAL or CENTRAL-SOUTH.')
        for other in seen:
            same_tier = item['tier'] is None or other['tier'] is None or item['tier'] == other['tier']
            if not same_tier:
                continue
            if item['passage_band_uid']:
                overlaps = (item['passage_band_uid'] == other['passage_band_uid']
                            and item['start_station_in'] < other['end_station_in']
                            and other['start_station_in'] < item['end_station_in'])
            else:
                overlaps = (other['cross_route_uid'] is not None
                            and route_stations[item['cross_route_uid']] == route_stations[other['cross_route_uid']]
                            and item['from_passage_band_uid'] == other['from_passage_band_uid'])
            if overlaps:
                raise ValueError('Segment markings overlap at the same pathway and tier. Edit the existing marking.')
        seen.append(item)


def apply_annotations(data: dict, geometry: dict, nodes: dict, edges: dict) -> None:
    route_stations = {r['uid']: r['station_in'] for r in geometry['cross_routes']}
    for edge in edges.values():
        if edge.edge_type not in ('PASSAGE', 'CROSS_ROUTE'):
            continue
        a, b = nodes[edge.source_node_id], nodes[edge.target_node_id]
        for item in data.get('segment_annotations', []):
            if item['tier'] is not None and item['tier'] != edge.tier:
                continue
            if edge.edge_type == 'PASSAGE':
                matches = (item['passage_band_uid'] == a.passage_band_uid
                           and item['start_station_in'] <= min(a.station_in, b.station_in)
                           and max(a.station_in, b.station_in) <= item['end_station_in'])
            else:
                # Aligned north/south cabinet routes may represent the same physical span.
                # A physical obstruction cannot be bypassed through a coincident representation.
                matches = (item['cross_route_uid'] is not None
                           and route_stations[item['cross_route_uid']] == a.station_in
                           and {item['from_passage_band_uid'], item['to_passage_band_uid']} == {a.passage_band_uid, b.passage_band_uid})
            if matches:
                edge.usable = item['usable']
                edge.cable_classes = item['cable_classes']
                break
