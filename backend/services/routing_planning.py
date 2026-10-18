"""Tier-aware planning with temporary cabinet takeoffs on the existing derived graph."""
from heapq import heappop, heappush

from backend.services.routing_graph import derive_graph


def cabinet_review_attachments(data, cabinets):
    """Reuse authoritative serpentine ordering; equal slots remain integer-inch schematics."""
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
                point=(route['station_in'], (low + high) // 2, 1))
    return result


class ReviewPlanner:
    def __init__(self, data, cabinet_uids):
        self.attachments = cabinet_review_attachments(data, cabinet_uids)
        self.nodes, self.edges, self.adjacency, self.row_edges = {}, {}, {}, {}
        self.span_by_id = {}
        graph = derive_graph(data)
        graph_nodes = {n.id: n for n in graph.nodes}
        for node in graph.nodes:
            point = node.x_in, node.y_in, node.tier
            self.nodes[point] = dict(node_id=node.id, x_in=node.x_in, y_in=node.y_in, tier=node.tier,
                passage_band_uid=node.passage_band_uid, passage_code=node.passage_code, cabinet_uid=None)
            self.adjacency[point] = []
        for edge in graph.edges:
            if not edge.usable:
                continue
            source, target = graph_nodes[edge.source_node_id], graph_nodes[edge.target_node_id]
            a, b = (source.x_in, source.y_in, source.tier), (target.x_in, target.y_in, target.tier)
            passage = source.passage_band_uid if edge.edge_type in ('PASSAGE', 'VERTICAL') else None
            if edge.edge_type == 'PASSAGE':
                sid = f'guide:passage:{passage}:{source.x_in}:{target.x_in}'
            elif edge.edge_type == 'CROSS_ROUTE':
                sid = f'guide:cross:{edge.cross_route_uid}:{source.passage_band_uid}:{target.passage_band_uid}'
            else:
                sid = f'vertical:{edge.vertical_transition_uid}'
            span = dict(id=sid, passage_band_uid=passage, cross_route_uid=edge.cross_route_uid,
                start_station_in=source.x_in if passage else None, end_station_in=target.x_in if passage else None,
                from_passage_band_uid=source.passage_band_uid if edge.edge_type == 'CROSS_ROUTE' else None,
                to_passage_band_uid=target.passage_band_uid if edge.edge_type == 'CROSS_ROUTE' else None,
                label=edge.label or next((v['label'] or f"Opening {v['uid']}" for v in data['vertical_transitions'] if v['uid'] == edge.vertical_transition_uid), 'Tier opening'), usable=True)
            self.span_by_id[sid] = span
            points = {a, b}
            if edge.edge_type == 'CROSS_ROUTE':
                points.update((takeoff['point'][0], takeoff['point'][1], edge.tier) for takeoff in self.attachments.values()
                    if takeoff['cross_route_uid'] == edge.cross_route_uid and min(a[1], b[1]) <= takeoff['point'][1] <= max(a[1], b[1]))
            ordered = sorted(points)
            for point in ordered:
                self.nodes.setdefault(point, dict(node_id=f'attachment:{point[0]}:{point[1]}:tier:{point[2]}', x_in=point[0], y_in=point[1], tier=point[2], passage_band_uid=None, cabinet_uid=None))
                self.adjacency.setdefault(point, [])
            for x, y in zip(ordered, ordered[1:]):
                eid = edge.id if len(ordered) == 2 else f'{edge.id}:takeoff:{x[0]},{x[1]}:{y[0]},{y[1]}'
                item = dict(id=eid, segment_id=sid, source=x, target=y, edge_type=edge.edge_type, tier=edge.tier,
                    passage_code=edge.passage_code, cross_route_uid=edge.cross_route_uid,
                    lower_tier=edge.lower_tier, upper_tier=edge.upper_tier, vertical_transition_uid=edge.vertical_transition_uid,
                    pathway_type=edge.pathway_type, width_in=edge.width_in,
                    planar_length_in=0 if edge.edge_type == 'VERTICAL' else abs(x[0]-y[0])+abs(x[1]-y[1]))
                self.edges[eid] = item
                self.adjacency[x].append((y, eid)); self.adjacency[y].append((x, eid))
                if edge.edge_type == 'CROSS_ROUTE': self.row_edges[(edge.cross_route_uid, x, y)] = eid
        self.spans = list(self.span_by_id.values())
        for takeoff in self.attachments.values():
            for tier in (1, 2, 3):
                point = (*takeoff['point'][:2], tier)
                if point in self.nodes: self.nodes[point]['cabinet_uid'] = takeoff['cabinet_uid']

    def endpoint(self, uid, tier=1):
        takeoff = self.attachments.get(uid)
        return (*takeoff['point'][:2], tier) if takeoff else None

    def route(self, source_uid, target_uid, start_tier=1, end_tier=1):
        a, b = self.attachments.get(source_uid), self.attachments.get(target_uid)
        start, end = self.endpoint(source_uid, start_tier), self.endpoint(target_uid, end_tier)
        if not a or not b or start not in self.nodes or end not in self.nodes:
            return None
        if a['row_uid'] == b['row_uid'] and start_tier == end_tier:
            points = sorted({p for route, x, y in self.row_edges if route == a['cross_route_uid'] and x[2] == start_tier
                for p in (x, y) if min(start[1], end[1]) <= p[1] <= max(start[1], end[1])})
            if not points or points[0] != min(start, end) or points[-1] != max(start, end): return None
            if start > end: points.reverse()
            edges = [self.row_edges.get((a['cross_route_uid'], min(x,y), max(x,y))) for x,y in zip(points, points[1:])]
            if any(e is None for e in edges): return None
            return self.result(points, edges, 'SAME_ROW')
        return self.shortest(start, end)

    def shortest(self, start, end, forbidden=(), allow_edge=None):
        if start not in self.nodes or end not in self.nodes:
            return None
        forbidden = set(forbidden) - {start}
        heuristic = lambda p: abs(p[0]-end[0]) + abs(p[1]-end[1])
        best, previous = {start: (0, 0, 0, ())}, {}
        queue = [(0, heuristic(start), 0, (), 0, start)]
        while queue:
            vertical, _, count, ids, length, point = heappop(queue)
            if best.get(point) != (vertical, length, count, ids): continue
            if point == end: break
            for target, eid in sorted(self.adjacency[point], key=lambda item: item[1]):
                if target in forbidden: continue
                if allow_edge is not None and not allow_edge(self.edges[eid]): continue
                candidate = (vertical + (self.edges[eid]['edge_type'] == 'VERTICAL'), length + self.edges[eid]['planar_length_in'], count + 1, ids + (eid,))
                if target not in best or candidate < best[target]:
                    best[target], previous[target] = candidate, (point, eid)
                    heappush(queue, (candidate[0], candidate[1] + heuristic(target), candidate[2], candidate[3], candidate[1], target))
        if end not in best: return None
        points, ids = [end], []
        while points[-1] != start:
            point, eid = previous[points[-1]]; points.append(point); ids.append(eid)
        return self.result(list(reversed(points)), list(reversed(ids)), 'ASTAR')

    def result(self, points, ids, method):
        return dict(method=method, points=[self.nodes[p] for p in points], load_ids=ids,
            segment_ids=list(dict.fromkeys(self.edges[e]['segment_id'] for e in ids)),
            planar_length_in=sum(self.edges[e]['planar_length_in'] for e in ids),
            vertical_transition_count=sum(self.edges[e]['edge_type'] == 'VERTICAL' for e in ids), length_label='Planar pathway length')
