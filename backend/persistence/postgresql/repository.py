from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.core.enums import CableProgressState, CableProgressStep, ConnectorType, ConstructionPhase, LifecycleStatus
from backend.ingest.cutsheet import CutsheetCableRow, CutsheetSummary
from backend.models import Cabinet, Cable, CableProgressPhase, Device, DeviceModel, DevicePortLayoutEntry, OpticModule, PortConnector, Room
from backend.persistence import TopologyDatabase
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.importer import replace_project_topology
from backend.persistence.postgresql.mutations import MutationUser, PersistedOperation
from backend.persistence.postgresql.mutations import bulk_update_status as bulk_update_postgresql_status
from backend.persistence.postgresql.mutations import list_operations as list_postgresql_operations
from backend.persistence.postgresql.mutations import update_cabinet_status, update_cable, update_device_status
from backend.persistence.postgresql.session import session_factory
from backend.persistence.repository import TopologyRepository
from backend.validation import detect_port_collisions
from backend.validation.device_models import DeviceModelFinding, detect_device_model_findings
from backend.validation.port_collisions import PortConnectionFinding


class PostgresTopologyRepository(TopologyRepository):
    def __init__(
        self,
        project_uid: str,
        building_id: str = "A",
        database_url: str | None = None,
    ):
        self.project_uid = project_uid
        self.building_id = building_id
        self._session_factory = session_factory(database_url)

    def load(self) -> TopologyDatabase:
        with self._session_factory() as session:
            return load_project_topology(session, project_uid=self.project_uid, building_id=self.building_id)

    def save(self, database: TopologyDatabase) -> None:
        with self._session_factory() as session:
            with session.begin():
                replace_project_topology(session, database)

    def update_cabinet_status(
        self,
        cabinet_uid: str,
        lifecycle_status: str | LifecycleStatus,
        expected_version: int | None = None,
        user: MutationUser | None = None,
    ) -> PersistedOperation:
        with self._session_factory() as session:
            with session.begin():
                return update_cabinet_status(
                    session,
                    cabinet_uid=cabinet_uid,
                    lifecycle_status=lifecycle_status,
                    expected_version=expected_version,
                    user=user,
                )

    def update_device_status(
        self,
        device_uid: str,
        lifecycle_status: str | LifecycleStatus,
        expected_version: int | None = None,
        user: MutationUser | None = None,
    ) -> PersistedOperation:
        with self._session_factory() as session:
            with session.begin():
                return update_device_status(
                    session,
                    device_uid=device_uid,
                    lifecycle_status=lifecycle_status,
                    expected_version=expected_version,
                    user=user,
                )

    def update_cable(
        self,
        cable_uid: str,
        *,
        status: str | None = None,
        progress: dict | None = None,
        current_phase: dict[str, Any] | CableProgressPhase | None = None,
        length_used_meters: float | None = None,
        note: str | None = None,
        expected_version: int | None = None,
        user: MutationUser | None = None,
    ) -> PersistedOperation:
        with self._session_factory() as session:
            with session.begin():
                return update_cable(
                    session,
                    cable_uid=cable_uid,
                    status=status,
                    progress=progress,
                    current_phase=current_phase,
                    length_used_meters=length_used_meters,
                    note=note,
                    expected_version=expected_version,
                    user=user,
                )

    def bulk_update_status(
        self,
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
    ) -> list[PersistedOperation]:
        with self._session_factory() as session:
            with session.begin():
                return bulk_update_postgresql_status(
                    session,
                    entity_type=entity_type,
                    entity_uids=entity_uids,
                    lifecycle_status=lifecycle_status,
                    status=status,
                    expected_version=expected_version,
                    user=user,
                    operation_group_uid=operation_group_uid,
                    source_type=source_type,
                    source_uid=source_uid,
                )

    def list_operations(self, limit: int = 100, after: int | None = None) -> list[PersistedOperation]:
        return self.list_operation_page(limit=limit, after=after).operations

    def list_operation_page(
        self,
        limit: int = 100,
        after: int | None = None,
        offset: int = 0,
        operation_type: str | None = None,
        user_uid: str | None = None,
        start_time=None,
        end_time=None,
    ):
        with self._session_factory() as session:
            return list_postgresql_operations(
                session,
                project_uid=self.project_uid,
                limit=limit,
                after=after,
                offset=offset,
                operation_type=operation_type,
                user_uid=user_uid,
                start_time=start_time,
                end_time=end_time,
            )


    def validation_findings(self) -> tuple[list[PortConnectionFinding], list[DeviceModelFinding], list[DeviceModelFinding]]:
        with self._session_factory() as session:
            return _validation_findings(session, self.project_uid)

    def revalidate(self) -> tuple[list[PortConnectionFinding], list[DeviceModelFinding], list[DeviceModelFinding]]:
        with self._session_factory() as session:
            with session.begin():
                rows = _source_rows(session, self.project_uid)
                port_collisions = detect_port_collisions(rows)
                device_model_mismatches, device_model_format_issues = detect_device_model_findings(rows)
                _replace_validation_findings(
                    session,
                    project_uid=self.project_uid,
                    port_collisions=port_collisions,
                    device_model_mismatches=device_model_mismatches,
                    device_model_format_issues=device_model_format_issues,
                )
                return port_collisions, device_model_mismatches, device_model_format_issues

def load_project_topology(
    session: Session,
    *,
    project_uid: str,
    building_id: str = "A",
) -> TopologyDatabase:
    building_uid = f"{project_uid}:{building_id}".upper()
    building = session.get(db.Building, building_uid)
    if building is None:
        raise ValueError(f"Building '{building_uid}' was not found.")

    rows = _source_rows(session, project_uid)
    ports_by_uid = _ports(session, project_uid)
    device_models = _device_models(session)
    cabinets = _cabinets(session, project_uid, ports_by_uid)
    data_halls = _rooms(session, project_uid, building_id, cabinets)
    cables = _cables(session, project_uid, ports_by_uid)
    port_collision_findings, device_model_mismatches, device_model_format_issues = _validation_findings(session, project_uid)
    summary = _summary(
        rows=rows,
        data_halls=data_halls,
        cabinets=cabinets,
        ports=ports_by_uid,
        cables=cables,
        port_collision_findings=port_collision_findings,
    )

    return TopologyDatabase(
        project_uid=project_uid,
        building_id=building.building_id,
        summary=summary,
        port_collision_findings=port_collision_findings,
        device_model_mismatches=device_model_mismatches,
        device_model_format_issues=device_model_format_issues,
        data_halls=data_halls,
        cabinets=cabinets,
        device_models=device_models,
        ports=sorted(ports_by_uid.values(), key=lambda port: port.uid),
        cables=cables,
        rows=rows,
    )


def _source_rows(session: Session, project_uid: str) -> list[CutsheetCableRow]:
    rows = session.execute(
        select(db.SourceCableRow)
        .join(db.SourceImport, db.SourceCableRow.source_import_uid == db.SourceImport.uid)
        .where(db.SourceImport.project_uid == project_uid)
        .order_by(db.SourceCableRow.row_number, db.SourceCableRow.uid)
    ).scalars()
    return [CutsheetCableRow(**row.payload) for row in rows]


def _ports(session: Session, project_uid: str) -> dict[str, PortConnector]:
    rows = session.execute(
        select(db.Port)
        .where(db.Port.project_uid == project_uid, db.Port.deleted_at.is_(None))
        .order_by(db.Port.uid)
    ).scalars()
    return {
        row.uid: PortConnector(
            uid=row.uid,
            type=ConnectorType(row.connector_type),
            note=row.note,
        )
        for row in rows
    }


def _device_models(session: Session) -> list[DeviceModel]:
    rows = session.execute(
        select(db.DeviceModel)
        .where(db.DeviceModel.deleted_at.is_(None))
        .order_by(db.DeviceModel.model_name, db.DeviceModel.uid)
    ).scalars()
    return [
        DeviceModel(
            uid=row.uid,
            model_name=row.model_name,
            manufacturer=row.manufacturer,
            rack_units=row.rack_units,
            front_panel_svg=row.front_panel_svg,
            back_panel_svg=row.back_panel_svg,
            port_layout=[_model_from_payload(DevicePortLayoutEntry, item) for item in row.port_layout],
            note=row.note,
        )
        for row in rows
    ]


def _cabinets(session: Session, project_uid: str, ports_by_uid: dict[str, PortConnector]) -> list[Cabinet]:
    devices_by_cabinet: dict[str, list[Device]] = defaultdict(list)
    for row in session.execute(
        select(db.Device)
        .where(db.Device.project_uid == project_uid, db.Device.deleted_at.is_(None))
        .order_by(db.Device.cabinet_uid, db.Device.rack_unit, db.Device.device_model_name)
    ).scalars():
        device_ports: dict[ConnectorType, list[PortConnector]] = defaultdict(list)
        for port_row in session.execute(
            select(db.Port)
            .where(db.Port.device_uid == row.uid, db.Port.deleted_at.is_(None))
            .order_by(db.Port.uid)
        ).scalars():
            port = ports_by_uid[port_row.uid]
            device_ports[port.type].append(port)
        devices_by_cabinet[row.cabinet_uid].append(
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
                port_layout_overrides=list(row.port_layout_overrides),
                ports_by_type={connector_type: ports for connector_type, ports in sorted(device_ports.items(), key=lambda item: item[0].value)},
                note=row.note,
            )
        )

    cabinet_rows = session.execute(
        select(db.Cabinet)
        .where(db.Cabinet.project_uid == project_uid, db.Cabinet.deleted_at.is_(None))
        .order_by(db.Cabinet.room_uid, db.Cabinet.source_row, db.Cabinet.source_col, db.Cabinet.cabinet_id)
    ).scalars()
    return [
        Cabinet(
            building_id=row.building_uid.split(":", 1)[1],
            data_hall_id=row.room_uid.rsplit(":", 1)[1],
            cabinet_id=row.cabinet_id,
            category=row.category,
            cabinet_group=row.cabinet_group,
            lifecycle_status=LifecycleStatus(row.lifecycle_status),
            construction_phase=ConstructionPhase(row.construction_phase),
            max_rack_unit=row.max_rack_unit,
            source_row=row.source_row,
            source_col=row.source_col,
            devices=devices_by_cabinet.get(row.uid, []),
        )
        for row in cabinet_rows
    ]


def _rooms(session: Session, project_uid: str, building_id: str, cabinets: list[Cabinet]) -> list[Room]:
    cabinets_by_room: dict[str, list[Cabinet]] = defaultdict(list)
    for cabinet in cabinets:
        cabinets_by_room[cabinet.data_hall_id].append(cabinet)
    room_rows = session.execute(
        select(db.Room)
        .where(db.Room.project_uid == project_uid, db.Room.deleted_at.is_(None))
        .order_by(db.Room.room_id)
    ).scalars()
    return [
        Room(
            building_id=building_id,
            room_id=row.room_id,
            lifecycle_status=LifecycleStatus(row.lifecycle_status),
            construction_phase=ConstructionPhase(row.construction_phase),
            cabinets=sorted(cabinets_by_room.get(row.room_id, []), key=lambda cabinet: cabinet.cabinet_id),
        )
        for row in room_rows
    ]


def _cables(session: Session, project_uid: str, ports_by_uid: dict[str, PortConnector]) -> list[Cable]:
    rows = session.execute(
        select(db.Cable)
        .where(db.Cable.project_uid == project_uid, db.Cable.deleted_at.is_(None))
        .order_by(db.Cable.uid)
    ).scalars()
    return [
        Cable(
            uid=row.uid,
            a_side=ports_by_uid[row.a_port_uid],
            z_side=ports_by_uid[row.z_port_uid],
            cable_type=row.cable_type,
            group=row.cable_group,
            status=row.import_status,
            construction_phase=ConstructionPhase(row.construction_phase),
            progress={CableProgressStep(key): CableProgressState(value) for key, value in row.progress.items()},
            current_phase=_optional_model(CableProgressPhase, row.current_phase),
            designed_length_meters=float(row.designed_length_meters) if row.designed_length_meters is not None else None,
            length_used_meters=float(row.length_used_meters),
            a_optic=_optional_model(OpticModule, row.a_optic),
            z_optic=_optional_model(OpticModule, row.z_optic),
            note=row.note,
        )
        for row in rows
    ]


def _validation_findings(
    session: Session,
    project_uid: str,
) -> tuple[list[PortConnectionFinding], list[DeviceModelFinding], list[DeviceModelFinding]]:
    rows = session.execute(
        select(db.ValidationFinding)
        .where(db.ValidationFinding.project_uid == project_uid)
        .order_by(db.ValidationFinding.uid)
    ).scalars()
    port_collisions: list[PortConnectionFinding] = []
    device_model_mismatches: list[DeviceModelFinding] = []
    device_model_format_issues: list[DeviceModelFinding] = []
    for row in rows:
        if row.finding_type == "port_collision":
            port_collisions.append(PortConnectionFinding(**row.payload))
        elif row.finding_type == "device_model_mismatch":
            device_model_mismatches.append(DeviceModelFinding(**row.payload))
        elif row.finding_type == "device_model_format_issue":
            device_model_format_issues.append(DeviceModelFinding(**row.payload))
    return port_collisions, device_model_mismatches, device_model_format_issues


def _replace_validation_findings(
    session: Session,
    *,
    project_uid: str,
    port_collisions: list[PortConnectionFinding],
    device_model_mismatches: list[DeviceModelFinding],
    device_model_format_issues: list[DeviceModelFinding],
) -> None:
    session.execute(delete(db.ValidationFinding).where(db.ValidationFinding.project_uid == project_uid))
    for index, finding in enumerate(port_collisions, start=1):
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
    for index, finding in enumerate(device_model_mismatches, start=1):
        session.add(
            db.ValidationFinding(
                uid=f"{project_uid}:device-model-mismatch:{index}",
                project_uid=project_uid,
                finding_type="device_model_mismatch",
                severity="warning",
                entity_type="device",
                entity_uid=finding.device_uid,
                payload=_payload(finding),
            )
        )
    for index, finding in enumerate(device_model_format_issues, start=1):
        session.add(
            db.ValidationFinding(
                uid=f"{project_uid}:device-model-format-issue:{index}",
                project_uid=project_uid,
                finding_type="device_model_format_issue",
                severity="warning",
                entity_type="device",
                entity_uid=finding.device_uid,
                payload=_payload(finding),
            )
        )


def _payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _summary(
    *,
    rows: list[CutsheetCableRow],
    data_halls: list[Room],
    cabinets: list[Cabinet],
    ports: dict[str, PortConnector],
    cables: list[Cable],
    port_collision_findings: list[PortConnectionFinding],
) -> CutsheetSummary:
    return CutsheetSummary(
        rows=len(rows),
        data_halls=len(data_halls),
        cabinets=len(cabinets),
        ports=len(ports),
        cables=len(cables),
        port_collision_findings=len(port_collision_findings),
    )


def _optional_model(model_type: type[BaseModel], payload: dict[str, Any] | None):
    if payload is None:
        return None
    return _model_from_payload(model_type, payload)


def _model_from_payload(model_type: type[BaseModel], payload: dict[str, Any]):
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)
    return model_type.parse_obj(payload)




