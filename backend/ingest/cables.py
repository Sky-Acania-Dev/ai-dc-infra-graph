from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from backend.models import Cabinet, Cable, ConnectorType, PortConnector, Room


DEFAULT_PROJECT_UID = "MSK01"
DEFAULT_BUILDING_ID = "A"
PORT_ID_PATTERN = re.compile(r"^(DH\d+):(\d{3}):(.+)$")
A_SIDE_COLUMNS = (
    "a",
    "a_side",
    "a_port",
    "a_port_id",
    "a_side_port",
    "a_side_port_id",
    "a_connector",
    "a_connector_id",
)
Z_SIDE_COLUMNS = (
    "z",
    "z_side",
    "z_port",
    "z_port_id",
    "z_side_port",
    "z_side_port_id",
    "z_connector",
    "z_connector_id",
)


class CableEndpoint(BaseModel):
    raw_uid: str
    data_hall_id: str
    cabinet_id: str
    port_id: str


class CableIngestionResult(BaseModel):
    project_uid: str = DEFAULT_PROJECT_UID
    building_id: str = DEFAULT_BUILDING_ID
    data_halls: list[Room] = Field(default_factory=list)
    cabinets: list[Cabinet] = Field(default_factory=list)
    ports: list[PortConnector] = Field(default_factory=list)
    cables: list[Cable] = Field(default_factory=list)


def ingest_cable_connections_csv(
    csv_path: str | Path,
    project_uid: str = DEFAULT_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
) -> CableIngestionResult:
    rows = _read_csv_rows(csv_path)
    return ingest_cable_connection_rows(rows, project_uid=project_uid, building_id=building_id)


def ingest_cable_connection_rows(
    rows: Iterable[dict[str, str]],
    project_uid: str = DEFAULT_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
) -> CableIngestionResult:
    data_hall_ids: set[str] = set()
    cabinet_ids: set[tuple[str, str]] = set()
    ports_by_uid: dict[str, PortConnector] = {}
    cables: list[Cable] = []

    for row_number, row in enumerate(rows, start=2):
        normalized_row = {
            _normalize_header(key): str(value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        a_uid = _first_present_value(normalized_row, A_SIDE_COLUMNS)
        z_uid = _first_present_value(normalized_row, Z_SIDE_COLUMNS)

        if not a_uid or not z_uid:
            raise ValueError(f"CSV row {row_number} must include A-side and Z-side port IDs.")

        a_endpoint = parse_cable_endpoint(a_uid)
        z_endpoint = parse_cable_endpoint(z_uid)
        a_port = _get_or_create_port(ports_by_uid, a_endpoint, _endpoint_type(normalized_row, "a"))
        z_port = _get_or_create_port(ports_by_uid, z_endpoint, _endpoint_type(normalized_row, "z"))

        data_hall_ids.update((a_endpoint.data_hall_id, z_endpoint.data_hall_id))
        cabinet_ids.update(
            (
                (a_endpoint.data_hall_id, a_endpoint.cabinet_id),
                (z_endpoint.data_hall_id, z_endpoint.cabinet_id),
            )
        )
        cables.append(
            Cable(
                a_side=a_port,
                z_side=z_port,
                cable_type=normalized_row.get("cable_type", ""),
                note=normalized_row.get("note", ""),
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

    return CableIngestionResult(
        project_uid=project_uid,
        building_id=building_id,
        data_halls=data_halls,
        cabinets=cabinets,
        ports=sorted(ports_by_uid.values(), key=lambda port: port.uid),
        cables=cables,
    )


def parse_cable_endpoint(port_uid: str) -> CableEndpoint:
    match = PORT_ID_PATTERN.match(port_uid.strip())
    if not match:
        raise ValueError(
            f"Invalid port ID '{port_uid}'. Expected format DH#:XXX:YYY, for example DH1:001:Eth1/1."
        )

    data_hall_id, cabinet_id, port_id = match.groups()
    return CableEndpoint(
        raw_uid=f"{data_hall_id}:{cabinet_id}:{port_id}",
        data_hall_id=data_hall_id,
        cabinet_id=cabinet_id,
        port_id=port_id,
    )


def result_to_json(result: CableIngestionResult) -> str:
    if hasattr(result, "model_dump"):
        payload = result.model_dump(mode="json")
    else:
        payload = result.dict()
    return json.dumps(payload, indent=2)


def _read_csv_rows(csv_path: str | Path) -> list[dict[str, str]]:
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("CSV file must include a header row.")
        return list(reader)


def _get_or_create_port(
    ports_by_uid: dict[str, PortConnector],
    endpoint: CableEndpoint,
    connector_type: ConnectorType,
) -> PortConnector:
    if endpoint.raw_uid not in ports_by_uid:
        ports_by_uid[endpoint.raw_uid] = PortConnector(
            uid=endpoint.raw_uid,
            type=connector_type,
            note=f"Imported port {endpoint.port_id} in cabinet {endpoint.cabinet_id}",
        )
    return ports_by_uid[endpoint.raw_uid]


def _endpoint_type(row: dict[str, str], side_prefix: str) -> ConnectorType:
    for column_name in (f"{side_prefix}_type", f"{side_prefix}_port_type", "port_type"):
        value = row.get(column_name)
        if value:
            return _connector_type_from_value(value)
    return ConnectorType.OTHER


def _connector_type_from_value(value: str) -> ConnectorType:
    normalized_value = value.strip().upper()
    for connector_type in ConnectorType:
        if connector_type.value.upper() == normalized_value:
            return connector_type
    return ConnectorType.OTHER


def _first_present_value(row: dict[str, str], column_names: tuple[str, ...]) -> str:
    for column_name in column_names:
        value = row.get(column_name)
        if value:
            return value
    return ""


def _normalize_header(header: Any) -> str:
    return str(header or "").strip().lower().replace(" ", "_")
