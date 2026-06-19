from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.ingest.cutsheet import CutsheetCableRow
from backend.models import Cable
from backend.persistence import TopologyDatabase


ChangeType = Literal["added", "removed", "changed"]
TopologyIdentity = Literal["cable_uid", "port_pair"]


class TopologyChange(BaseModel):
    change_type: ChangeType
    key: str
    old_row_number: int | None = None
    new_row_number: int | None = None
    old_cable_uid: str | None = None
    new_cable_uid: str | None = None
    fields: dict[str, dict[str, Any]] = Field(default_factory=dict)
    old_record: dict[str, Any] | None = None
    new_record: dict[str, Any] | None = None


class TopologyChangeList(BaseModel):
    old_project_uid: str
    new_project_uid: str
    old_rows: int
    new_rows: int
    added: int
    removed: int
    changed: int
    duplicate_old_keys: int
    duplicate_new_keys: int
    changes: list[TopologyChange] = Field(default_factory=list)


def compare_topology_databases(
    old_database: TopologyDatabase,
    new_database: TopologyDatabase,
    *,
    include_unchanged_fields: bool = False,
    directional: bool = True,
    identity: TopologyIdentity = "cable_uid",
    significant_fields: set[str] | None = None,
) -> TopologyChangeList:
    old_records = _connection_records(old_database, directional=directional)
    new_records = _connection_records(new_database, directional=directional)
    old_by_key = _records_by_key(old_records, identity=identity)
    new_by_key = _records_by_key(new_records, identity=identity)
    duplicate_old_keys = sum(1 for records in old_by_key.values() if len(records) > 1)
    duplicate_new_keys = sum(1 for records in new_by_key.values() if len(records) > 1)

    changes: list[TopologyChange] = []
    for key in sorted(set(old_by_key) | set(new_by_key)):
        old_bucket = old_by_key.get(key, [])
        new_bucket = new_by_key.get(key, [])
        matched_new_indexes: set[int] = set()

        for old_record in old_bucket:
            match_index = _best_match_index(old_record, new_bucket, matched_new_indexes)
            if match_index is None:
                changes.append(
                    TopologyChange(
                        change_type="removed",
                        key=key,
                        old_row_number=old_record["row_number"],
                        old_cable_uid=old_record.get("cable_uid"),
                        old_record=old_record,
                    )
                )
                continue

            matched_new_indexes.add(match_index)
            new_record = new_bucket[match_index]
            fields = _changed_fields(
                old_record,
                new_record,
                include_unchanged_fields=include_unchanged_fields,
                significant_fields=significant_fields,
            )
            if fields:
                changes.append(
                    TopologyChange(
                        change_type="changed",
                        key=key,
                        old_row_number=old_record["row_number"],
                        new_row_number=new_record["row_number"],
                        old_cable_uid=old_record.get("cable_uid"),
                        new_cable_uid=new_record.get("cable_uid"),
                        fields=fields,
                    )
                )

        for index, new_record in enumerate(new_bucket):
            if index in matched_new_indexes:
                continue
            changes.append(
                TopologyChange(
                    change_type="added",
                    key=key,
                    new_row_number=new_record["row_number"],
                    new_cable_uid=new_record.get("cable_uid"),
                    new_record=new_record,
                )
            )

    return TopologyChangeList(
        old_project_uid=old_database.project_uid,
        new_project_uid=new_database.project_uid,
        old_rows=len(old_records),
        new_rows=len(new_records),
        added=sum(1 for change in changes if change.change_type == "added"),
        removed=sum(1 for change in changes if change.change_type == "removed"),
        changed=sum(1 for change in changes if change.change_type == "changed"),
        duplicate_old_keys=duplicate_old_keys,
        duplicate_new_keys=duplicate_new_keys,
        changes=changes,
    )


def change_list_to_payload(change_list: TopologyChangeList) -> dict[str, Any]:
    if hasattr(change_list, "model_dump"):
        return change_list.model_dump(mode="json")
    return change_list.dict()


def _connection_records(database: TopologyDatabase, *, directional: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(database.rows, start=1):
        cable = database.cables[index - 1] if index <= len(database.cables) else None
        record = _row_payload(row)
        record.update(
            {
                "row_number": index,
                "cable_uid": cable.uid if cable is not None else None,
                "construction_phase": _enum_value(cable.construction_phase) if cable is not None else "",
                "port_pair_key": _port_pair_key(row, cable, directional=directional),
            }
        )
        records.append(record)
    return records


def _records_by_key(
    records: list[dict[str, Any]],
    *,
    identity: TopologyIdentity,
) -> dict[str, list[dict[str, Any]]]:
    records_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_key[_record_key(record, identity=identity)].append(record)
    return dict(records_by_key)


def _record_key(record: dict[str, Any], *, identity: TopologyIdentity) -> str:
    if identity == "port_pair":
        return record["port_pair_key"]
    cable_uid = str(record.get("cable_uid") or "").strip().upper()
    if cable_uid:
        return cable_uid
    return record["port_pair_key"]


def _best_match_index(
    old_record: dict[str, Any],
    new_bucket: list[dict[str, Any]],
    matched_new_indexes: set[int],
) -> int | None:
    best_index: int | None = None
    best_score: tuple[int, int, int] | None = None
    for index, new_record in enumerate(new_bucket):
        if index in matched_new_indexes:
            continue
        fields = _changed_fields(old_record, new_record, include_unchanged_fields=False)
        score = (
            0 if old_record.get("cable_type") == new_record.get("cable_type") else 1,
            0 if old_record.get("construction_phase") == new_record.get("construction_phase") else 1,
            len(fields),
        )
        if best_score is None or score < best_score:
            best_score = score
            best_index = index
    return best_index


def _changed_fields(
    old_record: dict[str, Any],
    new_record: dict[str, Any],
    *,
    include_unchanged_fields: bool,
    significant_fields: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    ignored_fields = {"row_number", "cable_uid", "source_cable_uid"}
    fields: dict[str, dict[str, Any]] = {}
    compared_fields = (set(old_record) | set(new_record)) - ignored_fields
    if significant_fields is not None:
        compared_fields &= significant_fields
    for field in sorted(compared_fields):
        old_value = old_record.get(field)
        new_value = new_record.get(field)
        if old_value != new_value or include_unchanged_fields:
            fields[field] = {"old": old_value, "new": new_value}
    return fields


def _port_pair_key(row: CutsheetCableRow, cable: Cable | None, *, directional: bool) -> str:
    construction_phase = _enum_value(cable.construction_phase) if cable is not None else ""
    a_port_uid = _normalize_port_uid(row.a_port_uid)
    z_port_uid = _normalize_port_uid(row.z_port_uid)
    if not directional and z_port_uid < a_port_uid:
        a_port_uid, z_port_uid = z_port_uid, a_port_uid
    return "|".join([construction_phase, a_port_uid, z_port_uid])


def _row_payload(row: CutsheetCableRow) -> dict[str, Any]:
    if hasattr(row, "model_dump"):
        return row.model_dump(mode="json")
    return row.dict()


def _normalize_port_uid(port_uid: str) -> str:
    parts = [part.strip() for part in port_uid.upper().split(":", 3)]
    if len(parts) != 4:
        return port_uid.strip().upper()
    data_hall_id, cabinet_id, rack_unit, port_name = parts
    return f"{data_hall_id}:{cabinet_id.zfill(3)}:{int(rack_unit)}:{port_name}"


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value or "")
