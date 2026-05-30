from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from backend.ingest.cutsheet import CutsheetIngestionResult, CutsheetSummary, ingest_cutsheet
from backend.ingest.overhead import OverheadIngestionResult, ingest_overhead
from backend.models import Cabinet, ConnectorType, Device, PortConnector, Room
from backend.persistence import TopologyDatabase
from backend.validation import BreakoutFanoutRule


def build_topology_database_from_sources(
    cutsheet_path: str | Path,
    overhead_path: str | Path,
    project_uid: str = "MSK01",
    building_id: str = "A",
    cutsheet_sheet_name: str | None = None,
    overhead_sheet_name: str | None = None,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> TopologyDatabase:
    cutsheet_result = ingest_cutsheet(
        cutsheet_path,
        project_uid=project_uid,
        building_id=building_id,
        sheet_name=cutsheet_sheet_name,
        breakout_rules=breakout_rules,
    )
    overhead_result = ingest_overhead(overhead_path, sheet_name=overhead_sheet_name)
    return build_topology_database_from_results(
        cutsheet_result=cutsheet_result,
        overhead_result=overhead_result,
        project_uid=project_uid,
        building_id=building_id,
    )


def build_topology_database_from_results(
    cutsheet_result: CutsheetIngestionResult,
    overhead_result: OverheadIngestionResult,
    project_uid: str = "MSK01",
    building_id: str = "A",
) -> TopologyDatabase:
    devices_by_cabinet = _devices_by_cabinet(cutsheet_result)
    cabinets = [
        Cabinet(
            building_id=building_id,
            data_hall_id=record.data_hall_id,
            cabinet_id=record.cabinet_id,
            category=record.category,
            cabinet_group=record.cabinet_group,
            source_row=record.source_row,
            source_col=record.source_col,
            devices=devices_by_cabinet.get((record.data_hall_id, record.cabinet_id), []),
        )
        for record in overhead_result.cabinets
    ]
    data_halls = _rooms_from_cabinets(cabinets, building_id=building_id)

    return TopologyDatabase(
        project_uid=project_uid,
        building_id=building_id,
        summary=CutsheetSummary(
            rows=len(cutsheet_result.rows),
            data_halls=len(data_halls),
            cabinets=len(cabinets),
            ports=len(cutsheet_result.ports),
            cables=len(cutsheet_result.cables),
            port_collision_findings=len(cutsheet_result.findings),
        ),
        port_collision_findings=cutsheet_result.findings,
        data_halls=data_halls,
        cabinets=cabinets,
        ports=cutsheet_result.ports,
        cables=cutsheet_result.cables,
        rows=cutsheet_result.rows,
    )


def _rooms_from_cabinets(cabinets: list[Cabinet], building_id: str) -> list[Room]:
    cabinets_by_data_hall: dict[str, list[Cabinet]] = defaultdict(list)
    for cabinet in cabinets:
        cabinets_by_data_hall[cabinet.data_hall_id].append(cabinet)

    return [
        Room(
            building_id=building_id,
            room_id=data_hall_id,
            cabinets=sorted(room_cabinets, key=lambda cabinet: cabinet.cabinet_id),
        )
        for data_hall_id, room_cabinets in sorted(cabinets_by_data_hall.items())
    ]


def _devices_by_cabinet(cutsheet_result: CutsheetIngestionResult) -> dict[tuple[str, str], list[Device]]:
    device_ports: dict[tuple[str, str, int, str, str], dict[ConnectorType, dict[str, PortConnector]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for row in cutsheet_result.rows:
        for side in ("a", "z"):
            data_hall_id = getattr(row, f"{side}_data_hall_id")
            cabinet_id = getattr(row, f"{side}_cabinet_id")
            rack_unit = getattr(row, f"{side}_rack_unit")
            device_name = getattr(row, f"{side}_device_name")
            device_model = getattr(row, f"{side}_device_model") or "Unknown"
            port_id = getattr(row, f"{side}_port_id")
            port_uid = getattr(row, f"{side}_port_uid")
            connector_type = _connector_type_from_cable(row.cable_type)
            key = (data_hall_id, cabinet_id, rack_unit, device_model, device_name)
            device_ports[key][connector_type][port_uid] = PortConnector(uid=port_uid, type=connector_type)

    cabinets: dict[tuple[str, str], list[Device]] = defaultdict(list)
    for (data_hall_id, cabinet_id, rack_unit, device_model, device_name), ports_by_type in device_ports.items():
        note = f"Device name: {device_name}" if device_name else ""
        cabinets[(data_hall_id, cabinet_id)].append(
            Device(
                cabinet_id=f"{data_hall_id}:{cabinet_id}",
                rack_unit=rack_unit,
                device_model=device_model,
                ports_by_type={
                    connector_type: sorted(ports.values(), key=lambda port: port.uid)
                    for connector_type, ports in sorted(ports_by_type.items(), key=lambda item: item[0].value)
                },
                note=note,
            )
        )

    return {
        cabinet_key: sorted(devices, key=lambda device: (device.rack_unit, device.device_model, device.note))
        for cabinet_key, devices in cabinets.items()
    }


def _connector_type_from_cable(cable_type: str) -> ConnectorType:
    normalized_cable_type = cable_type.upper()
    if "CAT6" in normalized_cable_type:
        return ConnectorType.CAT6
    if "MPO" in normalized_cable_type:
        return ConnectorType.MPO
    if "LC" in normalized_cable_type:
        return ConnectorType.LC
    if "SC" in normalized_cable_type:
        return ConnectorType.SC
    if "POWER" in normalized_cable_type:
        return ConnectorType.POWER
    return ConnectorType.OTHER
