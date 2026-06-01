from __future__ import annotations

from pydantic import BaseModel, Field

from backend.core.enums import (
    CableProgressPhaseType,
    CableProgressState,
    CableProgressStep,
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


class Device(BaseModel):
    cabinet_id: str
    rack_unit: int
    device_model: str
    lifecycle_status: LifecycleStatus = LifecycleStatus.NOT_INSTALLED
    aliases: list[str] = Field(default_factory=list)
    model_aliases: list[str] = Field(default_factory=list)
    ports_by_type: dict[ConnectorType, list[PortConnector]] = Field(default_factory=dict)
    note: str = ""


class Cabinet(BaseModel):
    building_id: str
    data_hall_id: str
    cabinet_id: str
    category: str = ""
    cabinet_group: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.NOT_INSTALLED
    max_rack_unit: int = 48
    source_row: int | None = None
    source_col: int | None = None
    devices: list[Device] = Field(default_factory=list)


class Room(BaseModel):
    building_id: str
    room_id: str
    lifecycle_status: LifecycleStatus = LifecycleStatus.UNKNOWN
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


class Cable(BaseModel):
    uid: str = ""
    a_side: PortConnector
    z_side: PortConnector
    cable_type: str
    group: str = ""
    status: str = ""
    progress: dict[CableProgressStep, CableProgressState] = Field(default_factory=dict)
    current_phase: CableProgressPhase | None = None
    designed_length_meters: float | None = None
    length_used_meters: float = 0
    a_optic: OpticModule | None = None
    z_optic: OpticModule | None = None
    note: str = ""
