from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, load_topology_database, save_topology_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Load an exported topology JSON as the runtime database snapshot.")
    parser.add_argument("json_path", help="Path to exported topology JSON.")
    parser.add_argument("--runtime-path", default=str(DEFAULT_RUNTIME_DATABASE_PATH))
    args = parser.parse_args()

    database = load_topology_database(args.json_path)
    saved_path = save_topology_database(database, args.runtime_path)

    print(f"runtime_database={saved_path}")
    print(f"project_uid={database.project_uid}")
    print(f"rows={database.summary.rows}")
    print(f"data_halls={database.summary.data_halls}")
    print(f"cabinets={database.summary.cabinets}")
    print(f"ports={database.summary.ports}")
    print(f"cables={database.summary.cables}")
    print(f"port_collision_findings={database.summary.port_collision_findings}")
    print(f"device_model_mismatches={len(database.device_model_mismatches)}")
    print(f"device_model_format_issues={len(database.device_model_format_issues)}")


if __name__ == "__main__":
    main()
