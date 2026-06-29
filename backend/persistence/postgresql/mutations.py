from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.core.enums import CableProgressState, CableProgressStep, LifecycleStatus
from backend.core.progress_config import normalize_cable_progress_phase
from backend.models import CableProgressPhase, CableProgressTask
from backend.persistence.postgresql import models as db


class MutationUser(BaseModel):
    uid: str
    role: str
    display_name: str = ""


class PersistedOperation(BaseModel):
    id: int
    operation_type: str
    entity_type: str
    entity_uid: str
    operation_group_uid: str | None = None
    source_type: str | None = None
    source_uid: str | None = None
    source_operator: str | None = None
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    user_uid: str | None = None
    user_role: str | None = None
    created_at: datetime | None = None
    version: int


class PersistedOperationList(BaseModel):
    operations: list[PersistedOperation]
    total: int
    offset: int
    limit: int
    has_more: bool
    version: int
    operation_types: list[str] = Field(default_factory=list)
    user_uids: list[str] = Field(default_factory=list)
    change_order_keys: list[str] = Field(default_factory=list)
    min_timestamp: datetime | None = None
    max_timestamp: datetime | None = None


class StaleWriteConflict(ValueError):
    def __init__(self, *, entity_type: str, entity_uid: str, expected_version: int, current_version: int):
        self.entity_type = entity_type
        self.entity_uid = entity_uid
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"{entity_type.title()} '{entity_uid}' changed at operation {current_version}; "
            f"refresh before writing from stale version {expected_version}."
        )


class RowLockedConflict(ValueError):
    def __init__(self, *, entity_type: str, entity_uid: str):
        self.entity_type = entity_type
        self.entity_uid = entity_uid
        super().__init__(f"{entity_type.title()} '{entity_uid}' row is currently being edited.")


def update_cabinet_status(
    session: Session,
    *,
    cabinet_uid: str,
    lifecycle_status: str | LifecycleStatus,
    expected_version: int | None = None,
    user: MutationUser | None = None,
    operation_group_uid: str | None = None,
    source_type: str | None = None,
    source_uid: str | None = None,
    source_operator: str | None = None,
) -> PersistedOperation:
    cabinet_uid = cabinet_uid.upper()
    _acquire_write_gate(session, entity_type="cabinet", entity_uid=cabinet_uid, user=user)
    cabinet = _locked_row(session, db.Cabinet, cabinet_uid, "Cabinet")
    _reject_stale_write(
        session,
        project_uid=cabinet.project_uid,
        entity_type="cabinet",
        entity_uid=cabinet.uid,
        expected_version=expected_version,
        user=user,
    )
    next_status = _enum_value(lifecycle_status)
    before = {"lifecycle_status": cabinet.lifecycle_status}
    after = {"lifecycle_status": next_status}
    cabinet.lifecycle_status = next_status
    return _append_operation(
        session,
        project_uid=cabinet.project_uid,
        entity_type="cabinet",
        entity_uid=cabinet.uid,
        before=before,
        after=after,
        user=user,
        operation_group_uid=operation_group_uid,
        source_type=source_type,
        source_uid=source_uid,
        source_operator=source_operator,
    )


def update_device_status(
    session: Session,
    *,
    device_uid: str,
    lifecycle_status: str | LifecycleStatus,
    expected_version: int | None = None,
    user: MutationUser | None = None,
    operation_group_uid: str | None = None,
    source_type: str | None = None,
    source_uid: str | None = None,
    source_operator: str | None = None,
) -> PersistedOperation:
    device_uid = _normalize_device_uid(device_uid)
    _acquire_write_gate(session, entity_type="device", entity_uid=device_uid, user=user)
    device = _locked_row(session, db.Device, device_uid, "Device")
    _reject_stale_write(
        session,
        project_uid=device.project_uid,
        entity_type="device",
        entity_uid=device.uid,
        expected_version=expected_version,
        user=user,
    )
    next_status = _enum_value(lifecycle_status)
    before = {"lifecycle_status": device.lifecycle_status}
    after = {"lifecycle_status": next_status}
    device.lifecycle_status = next_status
    return _append_operation(
        session,
        project_uid=device.project_uid,
        entity_type="device",
        entity_uid=device.uid,
        before=before,
        after=after,
        user=user,
        operation_group_uid=operation_group_uid,
        source_type=source_type,
        source_uid=source_uid,
        source_operator=source_operator,
    )


def update_cable(
    session: Session,
    *,
    cable_uid: str,
    status: str | None = None,
    progress: dict[str | CableProgressStep, str | CableProgressState] | None = None,
    current_phase: dict[str, Any] | CableProgressPhase | None = None,
    length_used_meters: float | None = None,
    note: str | None = None,
    expected_version: int | None = None,
    user: MutationUser | None = None,
    operation_group_uid: str | None = None,
    source_type: str | None = None,
    source_uid: str | None = None,
    source_operator: str | None = None,
) -> PersistedOperation:
    cable_uid = cable_uid.upper()
    _acquire_write_gate(session, entity_type="cable", entity_uid=cable_uid, user=user)
    cable = _locked_row(session, db.Cable, cable_uid, "Cable")
    _reject_stale_write(
        session,
        project_uid=cable.project_uid,
        entity_type="cable",
        entity_uid=cable.uid,
        expected_version=expected_version,
        user=user,
    )
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}

    if status is not None:
        before["status"] = cable.import_status
        after["status"] = status
        cable.import_status = status

    if progress is not None:
        before["progress"] = dict(cable.progress)
        next_progress = {
            _enum_value(key): _enum_value(value)
            for key, value in progress.items()
        }
        after["progress"] = {**before["progress"], **next_progress}
        cable.progress = after["progress"]

    if current_phase is not None:
        before["current_phase"] = cable.current_phase
        next_phase = _normalize_phase_payload(current_phase)
        after["current_phase"] = next_phase
        cable.current_phase = next_phase

    if length_used_meters is not None:
        if length_used_meters <= 0:
            raise ValueError("Length used must be greater than 0.")
        before["length_used_meters"] = float(cable.length_used_meters)
        after["length_used_meters"] = length_used_meters
        cable.length_used_meters = length_used_meters

    if note is not None:
        before["note"] = cable.note
        after["note"] = note
        cable.note = note

    if not after:
        raise ValueError("No cable fields were provided.")

    return _append_operation(
        session,
        project_uid=cable.project_uid,
        entity_type="cable",
        entity_uid=cable.uid,
        before=before,
        after=after,
        user=user,
        operation_group_uid=operation_group_uid,
        source_type=source_type,
        source_uid=source_uid,
        source_operator=source_operator,
    )


def bulk_update_status(
    session: Session,
    *,
    entity_type: str,
    entity_uids: list[str],
    lifecycle_status: str | LifecycleStatus | None = None,
    status: str | None = None,
    expected_version: int | None = None,
    user: MutationUser | None = None,
    operation_group_uid: str | None = None,
    source_type: str | None = None,
    source_uid: str | None = None,
    source_operator: str | None = None,
) -> list[PersistedOperation]:
    normalized_entity_type = entity_type.strip().lower()
    normalized_uids = _normalized_bulk_uids(normalized_entity_type, entity_uids)
    if not normalized_uids:
        raise ValueError("At least one entity UID is required.")
    _validate_bulk_targets_exist(session, normalized_entity_type, normalized_uids)

    operations: list[PersistedOperation] = []
    if normalized_entity_type == "cabinet":
        if lifecycle_status is None:
            raise ValueError("lifecycle_status is required for cabinet bulk status updates.")
        for cabinet_uid in normalized_uids:
            operations.append(
                update_cabinet_status(
                    session,
                    cabinet_uid=cabinet_uid,
                    lifecycle_status=lifecycle_status,
                    expected_version=expected_version,
                    user=user,
                    operation_group_uid=operation_group_uid,
                    source_type=source_type,
                    source_uid=source_uid,
                    source_operator=source_operator,
                )
            )
        return operations

    if normalized_entity_type == "device":
        if lifecycle_status is None:
            raise ValueError("lifecycle_status is required for device bulk status updates.")
        for device_uid in normalized_uids:
            operations.append(
                update_device_status(
                    session,
                    device_uid=device_uid,
                    lifecycle_status=lifecycle_status,
                    expected_version=expected_version,
                    user=user,
                    operation_group_uid=operation_group_uid,
                    source_type=source_type,
                    source_uid=source_uid,
                    source_operator=source_operator,
                )
            )
        return operations

    if normalized_entity_type == "cable":
        if status is None:
            raise ValueError("status is required for cable bulk status updates.")
        for cable_uid in normalized_uids:
            operations.append(
                update_cable(
                    session,
                    cable_uid=cable_uid,
                    status=status,
                    expected_version=expected_version,
                    user=user,
                    operation_group_uid=operation_group_uid,
                    source_type=source_type,
                    source_uid=source_uid,
                    source_operator=source_operator,
                )
            )
        return operations

    raise ValueError("entity_type must be one of: cabinet, device, cable.")


def list_operations(
    session: Session,
    *,
    project_uid: str,
    limit: int = 100,
    after: int | None = None,
    offset: int = 0,
    operation_type: str | None = None,
    user_uid: str | None = None,
    change_order_key: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> PersistedOperationList:
    clauses = [db.OperationLog.project_uid == project_uid]
    if after is not None:
        clauses.append(db.OperationLog.id > after)
    if operation_type:
        clauses.append(db.OperationLog.operation_type == operation_type)
    if user_uid:
        clauses.append(db.OperationLog.user_uid == user_uid)
    if change_order_key:
        clauses.append(db.OperationLog.operation_type == "source_update")
        clauses.append(
            (db.OperationLog.source_uid == change_order_key)
            | (db.OperationLog.source_operator == change_order_key)
            | (db.OperationLog.operation_group_uid == change_order_key)
        )
    if start_time is not None:
        clauses.append(db.OperationLog.created_at >= start_time)
    if end_time is not None:
        clauses.append(db.OperationLog.created_at <= end_time)
    normalized_limit = max(1, min(limit, 500))
    normalized_offset = max(0, offset)
    total = session.execute(select(func.count()).select_from(db.OperationLog).where(*clauses)).scalar_one()
    version = session.execute(
        select(func.max(db.OperationLog.id)).where(db.OperationLog.project_uid == project_uid)
    ).scalar_one() or 0
    rows = session.execute(
        select(db.OperationLog)
        .where(*clauses)
        .order_by(desc(db.OperationLog.id))
        .offset(normalized_offset)
        .limit(normalized_limit)
    ).scalars()
    facet_rows = session.execute(
        select(
            db.OperationLog.operation_type,
            db.OperationLog.user_uid,
            db.OperationLog.created_at,
            db.OperationLog.source_uid,
            db.OperationLog.source_operator,
            db.OperationLog.operation_group_uid,
        )
        .where(db.OperationLog.project_uid == project_uid)
        .order_by(db.OperationLog.id)
    ).all()
    timestamps = [row.created_at for row in facet_rows if row.created_at is not None]
    return PersistedOperationList(
        operations=[_operation_payload(row) for row in reversed(list(rows))],
        total=total,
        offset=normalized_offset,
        limit=normalized_limit,
        has_more=normalized_offset + normalized_limit < total,
        version=version if after is None or total else after,
        operation_types=sorted({row.operation_type for row in facet_rows if row.operation_type}),
        user_uids=sorted({row.user_uid for row in facet_rows if row.user_uid}),
        change_order_keys=sorted(
            {
                _change_order_key(row.source_uid, row.source_operator, row.operation_group_uid)
                for row in facet_rows
                if row.operation_type == "source_update"
                and _change_order_key(row.source_uid, row.source_operator, row.operation_group_uid)
            },
            key=_change_order_key_sort_value,
        ),
        min_timestamp=min(timestamps) if timestamps else None,
        max_timestamp=max(timestamps) if timestamps else None,
    )


def _change_order_key(source_uid: str | None, source_operator: str | None, operation_group_uid: str | None) -> str:
    return source_uid or source_operator or operation_group_uid or ""


def _change_order_key_sort_value(value: str) -> tuple[int, str]:
    digits = "".join(character for character in value if character.isdigit())
    return (int(digits) if digits else 0, value)

def _append_operation(
    session: Session,
    *,
    project_uid: str,
    entity_type: str,
    entity_uid: str,
    before: dict[str, Any],
    after: dict[str, Any],
    user: MutationUser | None,
    operation_type: str = "update",
    operation_group_uid: str | None = None,
    source_type: str | None = None,
    source_uid: str | None = None,
    source_operator: str | None = None,
) -> PersistedOperation:
    if user is not None:
        _ensure_user(session, user)
    operation = db.OperationLog(
        project_uid=project_uid,
        entity_type=entity_type,
        entity_uid=entity_uid,
        operation_type=operation_type,
        operation_group_uid=operation_group_uid,
        source_type=source_type,
        source_uid=source_uid,
        source_operator=source_operator,
        before=before,
        after=after,
        user_uid=user.uid if user else None,
        user_role=user.role if user else None,
    )
    session.add(operation)
    session.flush()
    return _operation_payload(operation)


def _reject_stale_write(
    session: Session,
    *,
    project_uid: str,
    entity_type: str,
    entity_uid: str,
    expected_version: int | None,
    user: MutationUser | None,
) -> None:
    if expected_version is None:
        return
    latest_operation = session.execute(
        select(db.OperationLog)
        .where(
            db.OperationLog.project_uid == project_uid,
            db.OperationLog.entity_type == entity_type,
            db.OperationLog.entity_uid == entity_uid,
        )
        .order_by(desc(db.OperationLog.id))
        .limit(1)
    ).scalar_one_or_none()
    if latest_operation is None or latest_operation.id <= expected_version:
        return
    if _role_rank(user.role if user else None) > _role_rank(latest_operation.user_role):
        return
    current_version = latest_operation.id
    if current_version > expected_version:
        raise StaleWriteConflict(
            entity_type=entity_type,
            entity_uid=entity_uid,
            expected_version=expected_version,
            current_version=current_version,
        )


def _ensure_user(session: Session, user: MutationUser) -> None:
    existing = session.get(db.User, user.uid)
    if existing is None:
        session.add(
            db.User(
                uid=user.uid,
                display_name=user.display_name or user.uid,
                role=user.role,
            )
        )
        session.flush()
        return
    if existing.role != user.role:
        existing.role = user.role


def _acquire_write_gate(session: Session, *, entity_type: str, entity_uid: str, user: MutationUser | None) -> None:
    role = user.role if user else "viewer"
    if not _try_advisory_lock(session, _advisory_key(f"{entity_type}:{entity_uid}:role:{role}")):
        raise RowLockedConflict(entity_type=entity_type, entity_uid=entity_uid)

    general_key = _advisory_key(f"{entity_type}:{entity_uid}:write")
    if role == "manager":
        session.execute(select(func.pg_advisory_xact_lock(general_key)))
        return
    if not _try_advisory_lock(session, general_key):
        raise RowLockedConflict(entity_type=entity_type, entity_uid=entity_uid)


def _try_advisory_lock(session: Session, key: int) -> bool:
    return bool(session.execute(select(func.pg_try_advisory_xact_lock(key))).scalar_one())


def _advisory_key(value: str) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False) & ((1 << 63) - 1)


def _operation_payload(operation: db.OperationLog) -> PersistedOperation:
    return PersistedOperation(
        id=operation.id,
        operation_type=operation.operation_type,
        entity_type=operation.entity_type,
        entity_uid=operation.entity_uid,
        operation_group_uid=operation.operation_group_uid,
        source_type=operation.source_type,
        source_uid=operation.source_uid,
        source_operator=operation.source_operator,
        before=operation.before,
        after=operation.after,
        user_uid=operation.user_uid,
        user_role=operation.user_role,
        created_at=operation.created_at,
        version=operation.id,
    )


def _locked_row(session: Session, model_type, uid: str, label: str):
    try:
        row = session.execute(
            select(model_type)
            .where(model_type.uid == uid, model_type.deleted_at.is_(None))
            .with_for_update(nowait=True)
        ).scalar_one_or_none()
    except OperationalError as exc:
        if _is_lock_not_available(exc):
            raise RowLockedConflict(entity_type=label.lower(), entity_uid=uid) from exc
        raise
    if row is None:
        raise ValueError(f"{label} '{uid}' was not found.")
    return row


def _is_lock_not_available(exc: OperationalError) -> bool:
    original = getattr(exc, "orig", None)
    return getattr(original, "sqlstate", None) == "55P03" or getattr(original, "pgcode", None) == "55P03"


def _role_rank(role: str | None) -> int:
    return {"viewer": 0, "editor": 1, "manager": 2}.get(role or "", 0)


def _normalize_phase_payload(phase: dict[str, Any] | CableProgressPhase) -> dict[str, Any]:
    if isinstance(phase, dict):
        task_values = {
            key: CableProgressTask(**value) if isinstance(value, dict) else value
            for key, value in phase.get("task_values", {}).items()
        }
        phase = CableProgressPhase(
            name=phase.get("name", ""),
            value=phase.get("value"),
            tasks=phase.get("tasks", {}),
            task_values=task_values,
        )
    normalized = normalize_cable_progress_phase(phase)
    if hasattr(normalized, "model_dump"):
        return normalized.model_dump(mode="json")
    return normalized.dict()


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _normalize_device_uid(device_uid: str) -> str:
    data_hall_id, cabinet_id, rack_unit = device_uid.upper().split(":", 2)
    return f"{data_hall_id}:{cabinet_id}:{int(rack_unit)}"


def _normalized_bulk_uids(entity_type: str, entity_uids: list[str]) -> list[str]:
    if entity_type == "device":
        normalized = [_normalize_device_uid(uid) for uid in entity_uids]
    elif entity_type in {"cabinet", "cable"}:
        normalized = [uid.upper() for uid in entity_uids]
    else:
        normalized = [uid.strip() for uid in entity_uids]
    return sorted({uid for uid in normalized if uid})


def _validate_bulk_targets_exist(session: Session, entity_type: str, entity_uids: list[str]) -> None:
    model_map = {
        "cabinet": db.Cabinet,
        "device": db.Device,
        "cable": db.Cable,
    }
    model_type = model_map.get(entity_type)
    if model_type is None:
        raise ValueError("entity_type must be one of: cabinet, device, cable.")
    existing = set(
        session.execute(
            select(model_type.uid).where(
                model_type.uid.in_(entity_uids),
                model_type.deleted_at.is_(None),
            )
        ).scalars()
    )
    missing = [uid for uid in entity_uids if uid not in existing]
    if missing:
        raise ValueError(f"Some {entity_type} UIDs were not found: {', '.join(missing)}")
