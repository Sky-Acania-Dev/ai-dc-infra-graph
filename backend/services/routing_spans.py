"""Domain span geometry shared by occupations, connections and cabinet takeoffs."""


def span_geometry(geometry, span):
    bands = {b['uid']: b for b in geometry['bands']}
    if span['passage_band_uid']:
        band = bands[span['passage_band_uid']]
        start = (span['start_station_in'], band['center_in'], band['uid'])
        end = (span['end_station_in'], band['center_in'], band['uid'])
        width = band['width_in']
    else:
        route = next(r for r in geometry['cross_routes'] if r['uid'] == span['cross_route_uid'])
        a, b = (bands[span[k]] for k in ('from_passage_band_uid', 'to_passage_band_uid'))
        start = (route['station_in'], a['center_in'], a['uid'])
        end = (route['station_in'], b['center_in'], b['uid'])
        width = route['width_in']
    return {'start': start, 'end': end, 'width_in': width, 'length_in': abs(end[0] - start[0]) + abs(end[1] - start[1])}


def node_id(point, tier):
    return f'passage:{point[2]}:station:{point[0]}:tier:{tier}'
