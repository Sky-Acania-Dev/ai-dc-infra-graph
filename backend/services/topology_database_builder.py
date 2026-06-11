from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Sequence

from backend.ingest.cutsheet import CutsheetIngestionResult, CutsheetSummary
from backend.ingest.cutsheet_pipeline import CutsheetIngestionPipelineResult, CutsheetSourceSpec, ingest_cutsheet_sources
from backend.ingest.overhead import OverheadIngestionResult, ingest_overhead
from backend.models import Cabinet, ConnectorType, ConstructionPhase, Device, LifecycleStatus, PortConnector, Room
from backend.persistence import TopologyDatabase
from backend.services.status_overrides import StatusOverrides, apply_status_overrides, load_status_overrides
from backend.validation import BreakoutFanoutRule, detect_port_collisions
from backend.validation.device_models import detect_device_model_findings


def build_topology_database_from_sources(
    cutsheet_path: str | Path,
    overhead_path: str | Path,
    roce_cutsheet_path: str | Path | None = None,
    project_uid: str = "MSK01",
    building_id: str = "A",
    cutsheet_sheet_name: str | None = None,
    roce_cutsheet_sheet_name: str | Sequence[str] | None = None,
    overhead_sheet_name: str | None = None,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
    status_overrides_path: str | Path | None = None,
    default_max_rack_unit: int = 48,
) -> TopologyDatabase:
    cutsheet_sources = [
        CutsheetSourceSpec(
            source_name="management",
            path=str(cutsheet_path),
            sheet_name=cutsheet_sheet_name,
            construction_phase=ConstructionPhase.MANAGEMENT_ETHERNET,
        )
    ]
    if roce_cutsheet_path:
        for sheet_name in _source_sheet_names(roce_cutsheet_sheet_name):
            source_name = "roce" if sheet_name is None else f"roce:{sheet_name}"
            cutsheet_sources.append(
                CutsheetSourceSpec(
                    source_name=source_name,
                    path=str(roce_cutsheet_path),
                    sheet_name=sheet_name,
                    construction_phase=ConstructionPhase.ROCE,
                )
            )
    cutsheet_pipeline_result = ingest_cutsheet_sources(
        cutsheet_sources,
        project_uid=project_uid,
        building_id=building_id,
        breakout_rules=breakout_rules,
    )
    overhead_result = ingest_overhead(overhead_path, sheet_name=overhead_sheet_name)
    return build_topology_database_from_pipeline_result(
        cutsheet_pipeline_result=cutsheet_pipeline_result,
        overhead_result=overhead_result,
        project_uid=project_uid,
        building_id=building_id,
        status_overrides=load_status_overrides(status_overrides_path),
        default_max_rack_unit=default_max_rack_unit,
        breakout_rules=breakout_rules,
    )


def _source_sheet_names(sheet_name: str | Sequence[str] | None) -> list[str | None]:
    if sheet_name is None:
        return [None]
    if isinstance(sheet_name, str):
        return [sheet_name]
    return list(sheet_name) or [None]


def build_topology_database_from_pipeline_result(
    cutsheet_pipeline_result: CutsheetIngestionPipelineResult,
    overhead_result: OverheadIngestionResult,
    project_uid: str = "MSK01",
    building_id: str = "A",
    status_overrides: StatusOverrides | None = None,
    default_max_rack_unit: int = 48,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> TopologyDatabase:
    if not cutsheet_pipeline_result.sources:
        raise ValueError("At least one cutsheet source is required.")
    return _build_topology_database_from_cutsheet_inputs(
        cutsheet_inputs=[
            (source.result, source.construction_phase)
            for source in cutsheet_pipeline_result.sources
        ],
        overhead_result=overhead_result,
        project_uid=project_uid,
        building_id=building_id,
        status_overrides=status_overrides,
        default_max_rack_unit=default_max_rack_unit,
        breakout_rules=breakout_rules,
    )


def build_topology_database_from_results(
    cutsheet_result: CutsheetIngestionResult,
    overhead_result: OverheadIngestionResult,
    roce_cutsheet_result: CutsheetIngestionResult | None = None,
    project_uid: str = "MSK01",
    building_id: str = "A",
    status_overrides: StatusOverrides | None = None,
    default_max_rack_unit: int = 48,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> TopologyDatabase:
    return _build_topology_database_from_cutsheet_inputs(
        cutsheet_inputs=_cutsheet_phase_inputs(cutsheet_result, roce_cutsheet_result),
        overhead_result=overhead_result,
        project_uid=project_uid,
        building_id=building_id,
        status_overrides=status_overrides,
        default_max_rack_unit=default_max_rack_unit,
        breakout_rules=breakout_rules,
    )


def _build_topology_database_from_cutsheet_inputs(
    cutsheet_inputs: list[tuple[CutsheetIngestionResult, ConstructionPhase]],
    overhead_result: OverheadIngestionResult,
    project_uid: str = "MSK01",
    building_id: str = "A",
    status_overrides: StatusOverrides | None = None,
    default_max_rack_unit: int = 48,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> TopologyDatabase:
    status_overrides = status_overrides or StatusOverrides()
    combined_rows = [row for result, _phase in cutsheet_inputs for row in result.rows]
    combined_ports = _combined_ports(cutsheet_inputs)
    combined_findings = detect_port_collisions(combined_rows, breakout_rules=breakout_rules)
    devices_by_cabinet = _devices_by_cabinet(cutsheet_inputs)
    cables = _cables_with_construction_phase(cutsheet_inputs)
    cabinets = [
        Cabinet(
            building_id=building_id,
            data_hall_id=record.data_hall_id,
            cabinet_id=record.cabinet_id,
            category=record.category,
            cabinet_group=record.cabinet_group,
            lifecycle_status=_cabinet_status(record.data_hall_id, record.cabinet_id, record.category, status_overrides),
            construction_phase=_cabinet_construction_phase(record.data_hall_id, record.category),
            max_rack_unit=_max_rack_unit(record.data_hall_id, record.cabinet_id, status_overrides, default_max_rack_unit),
            source_row=record.source_row,
            source_col=record.source_col,
            devices=_devices_for_cabinet(record.data_hall_id, record.cabinet_id, devices_by_cabinet, status_overrides),
        )
        for record in overhead_result.cabinets
    ]
    data_halls = _rooms_from_cabinets(cabinets, building_id=building_id, status_overrides=status_overrides)
    device_model_mismatches, device_model_format_issues = detect_device_model_findings(combined_rows)

    database = TopologyDatabase(
        project_uid=project_uid,
        building_id=building_id,
        summary=CutsheetSummary(
            rows=len(combined_rows),
            data_halls=len(data_halls),
            cabinets=len(cabinets),
            ports=len(combined_ports),
            cables=len(cables),
            port_collision_findings=len(combined_findings),
        ),
        port_collision_findings=combined_findings,
        device_model_mismatches=device_model_mismatches,
        device_model_format_issues=device_model_format_issues,
        data_halls=data_halls,
        cabinets=cabinets,
        ports=combined_ports,
        cables=cables,
        rows=combined_rows,
    )
    return apply_status_overrides(database, status_overrides)


def _cutsheet_phase_inputs(
    cutsheet_result: CutsheetIngestionResult,
    roce_cutsheet_result: CutsheetIngestionResult | None,
) -> list[tuple[CutsheetIngestionResult, ConstructionPhase]]:
    inputs = [(cutsheet_result, ConstructionPhase.MANAGEMENT_ETHERNET)]
    if roce_cutsheet_result is not None:
        inputs.append((roce_cutsheet_result, ConstructionPhase.ROCE))
    return inputs


def _rooms_from_cabinets(cabinets: list[Cabinet], building_id: str, status_overrides: StatusOverrides) -> list[Room]:
    cabinets_by_data_hall: dict[str, list[Cabinet]] = defaultdict(list)
    for cabinet in cabinets:
        cabinets_by_data_hall[cabinet.data_hall_id].append(cabinet)

    return [
        Room(
            building_id=building_id,
            room_id=data_hall_id,
            lifecycle_status=status_overrides.data_halls.get(data_hall_id, LifecycleStatus.UNKNOWN),
            construction_phase=_data_hall_construction_phase(data_hall_id),
            cabinets=sorted(room_cabinets, key=lambda cabinet: cabinet.cabinet_id),
        )
        for data_hall_id, room_cabinets in sorted(cabinets_by_data_hall.items())
    ]


def _combined_ports(cutsheet_inputs: list[tuple[CutsheetIngestionResult, ConstructionPhase]]) -> list[PortConnector]:
    ports_by_uid: dict[str, PortConnector] = {}
    for result, _phase in cutsheet_inputs:
        for port in result.ports:
            ports_by_uid[port.uid] = port
    return sorted(ports_by_uid.values(), key=lambda port: port.uid)


def _devices_by_cabinet(
    cutsheet_inputs: list[tuple[CutsheetIngestionResult, ConstructionPhase]],
) -> dict[tuple[str, str], list[Device]]:
    device_ports: dict[tuple[str, str, int], dict[ConnectorType, dict[str, PortConnector]]] = defaultdict(lambda: defaultdict(dict))
    device_names: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    device_models: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    device_phases: dict[tuple[str, str, int], set[ConstructionPhase]] = defaultdict(set)

    for result, construction_phase in cutsheet_inputs:
        for row in result.rows:
            for side in ("a", "z"):
                data_hall_id = getattr(row, f"{side}_data_hall_id")
                cabinet_id = getattr(row, f"{side}_cabinet_id")
                rack_unit = getattr(row, f"{side}_rack_unit")
                device_name = getattr(row, f"{side}_device_name")
                device_model = getattr(row, f"{side}_device_model")
                port_uid = getattr(row, f"{side}_port_uid")
                connector_type = _connector_type_from_cable(row.cable_type)
                key = (data_hall_id, cabinet_id, rack_unit)
                if device_name:
                    device_names[key].add(device_name)
                if device_model:
                    device_models[key].add(device_model)
                device_phases[key].add(construction_phase)
                device_ports[key][connector_type][port_uid] = PortConnector(uid=port_uid, type=connector_type)

    cabinets: dict[tuple[str, str], list[Device]] = defaultdict(list)
    for (data_hall_id, cabinet_id, rack_unit), ports_by_type in device_ports.items():
        model_aliases = sorted(device_models.get((data_hall_id, cabinet_id, rack_unit), set()))
        aliases = sorted(device_names.get((data_hall_id, cabinet_id, rack_unit), set()))
        device_model = model_aliases[0] if model_aliases else "Unknown"
        note = f"Aliases: {', '.join(aliases)}" if aliases else ""
        cabinets[(data_hall_id, cabinet_id)].append(
            Device(
                cabinet_id=f"{data_hall_id}:{cabinet_id}",
                rack_unit=rack_unit,
                device_model=device_model,
                lifecycle_status=LifecycleStatus.NOT_INSTALLED,
                construction_phase=_device_construction_phase(device_phases.get((data_hall_id, cabinet_id, rack_unit), set())),
                aliases=aliases,
                model_aliases=[model for model in model_aliases if model != device_model],
                ports_by_type={
                    connector_type: sorted(ports.values(), key=lambda port: port.uid)
                    for connector_type, ports in sorted(ports_by_type.items(), key=lambda item: item[0].value)
                },
                note=note,
            )
        )

    return {
        cabinet_key: sorted(devices, key=lambda device: (device.rack_unit, device.device_model))
        for cabinet_key, devices in cabinets.items()
    }


def _devices_for_cabinet(
    data_hall_id: str,
    cabinet_id: str,
    devices_by_cabinet: dict[tuple[str, str], list[Device]],
    status_overrides: StatusOverrides,
) -> list[Device]:
    devices_by_uid = {
        _device_uid(device.cabinet_id, device.rack_unit): _copy_device(device)
        for device in devices_by_cabinet.get((data_hall_id, cabinet_id), [])
    }
    cabinet_uid = f"{data_hall_id}:{cabinet_id}".upper()

    for device_uid_raw, override in status_overrides.devices.items():
        device_uid = _normalize_device_uid(device_uid_raw)
        if _cabinet_uid_from_device_uid(device_uid) != cabinet_uid:
            continue

        device = devices_by_uid.get(device_uid)
        if device is None:
            device = Device(
                cabinet_id=cabinet_uid,
                rack_unit=int(device_uid.split(":")[2]),
                device_model=override.device_model or "Unknown",
                construction_phase=ConstructionPhase.MANAGEMENT_ETHERNET,
            )
        elif _should_apply_device_model(device.device_model, override.device_model):
            device.device_model = override.device_model

        device.lifecycle_status = override.lifecycle_status
        if override.note:
            device.note = override.note
        devices_by_uid[device_uid] = device

    return sorted(devices_by_uid.values(), key=lambda device: (device.rack_unit, device.device_model))


def _cabinet_status(
    data_hall_id: str,
    cabinet_id: str,
    category: str,
    status_overrides: StatusOverrides,
) -> LifecycleStatus:
    cabinet_uid = f"{data_hall_id}:{cabinet_id}".upper()
    if cabinet_uid in status_overrides.cabinets:
        return status_overrides.cabinets[cabinet_uid]
    if category.upper() in {"RES", "U"}:
        return LifecycleStatus.NOT_PLANNED
    return LifecycleStatus.NOT_INSTALLED


def _cables_with_construction_phase(cutsheet_inputs: list[tuple[CutsheetIngestionResult, ConstructionPhase]]):
    cables = []
    for result, construction_phase in cutsheet_inputs:
        for cable in result.cables:
            copied_cable = _copy_cable_with_construction_phase(cable, construction_phase)
            copied_cable.uid = f"CBL-{len(cables) + 1:06d}"
            cables.append(copied_cable)
    return cables


def _copy_cable_with_construction_phase(cable, construction_phase: ConstructionPhase):
    if hasattr(cable, "model_copy"):
        copied_cable = cable.model_copy(deep=True)
    else:
        copied_cable = cable.copy(deep=True)
    copied_cable.construction_phase = construction_phase
    return copied_cable


def _data_hall_construction_phase(data_hall_id: str) -> ConstructionPhase:
    return ConstructionPhase.MANAGEMENT_ETHERNET


def _device_construction_phase(phases: set[ConstructionPhase]) -> ConstructionPhase:
    if phases == {ConstructionPhase.ROCE}:
        return ConstructionPhase.ROCE
    return ConstructionPhase.MANAGEMENT_ETHERNET


def _cabinet_construction_phase(data_hall_id: str, category: str) -> ConstructionPhase:
    if _is_roce_related_category(category):
        return ConstructionPhase.ROCE
    return ConstructionPhase.MANAGEMENT_ETHERNET


def _is_roce_related_category(category: str) -> bool:
    normalized = category.upper()
    return normalized.startswith("HD-GB3") or "GPU" in normalized


def _max_rack_unit(
    data_hall_id: str,
    cabinet_id: str,
    status_overrides: StatusOverrides,
    default_max_rack_unit: int,
) -> int:
    cabinet_uid = f"{data_hall_id}:{cabinet_id}".upper()
    return status_overrides.cabinet_max_rack_units.get(cabinet_uid, default_max_rack_unit)


def _should_apply_device_model(current_model: str, override_model: str | None) -> bool:
    if not override_model:
        return False
    if override_model == "Unknown" and current_model != "Unknown":
        return False
    return True


def _device_uid(cabinet_uid: str, rack_unit: int) -> str:
    return f"{cabinet_uid}:{rack_unit}".upper()


def _cabinet_uid_from_device_uid(device_uid: str) -> str:
    data_hall_id, cabinet_id, _ = _normalize_device_uid(device_uid).split(":", 2)
    return f"{data_hall_id}:{cabinet_id}".upper()


def _normalize_device_uid(device_uid: str) -> str:
    data_hall_id, cabinet_id, rack_unit = device_uid.upper().split(":", 2)
    return f"{data_hall_id}:{cabinet_id}:{int(rack_unit)}"


def _copy_device(device: Device) -> Device:
    if hasattr(device, "model_copy"):
        return device.model_copy(deep=True)
    return device.copy(deep=True)


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
