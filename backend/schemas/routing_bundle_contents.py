"""Logical coordinates inside a bundle box; these cells are not inches or tiers."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from backend.schemas.routing import Record

SectionEnd = Literal['SPAN', 'START', 'END']
Cell = Annotated[int, Field(strict=True, ge=1, le=64)]


class ContentUnitInput(Record):
    kind: Literal['RACK_PAIR', 'CABLE_LIST']
    cable_uids: Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1, max_length=10000)] | None = None
    source_cabinet_uid: Annotated[str, Field(min_length=1)] | None = None
    destination_cabinet_uid: Annotated[str, Field(min_length=1)] | None = None
    cable_type: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    layer: Cell
    position: Cell
    slot_width: Cell = 1
    slot_height: Cell = 1
    label: Annotated[str, Field(max_length=200)] | None = None

    @model_validator(mode='after')
    def selector(self):
        pair = (self.source_cabinet_uid, self.destination_cabinet_uid, self.cable_type)
        if self.kind == 'CABLE_LIST':
            if not self.cable_uids or any(v is not None for v in pair):
                raise ValueError('An explicit-list unit needs only a nonempty list of actual cable UIDs.')
            if len(set(self.cable_uids)) != len(self.cable_uids):
                raise ValueError('An explicit cable list must not repeat a cable UID.')
        elif self.cable_uids is not None or not all(pair) or pair[0] == pair[1]:
            raise ValueError('A rack-pair unit needs two different cabinet UIDs and one cable type.')
        return self


class BundleContentsInput(Record):
    expected_version: Annotated[str, Field(min_length=1)]
    grid_columns: Cell = 12
    grid_rows: Cell = 8
    units: Annotated[list[ContentUnitInput], Field(max_length=4096)] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode='after')
    def cells(self):
        occupied = set()
        for unit in self.units:
            if unit.position + unit.slot_width - 1 > self.grid_columns or unit.layer + unit.slot_height - 1 > self.grid_rows:
                raise ValueError('A unit footprint is outside its bundle-local grid.')
            for y in range(unit.layer, unit.layer + unit.slot_height):
                for x in range(unit.position, unit.position + unit.slot_width):
                    if (x, y) in occupied:
                        raise ValueError('Bundle-local unit footprints overlap.')
                    occupied.add((x, y))
        return self
