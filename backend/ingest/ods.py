from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NAMESPACES = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
TABLE_NAME = f"{{{NAMESPACES['table']}}}name"
ROW_REPEAT = f"{{{NAMESPACES['table']}}}number-rows-repeated"
CELL_REPEAT = f"{{{NAMESPACES['table']}}}number-columns-repeated"
TABLE_CELL = f"{{{NAMESPACES['table']}}}table-cell"
COVERED_TABLE_CELL = f"{{{NAMESPACES['table']}}}covered-table-cell"


def read_ods_sheet_rows(path: str | Path, sheet_name: str | None = None) -> list[list[str]]:
    with zipfile.ZipFile(path) as ods_file:
        root = ET.fromstring(ods_file.read("content.xml"))

    sheets = root.findall(".//table:table", NAMESPACES)
    if not sheets:
        raise ValueError("ODS file does not contain any sheets.")

    sheet = _select_sheet(sheets, sheet_name)
    rows: list[list[str]] = []
    for row in sheet.findall("table:table-row", NAMESPACES):
        row_repeat = int(row.attrib.get(ROW_REPEAT, "1"))
        values: list[str] = []
        for cell in row:
            if cell.tag not in {TABLE_CELL, COVERED_TABLE_CELL}:
                continue
            cell_repeat = int(cell.attrib.get(CELL_REPEAT, "1"))
            value = "" if cell.tag == COVERED_TABLE_CELL else _cell_text(cell)
            values.extend([value] * cell_repeat)

        trimmed_values = _trim_trailing_empty(values)
        if trimmed_values:
            rows.extend([trimmed_values] * row_repeat)

    return rows


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


def _trim_trailing_empty(values: list[str]) -> list[str]:
    while values and values[-1] == "":
        values.pop()
    return values
