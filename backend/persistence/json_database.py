from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from backend.ingest.cutsheet import CutsheetCableRow, CutsheetIngestionResult, CutsheetSummary
from backend.models import Cabinet, Cable, PortConnector, Room
from backend.validation import PortConnectionFinding


DEFAULT_RUNTIME_DATABASE_PATH = Path("data/runtime/current_database.json")
ModelT = TypeVar("ModelT", bound=BaseModel)


class TopologyDatabase(BaseModel):
    project_uid: str
    building_id: str
    summary: CutsheetSummary
    port_collision_findings: list[PortConnectionFinding] = Field(default_factory=list)
    data_halls: list[Room] = Field(default_factory=list)
    cabinets: list[Cabinet] = Field(default_factory=list)
    ports: list[PortConnector] = Field(default_factory=list)
    cables: list[Cable] = Field(default_factory=list)
    rows: list[CutsheetCableRow] = Field(default_factory=list)

    @property
    def has_port_collisions(self) -> bool:
        return bool(self.port_collision_findings)


def database_from_ingestion_result(result: CutsheetIngestionResult) -> TopologyDatabase:
    return TopologyDatabase(
        project_uid=result.project_uid,
        building_id=result.building_id,
        summary=CutsheetSummary(
            rows=len(result.rows),
            data_halls=len(result.data_halls),
            cabinets=len(result.cabinets),
            ports=len(result.ports),
            cables=len(result.cables),
            port_collision_findings=len(result.findings),
        ),
        port_collision_findings=result.findings,
        data_halls=result.data_halls,
        cabinets=result.cabinets,
        ports=result.ports,
        cables=result.cables,
        rows=result.rows,
    )


def load_topology_database(path: str | Path) -> TopologyDatabase:
    payload = json.loads(_read_json_text(Path(path)))
    return database_from_json_payload(payload)


def database_from_json_payload(payload: dict[str, Any]) -> TopologyDatabase:
    findings_payload = payload.get("port_collision_findings", payload.get("findings", []))
    rows_payload = payload.get("rows", [])
    data_halls_payload = payload.get("data_halls", [])
    cabinets_payload = payload.get("cabinets", [])
    ports_payload = payload.get("ports", [])
    cables_payload = payload.get("cables", [])
    summary_payload = payload.get("summary") or {
        "rows": len(rows_payload),
        "data_halls": len(data_halls_payload),
        "cabinets": len(cabinets_payload),
        "ports": len(ports_payload),
        "cables": len(cables_payload),
        "port_collision_findings": len(findings_payload),
    }

    return TopologyDatabase(
        project_uid=payload["project_uid"],
        building_id=payload["building_id"],
        summary=_model_from_payload(CutsheetSummary, summary_payload),
        port_collision_findings=[
            _model_from_payload(PortConnectionFinding, finding) for finding in findings_payload
        ],
        data_halls=[_model_from_payload(Room, data_hall) for data_hall in data_halls_payload],
        cabinets=[_model_from_payload(Cabinet, cabinet) for cabinet in cabinets_payload],
        ports=[_model_from_payload(PortConnector, port) for port in ports_payload],
        cables=[_model_from_payload(Cable, cable) for cable in cables_payload],
        rows=[_model_from_payload(CutsheetCableRow, row) for row in rows_payload],
    )


def save_topology_database(database: TopologyDatabase, path: str | Path = DEFAULT_RUNTIME_DATABASE_PATH) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(topology_database_to_json(database), encoding="utf-8")
    return output_path


def topology_database_to_json(database: TopologyDatabase) -> str:
    if hasattr(database, "model_dump"):
        payload = database.model_dump(mode="json")
    else:
        payload = database.dict()
    return json.dumps(payload, indent=2)


def _model_from_payload(model_type: type[ModelT], payload: dict[str, Any]) -> ModelT:
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(payload)
    return model_type.parse_obj(payload)


def _read_json_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8")
