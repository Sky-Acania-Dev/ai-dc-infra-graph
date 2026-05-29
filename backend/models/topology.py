from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ConnectorType(StrEnum):
    CAT6 = "CAT6"
    LC = "LC"
    SC = "SC"
    MPO = "MPO"
    POWER = "power"
    OTHER = "other"


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
    ports_by_type: dict[ConnectorType, list[PortConnector]] = Field(default_factory=dict)
    note: str = ""


class Cabinet(BaseModel):
    building_id: str
    data_hall_id: str
    cabinet_id: str
    devices: list[Device] = Field(default_factory=list)


class Room(BaseModel):
    building_id: str
    room_id: str
    cabinets: list[Cabinet] = Field(default_factory=list)


class Building(BaseModel):
    project_uid: str
    building_id: str
    rooms: list[Room] = Field(default_factory=list)


class Cable(BaseModel):
    a_side: PortConnector
    z_side: PortConnector
    cable_type: str
    group: str = ""
    status: str = ""
    a_optic: OpticModule | None = None
    z_optic: OpticModule | None = None
    note: str = ""
