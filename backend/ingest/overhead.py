from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel, Field


NAMESPACES = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
TABLE_NAME = f"{{{NAMESPACES['table']}}}name"
CELL_REPEAT = f"{{{NAMESPACES['table']}}}number-columns-repeated"
ROW_REPEAT = f"{{{NAMESPACES['table']}}}number-rows-repeated"
COL_SPAN = f"{{{NAMESPACES['table']}}}number-columns-spanned"
ROW_SPAN = f"{{{NAMESPACES['table']}}}number-rows-spanned"
TABLE_CELL = f"{{{NAMESPACES['table']}}}table-cell"
COVERED_TABLE_CELL = f"{{{NAMESPACES['table']}}}covered-table-cell"
UNKNOWN_CATEGORY = "UNKNOWN"


class CabinetInventoryRecord(BaseModel):
    cabinet_uid: str
    data_hall_id: str
    cabinet_id: str
    category: str
    cabinet_group: str = ""
    source_row: int
    source_col: int


class OverheadIngestionSummary(BaseModel):
    cabinets: int
    data_halls: int
    unknown_category_cabinets: int


class OverheadIngestionResult(BaseModel):
    summary: OverheadIngestionSummary
    cabinets: list[CabinetInventoryRecord] = Field(default_factory=list)


class _MergedLabel(BaseModel):
    row: int
    col: int
    row_span: int
    col_span: int
    value: str


def ingest_overhead(path: str | Path, sheet_name: str | None = None) -> OverheadIngestionResult:
    cells, merged_labels = _read_ods_grid(Path(path), sheet_name=sheet_name)
    cabinets = _extract_cabinets(cells, merged_labels)
    return OverheadIngestionResult(
        summary=OverheadIngestionSummary(
            cabinets=len(cabinets),
            data_halls=len({cabinet.data_hall_id for cabinet in cabinets}),
            unknown_category_cabinets=sum(1 for cabinet in cabinets if cabinet.category == UNKNOWN_CATEGORY),
        ),
        cabinets=cabinets,
    )


def overhead_result_to_json(result: OverheadIngestionResult) -> str:
    if hasattr(result, "model_dump"):
        payload = result.model_dump(mode="json")
    else:
        payload = result.dict()
    return json.dumps(payload, indent=2)


def _read_ods_grid(path: Path, sheet_name: str | None) -> tuple[dict[tuple[int, int], str], list[_MergedLabel]]:
    with zipfile.ZipFile(path) as ods_file:
        root = ET.fromstring(ods_file.read("content.xml"))

    sheets = root.findall(".//table:table", NAMESPACES)
    if not sheets:
        raise ValueError("ODS file does not contain any sheets.")

    sheet = _select_sheet(sheets, sheet_name)
    cells: dict[tuple[int, int], str] = {}
    merged_labels: list[_MergedLabel] = []
    row_index = 1

    for row in sheet.findall("table:table-row", NAMESPACES):
        row_repeat = int(row.attrib.get(ROW_REPEAT, "1"))
        for _ in range(row_repeat):
            col_index = 1
            for cell in row:
                if cell.tag not in {TABLE_CELL, COVERED_TABLE_CELL}:
                    continue
                col_repeat = int(cell.attrib.get(CELL_REPEAT, "1"))
                value = "" if cell.tag == COVERED_TABLE_CELL else _cell_text(cell)
                row_span = int(cell.attrib.get(ROW_SPAN, "1"))
                col_span = int(cell.attrib.get(COL_SPAN, "1"))
                for offset in range(col_repeat):
                    if value:
                        cells[(row_index, col_index + offset)] = value
                if value and _is_group_label_candidate(value, row_span, col_span):
                    merged_labels.append(
                        _MergedLabel(
                            row=row_index,
                            col=col_index,
                            row_span=row_span,
                            col_span=col_span,
                            value=value,
                        )
                    )
                col_index += col_repeat
            row_index += 1

    return cells, merged_labels


def _extract_cabinets(
    cells: dict[tuple[int, int], str],
    merged_labels: list[_MergedLabel],
) -> list[CabinetInventoryRecord]:
    records: list[CabinetInventoryRecord] = []

    for data_hall_id, start_col, end_col in (("DH1", 1, 37), ("DH2", 38, 80)):
        candidates: dict[int, tuple[int, int, str]] = {}
        for (row, col), value in cells.items():
            if not start_col <= col <= end_col or not _is_cabinet_number(value):
                continue

            cabinet_number = int(value)
            if not 1 <= cabinet_number <= 400:
                continue
            if not _has_numeric_neighbor(cells, row, col):
                continue

            category = _category_for_cabinet(cells, row, col)
            candidates[cabinet_number] = (row, col, category)

        missing = [cabinet_id for cabinet_id in range(1, 401) if cabinet_id not in candidates]
        if missing:
            raise ValueError(f"{data_hall_id} overhead layout is missing cabinet numbers: {missing}")

        for cabinet_number in range(1, 401):
            row, col, category = candidates[cabinet_number]
            cabinet_id = f"{cabinet_number:03d}"
            records.append(
                CabinetInventoryRecord(
                    cabinet_uid=f"{data_hall_id}:{cabinet_id}",
                    data_hall_id=data_hall_id,
                    cabinet_id=cabinet_id,
                    category=category,
                    cabinet_group=_find_cabinet_group(merged_labels, row, col),
                    source_row=row,
                    source_col=col,
                )
            )

    return records


def _find_cabinet_group(merged_labels: list[_MergedLabel], row: int, col: int) -> str:
    candidates: list[tuple[int, int, _MergedLabel]] = []
    for label in merged_labels:
        if _is_ignored_group_label(label.value):
            continue

        covers_col = label.col <= col < label.col + label.col_span
        covers_row = label.row <= row < label.row + label.row_span
        if covers_col and label.row <= row:
            candidates.append((row - label.row, 0, label))
        elif covers_row and label.col < col and col - label.col <= 20:
            candidates.append((0, col - label.col, label))

    if not candidates:
        return ""

    label = min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]
    return _normalize_group(label.value)


def _select_sheet(sheets: list[ET.Element], sheet_name: str | None) -> ET.Element:
    if sheet_name is None:
        return sheets[0]

    for sheet in sheets:
        if sheet.attrib.get(TABLE_NAME) == sheet_name:
            return sheet

    available_sheets = ", ".join(sheet.attrib.get(TABLE_NAME, "") for sheet in sheets)
    raise ValueError(f"Sheet '{sheet_name}' was not found. Available sheets: {available_sheets}")


def _cell_text(cell: ET.Element) -> str:
    paragraphs = []
    for paragraph in cell.findall(".//text:p", NAMESPACES):
        paragraphs.append("".join(paragraph.itertext()))
    return "\n".join(paragraphs).strip()


def _is_cabinet_number(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}", value or ""))


def _has_numeric_neighbor(cells: dict[tuple[int, int], str], row: int, col: int) -> bool:
    return _is_cabinet_number(cells.get((row, col - 1), "")) or _is_cabinet_number(
        cells.get((row, col + 1), "")
    )


def _category_for_cabinet(cells: dict[tuple[int, int], str], row: int, col: int) -> str:
    category = cells.get((row + 1, col), "").strip()
    if _is_category_value(category):
        return category

    for left_col in range(col - 1, 0, -1):
        if not _is_cabinet_number(cells.get((row, left_col), "")):
            break
        category = cells.get((row + 1, left_col), "").strip()
        if _is_category_value(category):
            return category

    for right_col in range(col + 1, col + 11):
        if not _is_cabinet_number(cells.get((row, right_col), "")):
            break
        category = cells.get((row + 1, right_col), "").strip()
        if _is_category_value(category):
            return category

    return UNKNOWN_CATEGORY


def _is_category_value(value: str) -> bool:
    return bool(value and not _is_cabinet_number(value) and value not in {"ROW", "TYPE"})


def _is_group_label_candidate(value: str, row_span: int, col_span: int) -> bool:
    return bool(value and (row_span > 1 or col_span > 1 or "\n" in value) and not _is_cabinet_number(value))


def _is_ignored_group_label(value: str) -> bool:
    normalized_value = value.strip().upper()
    return (
        "APPROVED" in normalized_value
        or normalized_value in {"ROW", "TYPE"}
        or normalized_value.startswith("ROWS ")
    )


def _normalize_group(value: str) -> str:
    return " / ".join(part.strip() for part in value.splitlines() if part.strip())
