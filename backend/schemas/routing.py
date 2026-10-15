from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Inches = Annotated[int, Field(strict=True, ge=0)]
PositiveInches = Annotated[int, Field(strict=True, gt=0)]
Tier = Annotated[int, Field(strict=True, ge=1, le=3)]
PathwayType = Literal['LADDER_RACK', 'BASKET_TRAY']


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)


class LayoutInput(Record):
    room_uid: str
    name: str = 'LBB01 DH1 routing'
    physical_hall_code: str = 'DH1'
    cabinet_row_depth_in: PositiveInches = 24
    hot_aisle_clear_in: PositiveInches = 96
    cold_aisle_clear_in: PositiveInches = 120
    row_pair_module_in: PositiveInches = 264
    section_extra_gap_in: PositiveInches = 216
    default_cross_route_width_in: PositiveInches = 24
    max_tier: Literal[3] = 3
    cabinets_per_row: Annotated[int, Field(strict=True, ge=1, le=1600)] = 10

    @model_validator(mode='after')
    def geometry(self):
        if self.row_pair_module_in != 2 * self.cabinet_row_depth_in + self.hot_aisle_clear_in + self.cold_aisle_clear_in:
            raise ValueError('Row-pair module must equal two rows + hot aisle + cold aisle.')
        for key in ('cabinet_row_depth_in', 'section_extra_gap_in', 'default_cross_route_width_in'):
            even_width(getattr(self, key))
        return self


def even_width(value: int) -> None:
    if value % 2:
        raise ValueError('Centerline dimensions must be even inches so derived stations remain integer inches.')


class SectionInput(Record):
    ordinal: Annotated[int, Field(strict=True, ge=1, le=5)]
    name: str
    room_uid: str | None = None


class BandInput(Record):
    ordinal: Annotated[int, Field(strict=True, ge=0)]
    kind: Literal['PASSAGE', 'ROW_FIELD']
    code: Literal['NORTH', 'NORTH_FIELD', 'CENTRAL', 'SOUTH_FIELD', 'SOUTH']
    width_in: PositiveInches

    @model_validator(mode='after')
    def band(self):
        even_width(self.width_in)
        codes = ('NORTH', 'NORTH_FIELD', 'CENTRAL', 'SOUTH_FIELD', 'SOUTH')
        if self.ordinal >= 5 or codes[self.ordinal] != self.code:
            raise ValueError('Bands must follow NORTH, NORTH_FIELD, CENTRAL, SOUTH_FIELD, SOUTH order.')
        if (self.kind == 'PASSAGE') != (self.code in ('NORTH', 'CENTRAL', 'SOUTH')):
            raise ValueError('Passage code and band kind disagree.')
        return self


class RowPairInput(Record):
    routing_section_uid: str
    row_field_band_uid: str
    ordinal_in_section: Annotated[int, Field(strict=True, ge=1)]
    name: str | None = None


class CabinetRowInput(Record):
    row_pair_uid: str
    position_in_pair: Literal['A', 'B']
    name: Annotated[str, Field(min_length=1)]
    existing_row_reference: str | None = None
    cabinet_number_start: Annotated[int, Field(strict=True, ge=1, le=1600)] | None = None
    cabinet_number_end: Annotated[int, Field(strict=True, ge=1, le=1600)] | None = None
    cold_route_face_offset_in: Inches = 0
    enabled: bool = True

    @model_validator(mode='after')
    def cabinet_range(self):
        if (self.cabinet_number_start is None) != (self.cabinet_number_end is None):
            raise ValueError('Provide both cabinet range endpoints.')
        if self.cabinet_number_start is not None and self.cabinet_number_end < self.cabinet_number_start:
            raise ValueError('Cabinet range must be in increasing order.')
        return self


class CrossRouteInput(Record):
    kind: Literal['CABINET_COLD_AISLE', 'SECTION_GAP']
    cabinet_row_uid: str | None = None
    section_boundary_after_section_uid: str | None = None
    width_in: PositiveInches = 24
    station_source: Literal['DERIVED', 'MANUAL', 'FIELD_MEASURED'] = 'DERIVED'
    manual_station_in: Inches | None = None
    label: str | None = None
    notes: str | None = None
    enabled: bool = True

    @model_validator(mode='after')
    def association(self):
        even_width(self.width_in)
        if self.kind == 'CABINET_COLD_AISLE':
            valid = self.cabinet_row_uid is not None and self.section_boundary_after_section_uid is None
        else:
            valid = self.cabinet_row_uid is None and self.section_boundary_after_section_uid is not None
        if not valid:
            raise ValueError('Cross route requires exactly its cabinet row or section-boundary reference.')
        if (self.station_source == 'DERIVED') != (self.manual_station_in is None):
            raise ValueError('MANUAL/FIELD_MEASURED require a station; DERIVED must not store one.')
        return self


class CrossRouteTierInput(Record):
    cross_route_uid: str
    tier: Tier
    pathway_type: PathwayType
    enabled: bool = True


class PassageTierInput(Record):
    passage_band_uid: str
    tier: Tier
    pathway_type: PathwayType
    enabled: bool = True


class VerticalTransitionInput(Record):
    passage_band_uid: str
    station_in: Inches
    lower_tier: Tier
    upper_tier: Tier
    label: str | None = None
    notes: str | None = None
    enabled: bool = True

    @model_validator(mode='after')
    def adjacent(self):
        if self.upper_tier != self.lower_tier + 1:
            raise ValueError('An opening connects two adjacent tiers only (T1-T2 or T2-T3).')
        return self


class PreviewInput(Record):
    start_node_id: str
    end_node_id: str


class InitializeInput(Record):
    project_uid: Literal['LBB01'] = 'LBB01'
    building_id: str = 'A'


class GraphNode(Record):
    id: str
    node_type: Literal['CROSS_PASSAGE_INTERSECTION', 'PASSAGE_STATION']
    x_in: int
    y_in: int
    station_in: int
    tier: int
    passage_code: str
    passage_band_uid: str
    cross_route_uid: str | None = None
    cross_route_kind: str | None = None
    cabinet_row_uid: str | None = None
    vertical_transition_uids: list[str] = Field(default_factory=list)
    label: str | None = None


class GraphEdge(Record):
    id: str
    edge_type: Literal['CROSS_ROUTE', 'PASSAGE', 'JUNCTION', 'VERTICAL']
    source_node_id: str
    target_node_id: str
    planar_length_in: int = 0
    tier: int | None = None
    lower_tier: int | None = None
    upper_tier: int | None = None
    pathway_type: str | None = None
    passage_code: str | None = None
    cross_route_uid: str | None = None
    cross_route_kind: str | None = None
    cabinet_row_uid: str | None = None
    vertical_transition_uid: str | None = None


class RoutingGraph(Record):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RoutePreview(Record):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    vertical_transition_count: int
    planar_length_in: int
    length_label: Literal['Planar pathway length'] = 'Planar pathway length'
    steps: list[str]
    vertical_opening_labels: list[str]
