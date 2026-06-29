from __future__ import annotations

import json
import logging
import threading
import time
from uuid import uuid4
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from backend.api.auth import AuthUser, current_user, require_editor, require_manager
from backend.core.config import DEFAULT_BUILDING_ID, DEFAULT_PROJECT_UID, use_postgresql_topology_storage
from backend.core.enums import (
    CableProgressPhaseType,
    CableProgressState,
    CableProgressStep,
    ConstructionPhase,
    LifecycleStatus,
)
from backend.core.progress_config import (
    cable_endpoint_termination_and_dress_percent,
    cable_progress_phase_definitions,
    normalize_cable_progress_phase,
)
from backend.graph import build_cabinet_graph
from backend.models import Cabinet, Cable, CableProgressPhase, CableProgressTask, ConnectorType, Device, DevicePortLayoutEntry, PortConnector
from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, TopologyDatabase, load_topology_database, save_topology_database
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql import queries as pg_queries
from backend.persistence.postgresql.mutations import MutationUser, PersistedOperation, RowLockedConflict, StaleWriteConflict
from backend.persistence.postgresql.repository import PostgresTopologyRepository
from backend.persistence.postgresql.session import session_factory
from backend.validation import detect_port_collisions
from backend.validation.device_models import DeviceModelFinding, detect_device_model_findings
from backend.validation.port_collisions import PortConnectionFinding


router = APIRouter(prefix="/topology", tags=["topology"])
LOGGER = logging.getLogger(__name__)
_DATABASE_CACHE: dict[str, TopologyDatabase] = {}
_GRAPH_CACHE: dict[tuple[str, float], object] = {}
_CABINET_PROGRESS_CACHE: dict[tuple[str, float], dict[str, tuple[float, float]]] = {}
_SNAPSHOT_TIMERS: dict[str, threading.Timer] = {}
_SNAPSHOT_LOCK = threading.Lock()
_UNDO_STACKS: dict[str, list["Operation"]] = {}
_REDO_STACKS: dict[str, list["Operation"]] = {}
_SNAPSHOT_DEBOUNCE_SECONDS = 1.0


class CabinetLayoutItem(BaseModel):
    cabinet_uid: str
    data_hall_id: str
    cabinet_id: str
    category: str
    cabinet_group: str
    lifecycle_status: str
    construction_phase: str
    max_rack_unit: int
    cable_termination_percent: float = 0
    cable_dress_percent: float = 0
    source_row: int | None = None
    source_col: int | None = None


class CabinetStats(BaseModel):
    devices: int
    ports: int
    cables: int
    connected_cabinets: int
    cable_termination_percent: float = 0
    cable_dress_percent: float = 0
    cable_type_counts: dict[str, int] = Field(default_factory=dict)


class CableStatusSummary(BaseModel):
    completed: int
    total: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class ChangeOrderDiffStats(BaseModel):
    removed: int = 0
    changed: int = 0
    added: int = 0


class CabinetConnection(BaseModel):
    target_cabinet_uid: str
    target_category: str = ""
    target_cabinet_group: str = ""
    total_cables: int
    cable_type_counts: dict[str, int]
    status_summary: CableStatusSummary
    change_order_stats: ChangeOrderDiffStats | None = None


class DataHallCableBucket(BaseModel):
    scope: str
    target_data_hall: str | None = None
    total_cables: int
    cable_type_counts: dict[str, int]
    status_summary: CableStatusSummary


class DataHallCableSummaryResponse(BaseModel):
    data_hall_id: str
    internal: DataHallCableBucket
    external: list[DataHallCableBucket]


class CabinetDetailResponse(BaseModel):
    cabinet: CabinetLayoutItem
    stats: CabinetStats
    devices: list[Device]
    intra_cabinet_connection: CabinetConnection | None = None
    connections: list[CabinetConnection]
    change_operations: list[Operation] = Field(default_factory=list)


class CabinetCableDetail(BaseModel):
    uid: str
    group: str
    status: str
    cable_type: str
    construction_phase: str
    a_label_text: str = ""
    z_label_text: str = ""
    progress: dict[str, str] = Field(default_factory=dict)
    current_phase: CableProgressPhase | None = None
    designed_length_meters: float | None = None
    length_used_meters: float = 0
    length_meters: float | None = None
    note: str = ""
    a_port_uid: str
    z_port_uid: str
    a_optic: str = ""
    z_optic: str = ""
    change_status: str = "green"


class CabinetCableDetailResponse(BaseModel):
    source_cabinet_uid: str
    target_cabinet_uid: str
    cables: list[CabinetCableDetail]
    total_cables: int | None = None
    limit: int | None = None
    offset: int = 0
    has_more: bool = False


class DeviceCableDetailResponse(BaseModel):
    source_device_uid: str
    target_device_uid: str
    cables: list[CabinetCableDetail]


class DeviceConnection(BaseModel):
    target_device_uid: str
    target_device_model: str = ""
    target_cabinet_uid: str
    target_rack_unit: int
    total_cables: int
    cable_type_counts: dict[str, int]
    status_summary: CableStatusSummary


class DeviceConnectionResponse(BaseModel):
    source_device_uid: str
    source_cabinet_uid: str
    source_rack_unit: int
    connected_cabinet_uids: list[str]
    connected_devices: list[DeviceConnection]


class ValidationSummary(BaseModel):
    port_collision_findings: int
    device_model_mismatches: int
    device_model_format_issues: int


class ValidationCableRowExample(BaseModel):
    status: str
    group: str
    cable_type: str
    a_port_uid: str
    z_port_uid: str
    a_device_model: str = ""
    z_device_model: str = ""


class ValidationPortConnectionFinding(PortConnectionFinding):
    examples: list[ValidationCableRowExample] = Field(default_factory=list)


class ValidationResponse(BaseModel):
    summary: ValidationSummary
    port_collision_findings: list[ValidationPortConnectionFinding]
    device_model_mismatches: list[DeviceModelFinding]
    device_model_format_issues: list[DeviceModelFinding]


class CableProgressTaskDefinitionResponse(BaseModel):
    name: str
    task_type: str
    enum_values: list[str] = Field(default_factory=list)
    default_value: float | str | None = None


class CableProgressPhaseDefinitionResponse(BaseModel):
    name: str
    tasks: list[CableProgressTaskDefinitionResponse]


class TopologyEnumResponse(BaseModel):
    lifecycle_statuses: list[str]
    construction_phases: list[str]
    cable_import_statuses: list[str]
    cable_progress_steps: list[str]
    cable_progress_states: list[str]
    cable_progress_phase_types: list[str]
    cable_progress_phase_names: list[str]
    cable_progress_phases: list[CableProgressPhaseDefinitionResponse]


class UpdateLifecycleStatusRequest(BaseModel):
    lifecycle_status: LifecycleStatus
    expected_version: int | None = None


class UpdateCableProgressPhaseRequest(BaseModel):
    name: str
    value: float | str | None = None
    tasks: dict[str, float] = Field(default_factory=dict)
    task_values: dict[str, CableProgressTask] = Field(default_factory=dict)


class UpdateCableRequest(BaseModel):
    status: str | None = None
    progress: dict[CableProgressStep, CableProgressState] | None = None
    current_phase: UpdateCableProgressPhaseRequest | None = None
    length_used_meters: float | None = None
    length_meters: float | None = None
    note: str | None = None
    expected_version: int | None = None


class BulkStatusUpdateRequest(BaseModel):
    entity_type: str
    entity_uids: list[str] = Field(min_length=1)
    lifecycle_status: LifecycleStatus | None = None
    status: str | None = None
    expected_version: int | None = None
    operation_group_uid: str | None = None
    source_type: str | None = None
    source_uid: str | None = None


class Operation(BaseModel):
    opId: int
    type: str
    entityType: str
    entityId: str
    before: dict[str, Any]
    after: dict[str, Any]
    timestamp: str
    userUid: str | None = None
    userRole: str | None = None
    operationGroupUid: str | None = None
    sourceType: str | None = None
    sourceUid: str | None = None
    sourceOperator: str | None = None


class OperationResponse(BaseModel):
    ok: bool
    operation: Operation
    version: int


class BulkOperationResponse(BaseModel):
    ok: bool
    operations: list[Operation]
    version: int


class OperationListResponse(BaseModel):
    operations: list[Operation]
    version: int
    total: int = 0
    offset: int = 0
    limit: int = 100
    has_more: bool = False
    operation_types: list[str] = Field(default_factory=list)
    user_uids: list[str] = Field(default_factory=list)
    change_order_keys: list[str] = Field(default_factory=list)
    min_timestamp: str | None = None
    max_timestamp: str | None = None


@router.get("/layout/cabinets", response_model=list[CabinetLayoutItem])
def cabinet_layout(
    data_hall: str | None = None,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> list[CabinetLayoutItem]:
    if use_postgresql_topology_storage():
        return _postgres_cabinet_layout(data_hall)

    database = _load_cached_database(database_path)
    cabinets = database.cabinets
    if data_hall:
        cabinets = [cabinet for cabinet in cabinets if cabinet.data_hall_id == data_hall.upper()]

    progress_stats = _load_cached_cabinet_progress(database_path, database)
    return [_layout_item(cabinet, progress_stats) for cabinet in sorted(cabinets, key=_cabinet_sort_key)]


@router.get("/data-halls/{data_hall_id}/cables/summary", response_model=DataHallCableSummaryResponse)
def data_hall_cable_summary(
    data_hall_id: str,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> DataHallCableSummaryResponse:
    data_hall_id = data_hall_id.upper()
    if use_postgresql_topology_storage():
        return _postgres_data_hall_cable_summary(data_hall_id)

    database = _load_cached_database(database_path)
    internal_cables = _data_hall_internal_cables(database.cables, data_hall_id)
    external_by_hall: dict[str, list[Cable]] = {}
    for cable in database.cables:
        other_data_hall = _other_data_hall_for_cable(cable, data_hall_id)
        if other_data_hall is None:
            continue
        external_by_hall.setdefault(other_data_hall, []).append(cable)

    return DataHallCableSummaryResponse(
        data_hall_id=data_hall_id,
        internal=_data_hall_cable_bucket("internal", internal_cables),
        external=[
            _data_hall_cable_bucket("external", cables, target_data_hall=target_data_hall)
            for target_data_hall, cables in sorted(external_by_hall.items())
        ],
    )


@router.get("/data-halls/{data_hall_id}/cables", response_model=CabinetCableDetailResponse)
def data_hall_cables(
    data_hall_id: str,
    scope: str = "internal",
    target_data_hall: str | None = None,
    cable_type: str | None = None,
    limit: int = 500,
    offset: int = 0,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> CabinetCableDetailResponse:
    data_hall_id = data_hall_id.upper()
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    if use_postgresql_topology_storage():
        return _postgres_data_hall_cables(
            data_hall_id,
            scope=scope,
            target_data_hall=target_data_hall,
            cable_type=cable_type,
            limit=limit,
            offset=offset,
        )

    database = _load_cached_database(database_path)
    if scope == "internal":
        cables = _data_hall_internal_cables(database.cables, data_hall_id)
        target_label = data_hall_id
    elif scope == "external":
        normalized_target = target_data_hall.upper() if target_data_hall else None
        cables = [
            cable
            for cable in database.cables
            if (other_data_hall := _other_data_hall_for_cable(cable, data_hall_id)) is not None
            and (normalized_target is None or other_data_hall == normalized_target)
        ]
        target_label = normalized_target or "EXTERNAL"
    else:
        raise HTTPException(status_code=422, detail="scope must be 'internal' or 'external'.")

    if cable_type:
        cables = [cable for cable in cables if cable.cable_type == cable_type]
    sorted_cables = sorted((_cable_detail(cable) for cable in cables), key=lambda cable: (cable.cable_type, cable.a_port_uid, cable.z_port_uid))
    total_cables = len(sorted_cables)

    return CabinetCableDetailResponse(
        source_cabinet_uid=data_hall_id,
        target_cabinet_uid=target_label,
        cables=sorted_cables[offset : offset + limit],
        total_cables=total_cables,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total_cables,
    )


@router.get("/enums", response_model=TopologyEnumResponse)
def topology_enums(database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH)) -> TopologyEnumResponse:
    if use_postgresql_topology_storage():
        return _postgres_topology_enums()

    database = _load_cached_database(database_path)
    imported_statuses = sorted({cable.status or "Unknown" for cable in database.cables})
    phase_definitions = cable_progress_phase_definitions()
    return TopologyEnumResponse(
        lifecycle_statuses=[status.value for status in LifecycleStatus],
        construction_phases=[phase.value for phase in ConstructionPhase],
        cable_import_statuses=imported_statuses,
        cable_progress_steps=[step.value for step in CableProgressStep],
        cable_progress_states=[state.value for state in CableProgressState],
        cable_progress_phase_types=[phase_type.value for phase_type in CableProgressPhaseType],
        cable_progress_phase_names=[phase.name for phase in phase_definitions],
        cable_progress_phases=[
            CableProgressPhaseDefinitionResponse(
                name=phase.name,
                tasks=[
                    CableProgressTaskDefinitionResponse(
                        name=task.name,
                        task_type=task.task_type.value,
                        enum_values=list(task.enum_values),
                        default_value=task.default_value,
                    )
                    for task in phase.tasks
                ],
            )
            for phase in phase_definitions
        ],
    )


@router.patch("/cabinets/{cabinet_uid}/status", response_model=OperationResponse)
def update_cabinet_status(
    cabinet_uid: str,
    request: UpdateLifecycleStatusRequest,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
    user: AuthUser = Depends(current_user),
) -> OperationResponse:
    response_start = time.perf_counter()
    require_editor(user)
    cabinet_uid = cabinet_uid.upper()
    if use_postgresql_topology_storage():
        try:
            operation = _postgres_repository().update_cabinet_status(
                cabinet_uid,
                request.lifecycle_status,
                expected_version=request.expected_version,
                user=_postgres_mutation_user(user),
            )
        except ValueError as exc:
            raise _postgres_http_exception(exc) from exc
        _log_operation_timing(_operation_from_postgres(operation), response_start)
        return OperationResponse(ok=True, operation=_operation_from_postgres(operation), version=operation.version)
    database = _load_cached_database(database_path)
    cabinet = _find_cabinet(database, cabinet_uid)
    if cabinet is None:
        raise HTTPException(status_code=404, detail=f"Cabinet '{cabinet_uid}' was not found.")
    _reject_stale_json_write(database_path, entity_type="cabinet", entity_id=cabinet_uid, expected_version=request.expected_version, user=user)
    before = {"lifecycle_status": cabinet.lifecycle_status.value}
    after = {"lifecycle_status": request.lifecycle_status.value}
    operation = _commit_operation(
        database_path=database_path,
        database=database,
        operation_type="update",
        entity_type="cabinet",
        entity_id=cabinet_uid,
        before=before,
        after=after,
        user=user,
    )
    _log_operation_timing(operation, response_start)
    return OperationResponse(ok=True, operation=operation, version=database.version)


@router.patch("/devices/{device_uid}/status", response_model=OperationResponse)
def update_device_status(
    device_uid: str,
    request: UpdateLifecycleStatusRequest,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
    user: AuthUser = Depends(current_user),
) -> OperationResponse:
    response_start = time.perf_counter()
    require_editor(user)
    if use_postgresql_topology_storage():
        try:
            operation = _postgres_repository().update_device_status(
                device_uid,
                request.lifecycle_status,
                expected_version=request.expected_version,
                user=_postgres_mutation_user(user),
            )
        except ValueError as exc:
            raise _postgres_http_exception(exc) from exc
        _log_operation_timing(_operation_from_postgres(operation), response_start)
        return OperationResponse(ok=True, operation=_operation_from_postgres(operation), version=operation.version)
    database = _load_cached_database(database_path)
    device = _find_device(database, device_uid)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_uid}' was not found.")
    normalized_device_uid = _normalize_device_uid(device_uid)
    _reject_stale_json_write(database_path, entity_type="device", entity_id=normalized_device_uid, expected_version=request.expected_version, user=user)
    before = {"lifecycle_status": device.lifecycle_status.value}
    after = {"lifecycle_status": request.lifecycle_status.value}
    operation = _commit_operation(
        database_path=database_path,
        database=database,
        operation_type="update",
        entity_type="device",
        entity_id=normalized_device_uid,
        before=before,
        after=after,
        user=user,
    )
    _log_operation_timing(operation, response_start)
    return OperationResponse(ok=True, operation=operation, version=database.version)


@router.patch("/cables/{cable_uid}", response_model=OperationResponse)
def update_cable(
    cable_uid: str,
    request: UpdateCableRequest,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
    user: AuthUser = Depends(current_user),
) -> OperationResponse:
    response_start = time.perf_counter()
    require_editor(user)
    if use_postgresql_topology_storage():
        phase_payload = None
        if request.current_phase is not None:
            phase_payload = _model_to_payload(request.current_phase)
        length_used = request.length_used_meters if request.length_used_meters is not None else request.length_meters
        try:
            operation = _postgres_repository().update_cable(
                cable_uid,
                status=request.status,
                progress=request.progress,
                current_phase=phase_payload,
                length_used_meters=length_used,
                note=request.note,
                expected_version=request.expected_version,
                user=_postgres_mutation_user(user),
            )
        except ValueError as exc:
            raise _postgres_http_exception(exc) from exc
        _log_operation_timing(_operation_from_postgres(operation), response_start)
        return OperationResponse(ok=True, operation=_operation_from_postgres(operation), version=operation.version)
    database = _load_cached_database(database_path)
    cable = _find_cable(database, cable_uid)
    if cable is None:
        raise HTTPException(status_code=404, detail=f"Cable '{cable_uid}' was not found.")
    _reject_stale_json_write(database_path, entity_type="cable", entity_id=cable.uid, expected_version=request.expected_version, user=user)
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    if request.status is not None:
        before["status"] = cable.status
        after["status"] = request.status
    if request.progress is not None:
        before["progress"] = _progress_payload(cable)
        after["progress"] = {**before["progress"], **{key.value: value.value for key, value in request.progress.items()}}
    if request.current_phase is not None:
        before["current_phase"] = _model_to_payload(normalize_cable_progress_phase(cable.current_phase or _phase_from_legacy_progress(cable)))
        next_phase = normalize_cable_progress_phase(
            CableProgressPhase(
                name=request.current_phase.name,
                value=request.current_phase.value,
                tasks=request.current_phase.tasks,
                task_values=request.current_phase.task_values,
            )
        )
        after["current_phase"] = _model_to_payload(next_phase)
    length_used = request.length_used_meters if request.length_used_meters is not None else request.length_meters
    if length_used is not None:
        if length_used <= 0:
            raise HTTPException(status_code=422, detail="Length used must be greater than 0.")
        before["length_used_meters"] = cable.length_used_meters
        after["length_used_meters"] = length_used
    if request.note is not None:
        before["note"] = cable.note
        after["note"] = request.note
    if not after:
        raise HTTPException(status_code=422, detail="No cable fields were provided.")
    operation = _commit_operation(
        database_path=database_path,
        database=database,
        operation_type="update",
        entity_type="cable",
        entity_id=cable.uid,
        before=before,
        after=after,
        user=user,
    )
    _log_operation_timing(operation, response_start)
    return OperationResponse(ok=True, operation=operation, version=database.version)


@router.patch("/bulk/status", response_model=BulkOperationResponse)
def bulk_update_status(
    request: BulkStatusUpdateRequest,
    user: AuthUser = Depends(current_user),
) -> BulkOperationResponse:
    response_start = time.perf_counter()
    require_editor(user)
    if not use_postgresql_topology_storage():
        raise HTTPException(status_code=422, detail="Bulk status updates are currently only available in PostgreSQL mode.")
    operation_group_uid = request.operation_group_uid or f"bulk:{uuid4().hex}"
    try:
        operations = _postgres_repository().bulk_update_status(
            entity_type=request.entity_type,
            entity_uids=request.entity_uids,
            lifecycle_status=request.lifecycle_status,
            status=request.status,
            expected_version=request.expected_version,
            user=_postgres_mutation_user(user),
            operation_group_uid=operation_group_uid,
            source_type=request.source_type or "manual_bulk",
            source_uid=request.source_uid,
        )
    except ValueError as exc:
        raise _postgres_http_exception(exc) from exc
    response_operations = [_operation_from_postgres(operation) for operation in operations]
    if response_operations:
        _log_operation_timing(response_operations[-1], response_start)
    return BulkOperationResponse(
        ok=True,
        operations=response_operations,
        version=operations[-1].version if operations else 0,
    )


@router.post("/operations/undo", response_model=OperationResponse)
def undo_operation(
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
    user: AuthUser = Depends(current_user),
) -> OperationResponse:
    response_start = time.perf_counter()
    require_editor(user)
    database = _load_cached_database(database_path)
    normalized_path = _normalized_database_path(database_path)
    if not _UNDO_STACKS.get(normalized_path):
        raise HTTPException(status_code=409, detail="No operation is available to undo.")
    original = _UNDO_STACKS[normalized_path].pop()
    _REDO_STACKS.setdefault(normalized_path, []).append(original)
    operation = _commit_operation(
        database_path=database_path,
        database=database,
        operation_type="undo",
        entity_type=original.entityType,
        entity_id=original.entityId,
        before=original.after,
        after=original.before,
        record_undo=False,
        user=user,
    )
    _log_operation_timing(operation, response_start)
    return OperationResponse(ok=True, operation=operation, version=database.version)


@router.post("/operations/redo", response_model=OperationResponse)
def redo_operation(
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
    user: AuthUser = Depends(current_user),
) -> OperationResponse:
    response_start = time.perf_counter()
    require_editor(user)
    database = _load_cached_database(database_path)
    normalized_path = _normalized_database_path(database_path)
    if not _REDO_STACKS.get(normalized_path):
        raise HTTPException(status_code=409, detail="No operation is available to redo.")
    original = _REDO_STACKS[normalized_path].pop()
    _UNDO_STACKS.setdefault(normalized_path, []).append(original)
    operation = _commit_operation(
        database_path=database_path,
        database=database,
        operation_type="redo",
        entity_type=original.entityType,
        entity_id=original.entityId,
        before=original.before,
        after=original.after,
        record_undo=False,
        user=user,
    )
    _log_operation_timing(operation, response_start)
    return OperationResponse(ok=True, operation=operation, version=database.version)


@router.get("/operations", response_model=OperationListResponse)
def list_operations(
    limit: int = 100,
    after: int | None = None,
    offset: int = 0,
    operation_type: str | None = None,
    user_uid: str | None = None,
    change_order_key: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> OperationListResponse:
    normalized_limit = min(500, max(1, limit))
    normalized_offset = max(0, offset)
    start_time = _normalize_operation_filter_time(start_time)
    end_time = _normalize_operation_filter_time(end_time)
    if use_postgresql_topology_storage():
        page = _postgres_repository().list_operation_page(
            limit=normalized_limit,
            after=after,
            offset=normalized_offset,
            operation_type=operation_type,
            user_uid=user_uid,
            change_order_key=change_order_key,
            start_time=start_time,
            end_time=end_time,
        )
        return OperationListResponse(
            operations=[_operation_from_postgres(operation) for operation in page.operations],
            version=page.version,
            total=page.total,
            offset=page.offset,
            limit=page.limit,
            has_more=page.has_more,
            operation_types=page.operation_types,
            user_uids=page.user_uids,
            change_order_keys=page.change_order_keys,
            min_timestamp=page.min_timestamp.isoformat() if page.min_timestamp else None,
            max_timestamp=page.max_timestamp.isoformat() if page.max_timestamp else None,
        )
    all_operations = _load_operations(_operations_path(database_path))
    operation_types = sorted({operation.type for operation in all_operations if operation.type})
    user_uids = sorted({operation.userUid for operation in all_operations if operation.userUid})
    change_order_keys = sorted({operation_change_order_key(operation) for operation in all_operations if operation.type == "source_update" and operation_change_order_key(operation)})
    timestamps = [operation.timestamp for operation in all_operations if operation.timestamp]
    operations = all_operations
    if after is not None:
        operations = [operation for operation in operations if operation.opId > after]
    if operation_type:
        operations = [operation for operation in operations if operation.type == operation_type]
    if user_uid:
        operations = [operation for operation in operations if operation.userUid == user_uid]
    if change_order_key:
        operations = [operation for operation in operations if operation.type == "source_update" and operation_change_order_key(operation) == change_order_key]
    if start_time is not None:
        operations = [operation for operation in operations if _parse_operation_timestamp(operation.timestamp) >= start_time]
    if end_time is not None:
        operations = [operation for operation in operations if _parse_operation_timestamp(operation.timestamp) <= end_time]
    total = len(operations)
    page_operations = operations[-(normalized_offset + normalized_limit):len(operations) - normalized_offset if normalized_offset else None]
    return OperationListResponse(
        operations=page_operations,
        version=all_operations[-1].opId if all_operations else (after or 0),
        total=total,
        offset=normalized_offset,
        limit=normalized_limit,
        has_more=normalized_offset + normalized_limit < total,
        operation_types=operation_types,
        user_uids=user_uids,
        change_order_keys=change_order_keys,
        min_timestamp=min(timestamps) if timestamps else None,
        max_timestamp=max(timestamps) if timestamps else None,
    )


def operation_change_order_key(operation: Operation) -> str:
    return operation.sourceUid or operation.sourceOperator or operation.operationGroupUid or ""


@router.get("/validation", response_model=ValidationResponse)
def validation_report(
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> ValidationResponse:
    if use_postgresql_topology_storage():
        return _validation_response_from_findings(*_postgres_repository().validation_findings())
    database = _load_cached_database(database_path)
    return _validation_response_from_database(database)


@router.post("/validation/revalidate", response_model=ValidationResponse)
def revalidate_report(
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
    user: AuthUser = Depends(current_user),
) -> ValidationResponse:
    require_manager(user)
    if use_postgresql_topology_storage():
        return _validation_response_from_findings(*_postgres_repository().revalidate())
    database = _load_cached_database(database_path)
    database.port_collision_findings = detect_port_collisions(database.rows)
    database.device_model_mismatches, database.device_model_format_issues = detect_device_model_findings(database.rows)
    save_topology_database(database, database_path)
    return _validation_response_from_database(database)

@router.get(
    "/cabinets/{cabinet_uid}/devices/{rack_unit}/connections",
    response_model=DeviceConnectionResponse,
)
def device_connections(
    cabinet_uid: str,
    rack_unit: int,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> DeviceConnectionResponse:
    cabinet_uid = cabinet_uid.upper()
    source_device_uid = _device_uid(cabinet_uid, rack_unit)
    if use_postgresql_topology_storage():
        return _postgres_device_connections(source_device_uid)

    database = _load_cached_database(database_path)
    if _find_cabinet(database, cabinet_uid) is None:
        raise HTTPException(status_code=404, detail=f"Cabinet '{cabinet_uid}' was not found.")

    source_prefix = f"{source_device_uid}:"
    connections_by_device: dict[str, list[Cable]] = {}
    connected_cabinets: set[str] = set()
    device_by_uid = {
        _normalize_device_uid(f"{device.cabinet_id}:{device.rack_unit}"): device
        for cabinet in database.cabinets
        for device in cabinet.devices
    }

    for cable in database.cables:
        other_port_uid = ""
        if cable.a_side.uid.startswith(source_prefix):
            other_port_uid = cable.z_side.uid
        elif cable.z_side.uid.startswith(source_prefix):
            other_port_uid = cable.a_side.uid

        if not other_port_uid:
            continue

        other_device = _device_uid_from_port_uid(other_port_uid)
        if other_device is None or other_device == source_device_uid:
            continue

        connections_by_device.setdefault(other_device, []).append(cable)
        connected_cabinets.add(_cabinet_uid_from_device_uid(other_device))

    connections = [
        DeviceConnection(
            target_device_uid=target_device_uid,
            target_device_model=device_by_uid.get(target_device_uid).device_model if device_by_uid.get(target_device_uid) else "",
            target_cabinet_uid=_cabinet_uid_from_device_uid(target_device_uid),
            target_rack_unit=int(target_device_uid.split(":")[2]),
            total_cables=len(cables),
            cable_type_counts=dict(sorted(Counter(cable.cable_type for cable in cables).items())),
            status_summary=_status_summary(cables),
        )
        for target_device_uid, cables in connections_by_device.items()
    ]
    return DeviceConnectionResponse(
        source_device_uid=source_device_uid,
        source_cabinet_uid=cabinet_uid,
        source_rack_unit=rack_unit,
        connected_cabinet_uids=sorted(connected_cabinets),
        connected_devices=sorted(
            connections,
            key=lambda connection: (-connection.total_cables, connection.target_device_uid),
        ),
    )


@router.get("/cabinets/{cabinet_uid}", response_model=CabinetDetailResponse)
def cabinet_detail(
    cabinet_uid: str,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> CabinetDetailResponse:
    cabinet_uid = cabinet_uid.upper()
    if use_postgresql_topology_storage():
        return _postgres_cabinet_detail(cabinet_uid)

    database = _load_cached_database(database_path)
    cabinet = _find_cabinet(database, cabinet_uid)
    if cabinet is None:
        raise HTTPException(status_code=404, detail=f"Cabinet '{cabinet_uid}' was not found.")

    graph = _load_cached_graph(database_path, database)
    progress_stats = _load_cached_cabinet_progress(database_path, database)
    connections = _cabinet_connections(database, cabinet_uid, graph)
    cable_type_counts = Counter(cable.cable_type for cable in _cables_for_cabinet(database.cables, cabinet_uid))
    intra_cabinet_connection = _intra_cabinet_connection(cabinet, database.cables)
    port_count = sum(len(ports) for device in cabinet.devices for ports in device.ports_by_type.values())
    cable_termination_percent, cable_dress_percent = progress_stats.get(cabinet_uid, (0.0, 0.0))
    return CabinetDetailResponse(
        cabinet=_layout_item(cabinet, progress_stats),
        stats=CabinetStats(
            devices=len(cabinet.devices),
            ports=port_count,
            cables=sum(cable_type_counts.values()),
            connected_cabinets=len(connections),
            cable_termination_percent=cable_termination_percent,
            cable_dress_percent=cable_dress_percent,
            cable_type_counts=dict(sorted(cable_type_counts.items())),
        ),
        devices=sorted(cabinet.devices, key=lambda device: (device.rack_unit, device.device_model, device.note)),
        intra_cabinet_connection=intra_cabinet_connection,
        connections=connections,
    )


@router.get(
    "/cabinets/{source_cabinet_uid}/connections/{target_cabinet_uid}/cables",
    response_model=CabinetCableDetailResponse,
)
def cabinet_connection_cables(
    source_cabinet_uid: str,
    target_cabinet_uid: str,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> CabinetCableDetailResponse:
    source_cabinet_uid = source_cabinet_uid.upper()
    target_cabinet_uid = target_cabinet_uid.upper()
    if use_postgresql_topology_storage():
        return _postgres_cabinet_connection_cables(source_cabinet_uid, target_cabinet_uid)

    database = _load_cached_database(database_path)
    cables = [
        _cable_detail(cable)
        for cable in _cables_between_cabinets(database.cables, source_cabinet_uid, target_cabinet_uid)
    ]
    return CabinetCableDetailResponse(
        source_cabinet_uid=source_cabinet_uid,
        target_cabinet_uid=target_cabinet_uid,
        cables=sorted(cables, key=lambda cable: (cable.cable_type, cable.a_port_uid, cable.z_port_uid)),
    )


@router.get(
    "/cabinets/{cabinet_uid}/change-order-cables",
    response_model=CabinetCableDetailResponse,
)
def cabinet_change_order_cables(
    cabinet_uid: str,
    change_status: str | None = None,
    change_order_key: list[str] | None = None,
) -> CabinetCableDetailResponse:
    cabinet_uid = cabinet_uid.upper()
    if not use_postgresql_topology_storage():
        raise HTTPException(status_code=400, detail="Change order cable details require PostgreSQL topology storage.")
    return _postgres_cabinet_change_order_cables(cabinet_uid, change_status, set(change_order_key or []))


@router.get(
    "/devices/{source_device_uid}/connections/{target_device_uid}/cables",
    response_model=DeviceCableDetailResponse,
)
def device_connection_cables(
    source_device_uid: str,
    target_device_uid: str,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> DeviceCableDetailResponse:
    source_device_uid = source_device_uid.upper()
    target_device_uid = target_device_uid.upper()
    if use_postgresql_topology_storage():
        return _postgres_device_connection_cables(source_device_uid, target_device_uid)

    database = _load_cached_database(database_path)
    cables = [
        _cable_detail(cable)
        for cable in _cables_between_devices(database.cables, source_device_uid, target_device_uid)
    ]
    return DeviceCableDetailResponse(
        source_device_uid=source_device_uid,
        target_device_uid=target_device_uid,
        cables=sorted(cables, key=lambda cable: (cable.cable_type, cable.a_port_uid, cable.z_port_uid)),
    )


def _commit_operation(
    *,
    database_path: str,
    database: TopologyDatabase,
    operation_type: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    record_undo: bool = True,
    user: AuthUser | None = None,
) -> Operation:
    normalized_path = _normalized_database_path(database_path)
    operation = Operation(
        opId=database.version + 1,
        type=operation_type,
        entityType=entity_type,
        entityId=entity_id,
        before=before,
        after=after,
        timestamp=datetime.now(timezone.utc).isoformat(),
        userUid=user.uid if user else None,
        userRole=user.role.value if user else None,
    )
    apply_start = time.perf_counter()
    _apply_operation(database, operation, use_before=False)
    apply_ms = (time.perf_counter() - apply_start) * 1000
    append_start = time.perf_counter()
    _append_operation(_operations_path(database_path), operation)
    append_ms = (time.perf_counter() - append_start) * 1000
    database.version = operation.opId
    _clear_derived_caches()
    _schedule_snapshot_save(database, database_path)
    if record_undo:
        _UNDO_STACKS.setdefault(normalized_path, []).append(operation)
        _REDO_STACKS[normalized_path] = []
    LOGGER.info(
        "operation persisted op_id=%s type=%s entity=%s:%s apply_ms=%.2f append_ms=%.2f version=%s",
        operation.opId,
        operation.type,
        operation.entityType,
        operation.entityId,
        apply_ms,
        append_ms,
        database.version,
    )
    return operation


def _apply_operation(database: TopologyDatabase, operation: Operation, *, use_before: bool) -> None:
    values = operation.before if use_before else operation.after
    if operation.entityType == "cabinet":
        cabinet = _find_cabinet(database, operation.entityId)
        if cabinet is None:
            raise HTTPException(status_code=404, detail=f"Cabinet '{operation.entityId}' was not found.")
        if "lifecycle_status" in values:
            status = LifecycleStatus(values["lifecycle_status"])
            cabinet.lifecycle_status = status
            _update_room_cabinet_status(database, operation.entityId, status)
        return

    if operation.entityType == "device":
        device = _find_device(database, operation.entityId)
        if device is None:
            raise HTTPException(status_code=404, detail=f"Device '{operation.entityId}' was not found.")
        if "lifecycle_status" in values:
            status = LifecycleStatus(values["lifecycle_status"])
            device.lifecycle_status = status
            _update_room_device_status(database, operation.entityId, status)
        return

    if operation.entityType == "cable":
        cable = _find_cable(database, operation.entityId)
        if cable is None:
            raise HTTPException(status_code=404, detail=f"Cable '{operation.entityId}' was not found.")
        if "status" in values:
            cable.status = values["status"]
        if "progress" in values:
            cable.progress = {
                CableProgressStep(key): CableProgressState(value)
                for key, value in values["progress"].items()
            }
        if "current_phase" in values:
            cable.current_phase = normalize_cable_progress_phase(CableProgressPhase(**values["current_phase"]))
        if "length_used_meters" in values:
            cable.length_used_meters = values["length_used_meters"]
        if "note" in values:
            cable.note = values["note"]
        return

    raise HTTPException(status_code=422, detail=f"Unsupported operation entity type '{operation.entityType}'.")


def _append_operation(path: Path, operation: Operation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_model_to_payload(operation), separators=(",", ":")))
        handle.write("\n")


def _load_operations(path: Path) -> list[Operation]:
    if not path.exists():
        return []
    operations: list[Operation] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        operations.append(Operation(**json.loads(line)))
    return operations


def _parse_operation_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_operation_filter_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _replay_operations(database: TopologyDatabase, database_path: str) -> TopologyDatabase:
    for operation in _load_operations(_operations_path(database_path)):
        if operation.opId <= database.version:
            continue
        try:
            _apply_operation(database, operation, use_before=False)
        except HTTPException as exc:
            LOGGER.warning(
                "skipping operation replay op_id=%s entity=%s:%s status=%s detail=%s",
                operation.opId,
                operation.entityType,
                operation.entityId,
                exc.status_code,
                exc.detail,
            )
            database.version = max(database.version, operation.opId)
            continue
        database.version = operation.opId
    return database


def _schedule_snapshot_save(database: TopologyDatabase, database_path: str) -> None:
    normalized_path = _normalized_database_path(database_path)

    def save_snapshot() -> None:
        save_start = time.perf_counter()
        try:
            save_topology_database(database, database_path)
            LOGGER.info(
                "snapshot save complete path=%s version=%s save_ms=%.2f",
                normalized_path,
                database.version,
                (time.perf_counter() - save_start) * 1000,
            )
        finally:
            with _SNAPSHOT_LOCK:
                _SNAPSHOT_TIMERS.pop(normalized_path, None)

    with _SNAPSHOT_LOCK:
        timer = _SNAPSHOT_TIMERS.get(normalized_path)
        if timer is not None:
            timer.cancel()
        timer = threading.Timer(_SNAPSHOT_DEBOUNCE_SECONDS, save_snapshot)
        timer.daemon = True
        _SNAPSHOT_TIMERS[normalized_path] = timer
        timer.start()


def _operations_path(database_path: str) -> Path:
    path = Path(database_path)
    if path.name == DEFAULT_RUNTIME_DATABASE_PATH.name:
        return path.with_name("operations.jsonl")
    return path.with_name(f"{path.stem}.operations.jsonl")


def _normalized_database_path(database_path: str) -> str:
    return str(Path(database_path).resolve())


def _model_to_payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _log_operation_timing(operation: Operation, response_start: float) -> None:
    LOGGER.info(
        "operation response complete op_id=%s type=%s entity=%s:%s total_response_ms=%.2f",
        operation.opId,
        operation.type,
        operation.entityType,
        operation.entityId,
        (time.perf_counter() - response_start) * 1000,
    )


def _postgres_repository() -> PostgresTopologyRepository:
    return PostgresTopologyRepository(project_uid=DEFAULT_PROJECT_UID, building_id=DEFAULT_BUILDING_ID)


def _postgres_mutation_user(user: AuthUser) -> MutationUser:
    return MutationUser(uid=user.uid, display_name=user.display_name, role=user.role.value)


def _operation_from_postgres(operation: PersistedOperation) -> Operation:
    return Operation(
        opId=operation.id,
        type=operation.operation_type,
        entityType=operation.entity_type,
        entityId=operation.entity_uid,
        before=operation.before,
        after=operation.after,
        timestamp=operation.created_at.isoformat() if operation.created_at else "",
        userUid=operation.user_uid,
        userRole=operation.user_role,
        operationGroupUid=operation.operation_group_uid,
        sourceType=operation.source_type,
        sourceUid=operation.source_uid,
        sourceOperator=operation.source_operator,
    )


def _operation_from_db_operation(operation: db.OperationLog) -> Operation:
    return Operation(
        opId=operation.id,
        type=operation.operation_type,
        entityType=operation.entity_type,
        entityId=operation.entity_uid,
        before=operation.before,
        after=operation.after,
        timestamp=operation.created_at.isoformat() if operation.created_at else "",
        userUid=operation.user_uid,
        userRole=operation.user_role,
        operationGroupUid=operation.operation_group_uid,
        sourceType=operation.source_type,
        sourceUid=operation.source_uid,
        sourceOperator=operation.source_operator,
    )


def _postgres_entity_source_update_operations(
    session,
    *,
    entity_type: str,
    entity_uids: list[str],
) -> dict[str, list[db.OperationLog]]:
    if not entity_uids:
        return {}
    operations = session.execute(
        select(db.OperationLog)
        .where(
            db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
            db.OperationLog.entity_type == entity_type,
            db.OperationLog.entity_uid.in_(entity_uids),
            db.OperationLog.operation_type == "source_update",
        )
        .order_by(db.OperationLog.entity_uid, db.OperationLog.id.desc())
    ).scalars()
    by_entity: dict[str, list[db.OperationLog]] = {}
    for operation in operations:
        by_entity.setdefault(operation.entity_uid, []).append(operation)
    return by_entity


def _postgres_http_exception(exc: ValueError) -> HTTPException:
    detail = str(exc)
    if isinstance(exc, RowLockedConflict):
        return HTTPException(
            status_code=409,
            detail={
                "message": detail,
                "entity_type": exc.entity_type,
                "entity_uid": exc.entity_uid,
            },
        )
    if isinstance(exc, StaleWriteConflict):
        return HTTPException(
            status_code=409,
            detail={
                "message": detail,
                "entity_type": exc.entity_type,
                "entity_uid": exc.entity_uid,
                "expected_version": exc.expected_version,
                "current_version": exc.current_version,
            },
        )
    status_code = 404 if "was not found" in detail else 422
    return HTTPException(status_code=status_code, detail=detail)


def _postgres_cabinet_layout(data_hall: str | None = None) -> list[CabinetLayoutItem]:
    with session_factory()() as session:
        clauses = [
            db.Cabinet.project_uid == DEFAULT_PROJECT_UID,
            db.Cabinet.deleted_at.is_(None),
        ]
        if data_hall:
            clauses.append(db.Cabinet.room_uid == _postgres_room_uid(data_hall.upper()))

        rows = session.execute(
            select(db.Cabinet)
            .where(*clauses)
            .order_by(db.Cabinet.room_uid, db.Cabinet.source_row, db.Cabinet.source_col, db.Cabinet.cabinet_id)
        ).scalars()
        return [_postgres_layout_item(row) for row in rows]


def _postgres_data_hall_cable_summary(data_hall_id: str) -> DataHallCableSummaryResponse:
    room_uid = _postgres_room_uid(data_hall_id)
    with session_factory()() as session:
        a_port = aliased(db.Port)
        z_port = aliased(db.Port)
        rows = session.execute(
            select(
                a_port.room_uid.label("a_room_uid"),
                z_port.room_uid.label("z_room_uid"),
                db.Cable.cable_type,
                db.Cable.import_status,
                func.count().label("total_cables"),
            )
            .join(a_port, db.Cable.a_port_uid == a_port.uid)
            .join(z_port, db.Cable.z_port_uid == z_port.uid)
            .where(
                db.Cable.project_uid == DEFAULT_PROJECT_UID,
                db.Cable.deleted_at.is_(None),
                or_(a_port.room_uid == room_uid, z_port.room_uid == room_uid),
            )
            .group_by(a_port.room_uid, z_port.room_uid, db.Cable.cable_type, db.Cable.import_status)
        ).all()

    internal_rows = [row for row in rows if row.a_room_uid == room_uid and row.z_room_uid == room_uid]
    external_by_hall: dict[str, list] = {}
    for row in rows:
        other_room_uid = None
        if row.a_room_uid == room_uid and row.z_room_uid != room_uid:
            other_room_uid = row.z_room_uid
        elif row.z_room_uid == room_uid and row.a_room_uid != room_uid:
            other_room_uid = row.a_room_uid
        if other_room_uid:
            external_by_hall.setdefault(other_room_uid.rsplit(":", 1)[-1], []).append(row)

    return DataHallCableSummaryResponse(
        data_hall_id=data_hall_id,
        internal=_postgres_data_hall_bucket("internal", internal_rows),
        external=[
            _postgres_data_hall_bucket("external", target_rows, target_data_hall=target_data_hall)
            for target_data_hall, target_rows in sorted(external_by_hall.items())
        ],
    )


def _postgres_topology_enums() -> TopologyEnumResponse:
    with session_factory()() as session:
        imported_statuses = sorted(
            status or "Unknown"
            for status in session.execute(
                select(db.Cable.import_status)
                .where(db.Cable.project_uid == DEFAULT_PROJECT_UID, db.Cable.deleted_at.is_(None))
                .distinct()
            ).scalars()
        )
    phase_definitions = cable_progress_phase_definitions()
    return TopologyEnumResponse(
        lifecycle_statuses=[status.value for status in LifecycleStatus],
        construction_phases=[phase.value for phase in ConstructionPhase],
        cable_import_statuses=imported_statuses,
        cable_progress_steps=[step.value for step in CableProgressStep],
        cable_progress_states=[state.value for state in CableProgressState],
        cable_progress_phase_types=[phase_type.value for phase_type in CableProgressPhaseType],
        cable_progress_phase_names=[phase.name for phase in phase_definitions],
        cable_progress_phases=[
            CableProgressPhaseDefinitionResponse(
                name=phase.name,
                tasks=[
                    CableProgressTaskDefinitionResponse(
                        name=task.name,
                        task_type=task.task_type.value,
                        enum_values=list(task.enum_values),
                        default_value=task.default_value,
                    )
                    for task in phase.tasks
                ],
            )
            for phase in phase_definitions
        ],
    )


def _postgres_cabinet_detail(cabinet_uid: str) -> CabinetDetailResponse:
    with session_factory()() as session:
        cabinet_row = session.get(db.Cabinet, cabinet_uid)
        if cabinet_row is None or cabinet_row.deleted_at is not None or cabinet_row.project_uid != DEFAULT_PROJECT_UID:
            raise HTTPException(status_code=404, detail=f"Cabinet '{cabinet_uid}' was not found.")

        port_rows = list(
            session.execute(
                select(db.Port)
                .where(db.Port.cabinet_uid == cabinet_uid, db.Port.deleted_at.is_(None))
                .order_by(db.Port.device_uid, db.Port.uid)
            ).scalars()
        )
        ports_by_device: dict[str, dict[ConnectorType, list[PortConnector]]] = {}
        for port_row in port_rows:
            if not port_row.device_uid:
                continue
            connector_type = _postgres_connector_type(port_row.connector_type)
            ports_by_device.setdefault(port_row.device_uid, {}).setdefault(connector_type, []).append(
                PortConnector(uid=port_row.uid, type=connector_type, note=port_row.note)
            )

        device_rows = session.execute(
            select(db.Device)
            .where(db.Device.cabinet_uid == cabinet_uid, db.Device.deleted_at.is_(None))
            .order_by(db.Device.rack_unit, db.Device.device_model_name, db.Device.uid)
        ).scalars()
        device_change_operations = _postgres_entity_source_update_operations(
            session,
            entity_type="device",
            entity_uids=[row.uid for row in device_rows],
        )
        device_rows = session.execute(
            select(db.Device)
            .where(db.Device.cabinet_uid == cabinet_uid, db.Device.deleted_at.is_(None))
            .order_by(db.Device.rack_unit, db.Device.device_model_name, db.Device.uid)
        ).scalars()
        devices = [
            Device(
                cabinet_id=row.cabinet_uid,
                rack_unit=row.rack_unit,
                device_model=row.device_model_name,
                device_model_uid=row.device_model_uid or "",
                rack_units=row.rack_units,
                lifecycle_status=LifecycleStatus(row.lifecycle_status),
                construction_phase=ConstructionPhase(row.construction_phase),
                aliases=list(row.aliases),
                model_aliases=list(row.model_aliases),
                port_layout_overrides=[_postgres_model_from_payload(DevicePortLayoutEntry, item) for item in row.port_layout_overrides],
                ports_by_type={
                    connector_type: ports
                    for connector_type, ports in sorted(
                        ports_by_device.get(row.uid, {}).items(),
                        key=lambda item: item[0].value,
                    )
                },
                change_operations=[
                    _operation_from_db_operation(operation)
                    for operation in device_change_operations.get(row.uid, [])
                ],
                note=row.note,
            )
            for row in device_rows
        ]

        cable_rows = _postgres_cables_for_cabinet(session, cabinet_uid)
        grouped_cables_by_target = _postgres_group_cables_by_target(cable_rows, cabinet_uid)
        connection_target_uids = {
            _postgres_other_cabinet_uid(row.a_cabinet_uid, row.z_cabinet_uid, cabinet_uid)
            for row in cable_rows
        }
        operation_target_uids = _postgres_source_update_target_cabinet_uids(session, cabinet_uid)
        all_connection_target_uids = connection_target_uids | operation_target_uids
        target_rows = {
            row.uid: row
            for row in session.execute(
                select(db.Cabinet).where(db.Cabinet.uid.in_(all_connection_target_uids), db.Cabinet.deleted_at.is_(None))
            ).scalars()
        } if all_connection_target_uids else {}

        connections: list[CabinetConnection] = []
        intra_cabinet_connection = None
        for target_uid in sorted(all_connection_target_uids):
            target_cables = grouped_cables_by_target.get(target_uid, [])
            target = target_rows.get(target_uid)
            connection = CabinetConnection(
                target_cabinet_uid=target_uid,
                target_category=target.category if target else "",
                target_cabinet_group=target.cabinet_group if target else "",
                total_cables=len(target_cables),
                cable_type_counts=_postgres_count_by(target_cables, "cable_type"),
                status_summary=_postgres_status_summary(target_cables),
                change_order_stats=_postgres_source_update_counts_for_cabinet_pair(
                    session,
                    source_cabinet_uid=cabinet_uid,
                    target_cabinet_uid=target_uid,
                ),
            )
            if target_uid == cabinet_uid:
                intra_cabinet_connection = connection
            else:
                connections.append(connection)

        cable_termination_percent, cable_dress_percent = _postgres_cabinet_progress_stats(cable_rows, cabinet_uid)
        cable_type_counts = _postgres_count_by(cable_rows, "cable_type")
        return CabinetDetailResponse(
            cabinet=_postgres_layout_item(
                cabinet_row,
                cable_termination_percent=cable_termination_percent,
                cable_dress_percent=cable_dress_percent,
            ),
            stats=CabinetStats(
                devices=len(devices),
                ports=len(port_rows),
                cables=len(cable_rows),
                connected_cabinets=len({connection.target_cabinet_uid for connection in connections}),
                cable_termination_percent=cable_termination_percent,
                cable_dress_percent=cable_dress_percent,
                cable_type_counts=cable_type_counts,
            ),
            devices=devices,
            intra_cabinet_connection=intra_cabinet_connection,
            connections=sorted(connections, key=lambda connection: (-connection.total_cables, connection.target_cabinet_uid)),
            change_operations=[
                _operation_from_db_operation(operation)
                for operation in _postgres_entity_source_update_operations(
                    session,
                    entity_type="cabinet",
                    entity_uids=[cabinet_uid],
                ).get(cabinet_uid, [])
            ],
        )


def _postgres_data_hall_cables(
    data_hall_id: str,
    *,
    scope: str,
    target_data_hall: str | None,
    cable_type: str | None,
    limit: int,
    offset: int,
) -> CabinetCableDetailResponse:
    room_uid = _postgres_room_uid(data_hall_id)
    source_port_prefix = f"{data_hall_id}:"
    normalized_target_data_hall = target_data_hall.upper() if target_data_hall else None
    target_port_prefix = f"{normalized_target_data_hall}:" if normalized_target_data_hall else None
    with session_factory()() as session:
        if session.get(db.Room, room_uid) is None:
            raise HTTPException(status_code=404, detail=f"Data hall '{data_hall_id}' was not found.")
        clauses: list[Any] = [
            db.Cable.project_uid == DEFAULT_PROJECT_UID,
            db.Cable.deleted_at.is_(None),
        ]
        if scope == "internal":
            clauses.extend([
                db.Cable.a_port_uid.like(f"{source_port_prefix}%"),
                db.Cable.z_port_uid.like(f"{source_port_prefix}%"),
            ])
            target_label = data_hall_id
        elif scope == "external":
            if target_port_prefix is not None:
                clauses.append(
                    or_(
                        and_(
                            db.Cable.a_port_uid.like(f"{source_port_prefix}%"),
                            db.Cable.z_port_uid.like(f"{target_port_prefix}%"),
                        ),
                        and_(
                            db.Cable.a_port_uid.like(f"{target_port_prefix}%"),
                            db.Cable.z_port_uid.like(f"{source_port_prefix}%"),
                        ),
                    )
                )
            else:
                clauses.append(
                    or_(
                        and_(
                            db.Cable.a_port_uid.like(f"{source_port_prefix}%"),
                            ~db.Cable.z_port_uid.like(f"{source_port_prefix}%"),
                        ),
                        and_(
                            db.Cable.z_port_uid.like(f"{source_port_prefix}%"),
                            ~db.Cable.a_port_uid.like(f"{source_port_prefix}%"),
                        ),
                    )
                )
            target_label = normalized_target_data_hall if normalized_target_data_hall else "EXTERNAL"
        else:
            raise HTTPException(status_code=422, detail="scope must be 'internal' or 'external'.")
        if cable_type:
            clauses.append(db.Cable.cable_type == cable_type)
        total_cables = session.scalar(select(func.count()).select_from(db.Cable).where(*clauses)) or 0
        filtered_cable_uids = (
            select(db.Cable.uid)
            .where(*clauses)
            .cte("filtered_data_hall_cables")
            .prefix_with("MATERIALIZED")
        )
        rows = list(
            session.execute(
                select(*_postgres_cable_detail_columns())
                .join(filtered_cable_uids, db.Cable.uid == filtered_cable_uids.c.uid)
                .order_by(db.Cable.cable_type, db.Cable.a_port_uid, db.Cable.z_port_uid, db.Cable.uid)
                .offset(offset)
                .limit(limit)
            ).scalars()
        )
        change_statuses = _postgres_source_update_statuses(session, [row.uid for row in rows])
        removed_cables = _postgres_removed_cable_details_for_data_hall_scope(
            session,
            data_hall_id=data_hall_id,
            scope=scope,
            target_data_hall=normalized_target_data_hall,
        )
    return CabinetCableDetailResponse(
        source_cabinet_uid=data_hall_id,
        target_cabinet_uid=target_label,
        cables=[_postgres_cable_detail(row, change_status=change_statuses.get(row.uid, "green")) for row in rows] + removed_cables,
        total_cables=total_cables,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total_cables,
    )


def _postgres_cabinet_connection_cables(source_cabinet_uid: str, target_cabinet_uid: str) -> CabinetCableDetailResponse:
    with session_factory()() as session:
        _postgres_require_cabinet(session, source_cabinet_uid)
        _postgres_require_cabinet(session, target_cabinet_uid)
        rows = _postgres_cable_detail_models(
            session,
            clauses=[
                db.Cable.project_uid == DEFAULT_PROJECT_UID,
                db.Cable.deleted_at.is_(None),
                _postgres_bidirectional_port_scope_clause(
                    _postgres_port_uid_scope(cabinet_uid=source_cabinet_uid),
                    _postgres_port_uid_scope(cabinet_uid=target_cabinet_uid),
                ),
            ],
        )
        change_statuses = _postgres_source_update_statuses(session, [row.uid for row in rows])
        operation_cables = _postgres_source_update_cable_details_for_cabinet_pair(
            session,
            source_cabinet_uid=source_cabinet_uid,
            target_cabinet_uid=target_cabinet_uid,
            excluded_uids={row.uid for row in rows},
        )
    return CabinetCableDetailResponse(
        source_cabinet_uid=source_cabinet_uid,
        target_cabinet_uid=target_cabinet_uid,
        cables=sorted(
            [_postgres_cable_detail(row, change_status=change_statuses.get(row.uid, "green")) for row in rows] + operation_cables,
            key=lambda cable: (cable.cable_type, cable.a_port_uid, cable.z_port_uid),
        ),
    )


def _postgres_device_connection_cables(source_device_uid: str, target_device_uid: str) -> DeviceCableDetailResponse:
    source_device_uid = _normalize_device_uid(source_device_uid)
    target_device_uid = _normalize_device_uid(target_device_uid)
    with session_factory()() as session:
        _postgres_require_device(session, source_device_uid)
        _postgres_require_device(session, target_device_uid)
        rows = _postgres_cable_detail_models(
            session,
            clauses=[
                db.Cable.project_uid == DEFAULT_PROJECT_UID,
                db.Cable.deleted_at.is_(None),
                _postgres_bidirectional_port_scope_clause(
                    _postgres_port_uid_scope(device_uid=source_device_uid),
                    _postgres_port_uid_scope(device_uid=target_device_uid),
                ),
            ],
        )
        change_statuses = _postgres_source_update_statuses(session, [row.uid for row in rows])
        operation_cables = _postgres_source_update_cable_details_for_port_scopes(
            session,
            source_scope=_postgres_port_uid_scope(device_uid=source_device_uid),
            target_scope=_postgres_port_uid_scope(device_uid=target_device_uid),
            excluded_uids={row.uid for row in rows},
        )
    return DeviceCableDetailResponse(
        source_device_uid=source_device_uid,
        target_device_uid=target_device_uid,
        cables=sorted(
            [_postgres_cable_detail(row, change_status=change_statuses.get(row.uid, "green")) for row in rows] + operation_cables,
            key=lambda cable: (cable.cable_type, cable.a_port_uid, cable.z_port_uid),
        ),
    )


def _postgres_device_connections(source_device_uid: str) -> DeviceConnectionResponse:
    with session_factory()() as session:
        try:
            summary = pg_queries.device_connections(session, source_device_uid=source_device_uid)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DeviceConnectionResponse(
        source_device_uid=summary.source_device_uid,
        source_cabinet_uid=summary.source_cabinet_uid,
        source_rack_unit=summary.source_rack_unit,
        connected_cabinet_uids=summary.connected_cabinet_uids,
        connected_devices=[
            DeviceConnection(
                target_device_uid=connection.target_device_uid,
                target_device_model=connection.target_device_model,
                target_cabinet_uid=connection.target_cabinet_uid,
                target_rack_unit=connection.target_rack_unit,
                total_cables=connection.total_cables,
                cable_type_counts=connection.cable_type_counts,
                status_summary=CableStatusSummary(
                    completed=connection.status_summary.completed,
                    total=connection.status_summary.total,
                    status_counts=connection.status_summary.status_counts,
                ),
            )
            for connection in summary.connected_devices
        ],
    )


def _postgres_layout_item(
    row: db.Cabinet,
    cable_termination_percent: float = 0.0,
    cable_dress_percent: float = 0.0,
) -> CabinetLayoutItem:
    data_hall_id = row.room_uid.rsplit(":", 1)[-1]
    return CabinetLayoutItem(
        cabinet_uid=row.uid,
        data_hall_id=data_hall_id,
        cabinet_id=row.cabinet_id,
        category=row.category,
        cabinet_group=row.cabinet_group,
        lifecycle_status=row.lifecycle_status,
        construction_phase=row.construction_phase,
        max_rack_unit=row.max_rack_unit,
        cable_termination_percent=cable_termination_percent,
        cable_dress_percent=cable_dress_percent,
        source_row=row.source_row,
        source_col=row.source_col,
    )


def _postgres_cables_for_cabinet(session, cabinet_uid: str):
    a_port = aliased(db.Port)
    z_port = aliased(db.Port)
    cabinet_ports = _postgres_port_uid_scope(cabinet_uid=cabinet_uid)
    return session.execute(
        select(
            db.Cable.uid,
            db.Cable.cable_type,
            db.Cable.import_status,
            db.Cable.current_phase,
            db.Cable.a_port_uid,
            db.Cable.z_port_uid,
            a_port.cabinet_uid.label("a_cabinet_uid"),
            z_port.cabinet_uid.label("z_cabinet_uid"),
        )
        .join(a_port, db.Cable.a_port_uid == a_port.uid)
        .join(z_port, db.Cable.z_port_uid == z_port.uid)
        .where(
            db.Cable.project_uid == DEFAULT_PROJECT_UID,
            db.Cable.deleted_at.is_(None),
            or_(db.Cable.a_port_uid.in_(cabinet_ports), db.Cable.z_port_uid.in_(cabinet_ports)),
        )
    ).all()


def _postgres_cable_detail_columns():
    return (
        db.Cable.uid,
        db.Cable.cable_group,
        db.Cable.import_status,
        db.Cable.cable_type,
        db.Cable.construction_phase,
        db.Cable.progress,
        db.Cable.current_phase,
        db.Cable.designed_length_meters,
        db.Cable.length_used_meters,
        db.Cable.note,
        db.Cable.a_port_uid,
        db.Cable.z_port_uid,
        db.Cable.a_optic,
        db.Cable.z_optic,
    )


def _postgres_cable_detail_models(
    session,
    *,
    clauses: list[Any],
    limit: int | None = None,
    offset: int | None = None,
):
    statement = select(*_postgres_cable_detail_columns()).where(*clauses).order_by(db.Cable.cable_type, db.Cable.a_port_uid, db.Cable.z_port_uid, db.Cable.uid)
    if offset is not None:
        statement = statement.offset(offset)
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.execute(statement).all())


def _postgres_port_uid_scope(
    *,
    cabinet_uid: str | None = None,
    device_uid: str | None = None,
    room_uid: str | None = None,
):
    clauses = [db.Port.deleted_at.is_(None)]
    if cabinet_uid is not None:
        clauses.append(db.Port.cabinet_uid == cabinet_uid)
    if device_uid is not None:
        clauses.append(db.Port.device_uid == device_uid)
    if room_uid is not None:
        clauses.append(db.Port.room_uid == room_uid)
    return select(db.Port.uid).where(*clauses)


def _postgres_bidirectional_port_scope_clause(source_ports, target_ports):
    return or_(
        and_(db.Cable.a_port_uid.in_(source_ports), db.Cable.z_port_uid.in_(target_ports)),
        and_(db.Cable.a_port_uid.in_(target_ports), db.Cable.z_port_uid.in_(source_ports)),
    )


def _postgres_cable_detail(row, *, change_status: str = "green") -> CabinetCableDetail:
    progress = {
        str(key): value.value if hasattr(value, "value") else str(value)
        for key, value in (row.progress or {}).items()
    }
    current_phase = _postgres_optional_model(CableProgressPhase, row.current_phase)
    return CabinetCableDetail(
        uid=row.uid,
        group=row.cable_group,
        status=row.import_status,
        cable_type=row.cable_type,
        construction_phase=row.construction_phase,
        a_label_text=getattr(row, "a_label_text", ""),
        z_label_text=getattr(row, "z_label_text", ""),
        progress=progress,
        current_phase=normalize_cable_progress_phase(current_phase) if current_phase is not None else None,
        designed_length_meters=float(row.designed_length_meters) if row.designed_length_meters is not None else None,
        length_used_meters=float(row.length_used_meters or 0),
        length_meters=float(row.length_used_meters) if row.length_used_meters else None,
        note=row.note,
        a_port_uid=row.a_port_uid,
        z_port_uid=row.z_port_uid,
        a_optic=_postgres_optic_model(row.a_optic),
        z_optic=_postgres_optic_model(row.z_optic),
        change_status=change_status,
    )


def _postgres_source_update_statuses(session, cable_uids: list[str]) -> dict[str, str]:
    if not cable_uids:
        return {}
    operations = session.execute(
        select(db.OperationLog)
        .where(
            db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
            db.OperationLog.entity_type == "cable",
            db.OperationLog.entity_uid.in_(cable_uids),
            db.OperationLog.operation_type == "source_update",
        )
        .order_by(db.OperationLog.entity_uid, db.OperationLog.id.desc())
    ).scalars()
    statuses: dict[str, str] = {}
    for operation in operations:
        if operation.entity_uid in statuses:
            continue
        statuses[operation.entity_uid] = _change_status_from_operation(operation)
    return statuses


def _postgres_cabinet_change_order_cables(
    cabinet_uid: str,
    change_status: str | None,
    change_order_keys: set[str] | None = None,
) -> CabinetCableDetailResponse:
    allowed_statuses = {"red", "yellow", "cyan", "replaced"}
    change_order_keys = change_order_keys or set()
    normalized_status = change_status.lower() if change_status else None
    if normalized_status is not None and normalized_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="change_status must be one of red, yellow, cyan, or replaced.")

    with session_factory()() as session:
        _postgres_require_cabinet(session, cabinet_uid)
        operations = session.execute(
            select(db.OperationLog)
            .where(
                db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
                db.OperationLog.entity_type == "cable",
                db.OperationLog.operation_type == "source_update",
            )
            .order_by(db.OperationLog.id.desc())
        ).scalars()
        latest_operation_ids = _latest_source_update_operation_ids(session)
        details: list[CabinetCableDetail] = []
        seen: set[str] = set()
        for operation in operations:
            if change_order_keys and _operation_change_order_key(operation) not in change_order_keys:
                continue
            if not change_order_keys and operation.entity_uid in seen:
                continue
            detail = _source_update_cable_detail_for_cabinet(
                operation,
                cabinet_uid,
                is_replaced=latest_operation_ids.get(operation.entity_uid) not in {None, operation.id},
            )
            if detail is None:
                continue
            if normalized_status is not None and detail.change_status != normalized_status:
                continue
            details.append(detail)
            if not change_order_keys:
                seen.add(operation.entity_uid)

    status_label = normalized_status or "all"
    return CabinetCableDetailResponse(
        source_cabinet_uid=cabinet_uid,
        target_cabinet_uid=f"change-order-{status_label}",
        cables=sorted(details, key=lambda cable: (cable.change_status, cable.cable_type, cable.a_port_uid, cable.z_port_uid, cable.uid)),
    )


def _latest_source_update_operation_ids(session) -> dict[str, int]:
    operations = session.execute(
        select(db.OperationLog.entity_uid, func.max(db.OperationLog.id))
        .where(
            db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
            db.OperationLog.entity_type == "cable",
            db.OperationLog.operation_type == "source_update",
        )
        .group_by(db.OperationLog.entity_uid)
    ).all()
    return {entity_uid: operation_id for entity_uid, operation_id in operations if entity_uid and operation_id is not None}


def _operation_change_order_key(operation: db.OperationLog) -> str:
    return operation.source_uid or operation.source_operator or operation.operation_group_uid or ""

def _postgres_source_update_target_cabinet_uids(session, cabinet_uid: str) -> set[str]:
    operations = session.execute(
        select(db.OperationLog)
        .where(
            db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
            db.OperationLog.entity_type == "cable",
            db.OperationLog.operation_type == "source_update",
        )
        .order_by(db.OperationLog.id.desc())
    ).scalars()
    target_uids: set[str] = set()
    seen: set[str] = set()
    for operation in operations:
        if operation.entity_uid in seen:
            continue
        seen.add(operation.entity_uid)
        change_status = _change_status_from_operation(operation)
        records = [_source_update_display_record(operation, change_status)]
        if change_status == "yellow":
            records = [
                _source_update_record(operation, "old_record", operation.before),
                _source_update_record(operation, "new_record", operation.after),
            ]
        for record in records:
            target_uid = _source_update_record_peer_cabinet_uid(record, cabinet_uid)
            if target_uid:
                target_uids.add(target_uid)
    return target_uids


def _source_update_record_peer_cabinet_uid(record: dict[str, Any], cabinet_uid: str) -> str | None:
    a_cabinet_uid = _cabinet_uid_from_port_uid(record.get("a_port_uid"))
    z_cabinet_uid = _cabinet_uid_from_port_uid(record.get("z_port_uid"))
    if a_cabinet_uid == cabinet_uid and z_cabinet_uid:
        return z_cabinet_uid
    if z_cabinet_uid == cabinet_uid and a_cabinet_uid:
        return a_cabinet_uid
    return None


def _cabinet_uid_from_port_uid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parts = value.split(":")
    if len(parts) < 2:
        return None
    return f"{parts[0].upper()}:{parts[1].zfill(3)}"


def _postgres_source_update_counts_for_cabinet_pair(
    session,
    *,
    source_cabinet_uid: str,
    target_cabinet_uid: str,
) -> ChangeOrderDiffStats | None:
    operations = session.execute(
        select(db.OperationLog)
        .where(
            db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
            db.OperationLog.entity_type == "cable",
            db.OperationLog.operation_type == "source_update",
        )
        .order_by(db.OperationLog.id.desc())
    ).scalars()
    stats = ChangeOrderDiffStats()
    seen: set[str] = set()
    for operation in operations:
        if operation.entity_uid in seen:
            continue
        change_status = _change_status_from_operation(operation)
        old_record = _source_update_record(operation, "old_record", operation.before)
        new_record = _source_update_record(operation, "new_record", operation.after)
        if change_status == "red":
            matches = _source_update_record_matches_cabinet_pair(old_record, source_cabinet_uid, target_cabinet_uid)
        elif change_status == "cyan":
            matches = _source_update_record_matches_cabinet_pair(new_record, source_cabinet_uid, target_cabinet_uid)
        elif change_status == "yellow":
            matches = (
                _source_update_record_matches_cabinet_pair(old_record, source_cabinet_uid, target_cabinet_uid)
                or _source_update_record_matches_cabinet_pair(new_record, source_cabinet_uid, target_cabinet_uid)
            )
        else:
            matches = False
        if not matches:
            continue
        if change_status == "red":
            stats.removed += 1
        elif change_status == "yellow":
            stats.changed += 1
        elif change_status == "cyan":
            stats.added += 1
        seen.add(operation.entity_uid)
    return stats if stats.removed or stats.changed or stats.added else None


def _postgres_source_update_cable_details_for_cabinet_pair(
    session,
    *,
    source_cabinet_uid: str,
    target_cabinet_uid: str,
    excluded_uids: set[str] | None = None,
) -> list[CabinetCableDetail]:
    excluded_uids = excluded_uids or set()
    source_prefix = f"{source_cabinet_uid}:"
    target_prefix = f"{target_cabinet_uid}:"
    operations = session.execute(
        select(db.OperationLog)
        .where(
            db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
            db.OperationLog.entity_type == "cable",
            db.OperationLog.operation_type == "source_update",
        )
        .order_by(db.OperationLog.id.desc())
    ).scalars()
    details: list[CabinetCableDetail] = []
    seen: set[str] = set()
    for operation in operations:
        if operation.entity_uid in seen or operation.entity_uid in excluded_uids:
            continue
        detail = _source_update_cable_detail_from_operation(operation)
        if detail is None:
            continue
        if (
            detail.a_port_uid.startswith(source_prefix) and detail.z_port_uid.startswith(target_prefix)
        ) or (
            detail.a_port_uid.startswith(target_prefix) and detail.z_port_uid.startswith(source_prefix)
        ):
            details.append(detail)
            seen.add(operation.entity_uid)
    return details

def _postgres_source_update_cable_details_for_port_scopes(
    session,
    *,
    source_scope,
    target_scope,
    excluded_uids: set[str] | None = None,
) -> list[CabinetCableDetail]:
    source_ports = set(session.execute(source_scope).scalars())
    target_ports = set(session.execute(target_scope).scalars())
    if not source_ports or not target_ports:
        return []
    excluded_uids = excluded_uids or set()
    operations = session.execute(
        select(db.OperationLog)
        .where(
            db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
            db.OperationLog.entity_type == "cable",
            db.OperationLog.operation_type == "source_update",
        )
        .order_by(db.OperationLog.id.desc())
    ).scalars()
    details: list[CabinetCableDetail] = []
    seen: set[str] = set()
    for operation in operations:
        if operation.entity_uid in seen or operation.entity_uid in excluded_uids:
            continue
        detail = _source_update_cable_detail_from_operation(operation)
        if detail is None:
            continue
        if (
            detail.a_port_uid in source_ports and detail.z_port_uid in target_ports
        ) or (
            detail.a_port_uid in target_ports and detail.z_port_uid in source_ports
        ):
            details.append(detail)
            seen.add(operation.entity_uid)
    return details

def _postgres_removed_cable_details_for_data_hall_scope(
    session,
    *,
    data_hall_id: str,
    scope: str,
    target_data_hall: str | None,
) -> list[CabinetCableDetail]:
    details: list[CabinetCableDetail] = []
    seen: set[str] = set()
    for operation in _postgres_removed_cable_operations(session):
        if operation.entity_uid in seen:
            continue
        detail = _removed_cable_detail_from_operation(operation)
        if detail is None:
            continue
        a_hall = detail.a_port_uid.split(":", 1)[0].upper()
        z_hall = detail.z_port_uid.split(":", 1)[0].upper()
        if scope == "internal" and a_hall == data_hall_id and z_hall == data_hall_id:
            details.append(detail)
            seen.add(operation.entity_uid)
        elif scope == "external" and target_data_hall and {a_hall, z_hall} == {data_hall_id, target_data_hall}:
            details.append(detail)
            seen.add(operation.entity_uid)
        elif scope == "external" and target_data_hall is None and (a_hall == data_hall_id) != (z_hall == data_hall_id):
            details.append(detail)
            seen.add(operation.entity_uid)
    return details


def _postgres_removed_cable_operations(session) -> list[db.OperationLog]:
    return list(
        session.execute(
            select(db.OperationLog)
            .where(
                db.OperationLog.project_uid == DEFAULT_PROJECT_UID,
                db.OperationLog.entity_type == "cable",
                db.OperationLog.operation_type == "source_update",
            )
            .order_by(db.OperationLog.id.desc())
        ).scalars()
    )


def _change_status_from_operation(operation: db.OperationLog) -> str:
    change_type = str((operation.after or {}).get("change_type") or "").lower()
    if change_type == "removed":
        return "red"
    if change_type == "added":
        return "cyan"
    if change_type == "changed":
        return "yellow"
    return "green"


def _source_update_cable_detail_from_operation(operation: db.OperationLog) -> CabinetCableDetail | None:
    change_status = _change_status_from_operation(operation)
    record = _source_update_display_record(operation, change_status)
    return _cable_detail_from_source_update_record(operation, record, change_status=change_status)


def _source_update_cable_detail_for_cabinet(operation: db.OperationLog, cabinet_uid: str, *, is_replaced: bool = False) -> CabinetCableDetail | None:
    base_change_status = _change_status_from_operation(operation)
    display_change_status = "replaced" if is_replaced else base_change_status
    old_record = _source_update_record(operation, "old_record", operation.before)
    new_record = _source_update_record(operation, "new_record", operation.after)
    match_records = [old_record, new_record] if base_change_status == "yellow" else [_source_update_display_record(operation, base_change_status)]
    if not any(_source_update_record_matches_cabinet(record, cabinet_uid) for record in match_records):
        return None
    return _cable_detail_from_source_update_record(
        operation,
        _source_update_display_record(operation, base_change_status),
        change_status=display_change_status,
    )
def _source_update_display_record(operation: db.OperationLog, change_status: str) -> dict[str, Any]:
    if change_status == "red":
        return _source_update_record(operation, "old_record", operation.before)
    return _source_update_record(operation, "new_record", operation.after)


def _source_update_record(operation: db.OperationLog, key: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    record = payload.get(key)
    return record if isinstance(record, dict) else payload


def _source_update_record_matches_cabinet(record: dict[str, Any], cabinet_uid: str) -> bool:
    cabinet_prefix = f"{cabinet_uid}:"
    return str(record.get("a_port_uid") or "").startswith(cabinet_prefix) or str(record.get("z_port_uid") or "").startswith(cabinet_prefix)


def _source_update_record_matches_cabinet_pair(record: dict[str, Any], source_cabinet_uid: str, target_cabinet_uid: str) -> bool:
    source_prefix = f"{source_cabinet_uid}:"
    target_prefix = f"{target_cabinet_uid}:"
    a_port_uid = str(record.get("a_port_uid") or "")
    z_port_uid = str(record.get("z_port_uid") or "")
    return (
        a_port_uid.startswith(source_prefix) and z_port_uid.startswith(target_prefix)
    ) or (
        a_port_uid.startswith(target_prefix) and z_port_uid.startswith(source_prefix)
    )


def _removed_cable_detail_from_operation(operation: db.OperationLog) -> CabinetCableDetail | None:
    payload = operation.before or {}
    record = payload.get("old_record") if isinstance(payload, dict) else None
    if not isinstance(record, dict):
        record = payload if isinstance(payload, dict) else {}
    return _cable_detail_from_source_update_record(operation, record, change_status="red")


def _cable_detail_from_source_update_record(
    operation: db.OperationLog,
    record: dict[str, Any],
    *,
    change_status: str,
) -> CabinetCableDetail | None:
    a_port_uid = str(record.get("a_port_uid") or "")
    z_port_uid = str(record.get("z_port_uid") or "")
    if not a_port_uid or not z_port_uid:
        return None
    return CabinetCableDetail(
        uid=str(record.get("cable_uid") or record.get("uid") or operation.entity_uid),
        group=str(record.get("cable_group") or record.get("group") or ""),
        status=str(record.get("status") or record.get("import_status") or ""),
        cable_type=str(record.get("cable_type") or ""),
        construction_phase=str(record.get("construction_phase") or ""),
        progress={},
        current_phase=None,
        designed_length_meters=_float_or_none(record.get("designed_length_meters")),
        length_used_meters=float(record.get("length_used_meters") or 0),
        length_meters=float(record.get("length_used_meters") or 0) if record.get("length_used_meters") else None,
        note=str(record.get("note") or ""),
        a_port_uid=a_port_uid,
        z_port_uid=z_port_uid,
        a_optic=_postgres_optic_model(record.get("a_optic") if isinstance(record.get("a_optic"), dict) else None),
        z_optic=_postgres_optic_model(record.get("z_optic") if isinstance(record.get("z_optic"), dict) else None),
        change_status=change_status,
    )


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _postgres_optic_model(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    model = payload.get("model")
    return str(model) if model is not None else ""


def _postgres_require_cabinet(session, cabinet_uid: str) -> None:
    cabinet = session.get(db.Cabinet, cabinet_uid)
    if cabinet is None or cabinet.deleted_at is not None or cabinet.project_uid != DEFAULT_PROJECT_UID:
        raise HTTPException(status_code=404, detail=f"Cabinet '{cabinet_uid}' was not found.")


def _postgres_require_device(session, device_uid: str) -> None:
    device = session.get(db.Device, device_uid)
    if device is None or device.deleted_at is not None or device.project_uid != DEFAULT_PROJECT_UID:
        raise HTTPException(status_code=404, detail=f"Device '{device_uid}' was not found.")


def _postgres_group_cables_by_target(cable_rows, cabinet_uid: str):
    grouped: dict[str, list] = {}
    for row in cable_rows:
        target_uid = _postgres_other_cabinet_uid(row.a_cabinet_uid, row.z_cabinet_uid, cabinet_uid)
        grouped.setdefault(target_uid, []).append(row)
    return grouped


def _postgres_other_cabinet_uid(a_cabinet_uid: str, z_cabinet_uid: str, cabinet_uid: str) -> str:
    if a_cabinet_uid == cabinet_uid and z_cabinet_uid == cabinet_uid:
        return cabinet_uid
    return z_cabinet_uid if a_cabinet_uid == cabinet_uid else a_cabinet_uid


def _postgres_cabinet_progress_stats(cable_rows, cabinet_uid: str) -> tuple[float, float]:
    termination_total = 0.0
    dress_total = 0.0
    endpoint_count = 0
    for row in cable_rows:
        current_phase = _postgres_optional_model(CableProgressPhase, row.current_phase)
        if row.a_cabinet_uid == cabinet_uid:
            termination, dress = cable_endpoint_termination_and_dress_percent(current_phase, "a")
            termination_total += termination
            dress_total += dress
            endpoint_count += 1
        if row.z_cabinet_uid == cabinet_uid:
            termination, dress = cable_endpoint_termination_and_dress_percent(current_phase, "z")
            termination_total += termination
            dress_total += dress
            endpoint_count += 1
    if endpoint_count == 0:
        return 0.0, 0.0
    return round(termination_total / endpoint_count, 1), round(dress_total / endpoint_count, 1)


def _postgres_status_summary(rows) -> CableStatusSummary:
    return CableStatusSummary(
        completed=sum(_postgres_row_count(row) for row in rows if _is_completed_status(row.import_status)),
        total=sum(_postgres_row_count(row) for row in rows),
        status_counts=_postgres_count_by(rows, "import_status"),
    )


def _postgres_data_hall_bucket(
    scope: str,
    rows,
    target_data_hall: str | None = None,
) -> DataHallCableBucket:
    return DataHallCableBucket(
        scope=scope,
        target_data_hall=target_data_hall,
        total_cables=sum(_postgres_row_count(row) for row in rows),
        cable_type_counts=_postgres_count_by(rows, "cable_type"),
        status_summary=_postgres_status_summary(rows),
    )


def _postgres_count_by(rows, attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = getattr(row, attribute) or "Unknown"
        counts[value] = counts.get(value, 0) + _postgres_row_count(row)
    return dict(sorted(counts.items()))


def _postgres_row_count(row) -> int:
    return int(getattr(row, "total_cables", 1) or 1)


def _postgres_room_uid(data_hall_id: str) -> str:
    return f"{DEFAULT_PROJECT_UID}:{DEFAULT_BUILDING_ID}:{data_hall_id}".upper()


def _postgres_connector_type(value: str) -> ConnectorType:
    try:
        return ConnectorType(value)
    except ValueError:
        return ConnectorType.OTHER


def _postgres_optional_model(model_type: type[BaseModel], payload: dict[str, Any] | None):
    if payload is None:
        return None
    return _postgres_model_from_payload(model_type, payload)


def _postgres_model_from_payload(model_type: type[BaseModel], payload: dict[str, Any]):
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)
    return model_type.parse_obj(payload)


def _reject_stale_json_write(
    database_path: str,
    *,
    entity_type: str,
    entity_id: str,
    expected_version: int | None,
    user: AuthUser | None,
) -> None:
    if expected_version is None:
        return
    latest_operation = max(
        (operation for operation in _load_operations(_operations_path(database_path)) if operation.entityType == entity_type and operation.entityId == entity_id),
        key=lambda operation: operation.opId,
        default=None,
    )
    if latest_operation is None or latest_operation.opId <= expected_version:
        return
    if _role_rank(user.role.value if user else None) > _role_rank(latest_operation.userRole):
        return
    latest = latest_operation.opId
    if latest > expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"{entity_type.title()} '{entity_id}' changed at operation {latest}; "
                    f"refresh before writing from stale version {expected_version}."
                ),
                "entity_type": entity_type,
                "entity_uid": entity_id,
                "expected_version": expected_version,
                "current_version": latest,
            },
        )


def _role_rank(role: str | None) -> int:
    return {"viewer": 0, "editor": 1, "manager": 2}.get(role or "", 0)


def _find_cabinet(database: TopologyDatabase, cabinet_uid: str) -> Cabinet | None:
    normalized_uid = cabinet_uid.upper()
    for cabinet in database.cabinets:
        if _cabinet_uid(cabinet) == normalized_uid:
            return cabinet
    return None


def _find_device(database: TopologyDatabase, device_uid: str) -> Device | None:
    normalized_uid = _normalize_device_uid(device_uid)
    cabinet_uid = _cabinet_uid_from_device_uid(normalized_uid)
    cabinet = _find_cabinet(database, cabinet_uid)
    if cabinet is None:
        return None
    for device in cabinet.devices:
        if _normalize_device_uid(f"{device.cabinet_id}:{device.rack_unit}") == normalized_uid:
            return device
    return None


def _find_cable(database: TopologyDatabase, cable_uid: str) -> Cable | None:
    normalized_uid = cable_uid.upper()
    for cable in database.cables:
        if cable.uid.upper() == normalized_uid:
            return cable
    return None


def _cable_detail(cable: Cable) -> CabinetCableDetail:
    return CabinetCableDetail(
        uid=cable.uid,
        group=cable.group,
        status=cable.status,
        cable_type=cable.cable_type,
        construction_phase=cable.construction_phase.value,
        a_label_text=cable.a_label_text,
        z_label_text=cable.z_label_text,
        progress=_progress_payload(cable),
        current_phase=normalize_cable_progress_phase(cable.current_phase or _phase_from_legacy_progress(cable)),
        designed_length_meters=cable.designed_length_meters,
        length_used_meters=cable.length_used_meters,
        length_meters=cable.length_used_meters or None,
        note=cable.note,
        a_port_uid=cable.a_side.uid,
        z_port_uid=cable.z_side.uid,
        a_optic=cable.a_optic.model if cable.a_optic else "",
        z_optic=cable.z_optic.model if cable.z_optic else "",
    )


def _validation_response_from_database(database: TopologyDatabase) -> ValidationResponse:
    return _validation_response_from_findings(
        database.port_collision_findings,
        database.device_model_mismatches,
        database.device_model_format_issues,
        database=database,
    )


def _validation_response_from_findings(
    port_collision_findings: list[PortConnectionFinding],
    device_model_mismatches: list[DeviceModelFinding],
    device_model_format_issues: list[DeviceModelFinding],
    *,
    database: TopologyDatabase | None = None,
) -> ValidationResponse:
    return ValidationResponse(
        summary=ValidationSummary(
            port_collision_findings=len(port_collision_findings),
            device_model_mismatches=len(device_model_mismatches),
            device_model_format_issues=len(device_model_format_issues),
        ),
        port_collision_findings=[
            ValidationPortConnectionFinding(
                port_uid=finding.port_uid,
                count=finding.count,
                message=finding.message,
                examples=_port_collision_examples(database, finding.port_uid) if database is not None else [],
            )
            for finding in port_collision_findings
        ],
        device_model_mismatches=device_model_mismatches,
        device_model_format_issues=device_model_format_issues,
    )


def _port_collision_examples(database: TopologyDatabase, port_uid: str) -> list[ValidationCableRowExample]:
    examples = []
    for row in database.rows:
        if row.a_port_uid != port_uid and row.z_port_uid != port_uid:
            continue
        examples.append(
            ValidationCableRowExample(
                status=row.status,
                group=row.group,
                cable_type=row.cable_type,
                a_port_uid=row.a_port_uid,
                z_port_uid=row.z_port_uid,
                a_device_model=row.a_device_model,
                z_device_model=row.z_device_model,
            )
        )
    return examples[:20]


def _load_cached_database(database_path: str) -> TopologyDatabase:
    if use_postgresql_topology_storage():
        return _postgres_repository().load()
    cache_key = _normalized_database_path(database_path)
    if cache_key not in _DATABASE_CACHE:
        _DATABASE_CACHE.clear()
        _GRAPH_CACHE.clear()
        _CABINET_PROGRESS_CACHE.clear()
        _DATABASE_CACHE[cache_key] = _replay_operations(load_topology_database(database_path), database_path)
    return _DATABASE_CACHE[cache_key]


def _load_cached_graph(database_path: str, database: TopologyDatabase):
    if use_postgresql_topology_storage():
        return build_cabinet_graph(database)
    path = Path(database_path)
    cache_key = (str(path), path.stat().st_mtime)
    if cache_key not in _GRAPH_CACHE:
        _GRAPH_CACHE.clear()
        _GRAPH_CACHE[cache_key] = build_cabinet_graph(database)
    return _GRAPH_CACHE[cache_key]


def _load_cached_cabinet_progress(
    database_path: str,
    database: TopologyDatabase,
) -> dict[str, tuple[float, float]]:
    if use_postgresql_topology_storage():
        return _cabinet_cable_progress_stats_by_cabinet(database.cables)
    path = Path(database_path)
    cache_key = (str(path), path.stat().st_mtime)
    if cache_key not in _CABINET_PROGRESS_CACHE:
        _CABINET_PROGRESS_CACHE.clear()
        _CABINET_PROGRESS_CACHE[cache_key] = _cabinet_cable_progress_stats_by_cabinet(database.cables)
    return _CABINET_PROGRESS_CACHE[cache_key]


def _save_database_and_clear_cache(database: TopologyDatabase, database_path: str) -> None:
    save_topology_database(database, database_path)
    _DATABASE_CACHE.clear()
    _clear_derived_caches()


def _clear_derived_caches() -> None:
    _GRAPH_CACHE.clear()
    _CABINET_PROGRESS_CACHE.clear()


def _update_room_cabinet_status(
    database: TopologyDatabase,
    cabinet_uid: str,
    lifecycle_status: LifecycleStatus,
) -> None:
    for room in database.data_halls:
        for cabinet in room.cabinets:
            if _cabinet_uid(cabinet) == cabinet_uid:
                cabinet.lifecycle_status = lifecycle_status


def _update_room_device_status(
    database: TopologyDatabase,
    device_uid: str,
    lifecycle_status: LifecycleStatus,
) -> None:
    normalized_device_uid = _normalize_device_uid(device_uid)
    for room in database.data_halls:
        for cabinet in room.cabinets:
            for device in cabinet.devices:
                if _normalize_device_uid(f"{device.cabinet_id}:{device.rack_unit}") == normalized_device_uid:
                    device.lifecycle_status = lifecycle_status


def _cabinet_connections(database: TopologyDatabase, cabinet_uid: str, graph) -> list[CabinetConnection]:
    if cabinet_uid not in graph:
        return []

    cabinet_by_uid = {_cabinet_uid(cabinet): cabinet for cabinet in database.cabinets}
    connections = []
    for neighbor_uid in sorted(graph.neighbors(cabinet_uid)):
        edge_data = graph.edges[cabinet_uid, neighbor_uid]
        target = cabinet_by_uid.get(neighbor_uid)
        cables = _cables_between_cabinets(database.cables, cabinet_uid, neighbor_uid)
        connections.append(
            CabinetConnection(
                target_cabinet_uid=neighbor_uid,
                target_category=target.category if target else "",
                target_cabinet_group=target.cabinet_group if target else "",
                total_cables=edge_data.get("total_cables", 0),
                cable_type_counts=edge_data.get("cable_type_counts", {}),
                status_summary=_status_summary(cables),
            )
        )
    return sorted(connections, key=lambda connection: (-connection.total_cables, connection.target_cabinet_uid))


def _intra_cabinet_connection(cabinet: Cabinet, cables: list[Cable]) -> CabinetConnection | None:
    cabinet_uid = _cabinet_uid(cabinet)
    intra_cabinet_cables = _cables_between_cabinets(cables, cabinet_uid, cabinet_uid)
    if not intra_cabinet_cables:
        return None

    return CabinetConnection(
        target_cabinet_uid=cabinet_uid,
        target_category=cabinet.category,
        target_cabinet_group=cabinet.cabinet_group,
        total_cables=len(intra_cabinet_cables),
        cable_type_counts=dict(sorted(Counter(cable.cable_type for cable in intra_cabinet_cables).items())),
        status_summary=_status_summary(intra_cabinet_cables),
    )


def _cables_for_cabinet(cables: list[Cable], cabinet_uid: str) -> list[Cable]:
    prefix = f"{cabinet_uid}:"
    return [
        cable
        for cable in cables
        if cable.a_side.uid.startswith(prefix) or cable.z_side.uid.startswith(prefix)
    ]


def _cables_between_cabinets(cables: list[Cable], source_cabinet_uid: str, target_cabinet_uid: str) -> list[Cable]:
    source_prefix = f"{source_cabinet_uid}:"
    target_prefix = f"{target_cabinet_uid}:"
    return [
        cable
        for cable in cables
        if (
            cable.a_side.uid.startswith(source_prefix)
            and cable.z_side.uid.startswith(target_prefix)
        )
        or (
            cable.a_side.uid.startswith(target_prefix)
            and cable.z_side.uid.startswith(source_prefix)
        )
    ]


def _cables_between_devices(cables: list[Cable], source_device_uid: str, target_device_uid: str) -> list[Cable]:
    source_prefix = f"{source_device_uid}:"
    target_prefix = f"{target_device_uid}:"
    return [
        cable
        for cable in cables
        if (
            cable.a_side.uid.startswith(source_prefix)
            and cable.z_side.uid.startswith(target_prefix)
        )
        or (
            cable.a_side.uid.startswith(target_prefix)
            and cable.z_side.uid.startswith(source_prefix)
        )
    ]


def _status_summary(cables: list[Cable]) -> CableStatusSummary:
    status_counts = Counter(cable.status or "Unknown" for cable in cables)
    return CableStatusSummary(
        completed=sum(1 for cable in cables if _is_completed_status(cable.status)),
        total=len(cables),
        status_counts=dict(sorted(status_counts.items())),
    )


def _data_hall_cable_bucket(
    scope: str,
    cables: list[Cable],
    target_data_hall: str | None = None,
) -> DataHallCableBucket:
    return DataHallCableBucket(
        scope=scope,
        target_data_hall=target_data_hall,
        total_cables=len(cables),
        cable_type_counts=dict(sorted(Counter(cable.cable_type for cable in cables).items())),
        status_summary=_status_summary(cables),
    )


def _data_hall_internal_cables(cables: list[Cable], data_hall_id: str) -> list[Cable]:
    return [
        cable
        for cable in cables
        if _data_hall_from_port_uid(cable.a_side.uid) == data_hall_id
        and _data_hall_from_port_uid(cable.z_side.uid) == data_hall_id
    ]


def _other_data_hall_for_cable(cable: Cable, data_hall_id: str) -> str | None:
    a_data_hall = _data_hall_from_port_uid(cable.a_side.uid)
    z_data_hall = _data_hall_from_port_uid(cable.z_side.uid)
    if a_data_hall == data_hall_id and z_data_hall and z_data_hall != data_hall_id:
        return z_data_hall
    if z_data_hall == data_hall_id and a_data_hall and a_data_hall != data_hall_id:
        return a_data_hall
    return None


def _progress_payload(cable: Cable) -> dict[str, str]:
    return {
        key.value if hasattr(key, "value") else str(key): value.value if hasattr(value, "value") else str(value)
        for key, value in cable.progress.items()
    }


def _phase_from_legacy_progress(cable: Cable) -> CableProgressPhase | None:
    if not cable.progress:
        return None
    progress = _progress_payload(cable)
    if "broken" in progress:
        return CableProgressPhase(
            name="final_result",
            phase_type=CableProgressPhaseType.ENUM_STATE,
            value="broken",
            enum_values=["validated", "broken"],
        )
    if "validated" in progress:
        return CableProgressPhase(
            name="final_result",
            phase_type=CableProgressPhaseType.ENUM_STATE,
            value="validated",
            enum_values=["validated", "broken"],
        )
    parallel_steps = {
        step: 100.0 if state == CableProgressState.COMPLETE.value else 0.0
        for step, state in progress.items()
        if step in {"a_side_terminated", "z_side_terminated", "a_side_dressed_in_cabinet", "z_side_dressed_in_cabinet"}
    }
    if parallel_steps:
        return CableProgressPhase(
            name="termination",
            phase_type=CableProgressPhaseType.PARALLEL_PERCENT,
            tasks=parallel_steps,
        )
    step, state = next(reversed(progress.items()))
    return CableProgressPhase(
        name=step,
        phase_type=CableProgressPhaseType.SINGLE_PERCENT,
        value=100.0 if state == CableProgressState.COMPLETE.value else 0.0,
    )


def _is_completed_status(status: str) -> bool:
    normalized = " ".join(status.casefold().split())
    return normalized == "cable is ran: complete"


def _device_uid(cabinet_uid: str, rack_unit: int) -> str:
    return f"{cabinet_uid}:{rack_unit}"


def _device_uid_from_port_uid(port_uid: str) -> str | None:
    parts = port_uid.split(":", 3)
    if len(parts) < 4 or not parts[2].isdigit():
        return None
    return f"{parts[0]}:{parts[1]}:{int(parts[2])}".upper()


def _cabinet_uid_from_device_uid(device_uid: str) -> str:
    data_hall_id, cabinet_id, _ = device_uid.split(":", 2)
    return f"{data_hall_id}:{cabinet_id}".upper()


def _cabinet_uid_from_port_uid(port_uid: str) -> str | None:
    parts = port_uid.split(":", 2)
    if len(parts) < 2:
        return None
    return f"{parts[0]}:{parts[1]}".upper()


def _data_hall_from_port_uid(port_uid: str) -> str | None:
    parts = port_uid.split(":", 1)
    if not parts or not parts[0]:
        return None
    return parts[0].upper()


def _normalize_device_uid(device_uid: str) -> str:
    data_hall_id, cabinet_id, rack_unit = device_uid.upper().split(":", 2)
    return f"{data_hall_id}:{cabinet_id}:{int(rack_unit)}"


def _layout_item(
    cabinet: Cabinet,
    progress_stats: dict[str, tuple[float, float]] | None = None,
) -> CabinetLayoutItem:
    cable_termination_percent, cable_dress_percent = (progress_stats or {}).get(_cabinet_uid(cabinet), (0.0, 0.0))
    return CabinetLayoutItem(
        cabinet_uid=_cabinet_uid(cabinet),
        data_hall_id=cabinet.data_hall_id,
        cabinet_id=cabinet.cabinet_id,
        category=cabinet.category,
        cabinet_group=cabinet.cabinet_group,
        lifecycle_status=cabinet.lifecycle_status.value,
        construction_phase=cabinet.construction_phase.value,
        max_rack_unit=cabinet.max_rack_unit,
        cable_termination_percent=cable_termination_percent,
        cable_dress_percent=cable_dress_percent,
        source_row=cabinet.source_row,
        source_col=cabinet.source_col,
    )


def _cabinet_cable_progress_stats_by_cabinet(cables: list[Cable]) -> dict[str, tuple[float, float]]:
    totals: dict[str, list[float]] = {}
    for cable in cables:
        for endpoint_uid, side in ((cable.a_side.uid, "a"), (cable.z_side.uid, "z")):
            cabinet_uid = _cabinet_uid_from_port_uid(endpoint_uid)
            if cabinet_uid is None:
                continue
            termination, dress = cable_endpoint_termination_and_dress_percent(cable.current_phase, side)
            cabinet_totals = totals.setdefault(cabinet_uid, [0.0, 0.0, 0.0])
            cabinet_totals[0] += termination
            cabinet_totals[1] += dress
            cabinet_totals[2] += 1

    return {
        cabinet_uid: (round(termination_total / endpoint_count, 1), round(dress_total / endpoint_count, 1))
        for cabinet_uid, (termination_total, dress_total, endpoint_count) in totals.items()
        if endpoint_count > 0
    }


def _cabinet_cable_progress_stats(cables: list[Cable], cabinet_uid: str) -> tuple[float, float]:
    termination_total = 0.0
    dress_total = 0.0
    endpoint_count = 0
    prefix = f"{cabinet_uid}:"
    for cable in cables:
        if cable.a_side.uid.startswith(prefix):
            termination, dress = cable_endpoint_termination_and_dress_percent(cable.current_phase, "a")
            termination_total += termination
            dress_total += dress
            endpoint_count += 1
        if cable.z_side.uid.startswith(prefix):
            termination, dress = cable_endpoint_termination_and_dress_percent(cable.current_phase, "z")
            termination_total += termination
            dress_total += dress
            endpoint_count += 1
    if endpoint_count == 0:
        return 0.0, 0.0
    return round(termination_total / endpoint_count, 1), round(dress_total / endpoint_count, 1)


def _cabinet_uid(cabinet: Cabinet) -> str:
    return f"{cabinet.data_hall_id}:{cabinet.cabinet_id}".upper()


def _cabinet_sort_key(cabinet: Cabinet) -> tuple[str, int, int, str]:
    return (
        cabinet.data_hall_id,
        cabinet.source_row or 0,
        cabinet.source_col or 0,
        cabinet.cabinet_id,
    )

