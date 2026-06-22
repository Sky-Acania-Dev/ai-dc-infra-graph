from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models import Cabinet as DomainCabinet
from backend.models import Cable as DomainCable
from backend.models import Device as DomainDevice
from backend.models import PortConnector
from backend.persistence import TopologyDatabase
from backend.persistence.postgresql import models as db


def replace_project_topology(
    session: Session,
    database: TopologyDatabase,
    *,
    version_name: str | None = None,
    version_date: date | None = None,
    source_operator: str | None = None,
) -> None:
    """Replace one project's imported topology rows in PostgreSQL.

    This is the first PostgreSQL persistence path for normalized cutsheet output.
    It is intentionally a project-scoped replace operation for imports, not a
    user-edit mutation path.
    """
    project_uid = database.project_uid
    building_uid = _building_uid(project_uid, database.building_id)
    version_name = version_name or f"import-{date.today().isoformat()}"
    version_date = version_date or date.today()
    source_operator = _normalize_source_operator(source_operator)
    topology_version_uid = _topology_version_uid(project_uid, version_name)
    source_import_uid = f"{topology_version_uid}:source-import"
    existing_entities = _current_entity_keys(session, project_uid)

    _delete_project_topology(session, project_uid)

    project = session.get(db.Project, project_uid)
    if project is None:
        session.add(
            db.Project(
                uid=project_uid,
                full_name=project_uid,
                metadata_json={"source": "cutsheet_import"},
            )
        )
    else:
        project.full_name = project.full_name or project_uid
        project.metadata_json = {**project.metadata_json, "source": "cutsheet_import"}
    session.flush()
    source_import = session.get(db.SourceImport, source_import_uid)
    if source_import is None:
        source_import = db.SourceImport(
            uid=source_import_uid,
            project_uid=project_uid,
            source_type="topology_database",
        )
        session.add(source_import)
    source_import.source_path = ""
    source_import.version_name = version_name
    source_import.version_date = version_date
    source_import.source_operator = source_operator
    source_import.summary = _payload(database.summary)
    session.flush()

    topology_version = session.get(db.TopologyVersion, topology_version_uid)
    if topology_version is None:
        topology_version = db.TopologyVersion(
            uid=topology_version_uid,
            project_uid=project_uid,
            version_name=version_name,
        )
        session.add(topology_version)
    topology_version.version_date = version_date
    topology_version.source_operator = source_operator
    topology_version.source_import_uid = source_import_uid
    topology_version.operation_group_uid = topology_version_uid
    topology_version.summary = _payload(database.summary)
    session.flush()

    session.add(
        db.Building(
            uid=building_uid,
            project_uid=project_uid,
            building_id=database.building_id,
        )
    )
    session.flush()

    for room in database.data_halls:
        room_uid = _room_uid(project_uid, database.building_id, room.room_id)
        session.add(
            db.Room(
                uid=room_uid,
                project_uid=project_uid,
                building_uid=building_uid,
                room_id=room.room_id,
                room_type="data_hall",
                lifecycle_status=_enum_value(room.lifecycle_status),
                construction_phase=_enum_value(room.construction_phase),
            )
        )
    session.flush()

    for model in database.device_models:
        session.add(
            db.DeviceModel(
                uid=model.uid,
                model_name=model.model_name,
                manufacturer=model.manufacturer,
                rack_units=model.rack_units,
                front_panel_svg=model.front_panel_svg,
                back_panel_svg=model.back_panel_svg,
                port_layout=_payload_list(model.port_layout),
                note=model.note,
            )
        )
    session.flush()

    for cabinet in database.cabinets:
        session.add(_cabinet_record(database, building_uid, cabinet))
    session.flush()

    for cabinet in database.cabinets:
        for device in cabinet.devices:
            session.add(_device_record(database, building_uid, cabinet, device))
    session.flush()

    ports_by_uid = _ports_by_uid(database)
    for port in sorted(ports_by_uid.values(), key=lambda item: item.uid):
        session.add(_port_record(database, building_uid, port))
    session.flush()

    for cable in database.cables:
        session.add(_cable_record(database, building_uid, cable))
    session.flush()

    for index, row in enumerate(database.rows, start=1):
        cable_uid = database.cables[index - 1].uid if index <= len(database.cables) else None
        session.add(
            db.SourceCableRow(
                uid=f"{source_import_uid}:row:{index}",
                source_import_uid=source_import_uid,
                row_number=index,
                payload=_payload(row),
                cable_uid=cable_uid,
            )
        )

    for index, finding in enumerate(database.port_collision_findings, start=1):
        session.add(
            db.ValidationFinding(
                uid=f"{project_uid}:port-collision:{index}",
                project_uid=project_uid,
                finding_type="port_collision",
                severity="error",
                entity_type="port",
                entity_uid=finding.port_uid,
                payload=_payload(finding),
            )
        )
    for index, finding in enumerate(database.device_model_mismatches, start=1):
        session.add(
            db.ValidationFinding(
                uid=f"{project_uid}:device-model-mismatch:{index}",
                project_uid=project_uid,
                finding_type="device_model_mismatch",
                severity="warning",
                entity_type="device",
                payload=_payload(finding),
            )
        )
    for index, finding in enumerate(database.device_model_format_issues, start=1):
        session.add(
            db.ValidationFinding(
                uid=f"{project_uid}:device-model-format-issue:{index}",
                project_uid=project_uid,
                finding_type="device_model_format_issue",
                severity="warning",
                entity_type="device",
                payload=_payload(finding),
            )
        )
    _sync_entity_history(
        session,
        project_uid=project_uid,
        topology_version_uid=topology_version_uid,
        existing_entities=existing_entities,
        current_entities=_database_entity_keys(database),
    )


def _delete_project_topology(session: Session, project_uid: str) -> None:
    source_import_uids = select(db.SourceImport.uid).where(db.SourceImport.project_uid == project_uid)
    session.execute(delete(db.SourceCableRow).where(db.SourceCableRow.source_import_uid.in_(source_import_uids)))
    for table_model in (
        db.CableBundleCable,
        db.CableBundleLadderRackSegment,
        db.Cable,
        db.Port,
        db.CableBundle,
        db.LadderRackSegment,
        db.LadderRackJunction,
        db.Device,
        db.Cabinet,
        db.Room,
        db.ValidationFinding,
        db.DeviceVariant,
        db.Building,
    ):
        if "project_uid" in table_model.__table__.columns:
            session.execute(delete(table_model).where(table_model.__table__.c.project_uid == project_uid))
    session.execute(delete(db.DeviceModel))


def _sync_entity_history(
    session: Session,
    *,
    project_uid: str,
    topology_version_uid: str,
    existing_entities: set[tuple[str, str]],
    current_entities: set[tuple[str, str]],
) -> None:
    for entity_type, entity_uid in sorted(current_entities):
        history_uid = _entity_history_uid(project_uid, entity_type, entity_uid)
        history = session.get(db.EntityHistory, history_uid)
        if history is None:
            session.add(
                db.EntityHistory(
                    uid=history_uid,
                    project_uid=project_uid,
                    entity_type=entity_type,
                    entity_uid=entity_uid,
                    first_version_uid=topology_version_uid,
                )
            )
            continue
        if history.last_version_uid is not None:
            history.last_version_uid = None
            history.last_operation_id = None

    for entity_type, entity_uid in sorted(existing_entities - current_entities):
        history_uid = _entity_history_uid(project_uid, entity_type, entity_uid)
        history = session.get(db.EntityHistory, history_uid)
        if history is not None and history.last_version_uid is None:
            history.last_version_uid = topology_version_uid


def _current_entity_keys(session: Session, project_uid: str) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for entity_type, model_type in (
        ("building", db.Building),
        ("room", db.Room),
        ("cabinet", db.Cabinet),
        ("device", db.Device),
        ("port", db.Port),
        ("cable", db.Cable),
        ("cable_bundle", db.CableBundle),
        ("ladder_rack_junction", db.LadderRackJunction),
        ("ladder_rack_segment", db.LadderRackSegment),
    ):
        keys.update(
            (entity_type, uid)
            for uid in session.execute(select(model_type.uid).where(model_type.project_uid == project_uid)).scalars()
        )
    return keys


def _database_entity_keys(database: TopologyDatabase) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = {("building", _building_uid(database.project_uid, database.building_id))}
    keys.update(("room", _room_uid(database.project_uid, database.building_id, room.room_id)) for room in database.data_halls)
    keys.update(("cabinet", _cabinet_uid(cabinet)) for cabinet in database.cabinets)
    for cabinet in database.cabinets:
        keys.update(("device", _device_uid(_cabinet_uid(cabinet), device.rack_unit)) for device in cabinet.devices)
    keys.update(("port", port.uid) for port in _ports_by_uid(database).values())
    keys.update(("cable", cable.uid) for cable in database.cables)
    return keys


def _entity_history_uid(project_uid: str, entity_type: str, entity_uid: str) -> str:
    return f"{project_uid}:{entity_type}:{entity_uid}".upper()


def _topology_version_uid(project_uid: str, version_name: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "-", version_name.upper()).strip("-")
    return f"{project_uid}:VERSION:{slug or 'IMPORT'}"


def _normalize_source_operator(source_operator: str | None) -> str:
    return (source_operator or "CUSTOMER").strip().upper()


def _cabinet_record(database: TopologyDatabase, building_uid: str, cabinet: DomainCabinet) -> db.Cabinet:
    cabinet_uid = _cabinet_uid(cabinet)
    return db.Cabinet(
        uid=cabinet_uid,
        project_uid=database.project_uid,
        building_uid=building_uid,
        room_uid=_room_uid(database.project_uid, database.building_id, cabinet.data_hall_id),
        cabinet_id=cabinet.cabinet_id,
        category=cabinet.category,
        cabinet_group=cabinet.cabinet_group,
        lifecycle_status=_enum_value(cabinet.lifecycle_status),
        construction_phase=_enum_value(cabinet.construction_phase),
        max_rack_unit=cabinet.max_rack_unit,
        source_row=cabinet.source_row,
        source_col=cabinet.source_col,
    )


def _device_record(
    database: TopologyDatabase,
    building_uid: str,
    cabinet: DomainCabinet,
    device: DomainDevice,
) -> db.Device:
    cabinet_uid = _cabinet_uid(cabinet)
    device_uid = _device_uid(cabinet_uid, device.rack_unit)
    return db.Device(
        uid=device_uid,
        project_uid=database.project_uid,
        building_uid=building_uid,
        room_uid=_room_uid(database.project_uid, database.building_id, cabinet.data_hall_id),
        cabinet_uid=cabinet_uid,
        rack_unit=device.rack_unit,
        device_model_uid=device.device_model_uid or None,
        device_model_name=device.device_model,
        rack_units=device.rack_units,
        lifecycle_status=_enum_value(device.lifecycle_status),
        construction_phase=_enum_value(device.construction_phase),
        aliases=list(device.aliases),
        model_aliases=list(device.model_aliases),
        port_layout_overrides=_payload_list(device.port_layout_overrides),
        note=device.note,
    )


def _port_record(database: TopologyDatabase, building_uid: str, port: PortConnector) -> db.Port:
    room_id, cabinet_id, rack_unit, port_name = _parse_port_uid(port.uid)
    cabinet_uid = f"{room_id}:{cabinet_id}".upper()
    device_uid = _device_uid(cabinet_uid, rack_unit)
    return db.Port(
        uid=port.uid,
        project_uid=database.project_uid,
        building_uid=building_uid,
        room_uid=_room_uid(database.project_uid, database.building_id, room_id),
        cabinet_uid=cabinet_uid,
        device_uid=device_uid,
        port_name=port_name,
        connector_type=_enum_value(port.type),
        note=port.note,
    )


def _cable_record(database: TopologyDatabase, building_uid: str, cable: DomainCable) -> db.Cable:
    a_room_id = _parse_port_uid(cable.a_side.uid)[0]
    z_room_id = _parse_port_uid(cable.z_side.uid)[0]
    room_uid = _room_uid(database.project_uid, database.building_id, a_room_id) if a_room_id == z_room_id else None
    return db.Cable(
        uid=cable.uid,
        project_uid=database.project_uid,
        building_uid=building_uid,
        room_uid=room_uid,
        a_port_uid=cable.a_side.uid,
        z_port_uid=cable.z_side.uid,
        cable_type=cable.cable_type,
        cable_group=cable.group,
        import_status=cable.status,
        construction_phase=_enum_value(cable.construction_phase),
        a_label_text=cable.a_label_text,
        z_label_text=cable.z_label_text,
        progress={_enum_value(key): _enum_value(value) for key, value in cable.progress.items()},
        current_phase=_payload_or_none(cable.current_phase),
        designed_length_meters=cable.designed_length_meters,
        length_used_meters=cable.length_used_meters,
        a_optic=_payload_or_none(cable.a_optic),
        z_optic=_payload_or_none(cable.z_optic),
        note=cable.note,
    )


def _ports_by_uid(database: TopologyDatabase) -> dict[str, PortConnector]:
    ports = {port.uid: port for port in database.ports}
    for cable in database.cables:
        ports[cable.a_side.uid] = cable.a_side
        ports[cable.z_side.uid] = cable.z_side
    return ports


def _payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _payload_or_none(model: BaseModel | None) -> dict[str, Any] | None:
    return _payload(model) if model is not None else None


def _payload_list(models: list[BaseModel]) -> list[dict[str, Any]]:
    return [_payload(model) for model in models]


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _building_uid(project_uid: str, building_id: str) -> str:
    return f"{project_uid}:{building_id}".upper()


def _room_uid(project_uid: str, building_id: str, room_id: str) -> str:
    return f"{project_uid}:{building_id}:{room_id}".upper()


def _cabinet_uid(cabinet: DomainCabinet) -> str:
    return f"{cabinet.data_hall_id}:{cabinet.cabinet_id}".upper()


def _device_uid(cabinet_uid: str, rack_unit: int) -> str:
    return f"{cabinet_uid}:{rack_unit}".upper()


def _parse_port_uid(port_uid: str) -> tuple[str, str, int, str]:
    room_id, cabinet_id, rack_unit, port_name = port_uid.split(":", 3)
    return room_id.upper(), cabinet_id.zfill(3), int(rack_unit), port_name
