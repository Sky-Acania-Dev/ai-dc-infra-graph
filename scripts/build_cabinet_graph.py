from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.graph import DEFAULT_CABINET_GRAPH_PATH, DEFAULT_CABINET_ROOT, build_cabinet_graph, save_cabinet_graph
from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, load_topology_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cabinet connectivity graph from runtime database JSON.")
    parser.add_argument("--database-path", default=str(DEFAULT_RUNTIME_DATABASE_PATH))
    parser.add_argument("--graph-path", default=str(DEFAULT_CABINET_GRAPH_PATH))
    parser.add_argument("--root-cabinet", default=DEFAULT_CABINET_ROOT)
    args = parser.parse_args()

    database = load_topology_database(args.database_path)
    graph = build_cabinet_graph(database, root_cabinet_uid=args.root_cabinet)
    saved_path = save_cabinet_graph(graph, args.graph_path)
    categories = Counter(data.get("visualization_category") or "<uncategorized>" for _, data in graph.nodes(data=True))
    hop_counts = Counter(data["distance_category"] for _, data in graph.nodes(data=True))

    print(f"cabinet_graph={saved_path}")
    print(f"nodes={graph.number_of_nodes()}")
    print(f"edges={graph.number_of_edges()}")
    print(f"root_cabinet={args.root_cabinet}")
    print("category_counts")
    for category, count in sorted(categories.items()):
        print(f"{category}={count}")
    print("hop_count_stats")
    for category, count in sorted(hop_counts.items()):
        print(f"{category}={count}")


if __name__ == "__main__":
    main()
