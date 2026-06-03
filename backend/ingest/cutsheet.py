from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from backend.core.config import DEFAULT_BUILDING_ID, DEFAULT_PROJECT_UID
from backend.ingest.ods import read_ods_sheet_rows
from backend.models import Cabinet, Cable, ConnectorType, OpticModule, PortConnector, Room
from backend.validation import BreakoutFanoutRule, PortConnectionFinding, detect_port_collisions


class LocationRackUnit(BaseModel):
    raw_value: str
    data_hall_id: str
    cabinet_id: str
    rack_unit: int


class CutsheetCableRow(BaseModel):
    group: str
    status: str
    cable_type: str
    a_data_hall_id: str
    a_cabinet_id: str
    a_rack_unit: int
    a_port_id: str
    a_port_uid: str
    a_device_name: str = ""
    a_device_model: str = ""
    a_breakout_loc_cab_ru: str = ""
    a_breakout_slot_port: str = ""
    a_optic: str = ""
    z_data_hall_id: str
    z_cabinet_id: str
    z_rack_unit: int
    z_port_id: str
    z_port_uid: str
    z_device_name: str = ""
    z_device_model: str = ""
    z_breakout_loc_cab_ru: str = ""
    z_breakout_slot_port: str = ""
    z_optic: str = ""
    z_patch_panel_loc_cab_ru_port: str = ""


class CutsheetIngestionResult(BaseModel):
    project_uid: str = DEFAULT_PROJECT_UID
    building_id: str = DEFAULT_BUILDING_ID
    rows: list[CutsheetCableRow] = Field(default_factory=list)
    data_halls: list[Room] = Field(default_factory=list)
    cabinets: list[Cabinet] = Field(default_factory=list)
    ports: list[PortConnector] = Field(default_factory=list)
    cables: list[Cable] = Field(default_factory=list)
    findings: list[PortConnectionFinding] = Field(default_factory=list)


class CutsheetSummary(BaseModel):
    rows: int
    data_halls: int
    cabinets: int
    ports: int
    cables: int
    port_collision_findings: int


def ingest_cutsheet(
    path: str | Path,
    project_uid: str = DEFAULT_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    sheet_name: str | None = None,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> CutsheetIngestionResult:
    path = Path(path)
    if path.suffix.lower() == ".ods":
        raw_rows = read_ods_sheet_rows(path, sheet_name=sheet_name)
        rows = _dict_rows_from_matrix(raw_rows)
    else:
        rows = _read_csv_rows(path)

    return ingest_cutsheet_rows(
        rows,
        project_uid=project_uid,
        building_id=building_id,
        breakout_rules=breakout_rules,
    )


def ingest_cutsheet_rows(
    rows: Iterable[dict[str, str]],
    project_uid: str = DEFAULT_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> CutsheetIngestionResult:
    current_group = ""
    enriched_rows: list[CutsheetCableRow] = []
    data_hall_ids: set[str] = set()
    cabinet_ids: set[tuple[str, str]] = set()
    ports_by_uid: dict[str, PortConnector] = {}
    cables: list[Cable] = []

    for row in rows:
        normalized_row = {_normalize_header(key): str(value or "").strip() for key, value in row.items()}
        status = normalized_row.get("status", "")
        if not any(normalized_row.values()):
            continue

        if _is_group_row(normalized_row):
            current_group = status
            continue

        if not _is_valid_cable_row(normalized_row):
            continue

        parsed_row = _parse_cable_row(normalized_row, current_group)
        enriched_rows.append(parsed_row)

        data_hall_ids.update((parsed_row.a_data_hall_id, parsed_row.z_data_hall_id))
        cabinet_ids.update(
            (
                (parsed_row.a_data_hall_id, parsed_row.a_cabinet_id),
                (parsed_row.z_data_hall_id, parsed_row.z_cabinet_id),
            )
        )

        a_port = _get_or_create_port(ports_by_uid, parsed_row.a_port_uid, parsed_row.cable_type)
        z_port = _get_or_create_port(ports_by_uid, parsed_row.z_port_uid, parsed_row.cable_type)

        cables.append(
            Cable(
                uid=f"CBL-{len(cables) + 1:06d}",
                a_side=a_port,
                z_side=z_port,
                cable_type=parsed_row.cable_type,
                group=parsed_row.group,
                status=parsed_row.status,
                a_optic=_optic_or_none(parsed_row.a_optic, "A"),
                z_optic=_optic_or_none(parsed_row.z_optic, "Z"),
            )
        )

    cabinets = [
        Cabinet(building_id=building_id, data_hall_id=data_hall_id, cabinet_id=cabinet_id)
        for data_hall_id, cabinet_id in sorted(cabinet_ids)
    ]
    data_halls = [
        Room(
            building_id=building_id,
            room_id=data_hall_id,
            cabinets=[cabinet for cabinet in cabinets if cabinet.data_hall_id == data_hall_id],
        )
        for data_hall_id in sorted(data_hall_ids)
    ]

    return CutsheetIngestionResult(
        project_uid=project_uid,
        building_id=building_id,
        rows=enriched_rows,
        data_halls=data_halls,
        cabinets=cabinets,
        ports=sorted(ports_by_uid.values(), key=lambda port: port.uid),
        cables=cables,
        findings=detect_port_collisions(enriched_rows, breakout_rules=breakout_rules),
    )


def parse_loc_cab_ru(value: str) -> LocationRackUnit:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2].isdigit():
        raise ValueError(f"Invalid LOC:CAB:RU value '{value}'. Expected format dh#:###:RU.")

    return LocationRackUnit(
        raw_value=value,
        data_hall_id=parts[0].upper(),
        cabinet_id=parts[1].zfill(3),
        rack_unit=int(parts[2]),
    )


def cutsheet_result_to_json(result: CutsheetIngestionResult) -> str:
    summary = CutsheetSummary(
        rows=len(result.rows),
        data_halls=len(result.data_halls),
        cabinets=len(result.cabinets),
        ports=len(result.ports),
        cables=len(result.cables),
        port_collision_findings=len(result.findings),
    )
    if hasattr(result, "model_dump"):
        result_payload = result.model_dump(mode="json")
        summary_payload = summary.model_dump(mode="json")
    else:
        result_payload = result.dict()
        summary_payload = summary.dict()
    payload = {
        "project_uid": result.project_uid,
        "building_id": result.building_id,
        "summary": summary_payload,
        "port_collision_findings": result_payload["findings"],
        "data_halls": result_payload["data_halls"],
        "cabinets": result_payload["cabinets"],
        "ports": result_payload["ports"],
        "cables": result_payload["cables"],
        "rows": result_payload["rows"],
    }
    return json.dumps(payload, indent=2)


def _parse_cable_row(row: dict[str, str], group: str) -> CutsheetCableRow:
    a_location = parse_loc_cab_ru(row.get("a_loc_cab_ru", ""))
    z_location = parse_loc_cab_ru(row.get("z_loc_cab_ru", ""))
    a_port_id = row.get("a_port", "")
    z_port_id = row.get("z_port", "")

    if not a_port_id or not z_port_id:
        raise ValueError("Cable row must include A-PORT and Z-PORT values.")

    return CutsheetCableRow(
        group=group,
        status=row.get("status", ""),
        cable_type=row.get("cable", ""),
        a_data_hall_id=a_location.data_hall_id,
        a_cabinet_id=a_location.cabinet_id,
        a_rack_unit=a_location.rack_unit,
        a_port_id=a_port_id,
        a_port_uid=_port_uid(a_location, a_port_id),
        a_device_name=row.get("a_side_dns_name", ""),
        a_device_model=row.get("a_model", ""),
        a_breakout_loc_cab_ru=row.get("a_breakout_loc_cab_ru", ""),
        a_breakout_slot_port=row.get("a_breakout_slot_port", ""),
        a_optic=row.get("a_optic", ""),
        z_data_hall_id=z_location.data_hall_id,
        z_cabinet_id=z_location.cabinet_id,
        z_rack_unit=z_location.rack_unit,
        z_port_id=z_port_id,
        z_port_uid=_port_uid(z_location, z_port_id),
        z_device_name=row.get("z_side_dns_name", ""),
        z_device_model=row.get("z_model", ""),
        z_breakout_loc_cab_ru=row.get("z_breakout_loc_cab_ru", ""),
        z_breakout_slot_port=row.get("z_breakout_slot_port", ""),
        z_optic=row.get("z_optic", ""),
        z_patch_panel_loc_cab_ru_port=row.get("z_patch_panel_loc_cab_ru_port", ""),
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("CSV file must include a header row.")
        return list(reader)


def _dict_rows_from_matrix(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        return []

    headers = rows[0]
    return [
        {headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))}
        for row in rows[1:]
    ]


def _is_group_row(row: dict[str, str]) -> bool:
    status = row.get("status", "")
    return bool(status) and all(not value for key, value in row.items() if key != "status")


def _is_valid_cable_row(row: dict[str, str]) -> bool:
    return bool(
        row.get("a_loc_cab_ru", "")
        and row.get("a_port", "")
        and row.get("z_loc_cab_ru", "")
        and row.get("z_port", "")
        and row.get("cable", "")
    )


def _get_or_create_port(
    ports_by_uid: dict[str, PortConnector],
    port_uid: str,
    cable_type: str,
) -> PortConnector:
    if port_uid not in ports_by_uid:
        ports_by_uid[port_uid] = PortConnector(
            uid=port_uid,
            type=_connector_type_from_cable(cable_type),
        )
    return ports_by_uid[port_uid]


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


def _optic_or_none(model: str, side: str) -> OpticModule | None:
    if not model:
        return None
    return OpticModule(model=model, side=side)


def _port_uid(location: LocationRackUnit, port_id: str) -> str:
    return f"{location.data_hall_id}:{location.cabinet_id}:{location.rack_unit}:{port_id}"


def _normalize_header(header: Any) -> str:
    return (
        str(header or "")
        .strip()
        .lower()
        .replace("\n", "_")
        .replace(":", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )
