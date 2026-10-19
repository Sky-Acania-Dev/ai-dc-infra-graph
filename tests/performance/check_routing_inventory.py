"""Read-only full-inventory audit; never seeds tiers or changes manual assignments.

Run from the repository root with ``python -m tests.performance.check_routing_inventory``.
HTTP measurements are optional and target the explicitly supplied local backend.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

import networkx as nx
from sqlalchemy import select, text

from backend.persistence.postgresql import routing_models as db
from backend.persistence.postgresql.session import session_factory
from backend.services.routing_configuration import find_layout, record, resolved_layout, snapshot
from backend.services.routing_graph import derive_graph
from backend.services.routing_inventory_review import inventory_review_context
from backend.services.routing_manual_paths import validate_chain


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def http_read(base, path):
    started = perf_counter()
    with urlopen(Request(base.rstrip('/') + path, headers={'Accept-Encoding': 'gzip'}), timeout=120) as response:
        payload = response.read()
        return dict(status=response.status, seconds=round(perf_counter()-started, 3),
                    bytes=len(payload), encoding=response.headers.get('Content-Encoding'))


def audit(output, api_base=None, repeats=2):
    metrics = {}
    with session_factory()(autoflush=False) as session, session.begin():
        session.execute(text('SET TRANSACTION READ ONLY'))
        layout = find_layout(session, 'LBB01', 'A', 'DH1')
        if layout is None:
            raise RuntimeError('Initialize and configure LBB01 DH1 before running this read-only audit.')
        uid = layout.uid
        metrics['database_revision'] = session.scalar(text('SELECT version_num FROM alembic_version'))
        before = digest(snapshot(session, uid))
        manuals = [record(r) for r in session.scalars(select(db.RoutingManualCableRoute)
                   .where(db.RoutingManualCableRoute.routing_layout_uid == uid).order_by(db.RoutingManualCableRoute.uid))]
        manual_digest = digest(manuals)
        timings, fingerprints = [], []
        for _ in range(repeats):
            started = perf_counter()
            review, planner = inventory_review_context(session, uid)
            timings.append(round(perf_counter()-started, 3))
            fingerprints.append(digest({k:v for k,v in review.items() if k != 'build_ms'}))
        assert len(set(fingerprints)) == 1, 'Identical inventory produced a different graph or route.'
        metrics['build_seconds'] = timings
        metrics.update({k:review[k] for k in ('inventory_cable_count','routed_cable_count','same_cabinet_count',
            'unrouted_cable_count','unmapped_cable_count','manual_group_count','unrouted_reasons','policy_counts')})
        assert review['inventory_cable_count'] == sum(review[k] for k in
            ('routed_cable_count','same_cabinet_count','unrouted_cable_count'))
        data = resolved_layout(session, uid)
        assert len(data['sections']) == 5 and len(data['geometry']['gaps']) == 4
        assert sum(r['kind'] == 'SECTION_GAP' for r in data['cross_routes']) == 4
        graph = derive_graph(data)
        assert len(graph.nodes) == len({(n.x_in,n.y_in,n.tier) for n in graph.nodes})
        assert graph == derive_graph(data), 'Graph IDs or ordering are nondeterministic.'
        passage_graph = nx.Graph()
        for edge in graph.edges:
            assert type(edge.planar_length_in) is int and edge.planar_length_in >= 0
            if edge.edge_type == 'VERTICAL':
                assert edge.planar_length_in == 0 and edge.upper_tier == edge.lower_tier + 1
            if edge.edge_type == 'PASSAGE':
                passage_graph.add_edge(edge.source_node_id,edge.target_node_id)
        connected = 0
        for band in data['geometry']['bands']:
            if band['kind'] != 'PASSAGE':
                continue
            for tier in data['passage_tiers']:
                if tier['passage_band_uid'] != band['uid'] or not tier['enabled']:
                    continue
                nodes = sorted((n for n in graph.nodes if n.passage_band_uid == band['uid'] and n.tier == tier['tier']),key=lambda n:n.x_in)
                assert nodes[0].x_in == 0 and nodes[-1].x_in == data['geometry']['hall_length_in']
                assert nx.has_path(passage_graph,nodes[0].id,nodes[-1].id)
                connected += 1
        members, routed = Counter(), 0
        for group in review['groups']:
            route = group['route']
            if group['route_source'] == 'MANUAL':
                assert group['manual_status'] == 'VALID', f"Invalid saved manual route: {group['uid']}"
            if not route:
                continue
            ids = [review['planning_segments'][i]['id'] for i in route['edge_indices']]
            points, complete = validate_chain(planner,group['source_cabinet_uid'],group['destination_cabinet_uid'],ids,
                complete=True,start_tier=group['start_tier'],end_tier=group['end_tier'])
            assert complete
            edges = [planner.edges[eid] for eid in ids]
            assert sum(e['planar_length_in'] for e in edges) == route['planar_length_in']
            assert sum(e['edge_type'] == 'VERTICAL' for e in edges) == route['vertical_transition_count']
            assert route['length_label'] == 'Planar pathway length'
            assert len(points) == len(edges)+1
            for index in route['edge_indices']:
                members[index] += group['count']
            routed += 1
        for load in review['loads']:
            assert members[load['edge_index']] == load['cable_count']
            assert sum(review['groups'][i]['count'] for i in load['group_indices']) == load['cable_count']
        metrics.update(groups=len(review['groups']),validated_routed_groups=routed,graph_nodes=len(graph.nodes),
            graph_edges=len(graph.edges),planning_segments=len(review['planning_segments']),loads=len(review['loads']),
            continuous_passage_tiers=connected,manual_fingerprint=manual_digest,deterministic=True)
        session.expire_all()
        assert digest(snapshot(session,uid)) == before, 'Domain configuration changed during read checks.'
        assert digest([record(r) for r in session.scalars(select(db.RoutingManualCableRoute)
            .where(db.RoutingManualCableRoute.routing_layout_uid == uid).order_by(db.RoutingManualCableRoute.uid))]) == manual_digest
        metrics['domain_and_manual_routes_unchanged'] = True
        output.parent.mkdir(parents=True,exist_ok=True)
        output.with_name(output.stem+'-review.json').write_text(json.dumps(review,separators=(',',':')),encoding='utf-8')
        output.with_name(output.stem+'-layout.json').write_text(json.dumps(data,default=str,separators=(',',':')),encoding='utf-8')
    if api_base:
        path = f'/routing/layouts/{uid}/cable-review?scope=hall'
        metrics['http_sequential'] = [http_read(api_base,path) for _ in range(3)]
        started = perf_counter()
        with ThreadPoolExecutor(max_workers=5) as pool:
            pending = [pool.submit(http_read,api_base,path) for _ in range(4)]
            health = pool.submit(http_read,api_base,'/health')
            metrics['http_concurrent_four'] = [r.result() for r in pending]
            metrics['http_health_during_load'] = health.result()
        metrics['http_concurrent_wall_seconds'] = round(perf_counter()-started,3)
    output.write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('tmp/routing-stability-audit.json'))
    parser.add_argument('--api-base')
    parser.add_argument('--repeats',type=int,default=2)
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error('At least two builds are required for determinism validation.')
    audit(args.output,args.api_base,args.repeats)
