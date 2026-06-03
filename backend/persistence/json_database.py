from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from backend.core.config import DEFAULT_RUNTIME_DATABASE_PATH, SCHEMA_VERSION
from backend.ingest.cutsheet import CutsheetCableRow, CutsheetIngestionResult, CutsheetSummary
from backend.models import Cabinet, Cable, Device, DeviceModel, PortConnector, Room
from backend.validation import PortConnectionFinding
from backend.validation.device_models import DeviceModelFinding, detect_device_model_findings


ModelT = TypeVar("ModelT", bound=BaseModel)


class TopologyDatabase(BaseModel):
    schema_version: int = SCHEMA_VERSION
    project_uid: str
    building_id: str
    summary: CutsheetSummary
    port_collision_findings: list[PortConnectionFinding] = Field(default_factory=list)
    device_model_mismatches: list[DeviceModelFinding] = Field(default_factory=list)
    device_model_format_issues: list[DeviceModelFinding] = Field(default_factory=list)
    data_halls: list[Room] = Field(default_factory=list)
    cabinets: list[Cabinet] = Field(default_factory=list)
    device_models: list[DeviceModel] = Field(default_factory=list)
    ports: list[PortConnector] = Field(default_factory=list)
    cables: list[Cable] = Field(default_factory=list)
    rows: list[CutsheetCableRow] = Field(default_factory=list)

    @property
    def has_port_collisions(self) -> bool:
        return bool(self.port_collision_findings)


def database_from_ingestion_result(result: CutsheetIngestionResult) -> TopologyDatabase:
    device_model_mismatches, device_model_format_issues = detect_device_model_findings(result.rows)
    device_models = _device_models_from_cabinets(result.cabinets)
    _apply_device_model_catalog(result.cabinets, device_models)
    _apply_device_model_catalog_to_data_halls(result.data_halls, device_models)
    return TopologyDatabase(
        schema_version=SCHEMA_VERSION,
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
        device_model_mismatches=device_model_mismatches,
        device_model_format_issues=device_model_format_issues,
        data_halls=result.data_halls,
        cabinets=result.cabinets,
        device_models=device_models,
        ports=result.ports,
        cables=result.cables,
        rows=result.rows,
    )


def load_topology_database(path: str | Path) -> TopologyDatabase:
    payload = json.loads(_read_json_text(Path(path)))
    return database_from_json_payload(payload)


def database_from_json_payload(payload: dict[str, Any]) -> TopologyDatabase:
    findings_payload = payload.get("port_collision_findings", payload.get("findings", []))
    device_model_mismatches_payload = payload.get("device_model_mismatches")
    device_model_format_issues_payload = payload.get("device_model_format_issues")
    rows_payload = payload.get("rows", [])
    data_halls_payload = payload.get("data_halls", [])
    cabinets_payload = payload.get("cabinets", [])
    device_models_payload = payload.get("device_models", [])
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

    rows = [_model_from_payload(CutsheetCableRow, row) for row in rows_payload]
    if device_model_mismatches_payload is None or device_model_format_issues_payload is None:
        detected_mismatches, detected_format_issues = detect_device_model_findings(rows)
        if device_model_mismatches_payload is None:
            device_model_mismatches_payload = [_model_to_payload(finding) for finding in detected_mismatches]
        if device_model_format_issues_payload is None:
            device_model_format_issues_payload = [_model_to_payload(finding) for finding in detected_format_issues]

    cables = [_model_from_payload(Cable, _normalize_cable_payload(cable)) for cable in cables_payload]
    _backfill_cable_uids(cables)
    cabinets = [_model_from_payload(Cabinet, cabinet) for cabinet in cabinets_payload]
    device_models = [_model_from_payload(DeviceModel, _normalize_device_model_payload(model)) for model in device_models_payload]
    if not device_models:
        device_models = _device_models_from_cabinets(cabinets)
    _apply_device_model_catalog(cabinets, device_models)
    data_halls = [_model_from_payload(Room, data_hall) for data_hall in data_halls_payload]
    _apply_device_model_catalog_to_data_halls(data_halls, device_models)

    return TopologyDatabase(
        schema_version=SCHEMA_VERSION,
        project_uid=payload["project_uid"],
        building_id=payload["building_id"],
        summary=_model_from_payload(CutsheetSummary, summary_payload),
        port_collision_findings=[
            _model_from_payload(PortConnectionFinding, finding) for finding in findings_payload
        ],
        device_model_mismatches=[
            _model_from_payload(DeviceModelFinding, _normalize_device_model_finding_payload(finding))
            for finding in device_model_mismatches_payload
        ],
        device_model_format_issues=[
            _model_from_payload(DeviceModelFinding, _normalize_device_model_finding_payload(finding))
            for finding in device_model_format_issues_payload
        ],
        data_halls=data_halls,
        cabinets=cabinets,
        device_models=device_models,
        ports=[_model_from_payload(PortConnector, port) for port in ports_payload],
        cables=cables,
        rows=rows,
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


def _model_to_payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _normalize_device_model_finding_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized_payload = dict(payload)
    for key in ("models", "normalized_models"):
        value = normalized_payload.get(key, [])
        if isinstance(value, dict):
            normalized_payload[key] = [
                {"value": model_value, "count": count} for model_value, count in sorted(value.items())
            ]
    return normalized_payload


def _normalize_cable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized_payload = dict(payload)
    if "length_used_meters" not in normalized_payload:
        normalized_payload["length_used_meters"] = normalized_payload.get("length_meters") or 0
    if "designed_length_meters" not in normalized_payload:
        normalized_payload["designed_length_meters"] = None
    return normalized_payload


def _normalize_device_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized_payload = dict(payload)
    model_name = normalized_payload.get("model_name") or normalized_payload.get("uid") or "Unknown"
    normalized_payload["model_name"] = model_name
    normalized_payload["uid"] = normalized_payload.get("uid") or _device_model_uid(model_name)
    normalized_payload["rack_units"] = max(1, int(normalized_payload.get("rack_units") or 1))
    return normalized_payload


def _device_models_from_cabinets(cabinets: list[Cabinet]) -> list[DeviceModel]:
    models_by_uid: dict[str, DeviceModel] = {}
    for cabinet in cabinets:
        for device in cabinet.devices:
            model_name = device.device_model or "Unknown"
            model_uid = device.device_model_uid or _device_model_uid(model_name)
            instance_uid = _device_uid(device)
            model = models_by_uid.get(model_uid)
            if model is None:
                model = DeviceModel(uid=model_uid, model_name=model_name)
                models_by_uid[model_uid] = model
            if instance_uid not in model.device_instance_uids:
                model.device_instance_uids.append(instance_uid)

    for model in models_by_uid.values():
        model.device_instance_uids.sort()
    return sorted(models_by_uid.values(), key=lambda model: model.model_name)


def _apply_device_model_catalog(cabinets: list[Cabinet], device_models: list[DeviceModel]) -> None:
    models_by_uid = {model.uid: model for model in device_models}
    for cabinet in cabinets:
        for device in cabinet.devices:
            _apply_device_model_to_device(device, models_by_uid)


def _apply_device_model_catalog_to_data_halls(data_halls: list[Room], device_models: list[DeviceModel]) -> None:
    models_by_uid = {model.uid: model for model in device_models}
    for data_hall in data_halls:
        for cabinet in data_hall.cabinets:
            for device in cabinet.devices:
                _apply_device_model_to_device(device, models_by_uid)


def _apply_device_model_to_device(device: Device, models_by_uid: dict[str, DeviceModel]) -> None:
    model_uid = device.device_model_uid or _device_model_uid(device.device_model or "Unknown")
    model = models_by_uid.get(model_uid)
    device.device_model_uid = model_uid
    if model is not None:
        device.rack_units = max(1, model.rack_units)
        return
    device.rack_units = max(1, int(device.rack_units or 1))


def _device_model_uid(model_name: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "-", model_name.upper()).strip("-")
    return normalized or "UNKNOWN"


def _device_uid(device: Device) -> str:
    return f"{device.cabinet_id}:{device.rack_unit}".upper()


def _backfill_cable_uids(cables: list[Cable]) -> None:
    used_uids = {cable.uid for cable in cables if cable.uid}
    for index, cable in enumerate(cables, start=1):
        if cable.uid:
            continue
        candidate = f"CBL-{index:06d}"
        while candidate in used_uids:
            index += 1
            candidate = f"CBL-{index:06d}"
        cable.uid = candidate
        used_uids.add(candidate)


def _read_json_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8")
