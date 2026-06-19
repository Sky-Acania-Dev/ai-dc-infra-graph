from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.persistence import load_topology_database
from backend.persistence.postgresql.importer import replace_project_topology
from backend.persistence.postgresql.session import session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist a reviewed topology JSON snapshot to PostgreSQL.")
    parser.add_argument("--snapshot-path", required=True)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--version-date", type=date.fromisoformat, required=True, help="Version date in YYYY-MM-DD format.")
    parser.add_argument("--source-operator", default="CUSTOMER", help="Source/operator responsible for this update, e.g. COREWEAVE or CUSTOMER.")
    args = parser.parse_args()

    database = load_topology_database(args.snapshot_path)
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
