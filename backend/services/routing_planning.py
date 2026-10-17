"""Untiered, provisional A* review. Never a substitute for confirmed tier topology."""
from heapq import heappop, heappush

from backend.services.routing_geometry import passage_span_label


def review_spans(data):
    g = data['geometry']
    bands = [b for b in g['bands'] if b['kind'] == 'PASSAGE']
    routes = [r for r in g['cross_routes'] if r['effective_enabled']]
    stations_by_route = {r['uid']: r['station_in'] for r in g['cross_routes']}
    spans = []
    for band in bands:
        stations = {0, g['hall_length_in']}
        stations.update(r['station_in'] for r in routes if band['uid'] in r['passage_band_uids'])
        stations.update(v['station_in'] for v in data['vertical_transitions'] if v['enabled'] and v['passage_band_uid'] == band['uid'])
        for a in data['segment_annotations']:
            if a['passage_band_uid'] == band['uid']:
                stations.update((a['start_station_in'], a['end_station_in']))
        ordered = sorted(stations)
        for a, b in zip(ordered, ordered[1:]):
            spans.append(dict(id=f"guide:passage:{band['uid']}:{a}:{b}", passage_band_uid=band['uid'], cross_route_uid=None,
                start_station_in=a, end_station_in=b, from_passage_band_uid=None, to_passage_band_uid=None,
                start=(a, band['center_in']), end=(b, band['center_in']), label=passage_span_label(g, band['uid'], a, b)))
    band_map = {b['uid']: b for b in bands}
    for route in routes:
        ids = route['passage_band_uids']
        for a, b in zip(ids, ids[1:]):
            spans.append(dict(id=f"guide:cross:{route['uid']}:{a}:{b}", passage_band_uid=None, cross_route_uid=route['uid'],
                start_station_in=None, end_station_in=None, from_passage_band_uid=a, to_passage_band_uid=b,
                start=(route['station_in'], band_map[a]['center_in']), end=(route['station_in'], band_map[b]['center_in']), label=route['display_label']))
    for span in spans:
        # An unassigned tier cannot be used to bypass any manually blocked span.
        span['usable'] = not any(not a['usable'] and (
            a['passage_band_uid'] == span['passage_band_uid'] and a['passage_band_uid'] and a['start_station_in'] <= span['start_station_in'] and a['end_station_in'] >= span['end_station_in']
            or a['cross_route_uid'] and span['cross_route_uid'] and stations_by_route[a['cross_route_uid']] == stations_by_route[span['cross_route_uid']] and a['from_passage_band_uid'] == span['from_passage_band_uid'] and a['to_passage_band_uid'] == span['to_passage_band_uid']) for a in data['segment_annotations'])
    return spans


def cabinet_review_attachments(data, cabinets):
    """Reuse authoritative serpentine columns; subdivisions are schematic integer inches."""
    inventory = {c['cabinet_uid']: c for c in data['cabinets']}
    wanted = set(cabinets)
    routes = {r['cabinet_row_uid']: r for r in data['geometry']['cross_routes'] if r['effective_enabled'] and r['cabinet_row_uid']}
    fields = {b['uid']: b for b in data['geometry']['bands']}
    result = {}
    for row in data['geometry']['cabinet_rows']:
        route = routes.get(row['uid'])
        if not row['enabled'] or not route or row['cabinet_number_start'] is None:
            continue
        entries = sorted((inventory[uid] for uid in row['existing_cabinet_uids'] if uid in inventory and inventory[uid]['cabinet_id'].isdigit() and inventory[uid]['source_col'] is not None), key=lambda c: int(c['cabinet_id']))
        if len(entries) < 2 or entries[-1]['source_col'] == entries[0]['source_col']:
            continue
        first, last = entries[0], entries[-1]
        direction = 1 if last['source_col'] > first['source_col'] else -1
        field, count = fields[row['row_field_band_uid']], data['layout']['cabinets_per_row']
        for c in entries:
            if c['cabinet_uid'] not in wanted:
                continue
            number = int(c['cabinet_id'])
            if c['source_col'] - first['source_col'] != (number - int(first['cabinet_id'])) * direction:
                continue
            slot = number - row['cabinet_number_start'] if direction > 0 else row['cabinet_number_end'] - number
            if not 0 <= slot < count:
                continue
            low = field['end_in'] - (slot + 1) * field['width_in'] // count
            high = field['end_in'] - slot * field['width_in'] // count
            result[c['cabinet_uid']] = dict(cabinet_uid=c['cabinet_uid'], row_uid=row['uid'], cross_route_uid=route['uid'],
                point=(route['station_in'], (low + high) // 2))
    return result


class ReviewPlanner:
    def __init__(self, data, cabinet_uids):
        self.spans = review_spans(data)
        self.attachments = cabinet_review_attachments(data, cabinet_uids)
        self.nodes, self.edges, self.adjacency = {}, {}, {}
        self.row_edges = {}
        band_points = {b['center_in']: b['uid'] for b in data['geometry']['bands'] if b['kind'] == 'PASSAGE'}
        for span in self.spans:
            if not span['usable']:
                continue
            points = {span['start'], span['end']}
            if span['cross_route_uid']:
                points.update(a['point'] for a in self.attachments.values() if a['cross_route_uid'] == span['cross_route_uid'])
            points = sorted(points)
            for point in points:
                self.nodes.setdefault(point, dict(x_in=point[0], y_in=point[1], passage_band_uid=band_points.get(point[1]), cabinet_uid=None))
                self.adjacency.setdefault(point, [])
            for a, b in zip(points, points[1:]):
                eid = f"{span['id']}:{a[0]},{a[1]}:{b[0]},{b[1]}"
                edge = dict(id=eid, segment_id=span['id'], source=a, target=b, planar_length_in=abs(a[0]-b[0])+abs(a[1]-b[1]))
                self.edges[eid] = edge
                self.adjacency[a].append((b, eid)); self.adjacency[b].append((a, eid))
                if span['cross_route_uid']:
                    self.row_edges[(span['cross_route_uid'], a, b)] = eid
        for attachment in self.attachments.values():
            if attachment['point'] in self.nodes:
                self.nodes[attachment['point']]['cabinet_uid'] = attachment['cabinet_uid']

    def route(self, source_uid, target_uid):
        a, b = self.attachments.get(source_uid), self.attachments.get(target_uid)
        if not a or not b or a['point'] not in self.nodes or b['point'] not in self.nodes:
            return None
        start, end = a['point'], b['point']
        if a['row_uid'] == b['row_uid']:
            points = sorted({p for route, x, y in self.row_edges if route == a['cross_route_uid'] for p in (x, y) if min(start[1], end[1]) <= p[1] <= max(start[1], end[1])})
            if not points or points[0] != min(start, end) or points[-1] != max(start, end):
                return None
            if start > end: points.reverse()
            edges = [self.row_edges.get((a['cross_route_uid'], min(x,y), max(x,y))) for x,y in zip(points, points[1:])]
            if any(e is None for e in edges): return None
            return self.result(points, edges, 'SAME_ROW')
        # Manhattan distance is admissible for rectilinear planar edge lengths.
        heuristic = lambda p: abs(p[0]-end[0]) + abs(p[1]-end[1])
        best, previous = {start: (0, 0, ())}, {}
        queue = [(heuristic(start), 0, 0, (), start)]
        while queue:
            _, length, count, ids, point = heappop(queue)
            if best.get(point) != (length, count, ids): continue
            if point == end: break
            for target, eid in sorted(self.adjacency[point], key=lambda item: item[1]):
                candidate = (length + self.edges[eid]['planar_length_in'], count + 1, ids + (eid,))
                if target not in best or candidate < best[target]:
                    best[target], previous[target] = candidate, (point, eid)
                    heappush(queue, (candidate[0] + heuristic(target), *candidate, target))
        if end not in best: return None
        points, ids = [end], []
        while points[-1] != start:
            point, eid = previous[points[-1]]; points.append(point); ids.append(eid)
        return self.result(list(reversed(points)), list(reversed(ids)), 'ASTAR')

    def result(self, points, ids, method):
        return dict(method=method, points=[self.nodes[p] for p in points], load_ids=ids,
            segment_ids=list(dict.fromkeys(self.edges[e]['segment_id'] for e in ids)),
            planar_length_in=sum(self.edges[e]['planar_length_in'] for e in ids))
