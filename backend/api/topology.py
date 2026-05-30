from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.graph import build_cabinet_graph
from backend.models import Cabinet, Cable, Device
from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, TopologyDatabase, load_topology_database


router = APIRouter(prefix="/topology", tags=["topology"])
_DATABASE_CACHE: dict[tuple[str, float], TopologyDatabase] = {}
_GRAPH_CACHE: dict[tuple[str, float], object] = {}


class CabinetLayoutItem(BaseModel):
    cabinet_uid: str
    data_hall_id: str
    cabinet_id: str
    category: str
    cabinet_group: str
    source_row: int | None = None
    source_col: int | None = None


class CabinetStats(BaseModel):
    devices: int
    ports: int
    cables: int
    connected_cabinets: int
    cable_type_counts: dict[str, int] = Field(default_factory=dict)


class CabinetConnection(BaseModel):
    target_cabinet_uid: str
    target_category: str = ""
    target_cabinet_group: str = ""
    total_cables: int
    cable_type_counts: dict[str, int]


class CabinetDetailResponse(BaseModel):
    cabinet: CabinetLayoutItem
    stats: CabinetStats
    devices: list[Device]
    connections: list[CabinetConnection]


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


@router.get("/cabinets/{cabinet_uid:path}", response_model=CabinetDetailResponse)
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
        connections=connections,
    )


def _find_cabinet(database: TopologyDatabase, cabinet_uid: str) -> Cabinet | None:
    normalized_uid = cabinet_uid.upper()
    for cabinet in database.cabinets:
        if _cabinet_uid(cabinet) == normalized_uid:
            return cabinet
    return None


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
        connections.append(
            CabinetConnection(
                target_cabinet_uid=neighbor_uid,
                target_category=target.category if target else "",
                target_cabinet_group=target.cabinet_group if target else "",
                total_cables=edge_data.get("total_cables", 0),
                cable_type_counts=edge_data.get("cable_type_counts", {}),
            )
        )
    return sorted(connections, key=lambda connection: (-connection.total_cables, connection.target_cabinet_uid))


def _cables_for_cabinet(cables: list[Cable], cabinet_uid: str) -> list[Cable]:
    prefix = f"{cabinet_uid}:"
    return [
        cable
        for cable in cables
        if cable.a_side.uid.startswith(prefix) or cable.z_side.uid.startswith(prefix)
    ]


def _layout_item(cabinet: Cabinet) -> CabinetLayoutItem:
    return CabinetLayoutItem(
        cabinet_uid=_cabinet_uid(cabinet),
        data_hall_id=cabinet.data_hall_id,
        cabinet_id=cabinet.cabinet_id,
        category=cabinet.category,
        cabinet_group=cabinet.cabinet_group,
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
