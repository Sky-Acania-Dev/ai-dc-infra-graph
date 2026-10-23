"""Intersections of resolved line/circular-arc movements, in local inches.

Screen tessellation is never used for optimization statistics. Plan crossings are
distinct from physical clashes; coincident runs are reported separately.
"""
from math import atan2, cos, hypot, pi, sin, sqrt

EPS = 1e-7
METHOD = 'LINE_CIRCULAR_ARC_V1'


def close(a, b):
    return hypot(a[0] - b[0], a[1] - b[1]) <= EPS


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def on_arc(p, arc):
    c = arc['center']
    start = atan2(arc['start'][1] - c[1], arc['start'][0] - c[0])
    end = atan2(arc['end'][1] - c[1], arc['end'][0] - c[0])
    at = atan2(p[1] - c[1], p[0] - c[0])
    sign = 1 if arc['sweep'] else -1
    return ((at - start) * sign) % (2*pi) <= ((end - start) * sign) % (2*pi) + EPS or close(p, arc['start'])


def primitive_hits(a, b):
    if a['kind'] == 'ARC' and b['kind'] == 'LINE':
        return primitive_hits(b, a)
    if a['kind'] == b['kind'] == 'LINE':
        p, q, r, s = a['start'], b['start'], a['end'], b['end']
        u, v = (r[0]-p[0], r[1]-p[1]), (s[0]-q[0], s[1]-q[1])
        d, w = cross(u, v), (q[0]-p[0], q[1]-p[1])
        if abs(d) <= EPS:
            if abs(cross(w, u)) > EPS or hypot(*u) <= EPS:
                return [], False
            axis = 0 if abs(u[0]) >= abs(u[1]) else 1
            overlap = min(max(p[axis], r[axis]), max(q[axis], s[axis])) - max(min(p[axis], r[axis]), min(q[axis], s[axis]))
            return [], overlap > EPS
        t, z = cross(w, v)/d, cross(w, u)/d
        return ([(p[0]+t*u[0], p[1]+t*u[1])] if -EPS <= t <= 1+EPS and -EPS <= z <= 1+EPS else []), False
    if a['kind'] == 'LINE':
        p, q, c = a['start'], a['end'], b['center']
        u, v = (q[0]-p[0], q[1]-p[1]), (p[0]-c[0], p[1]-c[1])
        aa, bb, cc = u[0]**2+u[1]**2, 2*(u[0]*v[0]+u[1]*v[1]), v[0]**2+v[1]**2-b['radius']**2
        if aa <= EPS:
            return [], False
        disc = bb*bb-4*aa*cc
        if disc <= EPS:  # Tangency is not a transverse crossing.
            return [], False
        hits = []
        for t in ((-bb-sqrt(disc))/(2*aa), (-bb+sqrt(disc))/(2*aa)):
            point = (p[0]+t*u[0], p[1]+t*u[1])
            if -EPS <= t <= 1+EPS and on_arc(point, b):
                hits.append(point)
        return hits, False
    c, d, r, s = a['center'], b['center'], a['radius'], b['radius']
    distance = hypot(d[0]-c[0], d[1]-c[1])
    if distance <= EPS:
        if abs(r-s) > EPS:
            return [], False
        # Endpoints alone also catch overlapping quarter arcs; shared endpoints
        # alone do not count as overlapping occupation.
        def midpoint(arc):
            angle = atan2(arc['start'][1]-c[1], arc['start'][0]-c[0]) + (1 if arc['sweep'] else -1)*pi/4
            return (c[0]+r*cos(angle), c[1]+r*sin(angle))
        return [], on_arc(midpoint(a), b) or on_arc(midpoint(b), a)
    if distance >= r+s-EPS or distance <= abs(r-s)+EPS:
        return [], False
    length = (r*r-s*s+distance*distance)/(2*distance)
    height = sqrt(max(0, r*r-length*length))
    x, y = c[0]+length*(d[0]-c[0])/distance, c[1]+length*(d[1]-c[1])/distance
    dx, dy = -(d[1]-c[1])*height/distance, (d[0]-c[0])*height/distance
    return [p for p in ((x+dx, y+dy), (x-dx, y-dy)) if on_arc(p, a) and on_arc(p, b)], False


def intersection_statistics(movements, *, estimated=False):
    complete = [m for m in movements if m.get('primitives') and m.get('geometry_status') == 'RESOLVED']
    unresolved = len(movements)-len(complete)
    points, events, overlaps = [], [], []
    ordered=sorted(complete,key=lambda m:m['uid'])
    for index, a in enumerate(ordered):
        for b in ordered[index+1:]:
            if a['uid'] == b['uid'] or a['tier'] != b['tier']:
                continue
            hits, overlapping = [], False
            for p in a['primitives']:
                for q in b['primitives']:
                    found, same = primitive_hits(p, q)
                    overlapping |= same
                    for point in found:
                        # Shared/terminating port points do not represent interior crossings.
                        if any(close(point, end) for end in (a['primitives'][0]['start'], a['primitives'][-1]['end'], b['primitives'][0]['start'], b['primitives'][-1]['end'])):
                            continue
                        if not any(close(point, h) for h in hits):
                            hits.append(point)
            if overlapping:
                overlaps.append([a['uid'], b['uid']])
            for hit in sorted(hits):
                point = next((v for v in points if v['tier']==a['tier'] and close(hit, (v['x_in'], v['y_in']))), None)
                if point is None:
                    point = dict(x_in=hit[0], y_in=hit[1], tier=a['tier'],movement_uids=[])
                    points.append(point)
                point['movement_uids'] = sorted(set(point['movement_uids']) | {a['uid'], b['uid']})
                events.append(dict(x_in=hit[0], y_in=hit[1], movement_uids=[a['uid'], b['uid']]))
    return dict(cable_intersection_point_count=None if unresolved else len(points),
                bundle_pair_crossing_count=None if unresolved else len(events),
                observed_intersection_point_count=len(points), unresolved_movement_count=unresolved,
                intersection_count_status='UNKNOWN' if unresolved else 'ESTIMATED' if estimated else 'EXACT',
                method=METHOD, points=sorted(points, key=lambda p: (p['x_in'], p['y_in'])),
                crossings=events, overlapping_movement_pairs=overlaps)
