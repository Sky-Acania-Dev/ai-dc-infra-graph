from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingest.cables import DEFAULT_PROJECT_UID, ingest_cable_connections_csv, result_to_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest cable connection CSV topology endpoints.")
    parser.add_argument("csv_path", help="Path to the cable connection CSV.")
    parser.add_argument("--project-uid", default=DEFAULT_PROJECT_UID)
    parser.add_argument("--building-id", default="A")
    args = parser.parse_args()

    result = ingest_cable_connections_csv(
        args.csv_path,
        project_uid=args.project_uid,
        building_id=args.building_id,
    )
    print(result_to_json(result))


if __name__ == "__main__":
    main()
