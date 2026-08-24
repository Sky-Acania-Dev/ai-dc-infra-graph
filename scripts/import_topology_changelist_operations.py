from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import DEFAULT_PROJECT_UID
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.session import session_factory
from sqlalchemy import delete, select


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist topology changelist rows as source-update operation records.")
    parser.add_argument("--changelist-path", required=True)
    parser.add_argument("--input-format", choices=("auto", "json", "csv"), default="auto")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--project-uid", default=DEFAULT_PROJECT_UID)
    parser.add_argument("--operation-group-uid", required=True)
    parser.add_argument("--source-uid", required=True)
    parser.add_argument("--source-operator", default="CUSTOMER")
    parser.add_argument("--source-type", default="topology_changelist")
    parser.add_argument("--source-path", default="")
    parser.add_argument("--version-name", default=None)
    parser.add_argument("--version-date", type=date.fromisoformat, default=None)
    args = parser.parse_args()

    changelist_payload = _load_changelist_payload(Path(args.changelist_path), input_format=args.input_format)
    changes = changelist_payload.get("changes", [])
    if not isinstance(changes, list):
        raise ValueError("Changelist must contain a list field named 'changes'.")

    factory = session_factory(args.database_url)
    with factory() as session:
        with session.begin():
            if args.version_name:
                _upsert_revision_records(
                    session,
                    project_uid=args.project_uid,
                    version_name=args.version_name,
                    version_date=args.version_date,
                    source_type=args.source_type,
                    source_path=args.source_path,
                    source_uid=args.source_uid,
                    source_operator=args.source_operator,
                    operation_group_uid=args.operation_group_uid,
                    changelist_payload=changelist_payload,
                )
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
                        entity_uid=_entity_uid(session, args.project_uid, change),
                        operation_type="source_update",
                        operation_group_uid=args.operation_group_uid,
                        source_type=args.source_type,
                        source_uid=args.source_uid,
                        source_operator=args.source_operator.strip().upper(),
                        before=_before_payload(change),
                        after=_after_payload(change, index),
                    )
                )

    print(f"operation_group_uid={args.operation_group_uid}")
    print(f"source_uid={args.source_uid}")
    print(f"source_operator={args.source_operator.strip().upper()}")
    if args.version_name:
        print(f"version_name={args.version_name}")
        print(f"version_date={args.version_date.isoformat() if args.version_date else ''}")
    print(f"source_update_operations={len(changes)}")


def _entity_uid(session, project_uid: str, change: dict) -> str:
    raw_uid = str(
        change.get("authoritative_cable_uid")
        or change.get("new_cable_uid")
        or change.get("old_cable_uid")
        or change.get("key")
        or ""
    ).upper()
    candidates = [raw_uid]
    if raw_uid and not raw_uid.startswith(f"{project_uid.upper()}:"):
        candidates.append(f"{project_uid.upper()}:{raw_uid}")
    rows = session.execute(
        select(db.Cable).where(
            db.Cable.project_uid == project_uid,
            db.Cable.uid.in_(candidates),
            db.Cable.deleted_at.is_(None),
        )
    ).scalars().all()
    if rows:
        return rows[0].uid

    matched = _entity_uid_from_records(session, project_uid, change)
    return matched or raw_uid


def _entity_uid_from_records(session, project_uid: str, change: dict) -> str:
    records = [
        record
        for record in (change.get("new_record"), change.get("old_record"))
        if isinstance(record, dict)
    ]
    for record in records:
        a_port_uid = _clean(record.get("a_port_uid")).upper()
        z_port_uid = _clean(record.get("z_port_uid")).upper()
        cable_type = _clean(record.get("cable_type"))
        if not a_port_uid or not z_port_uid or not cable_type:
            continue
        rows = session.execute(
            select(db.Cable)
            .where(
                db.Cable.project_uid == project_uid,
                db.Cable.a_port_uid == a_port_uid,
                db.Cable.z_port_uid == z_port_uid,
                db.Cable.cable_type == cable_type,
                db.Cable.deleted_at.is_(None),
            )
            .order_by(db.Cable.uid)
        ).scalars().all()
        if not rows:
            continue
        record_group = _clean(record.get("group") or record.get("cable_group"))
        for row in rows:
            if row.cable_group == record_group:
                return row.uid
        return rows[0].uid
    return ""


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


def _upsert_revision_records(
    session,
    *,
    project_uid: str,
    version_name: str,
    version_date: date | None,
    source_type: str,
    source_path: str,
    source_uid: str,
    source_operator: str,
    operation_group_uid: str,
    changelist_payload: dict,
) -> None:
    source_import_uid = f"{operation_group_uid}:source-import"
    normalized_source_operator = source_operator.strip().upper()
    source_import = session.get(db.SourceImport, source_import_uid)
    if source_import is None:
        source_import = db.SourceImport(
            uid=source_import_uid,
            project_uid=project_uid,
            source_type=source_type,
        )
        session.add(source_import)
    source_import.source_type = source_type
    source_import.source_path = source_path
    source_import.version_name = version_name
    source_import.version_date = version_date
    source_import.source_operator = normalized_source_operator
    source_import.summary = _revision_summary(changelist_payload)
    session.flush()

    version_uid = _topology_version_uid(project_uid, version_name)
    topology_version = session.get(db.TopologyVersion, version_uid)
    if topology_version is None:
        topology_version = db.TopologyVersion(
            uid=version_uid,
            project_uid=project_uid,
            version_name=version_name,
        )
        session.add(topology_version)
    topology_version.version_date = version_date
    topology_version.source_operator = normalized_source_operator
    topology_version.source_import_uid = source_import_uid
    topology_version.operation_group_uid = operation_group_uid
    topology_version.summary = source_import.summary


def _revision_summary(changelist_payload: dict) -> dict:
    changes = changelist_payload.get("changes", [])
    return {
        "old_rows": int(changelist_payload.get("old_rows") or 0),
        "new_rows": int(changelist_payload.get("new_rows") or 0),
        "added": int(changelist_payload.get("added") or _count_changes(changes, "added")),
        "removed": int(changelist_payload.get("removed") or _count_changes(changes, "removed")),
        "changed": int(changelist_payload.get("changed") or _count_changes(changes, "changed")),
        "duplicate_old_keys": int(changelist_payload.get("duplicate_old_keys") or 0),
        "duplicate_new_keys": int(changelist_payload.get("duplicate_new_keys") or 0),
    }


def _count_changes(changes: object, change_type: str) -> int:
    if not isinstance(changes, list):
        return 0
    return sum(1 for change in changes if isinstance(change, dict) and change.get("change_type") == change_type)


def _topology_version_uid(project_uid: str, version_name: str) -> str:
    slug = "".join(character if character.isalnum() else "-" for character in version_name.upper()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{project_uid}:VERSION:{slug or 'IMPORT'}"


def _load_changelist_payload(path: Path, *, input_format: str) -> dict:
    resolved_format = input_format
    if resolved_format == "auto":
        resolved_format = "csv" if path.suffix.lower() == ".csv" else "json"
    if resolved_format == "csv":
        changes = _load_csv_changes(path)
        return {
            "old_rows": 0,
            "new_rows": 0,
            "added": _count_changes(changes, "added"),
            "removed": _count_changes(changes, "removed"),
            "changed": _count_changes(changes, "changed"),
            "duplicate_old_keys": 0,
            "duplicate_new_keys": 0,
            "changes": changes,
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    changes = payload.get("changes", [])
    if not isinstance(changes, list):
        raise ValueError("Changelist JSON must contain a list field named 'changes'.")
    return payload


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
