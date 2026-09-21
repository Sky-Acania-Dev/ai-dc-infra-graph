from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


NORMAL_HISTORY_FIELDS = {"status", "a_device_name", "z_device_name"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Separate LBB01 source-revision changes into change-order and normal-history records."
    )
    parser.add_argument("--changelist-path", required=True)
    parser.add_argument("--change-order-output-path", required=True)
    parser.add_argument("--history-output-path", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.changelist_path).read_text(encoding="utf-8"))
    change_order_changes, history_changes = split_changes(payload.get("changes", []))

    change_order_payload = _payload_for_changes(payload, change_order_changes)
    history_payload = _payload_for_changes(payload, history_changes)
    _write(args.change_order_output_path, change_order_payload)
    _write(args.history_output_path, history_payload)

    print(f"change_order_records={len(change_order_changes)}")
    print(f"history_records={len(history_changes)}")
    print(f"change_order_output={args.change_order_output_path}")
    print(f"history_output={args.history_output_path}")


def split_changes(changes: object) -> tuple[list[dict], list[dict]]:
    change_order_changes: list[dict] = []
    history_changes: list[dict] = []
    for change in changes if isinstance(changes, list) else []:
        if not isinstance(change, dict):
            continue
        if change.get("change_type") != "changed":
            change_order_changes.append(change)
            continue
        fields = change.get("fields") if isinstance(change.get("fields"), dict) else {}
        normal_fields = {key: value for key, value in fields.items() if key in NORMAL_HISTORY_FIELDS}
        change_order_fields = {key: value for key, value in fields.items() if key not in NORMAL_HISTORY_FIELDS}
        if normal_fields:
            history_change = copy.deepcopy(change)
            history_change["fields"] = normal_fields
            history_changes.append(history_change)
        if change_order_fields:
            change_order_change = copy.deepcopy(change)
            change_order_change["fields"] = change_order_fields
            change_order_changes.append(change_order_change)

    return change_order_changes, history_changes


def _payload_for_changes(source: dict, changes: list[dict]) -> dict:
    payload = {key: value for key, value in source.items() if key not in {"changes", "added", "removed", "changed"}}
    payload.update(
        {
            "added": sum(change.get("change_type") == "added" for change in changes),
            "removed": sum(change.get("change_type") == "removed" for change in changes),
            "changed": sum(change.get("change_type") == "changed" for change in changes),
            "changes": changes,
        }
    )
    return payload


def _write(path: str, payload: dict) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
