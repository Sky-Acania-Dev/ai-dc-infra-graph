from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.persistence import load_topology_database
from backend.services.topology_change_list import change_list_to_payload, compare_topology_databases


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two canonical topology JSON snapshots.")
    parser.add_argument("--old-snapshot", required=True)
    parser.add_argument("--new-snapshot", required=True)
    parser.add_argument("--output-path", default=None)
    parser.add_argument(
        "--undirected",
        action="store_true",
        help="Treat A/Z endpoint order as interchangeable when matching port pairs.",
    )
    parser.add_argument(
        "--identity",
        choices=("cable_uid", "port_pair"),
        default="cable_uid",
        help="Record identity used for matching old and new cables. Defaults to authoritative cable UID.",
    )
    parser.add_argument(
        "--significant-field",
        action="append",
        dest="significant_fields",
        default=None,
        help="Only emit changed records when one of these fields changes. Can be repeated.",
    )
    parser.add_argument(
        "--include-unchanged-fields",
        action="store_true",
        help="Include unchanged fields in changed-record field payloads.",
    )
    args = parser.parse_args()

    old_database = load_topology_database(args.old_snapshot)
    new_database = load_topology_database(args.new_snapshot)
    change_list = compare_topology_databases(
        old_database,
        new_database,
        directional=not args.undirected,
        include_unchanged_fields=args.include_unchanged_fields,
        identity=args.identity,
        significant_fields=set(args.significant_fields) if args.significant_fields else None,
    )
    payload = change_list_to_payload(change_list)
    output = json.dumps(payload, indent=2)

    if args.output_path:
        output_path = Path(args.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"changelist={output_path}")
    else:
        print(output)

    print(f"old_rows={change_list.old_rows}")
    print(f"new_rows={change_list.new_rows}")
    print(f"added={change_list.added}")
    print(f"removed={change_list.removed}")
    print(f"changed={change_list.changed}")
    print(f"duplicate_old_keys={change_list.duplicate_old_keys}")
    print(f"duplicate_new_keys={change_list.duplicate_new_keys}")


if __name__ == "__main__":
    main()
