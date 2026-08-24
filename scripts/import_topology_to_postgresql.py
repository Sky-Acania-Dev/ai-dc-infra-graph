from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import DEFAULT_BUILDING_ID, DEFAULT_MAX_RACK_UNIT, DEFAULT_PROJECT_UID
from backend.ingest.cleaners.lbb01 import LBB01_PROJECT_UID, apply_lbb01_rack_unit_rule
from backend.persistence.postgresql.importer import replace_project_topology
from backend.persistence.postgresql.session import session_factory
from backend.services import build_topology_database_from_sources
from backend.validation import BreakoutFanoutRule


def main() -> None:
    parser = argparse.ArgumentParser(description="Build topology from cutsheets and persist it to PostgreSQL.")
    parser.add_argument("--cutsheet-path", required=True)
    parser.add_argument("--roce-cutsheet-path", default=None)
    parser.add_argument("--overhead-path", required=True)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--project-uid", default=DEFAULT_PROJECT_UID)
    parser.add_argument("--building-id", default=DEFAULT_BUILDING_ID)
    parser.add_argument("--cutsheet-sheet-name", default=None)
    parser.add_argument(
        "--roce-cutsheet-sheet-name",
        action="append",
        default=None,
        help="RoCE sheet name to ingest. Repeat to ingest multiple sheets from the same RoCE workbook.",
    )
    parser.add_argument("--overhead-sheet-name", default=None)
    parser.add_argument("--breakout-max-children", type=int, default=4)
    parser.add_argument("--status-overrides-path", default="data/status_overrides.json")
    parser.add_argument("--default-max-rack-unit", type=int, default=DEFAULT_MAX_RACK_UNIT)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--version-date", type=date.fromisoformat, required=True, help="Version date in YYYY-MM-DD format.")
    parser.add_argument("--source-operator", default="CUSTOMER", help="Source/operator responsible for this update, e.g. COREWEAVE or CUSTOMER.")
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
    if database.project_uid.upper() == LBB01_PROJECT_UID:
        apply_lbb01_rack_unit_rule(database.cabinets, database.rows)

    factory = session_factory(args.database_url)
    with factory() as session:
        with session.begin():
            replace_project_topology(
                session,
                database,
                version_name=args.version_name,
                version_date=args.version_date,
                source_operator=args.source_operator,
            )

    print(f"project_uid={database.project_uid}")
    print(f"version_name={args.version_name}")
    print(f"version_date={args.version_date}")
    print(f"source_operator={args.source_operator.strip().upper()}")
    print(f"rows={database.summary.rows}")
    print(f"data_halls={database.summary.data_halls}")
    print(f"cabinets={database.summary.cabinets}")
    print(f"ports={database.summary.ports}")
    print(f"cables={database.summary.cables}")
    print("postgresql_import=complete")


if __name__ == "__main__":
    main()
