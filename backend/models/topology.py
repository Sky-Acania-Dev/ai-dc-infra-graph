from __future__ import annotations

from pydantic import BaseModel, Field

from backend.core.enums import (
    CableProgressPhaseType,
    CableProgressTaskType,
    CableProgressState,
    CableProgressStep,
    ConstructionPhase,
    ConnectorType,
    LifecycleStatus,
)


class Project(BaseModel):
    uid: str
    full_name: str


class PortConnector(BaseModel):
    uid: str
    type: ConnectorType
    note: str = ""


class OpticModule(BaseModel):
    model: str
    side: str = ""
    note: str = ""


class DevicePortLayoutEntry(BaseModel):
    port_name: str
    side: str = "front"
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0
    connector_type: ConnectorType = ConnectorType.OTHER
    note: str = ""


class DeviceModel(BaseModel):
    uid: str
    model_name: str
    manufacturer: str = ""
    rack_units: int = 1
    device_instance_uids: list[str] = Field(default_factory=list)
    front_panel_svg: str = ""
    back_panel_svg: str = ""
    port_layout: list[DevicePortLayoutEntry] = Field(default_factory=list)
    note: str = ""


class Device(BaseModel):
    cabinet_id: str
    rack_unit: int
    device_model: str
    device_model_uid: str = ""
    rack_units: int = 1
    lifecycle_status: LifecycleStatus = LifecycleStatus.NOT_INSTALLED
    construction_phase: ConstructionPhase = ConstructionPhase.MANAGEMENT_ETHERNET
    aliases: list[str] = Field(default_factory=list)
    model_aliases: list[str] = Field(default_factory=list)
    front_panel_svg: str = ""
    back_panel_svg: str = ""
    port_layout: list[DevicePortLayoutEntry] = Field(default_factory=list)
    port_layout_overrides: list[DevicePortLayoutEntry] = Field(default_factory=list)
    ports_by_type: dict[ConnectorType, list[PortConnector]] = Field(default_factory=dict)
    note: str = ""


class Cabinet(BaseModel):
    building_id: str
    data_hall_id: str
    cabinet_id: str
    category: str = ""
    cabinet_group: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.NOT_INSTALLED
    construction_phase: ConstructionPhase = ConstructionPhase.MANAGEMENT_ETHERNET
    max_rack_unit: int = 48
    source_row: int | None = None
    source_col: int | None = None
    devices: list[Device] = Field(default_factory=list)


class Room(BaseModel):
    building_id: str
    room_id: str
    lifecycle_status: LifecycleStatus = LifecycleStatus.UNKNOWN
    construction_phase: ConstructionPhase = ConstructionPhase.MANAGEMENT_ETHERNET
    cabinets: list[Cabinet] = Field(default_factory=list)


class Building(BaseModel):
    project_uid: str
    building_id: str
    rooms: list[Room] = Field(default_factory=list)


class CableProgressPhase(BaseModel):
    name: str = ""
    phase_type: CableProgressPhaseType = CableProgressPhaseType.SINGLE_PERCENT
    value: float | str | None = None
    tasks: dict[str, float] = Field(default_factory=dict)
    enum_values: list[str] = Field(default_factory=list)
    task_values: dict[str, "CableProgressTask"] = Field(default_factory=dict)


class CableProgressTask(BaseModel):
    task_type: CableProgressTaskType = CableProgressTaskType.PERCENT
    value: float | str | None = None
    enum_values: list[str] = Field(default_factory=list)


class Cable(BaseModel):
    uid: str = ""
    a_side: PortConnector
    z_side: PortConnector
    cable_type: str
    group: str = ""
    status: str = ""
    construction_phase: ConstructionPhase = ConstructionPhase.MANAGEMENT_ETHERNET
    progress: dict[CableProgressStep, CableProgressState] = Field(default_factory=dict)
    current_phase: CableProgressPhase | None = None
    designed_length_meters: float | None = None
    length_used_meters: float = 0
    a_optic: OpticModule | None = None
    z_optic: OpticModule | None = None
    note: str = ""
