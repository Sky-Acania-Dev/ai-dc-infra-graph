from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from backend.persistence import TopologyDatabase


DEFAULT_CABINET_ROOT = "DH1:001"
DEFAULT_CABINET_GRAPH_PATH = Path("data/runtime/graphs/cabinet_graph.json")


def build_cabinet_graph(
    database: TopologyDatabase,
    root_cabinet_uid: str = DEFAULT_CABINET_ROOT,
) -> nx.Graph:
    graph = nx.Graph(
        graph_type="cabinet_connectivity",
        project_uid=database.project_uid,
        building_id=database.building_id,
        root_cabinet_uid=root_cabinet_uid,
    )

    for cabinet in database.cabinets:
        cabinet_uid = cabinet_uid_from_parts(cabinet.data_hall_id, cabinet.cabinet_id)
        graph.add_node(
            cabinet_uid,
            data_hall_id=cabinet.data_hall_id,
            cabinet_id=cabinet.cabinet_id,
            category=cabinet.category,
            visualization_category=cabinet.category,
            cabinet_group=cabinet.cabinet_group,
            source_row=cabinet.source_row,
            source_col=cabinet.source_col,
        )

    for row in database.rows:
        a_cabinet_uid = cabinet_uid_from_parts(row.a_data_hall_id, row.a_cabinet_id)
        z_cabinet_uid = cabinet_uid_from_parts(row.z_data_hall_id, row.z_cabinet_id)
        if a_cabinet_uid == z_cabinet_uid:
            continue

        _add_or_increment_edge(graph, a_cabinet_uid, z_cabinet_uid, row.cable_type)

    categorize_cabinets_by_root_distance(graph, root_cabinet_uid=root_cabinet_uid)
    return graph


def categorize_cabinets_by_root_distance(
    graph: nx.Graph,
    root_cabinet_uid: str = DEFAULT_CABINET_ROOT,
) -> None:
    if root_cabinet_uid not in graph:
        for node in graph.nodes:
            graph.nodes[node]["root_distance"] = None
            graph.nodes[node]["hop_count"] = None
            graph.nodes[node]["distance_category"] = "root_missing"
        return

    distances = nx.single_source_shortest_path_length(graph, root_cabinet_uid)
    for node in graph.nodes:
        distance = distances.get(node)
        graph.nodes[node]["root_distance"] = distance
        graph.nodes[node]["hop_count"] = distance
        graph.nodes[node]["distance_category"] = _distance_category(distance)


def save_cabinet_graph(graph: nx.Graph, path: str | Path = DEFAULT_CABINET_GRAPH_PATH) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_graph.node_link_data(graph, edges="edges")
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def load_cabinet_graph(path: str | Path = DEFAULT_CABINET_GRAPH_PATH) -> nx.Graph:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return json_graph.node_link_graph(payload, edges="edges")


def cabinet_uid_from_parts(data_hall_id: str, cabinet_id: str) -> str:
    return f"{data_hall_id.upper()}:{cabinet_id.zfill(3)}"


def _add_or_increment_edge(graph: nx.Graph, a_cabinet_uid: str, z_cabinet_uid: str, cable_type: str) -> None:
    cable_type_key = cable_type or "UNKNOWN"
    if graph.has_edge(a_cabinet_uid, z_cabinet_uid):
        edge_data = graph.edges[a_cabinet_uid, z_cabinet_uid]
    else:
        graph.add_edge(a_cabinet_uid, z_cabinet_uid, total_cables=0, cable_type_counts={})
        edge_data = graph.edges[a_cabinet_uid, z_cabinet_uid]

    edge_data["total_cables"] += 1
    cable_type_counts = edge_data["cable_type_counts"]
    cable_type_counts[cable_type_key] = cable_type_counts.get(cable_type_key, 0) + 1


def _distance_category(distance: int | None) -> str:
    if distance is None:
        return "unreachable"
    if distance == 0:
        return "root"
    return f"hop_{distance}"
