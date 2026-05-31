from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.graph import build_cabinet_graph
from backend.models import Cabinet, Cable, Device
from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, TopologyDatabase, load_topology_database
from backend.validation.device_models import DeviceModelFinding
from backend.validation.port_collisions import PortConnectionFinding


router = APIRouter(prefix="/topology", tags=["topology"])
_DATABASE_CACHE: dict[tuple[str, float], TopologyDatabase] = {}
_GRAPH_CACHE: dict[tuple[str, float], object] = {}


class CabinetLayoutItem(BaseModel):
    cabinet_uid: str
    data_hall_id: str
    cabinet_id: str
    category: str
    cabinet_group: str
    lifecycle_status: str
    max_rack_unit: int
    source_row: int | None = None
    source_col: int | None = None


class CabinetStats(BaseModel):
    devices: int
    ports: int
    cables: int
    connected_cabinets: int
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
    progress: dict[str, str] = Field(default_factory=dict)
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


@router.get("/layout/cabinets", response_model=list[CabinetLayoutItem])
def cabinet_layout(
    data_hall: str | None = None,
    database_path: str = str(DEFAULT_RUNTIME_DATABASE_PATH),
) -> list[CabinetLayoutItem]:
    database = _load_cached_database(database_path)
    cabinets = database.cabinets
    if data_hall:
        cabinets = [cabinet for cabinet in cabinets if cabinet.data_hall_id == data_hall.upper()]

    return [_layout_item(cabinet) for cabinet in sorted(cabinets, key=_cabinet_sort_key)]


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
    connections = _cabinet_connections(database, cabinet_uid, graph)
    cable_type_counts = Counter(cable.cable_type for cable in _cables_for_cabinet(database.cables, cabinet_uid))
    intra_cabinet_connection = _intra_cabinet_connection(cabinet, database.cables)
    port_count = sum(len(ports) for device in cabinet.devices for ports in device.ports_by_type.values())
    return CabinetDetailResponse(
        cabinet=_layout_item(cabinet),
        stats=CabinetStats(
            devices=len(cabinet.devices),
            ports=port_count,
            cables=sum(cable_type_counts.values()),
            connected_cabinets=len(connections),
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
        CabinetCableDetail(
            uid=cable.uid,
            group=cable.group,
            status=cable.status,
            cable_type=cable.cable_type,
            progress=_progress_payload(cable),
            length_meters=cable.length_meters,
            note=cable.note,
            a_port_uid=cable.a_side.uid,
            z_port_uid=cable.z_side.uid,
            a_optic=cable.a_optic.model if cable.a_optic else "",
            z_optic=cable.z_optic.model if cable.z_optic else "",
        )
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
        CabinetCableDetail(
            uid=cable.uid,
            group=cable.group,
            status=cable.status,
            cable_type=cable.cable_type,
            progress=_progress_payload(cable),
            length_meters=cable.length_meters,
            note=cable.note,
            a_port_uid=cable.a_side.uid,
            z_port_uid=cable.z_side.uid,
            a_optic=cable.a_optic.model if cable.a_optic else "",
            z_optic=cable.z_optic.model if cable.z_optic else "",
        )
        for cable in _cables_between_devices(database.cables, source_device_uid, target_device_uid)
    ]
    return DeviceCableDetailResponse(
        source_device_uid=source_device_uid,
        target_device_uid=target_device_uid,
        cables=sorted(cables, key=lambda cable: (cable.cable_type, cable.a_port_uid, cable.z_port_uid)),
    )


def _find_cabinet(database: TopologyDatabase, cabinet_uid: str) -> Cabinet | None:
    normalized_uid = cabinet_uid.upper()
    for cabinet in database.cabinets:
        if _cabinet_uid(cabinet) == normalized_uid:
            return cabinet
    return None


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
    path = Path(database_path)
    cache_key = (str(path), path.stat().st_mtime)
    if cache_key not in _DATABASE_CACHE:
        _DATABASE_CACHE.clear()
        _GRAPH_CACHE.clear()
        _DATABASE_CACHE[cache_key] = load_topology_database(path)
    return _DATABASE_CACHE[cache_key]


def _load_cached_graph(database_path: str, database: TopologyDatabase):
    path = Path(database_path)
    cache_key = (str(path), path.stat().st_mtime)
    if cache_key not in _GRAPH_CACHE:
        _GRAPH_CACHE.clear()
        _GRAPH_CACHE[cache_key] = build_cabinet_graph(database)
    return _GRAPH_CACHE[cache_key]


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


def _progress_payload(cable: Cable) -> dict[str, str]:
    return {
        key.value if hasattr(key, "value") else str(key): value.value if hasattr(value, "value") else str(value)
        for key, value in cable.progress.items()
    }


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


def _layout_item(cabinet: Cabinet) -> CabinetLayoutItem:
    return CabinetLayoutItem(
        cabinet_uid=_cabinet_uid(cabinet),
        data_hall_id=cabinet.data_hall_id,
        cabinet_id=cabinet.cabinet_id,
        category=cabinet.category,
        cabinet_group=cabinet.cabinet_group,
        lifecycle_status=cabinet.lifecycle_status.value,
        max_rack_unit=cabinet.max_rack_unit,
        source_row=cabinet.source_row,
        source_col=cabinet.source_col,
    )


def _cabinet_uid(cabinet: Cabinet) -> str:
    return f"{cabinet.data_hall_id}:{cabinet.cabinet_id}".upper()


def _cabinet_sort_key(cabinet: Cabinet) -> tuple[str, int, int, str]:
    return (
        cabinet.data_hall_id,
        cabinet.source_row or 0,
        cabinet.source_col or 0,
        cabinet.cabinet_id,
    )
