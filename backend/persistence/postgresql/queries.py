from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from backend.persistence.postgresql import models as db


class SearchResult(BaseModel):
    entity_type: str
    uid: str
    label: str
    description: str = ""


class CabinetFilter(BaseModel):
    project_uid: str
    room_uid: str | None = None
    category: str | None = None
    cabinet_group: str | None = None
    lifecycle_status: str | None = None
    construction_phase: str | None = None
    query: str | None = None
    limit: int = 500


class CabinetSummary(BaseModel):
    uid: str
    room_uid: str
    cabinet_id: str
    category: str
    cabinet_group: str
    lifecycle_status: str
    construction_phase: str
    source_row: int | None = None
    source_col: int | None = None


class StatusSummary(BaseModel):
    completed: int
    total: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class CabinetStats(BaseModel):
    cabinet_uid: str
    devices: int
    ports: int
    cables: int
    connected_cabinets: int
    cable_type_counts: dict[str, int] = Field(default_factory=dict)
    status_summary: StatusSummary


class DataHallCableBucket(BaseModel):
    scope: str
    target_room_uid: str | None = None
    total_cables: int
    cable_type_counts: dict[str, int] = Field(default_factory=dict)
    status_summary: StatusSummary


class DataHallCableSummary(BaseModel):
    room_uid: str
    internal: DataHallCableBucket
    external: list[DataHallCableBucket]


class CabinetGraphEdge(BaseModel):
    source_cabinet_uid: str
    target_cabinet_uid: str
    total_cables: int
    cable_type_counts: dict[str, int] = Field(default_factory=dict)


class DeviceConnection(BaseModel):
    target_device_uid: str
    target_cabinet_uid: str
    target_rack_unit: int
    total_cables: int
    cable_type_counts: dict[str, int] = Field(default_factory=dict)
    status_summary: StatusSummary


class DeviceConnectionSummary(BaseModel):
    source_device_uid: str
    source_cabinet_uid: str
    source_rack_unit: int
    connected_cabinet_uids: list[str]
    connected_devices: list[DeviceConnection]


def search_topology(
    session: Session,
    *,
    project_uid: str,
    query: str,
    limit: int = 50,
) -> list[SearchResult]:
    pattern = f"%{query.strip()}%"
    if not query.strip():
        return []

    cabinet_rows = session.execute(
        select(db.Cabinet.uid, db.Cabinet.category, db.Cabinet.cabinet_group)
        .where(
            db.Cabinet.project_uid == project_uid,
            db.Cabinet.deleted_at.is_(None),
            or_(
                db.Cabinet.uid.ilike(pattern),
                db.Cabinet.cabinet_id.ilike(pattern),
                db.Cabinet.category.ilike(pattern),
                db.Cabinet.cabinet_group.ilike(pattern),
            ),
        )
        .order_by(db.Cabinet.uid)
        .limit(limit)
    ).all()

    remaining = max(0, limit - len(cabinet_rows))
    device_rows = session.execute(
        select(db.Device.uid, db.Device.device_model_name, db.Device.note)
        .where(
            db.Device.project_uid == project_uid,
            db.Device.deleted_at.is_(None),
            remaining > 0,
            or_(
                db.Device.uid.ilike(pattern),
                db.Device.device_model_name.ilike(pattern),
                db.Device.note.ilike(pattern),
            ),
        )
        .order_by(db.Device.uid)
        .limit(remaining)
    ).all()

    remaining = max(0, limit - len(cabinet_rows) - len(device_rows))
    cable_rows = session.execute(
        select(db.Cable.uid, db.Cable.cable_type, db.Cable.import_status)
        .where(
            db.Cable.project_uid == project_uid,
            db.Cable.deleted_at.is_(None),
            remaining > 0,
            or_(
                db.Cable.uid.ilike(pattern),
                db.Cable.cable_type.ilike(pattern),
                db.Cable.import_status.ilike(pattern),
                db.Cable.a_port_uid.ilike(pattern),
                db.Cable.z_port_uid.ilike(pattern),
            ),
        )
        .order_by(db.Cable.uid)
        .limit(remaining)
    ).all()

    return [
        SearchResult(entity_type="cabinet", uid=row.uid, label=row.uid, description=" / ".join(part for part in (row.category, row.cabinet_group) if part))
        for row in cabinet_rows
    ] + [
        SearchResult(entity_type="device", uid=row.uid, label=row.uid, description=row.device_model_name or row.note or "")
        for row in device_rows
    ] + [
        SearchResult(entity_type="cable", uid=row.uid, label=row.uid, description=" / ".join(part for part in (row.cable_type, row.import_status) if part))
        for row in cable_rows
    ]


def filter_cabinets(session: Session, filters: CabinetFilter) -> list[CabinetSummary]:
    clauses = [db.Cabinet.project_uid == filters.project_uid, db.Cabinet.deleted_at.is_(None)]
    if filters.room_uid:
        clauses.append(db.Cabinet.room_uid == filters.room_uid)
    if filters.category:
        clauses.append(db.Cabinet.category == filters.category)
    if filters.cabinet_group:
        clauses.append(db.Cabinet.cabinet_group == filters.cabinet_group)
    if filters.lifecycle_status:
        clauses.append(db.Cabinet.lifecycle_status == filters.lifecycle_status)
    if filters.construction_phase:
        clauses.append(db.Cabinet.construction_phase == filters.construction_phase)
    if filters.query:
        pattern = f"%{filters.query.strip()}%"
        clauses.append(
            or_(
                db.Cabinet.uid.ilike(pattern),
                db.Cabinet.cabinet_id.ilike(pattern),
                db.Cabinet.category.ilike(pattern),
                db.Cabinet.cabinet_group.ilike(pattern),
            )
        )

    rows = session.execute(
        select(db.Cabinet)
        .where(*clauses)
        .order_by(db.Cabinet.room_uid, db.Cabinet.source_row, db.Cabinet.source_col, db.Cabinet.cabinet_id)
        .limit(max(1, min(filters.limit, 2000)))
    ).scalars()
    return [
        CabinetSummary(
            uid=row.uid,
            room_uid=row.room_uid,
            cabinet_id=row.cabinet_id,
            category=row.category,
            cabinet_group=row.cabinet_group,
            lifecycle_status=row.lifecycle_status,
            construction_phase=row.construction_phase,
            source_row=row.source_row,
            source_col=row.source_col,
        )
        for row in rows
    ]


def cabinet_stats(session: Session, *, cabinet_uid: str) -> CabinetStats:
    cabinet_uid = cabinet_uid.upper()
    device_count = session.scalar(
        select(func.count())
        .select_from(db.Device)
        .where(db.Device.cabinet_uid == cabinet_uid, db.Device.deleted_at.is_(None))
    ) or 0
    port_count = session.scalar(
        select(func.count())
        .select_from(db.Port)
        .where(db.Port.cabinet_uid == cabinet_uid, db.Port.deleted_at.is_(None))
    ) or 0
    cable_rows = _cables_for_cabinet(session, cabinet_uid)
    connected_cabinets = {
        _other_cabinet_uid(row.a_cabinet_uid, row.z_cabinet_uid, cabinet_uid)
        for row in cable_rows
        if _other_cabinet_uid(row.a_cabinet_uid, row.z_cabinet_uid, cabinet_uid) != cabinet_uid
    }
    cable_type_counts = _count_by(cable_rows, "cable_type")
    return CabinetStats(
        cabinet_uid=cabinet_uid,
        devices=device_count,
        ports=port_count,
        cables=len(cable_rows),
        connected_cabinets=len(connected_cabinets),
        cable_type_counts=cable_type_counts,
        status_summary=_status_summary(cable_rows),
    )


def data_hall_cable_summary(session: Session, *, room_uid: str) -> DataHallCableSummary:
    rows = _cables_for_room(session, room_uid)
    internal_rows = [row for row in rows if row.a_room_uid == room_uid and row.z_room_uid == room_uid]
    external_by_room: dict[str, list] = defaultdict(list)
    for row in rows:
        other_room = None
        if row.a_room_uid == room_uid and row.z_room_uid != room_uid:
            other_room = row.z_room_uid
        elif row.z_room_uid == room_uid and row.a_room_uid != room_uid:
            other_room = row.a_room_uid
        if other_room:
            external_by_room[other_room].append(row)

    return DataHallCableSummary(
        room_uid=room_uid,
        internal=DataHallCableBucket(
            scope="internal",
            total_cables=len(internal_rows),
            cable_type_counts=_count_by(internal_rows, "cable_type"),
            status_summary=_status_summary(internal_rows),
        ),
        external=[
            DataHallCableBucket(
                scope="external",
                target_room_uid=target_room,
                total_cables=len(target_rows),
                cable_type_counts=_count_by(target_rows, "cable_type"),
                status_summary=_status_summary(target_rows),
            )
            for target_room, target_rows in sorted(external_by_room.items())
        ],
    )


def cabinet_graph_edges(session: Session, *, project_uid: str) -> list[CabinetGraphEdge]:
    a_port = aliased(db.Port)
    z_port = aliased(db.Port)
    rows = session.execute(
        select(
            func.least(a_port.cabinet_uid, z_port.cabinet_uid).label("source_cabinet_uid"),
            func.greatest(a_port.cabinet_uid, z_port.cabinet_uid).label("target_cabinet_uid"),
            db.Cable.cable_type,
            func.count().label("total_cables"),
        )
        .join(a_port, db.Cable.a_port_uid == a_port.uid)
        .join(z_port, db.Cable.z_port_uid == z_port.uid)
        .where(
            db.Cable.project_uid == project_uid,
            db.Cable.deleted_at.is_(None),
            a_port.cabinet_uid != z_port.cabinet_uid,
        )
        .group_by("source_cabinet_uid", "target_cabinet_uid", db.Cable.cable_type)
    ).all()

    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        key = (row.source_cabinet_uid, row.target_cabinet_uid)
        count = int(row.total_cables)
        grouped[key][row.cable_type or "UNKNOWN"] = count
        totals[key] += count

    return [
        CabinetGraphEdge(
            source_cabinet_uid=source_uid,
            target_cabinet_uid=target_uid,
            total_cables=totals[(source_uid, target_uid)],
            cable_type_counts=dict(sorted(grouped[(source_uid, target_uid)].items())),
        )
        for source_uid, target_uid in sorted(grouped)
    ]


def device_connections(session: Session, *, source_device_uid: str) -> DeviceConnectionSummary:
    source_device_uid = source_device_uid.upper()
    source_device = session.get(db.Device, source_device_uid)
    if source_device is None:
        raise ValueError(f"Device '{source_device_uid}' was not found.")

    rows = _cables_for_device(session, source_device_uid)
    by_device: dict[str, list] = defaultdict(list)
    for row in rows:
        other_device_uid = row.z_device_uid if row.a_device_uid == source_device_uid else row.a_device_uid
        if other_device_uid and other_device_uid != source_device_uid:
            by_device[other_device_uid].append(row)

    connections = [
        DeviceConnection(
            target_device_uid=target_device_uid,
            target_cabinet_uid=target_rows[0].z_cabinet_uid if target_rows[0].z_device_uid == target_device_uid else target_rows[0].a_cabinet_uid,
            target_rack_unit=int(target_device_uid.split(":")[2]),
            total_cables=len(target_rows),
            cable_type_counts=_count_by(target_rows, "cable_type"),
            status_summary=_status_summary(target_rows),
        )
        for target_device_uid, target_rows in by_device.items()
    ]
    connected_cabinets = sorted({connection.target_cabinet_uid for connection in connections})
    return DeviceConnectionSummary(
        source_device_uid=source_device_uid,
        source_cabinet_uid=source_device.cabinet_uid,
        source_rack_unit=source_device.rack_unit,
        connected_cabinet_uids=connected_cabinets,
        connected_devices=sorted(connections, key=lambda item: (-item.total_cables, item.target_device_uid)),
    )


def _cables_for_cabinet(session: Session, cabinet_uid: str):
    a_port = aliased(db.Port)
    z_port = aliased(db.Port)
    return session.execute(
        select(
            db.Cable.uid,
            db.Cable.cable_type,
            db.Cable.import_status,
            a_port.cabinet_uid.label("a_cabinet_uid"),
            z_port.cabinet_uid.label("z_cabinet_uid"),
        )
        .join(a_port, db.Cable.a_port_uid == a_port.uid)
        .join(z_port, db.Cable.z_port_uid == z_port.uid)
        .where(
            db.Cable.deleted_at.is_(None),
            or_(a_port.cabinet_uid == cabinet_uid, z_port.cabinet_uid == cabinet_uid),
        )
    ).all()


def _cables_for_room(session: Session, room_uid: str):
    a_port = aliased(db.Port)
    z_port = aliased(db.Port)
    return session.execute(
        select(
            db.Cable.uid,
            db.Cable.cable_type,
            db.Cable.import_status,
            a_port.room_uid.label("a_room_uid"),
            z_port.room_uid.label("z_room_uid"),
        )
        .join(a_port, db.Cable.a_port_uid == a_port.uid)
        .join(z_port, db.Cable.z_port_uid == z_port.uid)
        .where(
            db.Cable.deleted_at.is_(None),
            or_(a_port.room_uid == room_uid, z_port.room_uid == room_uid),
        )
    ).all()


def _cables_for_device(session: Session, source_device_uid: str):
    a_port = aliased(db.Port)
    z_port = aliased(db.Port)
    return session.execute(
        select(
            db.Cable.uid,
            db.Cable.cable_type,
            db.Cable.import_status,
            a_port.device_uid.label("a_device_uid"),
            z_port.device_uid.label("z_device_uid"),
            a_port.cabinet_uid.label("a_cabinet_uid"),
            z_port.cabinet_uid.label("z_cabinet_uid"),
        )
        .join(a_port, db.Cable.a_port_uid == a_port.uid)
        .join(z_port, db.Cable.z_port_uid == z_port.uid)
        .where(
            db.Cable.deleted_at.is_(None),
            or_(a_port.device_uid == source_device_uid, z_port.device_uid == source_device_uid),
        )
    ).all()


def _status_summary(rows) -> StatusSummary:
    status_counts = _count_by(rows, "import_status")
    return StatusSummary(
        completed=sum(1 for row in rows if _is_completed_status(row.import_status)),
        total=len(rows),
        status_counts=status_counts,
    )


def _count_by(rows, attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = getattr(row, attribute) or "Unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _other_cabinet_uid(a_cabinet_uid: str, z_cabinet_uid: str, cabinet_uid: str) -> str:
    return z_cabinet_uid if a_cabinet_uid == cabinet_uid else a_cabinet_uid


def _is_completed_status(status: str) -> bool:
    normalized = " ".join((status or "").casefold().split())
    return normalized == "cable is ran: complete"
