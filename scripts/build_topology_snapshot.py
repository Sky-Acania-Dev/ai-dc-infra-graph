from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import DEFAULT_BUILDING_ID, DEFAULT_MAX_RACK_UNIT, DEFAULT_PROJECT_UID
from backend.persistence import save_topology_database
from backend.services import build_topology_database_from_sources
from backend.validation import BreakoutFanoutRule


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a canonical topology JSON snapshot from cutsheet and overhead sources."
    )
    parser.add_argument("--cutsheet-path", required=True)
    parser.add_argument("--overhead-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--roce-cutsheet-path", default=None)
    parser.add_argument("--project-uid", default=DEFAULT_PROJECT_UID)
    parser.add_argument("--building-id", default=DEFAULT_BUILDING_ID)
    parser.add_argument("--cutsheet-sheet-name", default=None)
    parser.add_argument(
        "--roce-cutsheet-sheet-name",
        action="append",
        default=None,
        help="RoCE sheet name to ingest. Repeat for multi-sheet RoCE workbooks.",
    )
    parser.add_argument("--overhead-sheet-name", default=None)
    parser.add_argument("--breakout-max-children", type=int, default=4)
    parser.add_argument("--status-overrides-path", default="data/status_overrides.json")
    parser.add_argument("--default-max-rack-unit", type=int, default=DEFAULT_MAX_RACK_UNIT)
    args = parser.parse_args()

    database = build_topology_database_from_sources(
        cutsheet_path=args.cutsheet_path,
        roce_cutsheet_path=args.roce_cutsheet_path,
        overhead_path=args.overhead_path,
        project_uid=args.project_uid,
        building_id=args.building_id,
        cutsheet_sheet_name=args.cutsheet_sheet_name,
        roce_cutsheet_sheet_name=args.roce_cutsheet_sheet_name,
        overhead_sheet_name=args.overhead_sheet_name,
        breakout_rules=[BreakoutFanoutRule(max_child_connections=args.breakout_max_children)],
        status_overrides_path=args.status_overrides_path,
        default_max_rack_unit=args.default_max_rack_unit,
    )
    saved_path = save_topology_database(database, args.output_path)

    print(f"snapshot={saved_path}")
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
