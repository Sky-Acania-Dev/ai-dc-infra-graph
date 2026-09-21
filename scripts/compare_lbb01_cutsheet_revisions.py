from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingest.cleaners.lbb01 import ingest_lbb01_non_roce_cutsheet, ingest_lbb01_overhead
from backend.services import build_topology_database_from_results
from backend.services.topology_change_list import change_list_to_payload, compare_topology_databases


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two LBB01 main cutsheet revisions by physical port pair.")
    parser.add_argument("--old-path", required=True)
    parser.add_argument("--old-sheet", required=True)
    parser.add_argument("--new-path", required=True)
    parser.add_argument("--new-sheet", required=True)
    parser.add_argument("--output-path", required=True)
    args = parser.parse_args()

    old_database = _database(args.old_path, args.old_sheet)
    new_database = _database(args.new_path, args.new_sheet)
    change_list = compare_topology_databases(old_database, new_database, identity="port_pair")
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(change_list_to_payload(change_list), indent=2), encoding="utf-8")

    print(f"changelist={output_path}")
    print(f"old_rows={change_list.old_rows}")
    print(f"new_rows={change_list.new_rows}")
    print(f"added={change_list.added}")
    print(f"removed={change_list.removed}")
    print(f"changed={change_list.changed}")
    print(f"duplicate_old_keys={change_list.duplicate_old_keys}")
    print(f"duplicate_new_keys={change_list.duplicate_new_keys}")


def _database(path: str, sheet_name: str):
    return build_topology_database_from_results(
        cutsheet_result=ingest_lbb01_non_roce_cutsheet(path, sheet_name=sheet_name),
        overhead_result=ingest_lbb01_overhead(path),
        project_uid="LBB01",
        building_id="A",
    )


if __name__ == "__main__":
    main()
