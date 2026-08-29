from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, Field

from backend.core.config import DEFAULT_BUILDING_ID
from backend.ingest.cutsheet import CutsheetCableRow, CutsheetIngestionResult, CutsheetSummary, ingest_cutsheet_rows
from backend.ingest.ods import read_ods_sheet_rows
from backend.ingest.overhead import CabinetInventoryRecord, OverheadIngestionResult, OverheadIngestionSummary
from backend.ingest.xlsx import dict_rows_from_header_sheet, read_xlsx_sheet_rows
from backend.models import Cabinet, Cable, ConnectorType, OpticModule, PortConnector, Room
from backend.validation import PortConnectionFinding, detect_port_collisions


LBB01_PROJECT_UID = "LBB01"
LBB01_DEFAULT_MAX_RACK_UNIT = 48
LBB01_VR_GPU_MAX_RACK_UNIT = 54
DEFAULT_OVERHEAD_SHEET = "OVERHEAD"
DEFAULT_NODE_TO_LEAF_SHEET = "DH3 Node to Leaf Pull Schedule"
DEFAULT_LEAF_TO_SPINE_SHEET = "x4 rack DH3 Rack 349 Leaf Pull "
DEFAULT_LEAF_TO_SPINE_SHEETS = (
    "x4 rack DH3 Rack 349 Leaf Pull ",
    "x8 rack DH3 Rack 349 Leaf Pull ",
)
DEFAULT_NON_ROCE_SHEET = "Copy of CUTSHEET"
DEFAULT_VR_ROCE_SHEETS = (
    "DH1-VR_PS NODE to TIER-0",
    "DH1-VR_PS TIER-0 to TIER-1",
)
DEFAULT_ROCE_CUTSHEET_SHEETS = (
    "SP2 DH1 NODE TO TIER-0",
    "SP2 DH1 TIER-0 TO TIER-1",
)
NODE_TO_LEAF_GROUP = "DH1-3 Node to Leaf"
LEAF_TO_SPINE_GROUP = "DH1-3 Leaf to Spine"
ROCE_CUTSHEET_GROUP = "LBB01 RoCE"
LEAF_RACK_UNIT_BY_INDEX = {
    1: 45,
    2: 40,
    3: 35,
    4: 30,
    5: 25,
    6: 20,
    7: 15,
    8: 10,
}
SPINE_RACK_UNIT_BY_NAME = {
    "S1": 45,
    "S2": 40,
    "S3": 35,
    "S4": 30,
}


class Lbb01IngestionSummary(BaseModel):
    overhead_cabinets: int
    cable_rows: int
    ports: int
    cables: int
    data_halls: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    port_collision_findings: int = 0


class Lbb01IngestionResult(BaseModel):
    project_uid: str = LBB01_PROJECT_UID
    building_id: str = DEFAULT_BUILDING_ID
    overhead: OverheadIngestionResult
    cutsheet: CutsheetIngestionResult
    summary: Lbb01IngestionSummary


def apply_lbb01_rack_unit_rule(cabinets: list[Cabinet], rows: Sequence[CutsheetCableRow] | None = None) -> None:
    observed_max_ru_by_cabinet = _observed_max_ru_by_cabinet(cabinets, rows)
    for cabinet in cabinets:
        cabinet_uid = f"{cabinet.data_hall_id}:{cabinet.cabinet_id}".upper()
        observed_max_ru = observed_max_ru_by_cabinet.get(cabinet_uid, 0)
        cabinet.max_rack_unit = LBB01_DEFAULT_MAX_RACK_UNIT
        if _is_lbb01_vr_gpu_cabinet(cabinet) or (
            observed_max_ru > LBB01_DEFAULT_MAX_RACK_UNIT and _is_lbb01_vr_roce_switch_cabinet(cabinet)
        ):
            cabinet.max_rack_unit = LBB01_VR_GPU_MAX_RACK_UNIT if observed_max_ru <= LBB01_VR_GPU_MAX_RACK_UNIT else observed_max_ru


def ingest_lbb01_workbook(
    path: str | Path,
    project_uid: str = LBB01_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    overhead_sheet_name: str = DEFAULT_OVERHEAD_SHEET,
    node_to_leaf_sheet_name: str = DEFAULT_NODE_TO_LEAF_SHEET,
    leaf_to_spine_sheet_name: str | None = None,
    leaf_to_spine_sheet_names: Sequence[str] | None = DEFAULT_LEAF_TO_SPINE_SHEETS,
    non_roce_path: str | Path | None = None,
    non_roce_sheet_name: str = DEFAULT_NON_ROCE_SHEET,
) -> Lbb01IngestionResult:
    overhead = ingest_lbb01_overhead(path, sheet_name=overhead_sheet_name)
    node_to_leaf = ingest_lbb01_node_to_leaf(
        path,
        project_uid=project_uid,
        building_id=building_id,
        sheet_name=node_to_leaf_sheet_name,
    )
    cutsheet_results = [node_to_leaf]
    sheet_names = list(leaf_to_spine_sheet_names or [])
    if leaf_to_spine_sheet_name:
        sheet_names.append(leaf_to_spine_sheet_name)
    for sheet_name in dict.fromkeys(sheet_names):
        cutsheet_results.append(
            ingest_lbb01_leaf_to_spine(
                path,
                project_uid=project_uid,
                building_id=building_id,
                sheet_name=sheet_name,
            )
        )
    if non_roce_path:
        cutsheet_results.append(
            ingest_lbb01_non_roce_cutsheet(
                non_roce_path,
                project_uid=project_uid,
                building_id=building_id,
                sheet_name=non_roce_sheet_name,
            )
        )
    cutsheet = _combine_cutsheet_results(cutsheet_results, project_uid=project_uid, building_id=building_id)
    data_hall_counts = Counter(record.data_hall_id for record in overhead.cabinets)
    status_counts = Counter(row.status for row in cutsheet.rows)
    return Lbb01IngestionResult(
        project_uid=project_uid,
        building_id=building_id,
        overhead=overhead,
        cutsheet=cutsheet,
        summary=Lbb01IngestionSummary(
            overhead_cabinets=len(overhead.cabinets),
            cable_rows=len(cutsheet.rows),
            ports=len(cutsheet.ports),
            cables=len(cutsheet.cables),
            data_halls=dict(sorted(data_hall_counts.items())),
            status_counts=dict(sorted(status_counts.items())),
            port_collision_findings=len(cutsheet.findings),
        ),
    )


def ingest_lbb01_overhead(path: str | Path, sheet_name: str = DEFAULT_OVERHEAD_SHEET) -> OverheadIngestionResult:
    rows = read_xlsx_sheet_rows(path, sheet_name)
    cells = _cells_from_rows(rows)
    cabinets: list[CabinetInventoryRecord] = []
    for row_number, row in enumerate(rows, start=1):
        for col_number, value in enumerate(row, start=1):
            if not _is_cabinet_number(value):
                continue
            if not (_is_cabinet_number(cells.get((row_number, col_number - 1))) or _is_cabinet_number(cells.get((row_number, col_number + 1)))):
                continue
            cabinet_number = int(value)
            cabinets.append(
                CabinetInventoryRecord(
                    cabinet_uid=f"{_section_for_lbb_cabinet(cabinet_number)}:{cabinet_number:03d}",
                    data_hall_id=_section_for_lbb_cabinet(cabinet_number),
                    cabinet_id=f"{cabinet_number:03d}",
                    category=_category_for_cabinet(cells, row_number, col_number),
                    cabinet_group=_grid_group_for_cell(cells, row_number, col_number),
                    source_row=row_number,
                    source_col=col_number,
                )
            )
    cabinets_by_number = {int(record.cabinet_id): record for record in cabinets}
    missing = [cabinet_number for cabinet_number in range(1, 1601) if cabinet_number not in cabinets_by_number]
    if missing:
        raise ValueError(f"LBB01 OVERHEAD is missing cabinet numbers: {missing}")
    ordered_cabinets = [cabinets_by_number[cabinet_number] for cabinet_number in range(1, 1601)]
    return OverheadIngestionResult(
        summary=OverheadIngestionSummary(
            cabinets=len(ordered_cabinets),
            data_halls=len({cabinet.data_hall_id for cabinet in ordered_cabinets}),
            unknown_category_cabinets=sum(1 for cabinet in ordered_cabinets if cabinet.category == "UNKNOWN"),
        ),
        cabinets=ordered_cabinets,
    )


def ingest_lbb01_node_to_leaf(
    path: str | Path,
    project_uid: str = LBB01_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    sheet_name: str = DEFAULT_NODE_TO_LEAF_SHEET,
) -> CutsheetIngestionResult:
    raw_rows = dict_rows_from_header_sheet(path, sheet_name)
    parsed_rows: list[CutsheetCableRow] = []
    ports_by_uid: dict[str, PortConnector] = {}
    cables: list[Cable] = []
    findings: list[PortConnectionFinding]

    for row_number, row in enumerate(raw_rows, start=2):
        if not _has_node_to_leaf_required_values(row):
            continue
        parsed_row = _node_to_leaf_row(row, row_number)
        parsed_rows.append(parsed_row)
        a_port = _get_or_create_port(ports_by_uid, parsed_row.a_port_uid)
        z_port = _get_or_create_port(ports_by_uid, parsed_row.z_port_uid)
        cables.append(
            Cable(
                uid=parsed_row.source_cable_uid,
                a_side=a_port,
                z_side=z_port,
                cable_type=parsed_row.cable_type,
                group=parsed_row.group,
                status=parsed_row.status,
                a_label_text=row_text(row, "source_label"),
                z_label_text=row_text(row, "destination_label"),
                a_optic=_optic_or_none(parsed_row.a_optic, "A"),
                z_optic=_optic_or_none(parsed_row.z_optic, "Z"),
                note=f"Imported from {sheet_name} row {row_number}. Fabric: {row_text(row, 'fabric_id')}",
            )
        )

    data_hall_ids = sorted({row.a_data_hall_id for row in parsed_rows} | {row.z_data_hall_id for row in parsed_rows})
    cabinet_ids = sorted(
        {
            (row.a_data_hall_id, row.a_cabinet_id)
            for row in parsed_rows
        }
        | {
            (row.z_data_hall_id, row.z_cabinet_id)
            for row in parsed_rows
        }
    )
    findings = detect_port_collisions(parsed_rows)
    return CutsheetIngestionResult(
        project_uid=project_uid,
        building_id=building_id,
        rows=parsed_rows,
        data_halls=[
            Room(
                building_id=building_id,
                room_id=data_hall_id,
            )
            for data_hall_id in data_hall_ids
        ],
        cabinets=[],
        ports=sorted(ports_by_uid.values(), key=lambda port: port.uid),
        cables=cables,
        findings=findings,
    )


def ingest_lbb01_leaf_to_spine(
    path: str | Path,
    project_uid: str = LBB01_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    sheet_name: str = DEFAULT_LEAF_TO_SPINE_SHEET,
) -> CutsheetIngestionResult:
    raw_rows = dict_rows_from_header_sheet(path, sheet_name)
    parsed_rows: list[CutsheetCableRow] = []
    ports_by_uid: dict[str, PortConnector] = {}
    cables: list[Cable] = []

    for row_number, row in enumerate(raw_rows, start=2):
        if not _has_leaf_to_spine_required_values(row):
            continue
        parsed_row = _leaf_to_spine_row(row, row_number)
        parsed_rows.append(parsed_row)
        a_port = _get_or_create_port(ports_by_uid, parsed_row.a_port_uid)
        z_port = _get_or_create_port(ports_by_uid, parsed_row.z_port_uid)
        cables.append(
            Cable(
                uid=parsed_row.source_cable_uid,
                a_side=a_port,
                z_side=z_port,
                cable_type=parsed_row.cable_type,
                group=parsed_row.group,
                status=parsed_row.status,
                a_label_text=row_text(row, "source_label"),
                z_label_text=row_text(row, "destination_label"),
                a_optic=_optic_or_none(parsed_row.a_optic, "A"),
                z_optic=_optic_or_none(parsed_row.z_optic, "Z"),
                note=f"Imported from {sheet_name} row {row_number}. Fabric: {row_text(row, 'fabric_id')}",
            )
        )

    data_hall_ids = sorted({row.a_data_hall_id for row in parsed_rows} | {row.z_data_hall_id for row in parsed_rows})
    findings = detect_port_collisions(parsed_rows)
    return CutsheetIngestionResult(
        project_uid=project_uid,
        building_id=building_id,
        rows=parsed_rows,
        data_halls=[Room(building_id=building_id, room_id=data_hall_id) for data_hall_id in data_hall_ids],
        cabinets=[],
        ports=sorted(ports_by_uid.values(), key=lambda port: port.uid),
        cables=cables,
        findings=findings,
    )


def ingest_lbb01_non_roce_cutsheet(
    path: str | Path,
    project_uid: str = LBB01_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    sheet_name: str = DEFAULT_NON_ROCE_SHEET,
) -> CutsheetIngestionResult:
    rows = dict_rows_from_header_sheet(path, sheet_name)
    normalized_rows = [_normalize_lbb_non_roce_row(row) for row in rows]
    return ingest_cutsheet_rows(normalized_rows, project_uid=project_uid, building_id=building_id)


def ingest_lbb01_vr_roce_cutsheets(
    path: str | Path,
    project_uid: str = LBB01_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    sheet_names: Sequence[str] = DEFAULT_VR_ROCE_SHEETS,
) -> CutsheetIngestionResult:
    results = [
        ingest_cutsheet_rows(
            [_normalize_lbb_non_roce_row(row) for row in _dict_rows_from_vr_roce_sheet(path, sheet_name)],
            project_uid=project_uid,
            building_id=building_id,
        )
        for sheet_name in sheet_names
    ]
    return _combine_cutsheet_results(results, project_uid=project_uid, building_id=building_id)


def ingest_lbb01_roce_cutsheets(
    path: str | Path,
    project_uid: str = LBB01_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    sheet_names: Sequence[str] = DEFAULT_ROCE_CUTSHEET_SHEETS,
) -> CutsheetIngestionResult:
    sheet_names = sheet_names or DEFAULT_ROCE_CUTSHEET_SHEETS
    results = [
        ingest_cutsheet_rows(
            [_normalize_lbb_non_roce_row(row) for row in _dict_rows_from_vr_roce_sheet(path, sheet_name)],
            project_uid=project_uid,
            building_id=building_id,
        )
        for sheet_name in sheet_names
    ]
    return _with_default_group(
        _combine_cutsheet_results(results, project_uid=project_uid, building_id=building_id),
        ROCE_CUTSHEET_GROUP,
    )


def _node_to_leaf_row(row: dict[str, Any], row_number: int) -> CutsheetCableRow:
    rack_number = _int_value(row.get("rack_number"), f"rack number at row {row_number}")
    data_hall_id = _section_for_lbb_cabinet(rack_number)
    node_number = _int_value(row.get("node_number"), f"node number at row {row_number}")
    source_node = row_text(row, "source_node") or f"NODE{node_number}"
    source_port = _node_source_port(row)
    destination = row_text(row, "destination")
    leaf = _parse_leaf_destination(destination, data_hall_id)
    destination_port = row_text(row, "destination_port")
    cable_type = row_text(row, "cable_type") or "MTP"
    status = row_text(row, "status") or "Cable Not Run"
    cable_uid = f"LBB01-{data_hall_id}-{rack_number:03d}-{source_node}-{source_port}-TO-{leaf.device_name}-{destination_port}"
    cable_uid = re.sub(r"[^A-Z0-9]+", "-", cable_uid.upper()).strip("-")
    return CutsheetCableRow(
        source_cable_uid=cable_uid,
        group=NODE_TO_LEAF_GROUP,
        status=status,
        cable_type=cable_type,
        a_data_hall_id=data_hall_id,
        a_cabinet_id=f"{rack_number:03d}",
        a_rack_unit=node_number,
        a_port_id=source_port,
        a_port_uid=f"{data_hall_id}:{rack_number:03d}:{node_number}:{source_port}",
        a_device_name=f"R{rack_number}.{source_node}",
        a_device_model="HGX Node",
        a_optic=row_text(row, "optic_type"),
        z_data_hall_id=leaf.data_hall_id,
        z_cabinet_id=leaf.cabinet_id,
        z_rack_unit=leaf.rack_unit,
        z_port_id=destination_port,
        z_port_uid=f"{leaf.data_hall_id}:{leaf.cabinet_id}:{leaf.rack_unit}:{leaf.device_name}:{destination_port}",
        z_device_name=leaf.device_name,
        z_device_model="Q3400-RA",
        z_optic=row_text(row, "optic_type"),
    )


def _leaf_to_spine_row(row: dict[str, Any], row_number: int) -> CutsheetCableRow:
    source = _parse_leaf_destination(row_text(row, "source"), "DH1-3")
    source_port = row_text(row, "source_port")
    spine = _parse_spine_destination(row_text(row, "destination"), source)
    destination_port = row_text(row, "destination_port")
    cable_type = row_text(row, "cable_type") or "MTP"
    status = row_text(row, "status") or "Cable Not Run"
    cable_uid = f"LBB01-{source.data_hall_id}-{source.device_name}-{source_port}-TO-{spine.device_name}-{destination_port}"
    cable_uid = re.sub(r"[^A-Z0-9]+", "-", cable_uid.upper()).strip("-")
    return CutsheetCableRow(
        source_cable_uid=cable_uid,
        group=LEAF_TO_SPINE_GROUP,
        status=status,
        cable_type=cable_type,
        a_data_hall_id=source.data_hall_id,
        a_cabinet_id=source.cabinet_id,
        a_rack_unit=source.rack_unit,
        a_port_id=source_port,
        a_port_uid=f"{source.data_hall_id}:{source.cabinet_id}:{source.rack_unit}:{source.device_name}:{source_port}",
        a_device_name=source.device_name,
        a_device_model="Q3400-RA",
        a_optic=row_text(row, "optic_type"),
        z_data_hall_id=spine.data_hall_id,
        z_cabinet_id=spine.cabinet_id,
        z_rack_unit=spine.rack_unit,
        z_port_id=destination_port,
        z_port_uid=f"{spine.data_hall_id}:{spine.cabinet_id}:{spine.rack_unit}:{spine.device_name}:{destination_port}",
        z_device_name=spine.device_name,
        z_device_model="Q3400-RA",
        z_optic=row_text(row, "optic_type"),
    )


class _LeafDestination(BaseModel):
    data_hall_id: str
    cabinet_id: str
    rack_unit: int
    device_name: str


def _parse_leaf_destination(value: str, fallback_data_hall_id: str) -> _LeafDestination:
    match = re.match(r"^L(?P<cabinet>\d{3,4})\.(?P<group>\d+)(?:\.(?P<leaf>\d+))?(?:-(?P<hall>DH\d+(?:-\d+)?))?$", value.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid LBB leaf destination '{value}'.")
    leaf_index = int(match.group("leaf") or match.group("group"))
    cabinet_id = match.group("cabinet")
    data_hall_id = _section_for_lbb_cabinet(int(cabinet_id)) if cabinet_id.isdigit() else (match.group("hall") or fallback_data_hall_id).upper()
    return _LeafDestination(
        data_hall_id=data_hall_id,
        cabinet_id=cabinet_id,
        rack_unit=LEAF_RACK_UNIT_BY_INDEX.get(leaf_index, max(1, 50 - leaf_index * 5)),
        device_name=value.strip().upper(),
    )


def _parse_spine_destination(value: str, source: _LeafDestination) -> _LeafDestination:
    device_name = value.strip().upper()
    if device_name not in SPINE_RACK_UNIT_BY_NAME:
        raise ValueError(f"Invalid LBB spine destination '{value}'.")
    return _LeafDestination(
        data_hall_id=source.data_hall_id,
        cabinet_id=f"{int(source.cabinet_id) + 1:03d}",
        rack_unit=SPINE_RACK_UNIT_BY_NAME[device_name],
        device_name=device_name,
    )


def _node_source_port(row: dict[str, Any]) -> str:
    ibp = row_text(row, "ibp")
    phy = row_text(row, "rhgx_phy_port")
    if ibp and phy:
        return f"{ibp}:{phy}"
    return ibp or phy or row_text(row, "source_port")


def _has_node_to_leaf_required_values(row: dict[str, Any]) -> bool:
    return bool(
        row_text(row, "status")
        and row.get("rack_number") not in (None, "")
        and row.get("node_number") not in (None, "")
        and row_text(row, "destination")
        and row_text(row, "destination_port")
        and row_text(row, "cable_type")
    )


def _has_leaf_to_spine_required_values(row: dict[str, Any]) -> bool:
    return bool(
        row_text(row, "status")
        and row_text(row, "source")
        and row_text(row, "source_port")
        and row_text(row, "destination")
        and row_text(row, "destination_port")
        and row_text(row, "cable_type")
    )


def _combine_cutsheet_results(
    results: list[CutsheetIngestionResult],
    project_uid: str,
    building_id: str,
) -> CutsheetIngestionResult:
    rows_by_uid = {
        _row_dedupe_key(row, result_index, row_index): row
        for result_index, result in enumerate(results)
        for row_index, row in enumerate(result.rows)
    }
    rows = list(rows_by_uid.values())
    ports_by_uid = {port.uid: port for result in results for port in result.ports}
    cables_by_uid = {
        _cable_dedupe_key(cable, result_index, cable_index): cable
        for result_index, result in enumerate(results)
        for cable_index, cable in enumerate(result.cables)
    }
    cables = list(cables_by_uid.values())
    data_hall_ids = sorted({row.a_data_hall_id for row in rows} | {row.z_data_hall_id for row in rows})
    return CutsheetIngestionResult(
        project_uid=project_uid,
        building_id=building_id,
        rows=rows,
        data_halls=[Room(building_id=building_id, room_id=data_hall_id) for data_hall_id in data_hall_ids],
        cabinets=[],
        ports=sorted(ports_by_uid.values(), key=lambda port: port.uid),
        cables=cables,
        findings=detect_port_collisions(rows),
    )


def _with_default_group(result: CutsheetIngestionResult, group: str) -> CutsheetIngestionResult:
    for row in result.rows:
        if not row.group:
            row.group = group
    for cable in result.cables:
        if not cable.group:
            cable.group = group
    return result


def _row_dedupe_key(row: CutsheetCableRow, result_index: int, row_index: int) -> str:
    if row.source_cable_uid:
        return f"uid:{row.source_cable_uid}"
    return f"row:{result_index}|{row.a_port_uid}|{row.z_port_uid}|{row.cable_type}|{row.status}|{row_index}"


def _cable_dedupe_key(cable: Cable, result_index: int, cable_index: int) -> str:
    if cable.uid and not re.fullmatch(r"CBL-\d{6}", cable.uid):
        return f"uid:{cable.uid}"
    return f"cable:{result_index}|{cable.a_side.uid}|{cable.z_side.uid}|{cable.cable_type}|{cable.status}|{cable_index}"


def _observed_max_ru_by_cabinet(cabinets: list[Cabinet], rows: Sequence[CutsheetCableRow] | None) -> dict[str, int]:
    max_ru_by_cabinet: dict[str, int] = {}
    if rows is not None:
        for row in rows:
            for data_hall_id, cabinet_id, rack_unit in (
                (row.a_data_hall_id, row.a_cabinet_id, row.a_rack_unit),
                (row.z_data_hall_id, row.z_cabinet_id, row.z_rack_unit),
            ):
                cabinet_uid = f"{data_hall_id}:{cabinet_id}".upper()
                max_ru_by_cabinet[cabinet_uid] = max(max_ru_by_cabinet.get(cabinet_uid, 0), rack_unit)
        return max_ru_by_cabinet

    for cabinet in cabinets:
        cabinet_uid = f"{cabinet.data_hall_id}:{cabinet.cabinet_id}".upper()
        for device in cabinet.devices:
            max_ru_by_cabinet[cabinet_uid] = max(max_ru_by_cabinet.get(cabinet_uid, 0), device.rack_unit)
    return max_ru_by_cabinet


def _is_lbb01_vr_gpu_cabinet(cabinet: Cabinet) -> bool:
    return cabinet.category.upper().startswith("VR-NVL")


def _is_lbb01_vr_roce_switch_cabinet(cabinet: Cabinet) -> bool:
    normalized = cabinet.category.upper()
    return normalized.startswith("T0-RO-V3") or normalized.startswith("T1-RO-V4")


def _normalize_lbb_non_roce_row(row: dict[str, Any]) -> dict[str, str]:
    normalized = {_normalize_non_roce_header(key): row_text(row, key) for key in row}
    for key in ("a_loc_cab_ru", "z_loc_cab_ru"):
        normalized[key] = _normalize_lbb_loc_cab_ru(normalized.get(key, ""))
    return normalized


def _normalize_non_roce_header(header: Any) -> str:
    return (
        str(header or "")
        .strip()
        .lower()
        .replace("\n", "_")
        .replace(":", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _normalize_lbb_loc_cab_ru(value: str) -> str:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) != 3 or not parts[1].isdigit():
        return value
    return f"{_section_for_lbb_cabinet(int(parts[1]))}:{parts[1].zfill(3)}:{parts[2]}"


def _dict_rows_from_ods_sheet(path: str | Path, sheet_name: str) -> list[dict[str, str]]:
    rows = read_ods_sheet_rows(path, sheet_name)
    return _dict_rows_from_matrix(rows)


def _dict_rows_from_vr_roce_sheet(path: str | Path, sheet_name: str) -> list[dict[str, Any]]:
    path = Path(path)
    if path.suffix.lower() == ".ods":
        return _dict_rows_from_matrix(read_ods_sheet_rows(path, sheet_name))
    return _dict_rows_from_matrix(read_xlsx_sheet_rows(path, sheet_name))


def _dict_rows_from_matrix(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    headers = rows[0]
    return [
        {headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))}
        for row in rows[1:]
    ]


def _get_or_create_port(ports_by_uid: dict[str, PortConnector], port_uid: str) -> PortConnector:
    if port_uid not in ports_by_uid:
        ports_by_uid[port_uid] = PortConnector(uid=port_uid, type=ConnectorType.MPO)
    return ports_by_uid[port_uid]


def _optic_or_none(model: str, side: str) -> OpticModule | None:
    return OpticModule(model=model, side=side) if model else None


def _section_for_lbb_cabinet(cabinet_number: int) -> str:
    if 1 <= cabinet_number <= 150 or 801 <= cabinet_number <= 950:
        return "DH1-1"
    if 151 <= cabinet_number <= 300 or 951 <= cabinet_number <= 1100:
        return "DH1-2"
    if 301 <= cabinet_number <= 450 or 1101 <= cabinet_number <= 1250:
        return "DH1-3"
    if 451 <= cabinet_number <= 600 or 1251 <= cabinet_number <= 1400:
        return "DH1-4"
    if 601 <= cabinet_number <= 800 or 1401 <= cabinet_number <= 1600:
        return "DH1-5"
    raise ValueError(f"LBB01 cabinet number is outside expected range: {cabinet_number}")


def _cells_from_rows(rows: list[list[Any]]) -> dict[tuple[int, int], Any]:
    cells: dict[tuple[int, int], Any] = {}
    for row_number, row in enumerate(rows, start=1):
        for col_number, value in enumerate(row, start=1):
            if value not in (None, ""):
                cells[(row_number, col_number)] = value
    return cells


def _category_for_cabinet(cells: dict[tuple[int, int], Any], row: int, col: int) -> str:
    category = str(cells.get((row + 1, col), "") or "").strip()
    if _is_category_value(category):
        return category
    for left_col in range(col - 1, 0, -1):
        if not _is_cabinet_number(cells.get((row, left_col))):
            break
        category = str(cells.get((row + 1, left_col), "") or "").strip()
        if _is_category_value(category):
            return category
    for right_col in range(col + 1, col + 11):
        if not _is_cabinet_number(cells.get((row, right_col))):
            break
        category = str(cells.get((row + 1, right_col), "") or "").strip()
        if _is_category_value(category):
            return category
    return "UNKNOWN"


def _grid_group_for_cell(cells: dict[tuple[int, int], Any], row: int, col: int) -> str:
    for search_row in range(row, max(0, row - 18), -1):
        for search_col in range(col, max(0, col - 5), -1):
            value = str(cells.get((search_row, search_col), "") or "").strip()
            if value.startswith("GRID-"):
                return " / ".join(part.strip() for part in value.splitlines() if part.strip())
    return ""


def _is_cabinet_number(value: Any) -> bool:
    if isinstance(value, int):
        return 1 <= value <= 1600
    if isinstance(value, float):
        return value.is_integer() and 1 <= int(value) <= 1600
    text = str(value or "").strip()
    return bool(re.fullmatch(r"\d{1,4}", text) and 1 <= int(text) <= 1600)


def _is_category_value(value: str) -> bool:
    return bool(value and value not in {"ROW", "TYPE"} and not _is_cabinet_number(value))


def _normalize_data_hall(value: str) -> str:
    match = re.search(r"DH\d+(?:-\d+)?", value.upper())
    if not match:
        raise ValueError(f"Cannot parse LBB data hall from '{value}'.")
    return match.group(0)


def _data_hall_from_leaf_label(value: str) -> str:
    match = re.search(r"DH\d+(?:-\d+)?", value.upper())
    return match.group(0) if match else ""


def _int_value(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}: {value!r}") from exc


def row_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
