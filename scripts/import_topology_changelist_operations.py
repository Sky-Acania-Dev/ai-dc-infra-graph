from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import DEFAULT_PROJECT_UID
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.session import session_factory
from sqlalchemy import delete


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist topology changelist rows as source-update operation records.")
    parser.add_argument("--changelist-path", required=True)
    parser.add_argument("--input-format", choices=("auto", "json", "csv"), default="auto")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--project-uid", default=DEFAULT_PROJECT_UID)
    parser.add_argument("--operation-group-uid", required=True)
    parser.add_argument("--source-uid", required=True)
    parser.add_argument("--source-operator", default="CUSTOMER")
    args = parser.parse_args()

    changes = _load_changes(Path(args.changelist_path), input_format=args.input_format)

    factory = session_factory(args.database_url)
    with factory() as session:
        with session.begin():
            session.execute(
                delete(db.OperationLog).where(
                    db.OperationLog.project_uid == args.project_uid,
                    db.OperationLog.operation_type == "source_update",
                    db.OperationLog.operation_group_uid == args.operation_group_uid,
                    db.OperationLog.source_uid == args.source_uid,
                )
            )
            for index, change in enumerate(changes, start=1):
                if not isinstance(change, dict):
                    continue
                session.add(
                    db.OperationLog(
                        project_uid=args.project_uid,
                        entity_type="cable",
                        entity_uid=_entity_uid(change),
                        operation_type="source_update",
                        operation_group_uid=args.operation_group_uid,
                        source_type="topology_changelist",
                        source_uid=args.source_uid,
                        source_operator=args.source_operator.strip().upper(),
                        before=_before_payload(change),
                        after=_after_payload(change, index),
                    )
                )

    print(f"operation_group_uid={args.operation_group_uid}")
    print(f"source_uid={args.source_uid}")
    print(f"source_operator={args.source_operator.strip().upper()}")
    print(f"source_update_operations={len(changes)}")


def _entity_uid(change: dict) -> str:
    return str(
        change.get("authoritative_cable_uid")
        or change.get("new_cable_uid")
        or change.get("old_cable_uid")
        or change.get("key")
        or ""
    ).upper()


def _before_payload(change: dict) -> dict:
    payload: dict = {"change_type": change.get("change_type"), "key": change.get("key")}
    if change.get("change_subtype") is not None:
        payload["change_subtype"] = change["change_subtype"]
    if change.get("authoritative_cable_uid") is not None:
        payload["authoritative_cable_uid"] = change["authoritative_cable_uid"]
    if change.get("old_record") is not None:
        payload["old_record"] = change["old_record"]
    if change.get("fields") is not None:
        payload["fields"] = change["fields"]
    return payload


def _after_payload(change: dict, index: int) -> dict:
    payload: dict = {
        "change_type": change.get("change_type"),
        "key": change.get("key"),
        "change_index": index,
    }
    if change.get("change_subtype") is not None:
        payload["change_subtype"] = change["change_subtype"]
    if change.get("authoritative_cable_uid") is not None:
        payload["authoritative_cable_uid"] = change["authoritative_cable_uid"]
    if change.get("new_record") is not None:
        payload["new_record"] = change["new_record"]
    if change.get("fields") is not None:
        payload["fields"] = change["fields"]
    return payload


def _load_changes(path: Path, *, input_format: str) -> list[dict]:
    resolved_format = input_format
    if resolved_format == "auto":
        resolved_format = "csv" if path.suffix.lower() == ".csv" else "json"
    if resolved_format == "csv":
        return _load_csv_changes(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    changes = payload.get("changes", [])
    if not isinstance(changes, list):
        raise ValueError("Changelist JSON must contain a list field named 'changes'.")
    return changes


def _load_csv_changes(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("Changelist CSV must include a header row.")
        return [_csv_row_to_change(row) for row in reader]


def _csv_row_to_change(row: dict[str, str]) -> dict:
    fields = _json_field(row.get("field_changes_json", ""))
    authoritative_cable_uid = _clean(row.get("authoritative_cable_uid"))
    old_record = _prefixed_record(row, "old_")
    new_record = _prefixed_record(row, "new_")
    return {
        "change_type": _clean(row.get("change_type")),
        "change_subtype": _clean(row.get("change_subtype")),
        "key": authoritative_cable_uid or _clean(row.get("new_key")) or _clean(row.get("old_key")),
        "authoritative_cable_uid": authoritative_cable_uid,
        "old_row_number": _int_or_none(row.get("old_source_row_number") or row.get("old_row_number")),
        "new_row_number": _int_or_none(row.get("new_source_row_number") or row.get("new_row_number")),
        "old_cable_uid": _clean(row.get("old_source_cable_uid") or row.get("old_cable_uid")),
        "new_cable_uid": _clean(row.get("new_source_cable_uid") or row.get("new_cable_uid")),
        "fields": fields,
        "old_record": old_record or None,
        "new_record": new_record or None,
    }


def _prefixed_record(row: dict[str, str], prefix: str) -> dict[str, str | int]:
    excluded = {
        f"{prefix}key",
        f"{prefix}change_type",
        f"{prefix}source_row_number",
        f"{prefix}source_cable_uid",
    }
    record: dict[str, str | int] = {}
    for key, value in row.items():
        if not key.startswith(prefix) or key in excluded:
            continue
        record_key = key.removeprefix(prefix)
        cleaned = _clean(value)
        if cleaned == "":
            continue
        record[record_key] = _int_or_value(cleaned)
    return record


def _json_field(value: str) -> dict:
    value = _clean(value)
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("field_changes_json must contain a JSON object.")
    return parsed


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def _int_or_none(value: str | None) -> int | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    return int(cleaned)


def _int_or_value(value: str) -> str | int:
    return int(value) if value.isdigit() else value


if __name__ == "__main__":
    main()
