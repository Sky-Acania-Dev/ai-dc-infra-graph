from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.auth import AuthUser, current_user, require_editor
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
from backend.models import Cabinet, Cable, CableProgressPhase, CableProgressTask, Device
from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, TopologyDatabase, load_topology_database, save_topology_database
from backend.validation.device_models import DeviceModelFinding
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


class CabinetConnection(BaseModel):
    target_cabinet_uid: str
    target_category: str = ""
    target_cabinet_group: str = ""
    total_cables: int
    cable_type_counts: dict[str, int]
    status_summary: CableStatusSummary


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


class CabinetCableDetail(BaseModel):
    uid: str
    group: str
    status: str
    cable_type: str
    construction_phase: str
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


class CabinetCableDetailResponse(BaseModel):
    source_cabinet_uid: str
    target_cabinet_uid: str
    cables: list[CabinetCableDetail]


class DeviceCableDetailResponse(BaseModel):
    source_device_uid: str
    target_device_uid: str
    cables: list[CabinetCableDetail]


class DeviceConnection(BaseModel):
    target_device_uid: str
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


class Operation(BaseModel):
    opId: int
    type: str
    entityType: str
    entityId: str
    before: dict[str, Any]
    after: dict[str, Any]
    timestamp: str


class OperationResponse(BaseModel):
    ok: bool
    operation: Operation
    version: int


class OperationListResponse(BaseModel):
    operations: list[Operation]
    version: int


@router.get("/layout/cabinets", response_model=list[CabinetLayoutItem])
def cabinet_layout(
    data_hall: str | None = None,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> list[CabinetLayoutItem]:
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
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> CabinetCableDetailResponse:
    data_hall_id = data_hall_id.upper()
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

    return CabinetCableDetailResponse(
        source_cabinet_uid=data_hall_id,
        target_cabinet_uid=target_label,
        cables=sorted((_cable_detail(cable) for cable in cables), key=lambda cable: (cable.cable_type, cable.a_port_uid, cable.z_port_uid)),
    )


@router.get("/enums", response_model=TopologyEnumResponse)
def topology_enums(database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH)) -> TopologyEnumResponse:
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
    database = _load_cached_database(database_path)
    cabinet = _find_cabinet(database, cabinet_uid)
    if cabinet is None:
        raise HTTPException(status_code=404, detail=f"Cabinet '{cabinet_uid}' was not found.")
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
    database = _load_cached_database(database_path)
    device = _find_device(database, device_uid)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_uid}' was not found.")
    normalized_device_uid = _normalize_device_uid(device_uid)
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
    database = _load_cached_database(database_path)
    cable = _find_cable(database, cable_uid)
    if cable is None:
        raise HTTPException(status_code=404, detail=f"Cable '{cable_uid}' was not found.")
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
    )
    _log_operation_timing(operation, response_start)
    return OperationResponse(ok=True, operation=operation, version=database.version)


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
    )
    _log_operation_timing(operation, response_start)
    return OperationResponse(ok=True, operation=operation, version=database.version)


@router.get("/operations", response_model=OperationListResponse)
def list_operations(
    limit: int = 100,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> OperationListResponse:
    normalized_limit = min(500, max(1, limit))
    operations = _load_operations(_operations_path(database_path))
    return OperationListResponse(
        operations=operations[-normalized_limit:],
        version=operations[-1].opId if operations else 0,
    )


@router.get("/validation", response_model=ValidationResponse)
def validation_report(
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> ValidationResponse:
    database = _load_cached_database(database_path)
    return ValidationResponse(
        summary=ValidationSummary(
            port_collision_findings=len(database.port_collision_findings),
            device_model_mismatches=len(database.device_model_mismatches),
            device_model_format_issues=len(database.device_model_format_issues),
        ),
        port_collision_findings=[
            ValidationPortConnectionFinding(
                port_uid=finding.port_uid,
                count=finding.count,
                message=finding.message,
                examples=_port_collision_examples(database, finding.port_uid),
            )
            for finding in database.port_collision_findings
        ],
        device_model_mismatches=database.device_model_mismatches,
        device_model_format_issues=database.device_model_format_issues,
    )


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
    database = _load_cached_database(database_path)
    if _find_cabinet(database, cabinet_uid) is None:
        raise HTTPException(status_code=404, detail=f"Cabinet '{cabinet_uid}' was not found.")

    source_device_uid = _device_uid(cabinet_uid, rack_unit)
    source_prefix = f"{source_device_uid}:"
    connections_by_device: dict[str, list[Cable]] = {}
    connected_cabinets: set[str] = set()

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
    cache_key = _normalized_database_path(database_path)
    if cache_key not in _DATABASE_CACHE:
        _DATABASE_CACHE.clear()
        _GRAPH_CACHE.clear()
        _CABINET_PROGRESS_CACHE.clear()
        _DATABASE_CACHE[cache_key] = _replay_operations(load_topology_database(database_path), database_path)
    return _DATABASE_CACHE[cache_key]


def _load_cached_graph(database_path: str, database: TopologyDatabase):
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
