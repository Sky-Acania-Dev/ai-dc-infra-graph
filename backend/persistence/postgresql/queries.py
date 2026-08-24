from __future__ import annotations

import re
from collections import defaultdict

from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
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
    target_device_model: str = ""
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
    search_term = query.strip()
    if not search_term:
        return []
    patterns = _search_patterns(search_term)

    cabinet_rows = session.execute(
        select(db.Cabinet.uid, db.Cabinet.category, db.Cabinet.cabinet_group)
        .where(
            db.Cabinet.project_uid == project_uid,
            db.Cabinet.deleted_at.is_(None),
            or_(
                *[db.Cabinet.uid.ilike(pattern) for pattern in patterns],
                *[db.Cabinet.cabinet_id.ilike(pattern) for pattern in patterns],
                *[db.Cabinet.category.ilike(pattern) for pattern in patterns],
                *[db.Cabinet.cabinet_group.ilike(pattern) for pattern in patterns],
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
                *[db.Device.uid.ilike(pattern) for pattern in patterns],
                *[db.Device.device_model_name.ilike(pattern) for pattern in patterns],
                *[db.Device.note.ilike(pattern) for pattern in patterns],
            ),
        )
        .order_by(db.Device.uid)
        .limit(remaining)
    ).all()

    remaining = max(0, limit - len(cabinet_rows) - len(device_rows))
    cable_search_uid = _cable_search_uid_expression()
    cable_rows = session.execute(
        select(db.Cable.uid, cable_search_uid.label("search_uid"), db.Cable.cable_type, db.Cable.import_status)
        .where(
            db.Cable.project_uid == project_uid,
            db.Cable.deleted_at.is_(None),
            remaining > 0,
            or_(
                *[db.Cable.uid.ilike(pattern) for pattern in patterns],
                *[cable_search_uid.ilike(pattern) for pattern in patterns],
                *[db.Cable.cable_type.ilike(pattern) for pattern in patterns],
                *[db.Cable.import_status.ilike(pattern) for pattern in patterns],
                *[db.Cable.a_port_uid.ilike(pattern) for pattern in patterns],
                *[db.Cable.z_port_uid.ilike(pattern) for pattern in patterns],
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
        SearchResult(entity_type="cable", uid=row.uid, label=row.search_uid, description=" / ".join(part for part in (row.cable_type, row.import_status) if part))
        for row in cable_rows
    ]


def _cable_search_uid_expression():
    scoped_prefix = db.Cable.project_uid + ":"
    return func.concat(
        db.Cable.project_uid,
        ":",
        func.regexp_replace(db.Cable.uid, "^" + scoped_prefix, ""),
    )


def _search_patterns(search_term: str) -> list[str]:
    normalized_terms = {
        search_term,
        re.sub(r"[\s+]+", ":", search_term),
    }
    return [f"%{term}%" for term in sorted(normalized_terms) if term]


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
    if source_device is None or source_device.deleted_at is not None:
        raise ValueError(f"Device '{source_device_uid}' was not found.")

    rows = _device_connection_counts(session, source_device_uid=source_device_uid, project_uid=source_device.project_uid)
    by_device: dict[str, dict[str, object]] = {}
    for row in rows:
        target = by_device.setdefault(
            row.target_device_uid,
            {
                "target_cabinet_uid": row.target_cabinet_uid,
                "target_device_model": row.target_device_model,
                "target_rack_unit": row.target_rack_unit,
                "total_cables": 0,
                "cable_type_counts": {},
                "status_counts": {},
            },
        )
        count = int(row.total_cables)
        target["total_cables"] = int(target["total_cables"]) + count
        cable_type_counts = target["cable_type_counts"]
        status_counts = target["status_counts"]
        assert isinstance(cable_type_counts, dict)
        assert isinstance(status_counts, dict)
        cable_type_counts[row.cable_type or "Unknown"] = cable_type_counts.get(row.cable_type or "Unknown", 0) + count
        status_counts[row.import_status or "Unknown"] = status_counts.get(row.import_status or "Unknown", 0) + count

    connections = [
        DeviceConnection(
            target_device_uid=target_device_uid,
            target_device_model=str(target["target_device_model"] or ""),
            target_cabinet_uid=str(target["target_cabinet_uid"]),
            target_rack_unit=int(target["target_rack_unit"]),
            total_cables=int(target["total_cables"]),
            cable_type_counts=dict(sorted(target["cable_type_counts"].items())),
            status_summary=StatusSummary(
                completed=sum(count for status, count in target["status_counts"].items() if _is_completed_status(str(status))),
                total=int(target["total_cables"]),
                status_counts=dict(sorted(target["status_counts"].items())),
            ),
        )
        for target_device_uid, target in by_device.items()
    ]
    connected_cabinets = sorted({connection.target_cabinet_uid for connection in connections})
    return DeviceConnectionSummary(
        source_device_uid=source_device_uid,
        source_cabinet_uid=source_device.cabinet_uid,
        source_rack_unit=source_device.rack_unit,
        connected_cabinet_uids=connected_cabinets,
        connected_devices=sorted(connections, key=lambda item: (-item.total_cables, item.target_device_uid)),
    )


def _device_connection_counts(session: Session, *, source_device_uid: str, project_uid: str):
    a_port = aliased(db.Port)
    z_port = aliased(db.Port)
    target_device = aliased(db.Device)
    source_on_a = (
        select(
            z_port.device_uid.label("target_device_uid"),
            z_port.cabinet_uid.label("target_cabinet_uid"),
            target_device.device_model_name.label("target_device_model"),
            target_device.rack_unit.label("target_rack_unit"),
            db.Cable.cable_type.label("cable_type"),
            db.Cable.import_status.label("import_status"),
            func.count().label("total_cables"),
        )
        .join(a_port, db.Cable.a_port_uid == a_port.uid)
        .join(z_port, db.Cable.z_port_uid == z_port.uid)
        .join(target_device, z_port.device_uid == target_device.uid)
        .where(
            db.Cable.project_uid == project_uid,
            db.Cable.deleted_at.is_(None),
            a_port.deleted_at.is_(None),
            z_port.deleted_at.is_(None),
            target_device.deleted_at.is_(None),
            a_port.device_uid == source_device_uid,
            z_port.device_uid.is_not(None),
            z_port.device_uid != source_device_uid,
        )
        .group_by(
            z_port.device_uid,
            z_port.cabinet_uid,
            target_device.device_model_name,
            target_device.rack_unit,
            db.Cable.cable_type,
            db.Cable.import_status,
        )
    )

    a_port_other = aliased(db.Port)
    z_port_source = aliased(db.Port)
    target_device_other = aliased(db.Device)
    source_on_z = (
        select(
            a_port_other.device_uid.label("target_device_uid"),
            a_port_other.cabinet_uid.label("target_cabinet_uid"),
            target_device_other.device_model_name.label("target_device_model"),
            target_device_other.rack_unit.label("target_rack_unit"),
            db.Cable.cable_type.label("cable_type"),
            db.Cable.import_status.label("import_status"),
            func.count().label("total_cables"),
        )
        .join(a_port_other, db.Cable.a_port_uid == a_port_other.uid)
        .join(z_port_source, db.Cable.z_port_uid == z_port_source.uid)
        .join(target_device_other, a_port_other.device_uid == target_device_other.uid)
        .where(
            db.Cable.project_uid == project_uid,
            db.Cable.deleted_at.is_(None),
            a_port_other.deleted_at.is_(None),
            z_port_source.deleted_at.is_(None),
            target_device_other.deleted_at.is_(None),
            z_port_source.device_uid == source_device_uid,
            a_port_other.device_uid.is_not(None),
            a_port_other.device_uid != source_device_uid,
        )
        .group_by(
            a_port_other.device_uid,
            a_port_other.cabinet_uid,
            target_device_other.device_model_name,
            target_device_other.rack_unit,
            db.Cable.cable_type,
            db.Cable.import_status,
        )
    )

    return session.execute(source_on_a.union_all(source_on_z)).all()


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
