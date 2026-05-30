from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingest.overhead import ingest_overhead, overhead_result_to_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest overhead cabinet layout inventory from ODS.")
    parser.add_argument("path", help="Path to the overhead .ods file.")
    parser.add_argument("--sheet-name", default=None)
    args = parser.parse_args()

    result = ingest_overhead(args.path, sheet_name=args.sheet_name)
    print(overhead_result_to_json(result))


if __name__ == "__main__":
    main()
