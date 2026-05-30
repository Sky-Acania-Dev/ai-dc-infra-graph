from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingest.cutsheet import DEFAULT_PROJECT_UID, cutsheet_result_to_json, ingest_cutsheet
from backend.validation import BreakoutFanoutRule


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a cable cutsheet from ODS or CSV.")
    parser.add_argument("path", help="Path to the cutsheet .ods or exported .csv file.")
    parser.add_argument("--project-uid", default=DEFAULT_PROJECT_UID)
    parser.add_argument("--building-id", default="A")
    parser.add_argument("--sheet-name", default=None)
    parser.add_argument(
        "--breakout-max-children",
        type=int,
        default=4,
        help="Maximum cable connections allowed for a breakout source port.",
    )
    args = parser.parse_args()

    result = ingest_cutsheet(
        args.path,
        project_uid=args.project_uid,
        building_id=args.building_id,
        sheet_name=args.sheet_name,
        breakout_rules=[BreakoutFanoutRule(max_child_connections=args.breakout_max_children)],
    )
    print(cutsheet_result_to_json(result))


if __name__ == "__main__":
    main()
