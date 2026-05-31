from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from backend.models import CableProgressState, CableProgressStep, Device, LifecycleStatus


class DeviceStatusOverride(BaseModel):
    device_uid: str
    lifecycle_status: LifecycleStatus
    device_model: str | None = None
    note: str = ""


class CableOverride(BaseModel):
    cable_uid: str
    progress: dict[CableProgressStep, CableProgressState] = Field(default_factory=dict)
    length_meters: float | None = None
    note: str = ""


class StatusOverrides(BaseModel):
    data_halls: dict[str, LifecycleStatus] = Field(default_factory=dict)
    cabinets: dict[str, LifecycleStatus] = Field(default_factory=dict)
    cabinet_max_rack_units: dict[str, int] = Field(default_factory=dict)
    devices: dict[str, DeviceStatusOverride] = Field(default_factory=dict)
    cables: dict[str, CableOverride] = Field(default_factory=dict)


def load_status_overrides(path: str | Path | None) -> StatusOverrides:
    if path is None:
        return StatusOverrides()

    override_path = Path(path)
    if not override_path.exists():
        raise FileNotFoundError(f"Status override file was not found: {override_path}")

    payload = json.loads(override_path.read_text(encoding="utf-8"))
    return StatusOverrides(
        data_halls={key.upper(): LifecycleStatus(value) for key, value in payload.get("data_halls", {}).items()},
        cabinets={key.upper(): LifecycleStatus(value) for key, value in payload.get("cabinets", {}).items()},
        cabinet_max_rack_units={
            key.upper(): int(value) for key, value in payload.get("cabinet_max_rack_units", {}).items()
        },
        devices={
            _normalize_device_uid(key): DeviceStatusOverride(device_uid=_normalize_device_uid(key), **value)
            for key, value in payload.get("devices", {}).items()
        },
        cables={
            key.upper(): CableOverride(cable_uid=key.upper(), **value)
            for key, value in payload.get("cables", {}).items()
        },
    )


def apply_status_overrides(database, overrides: StatusOverrides):
    for data_hall in database.data_halls:
        data_hall_uid = data_hall.room_id.upper()
        if data_hall_uid in overrides.data_halls:
            data_hall.lifecycle_status = overrides.data_halls[data_hall_uid]
        _apply_cabinet_overrides(data_hall.cabinets, overrides)

    _apply_cabinet_overrides(database.cabinets, overrides)
    _apply_cable_overrides(database.cables, overrides)
    return database


def _apply_cable_overrides(cables, overrides: StatusOverrides) -> None:
    cables_by_uid = {cable.uid.upper(): cable for cable in cables if cable.uid}
    for cable_uid, override in overrides.cables.items():
        cable = cables_by_uid.get(cable_uid)
        if cable is None:
            continue
        if override.progress:
            cable.progress.update(override.progress)
        if override.length_meters is not None:
            cable.length_meters = override.length_meters
        if override.note:
            cable.note = override.note


def _apply_cabinet_overrides(cabinets, overrides: StatusOverrides) -> None:
    cabinets_by_uid = {f"{cabinet.data_hall_id}:{cabinet.cabinet_id}".upper(): cabinet for cabinet in cabinets}
    for cabinet_uid, cabinet in cabinets_by_uid.items():
        if cabinet_uid in overrides.cabinets:
            cabinet.lifecycle_status = overrides.cabinets[cabinet_uid]
        elif cabinet.category.upper() in {"RES", "U"}:
            cabinet.lifecycle_status = LifecycleStatus.NOT_PLANNED
        if cabinet_uid in overrides.cabinet_max_rack_units:
            cabinet.max_rack_unit = overrides.cabinet_max_rack_units[cabinet_uid]

    for device_uid, override in overrides.devices.items():
        cabinet_uid = _cabinet_uid_from_device_uid(device_uid)
        cabinet = cabinets_by_uid.get(cabinet_uid)
        if cabinet is None:
            continue

        cabinet.devices = _dedupe_devices_by_rack_unit(cabinet.devices)
        device = _find_device(cabinet.devices, device_uid)
        if device is None:
            device = Device(
                cabinet_id=cabinet_uid,
                rack_unit=int(device_uid.split(":")[2]),
                device_model=override.device_model or "Unknown",
            )
            cabinet.devices.append(device)
        elif _should_apply_device_model(device.device_model, override.device_model):
            device.device_model = override.device_model

        device.lifecycle_status = override.lifecycle_status
        if override.note:
            device.note = override.note
        cabinet.devices.sort(key=lambda item: (item.rack_unit, item.device_model))


def _find_device(devices: list[Device], device_uid: str) -> Device | None:
    normalized_uid = _normalize_device_uid(device_uid)
    for device in devices:
        if _normalize_device_uid(f"{device.cabinet_id}:{device.rack_unit}") == normalized_uid:
            return device
    return None


def _should_apply_device_model(current_model: str, override_model: str | None) -> bool:
    if not override_model:
        return False
    if override_model == "Unknown" and current_model != "Unknown":
        return False
    return True


def _dedupe_devices_by_rack_unit(devices: list[Device]) -> list[Device]:
    devices_by_position: dict[tuple[str, int], Device] = {}
    for device in sorted(devices, key=lambda item: (item.rack_unit, item.device_model == "Unknown")):
        key = (device.cabinet_id.upper(), device.rack_unit)
        existing = devices_by_position.get(key)
        if existing is None:
            devices_by_position[key] = device
            continue

        if existing.device_model == "Unknown" and device.device_model != "Unknown":
            existing.device_model = device.device_model
        existing.aliases = sorted(set(existing.aliases + device.aliases))
        existing.model_aliases = sorted(set(existing.model_aliases + device.model_aliases))
        for connector_type, ports in device.ports_by_type.items():
            existing_ports = {port.uid: port for port in existing.ports_by_type.get(connector_type, [])}
            existing_ports.update({port.uid: port for port in ports})
            existing.ports_by_type[connector_type] = sorted(existing_ports.values(), key=lambda port: port.uid)
        if not existing.note and device.note:
            existing.note = device.note

    return sorted(devices_by_position.values(), key=lambda item: (item.rack_unit, item.device_model))


def _cabinet_uid_from_device_uid(device_uid: str) -> str:
    data_hall_id, cabinet_id, _ = _normalize_device_uid(device_uid).split(":", 2)
    return f"{data_hall_id}:{cabinet_id}".upper()


def _normalize_device_uid(device_uid: str) -> str:
    data_hall_id, cabinet_id, rack_unit = device_uid.upper().split(":", 2)
    return f"{data_hall_id}:{cabinet_id}:{int(rack_unit)}"
