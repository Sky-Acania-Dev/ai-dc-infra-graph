"""Persist routing facts only; graph nodes and edges are derived at read time."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.persistence.postgresql.models import Base


class RoutingRecord:
    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LayoutChild(RoutingRecord):
    routing_layout_uid: Mapped[str] = mapped_column(ForeignKey("routing_layouts.uid", ondelete="CASCADE"), index=True)


class RoutingLayout(RoutingRecord, Base):
    __tablename__ = "routing_layouts"
    __table_args__ = (
        CheckConstraint("cabinet_row_depth_in > 0 AND cabinet_row_depth_in % 2 = 0", name="ck_routing_row_depth"),
        CheckConstraint("hot_aisle_clear_in > 0 AND cold_aisle_clear_in > 0", name="ck_routing_aisles"),
        CheckConstraint("row_pair_module_in = 2 * cabinet_row_depth_in + hot_aisle_clear_in + cold_aisle_clear_in", name="ck_routing_module"),
        CheckConstraint("section_extra_gap_in > 0 AND section_extra_gap_in % 2 = 0", name="ck_routing_gap"),
        CheckConstraint("default_cross_route_width_in > 0 AND default_cross_route_width_in % 2 = 0", name="ck_routing_default_width"),
        CheckConstraint("max_tier = 3", name="ck_routing_max_tier"),
        CheckConstraint("cabinets_per_row > 0", name="ck_routing_cabinet_count"),
    )
    room_uid: Mapped[str] = mapped_column(ForeignKey("rooms.uid"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    physical_hall_code: Mapped[str] = mapped_column(Text, default="DH1")
    cabinet_row_depth_in: Mapped[int] = mapped_column(Integer, default=24)
    hot_aisle_clear_in: Mapped[int] = mapped_column(Integer, default=96)
    cold_aisle_clear_in: Mapped[int] = mapped_column(Integer, default=120)
    row_pair_module_in: Mapped[int] = mapped_column(Integer, default=264)
    section_extra_gap_in: Mapped[int] = mapped_column(Integer, default=216)
    default_cross_route_width_in: Mapped[int] = mapped_column(Integer, default=24)
    max_tier: Mapped[int] = mapped_column(Integer, default=3)
    cabinets_per_row: Mapped[int] = mapped_column(Integer, default=10)


class RoutingSection(LayoutChild, Base):
    __tablename__ = "routing_sections"
    __table_args__ = (UniqueConstraint("routing_layout_uid", "ordinal", name="uq_routing_section_ordinal"),
                      CheckConstraint("ordinal BETWEEN 1 AND 5", name="ck_routing_section_ordinal"))
    ordinal: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Text)
    room_uid: Mapped[str | None] = mapped_column(ForeignKey("rooms.uid"))


class RoutingBand(LayoutChild, Base):
    __tablename__ = "routing_bands"
    __table_args__ = (
        UniqueConstraint("routing_layout_uid", "ordinal", name="uq_routing_band_ordinal"),
        UniqueConstraint("routing_layout_uid", "code", name="uq_routing_band_code"),
        CheckConstraint("ordinal >= 0", name="ck_routing_band_ordinal"),
        CheckConstraint("width_in > 0 AND width_in % 2 = 0", name="ck_routing_band_width"),
        CheckConstraint("(kind = 'PASSAGE' AND code IN ('NORTH','CENTRAL','SOUTH')) OR (kind = 'ROW_FIELD' AND code IN ('NORTH_FIELD','SOUTH_FIELD'))", name="ck_routing_band_kind"),
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)
    width_in: Mapped[int] = mapped_column(Integer)


class RoutingRowPair(LayoutChild, Base):
    __tablename__ = "routing_row_pairs"
    __table_args__ = (UniqueConstraint("routing_section_uid", "row_field_band_uid", "ordinal_in_section", name="uq_routing_pair_ordinal"),
                      CheckConstraint("ordinal_in_section >= 1", name="ck_routing_pair_ordinal"))
    routing_section_uid: Mapped[str] = mapped_column(ForeignKey("routing_sections.uid", ondelete="CASCADE"), index=True)
    row_field_band_uid: Mapped[str] = mapped_column(ForeignKey("routing_bands.uid"), index=True)
    ordinal_in_section: Mapped[int] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(Text)


class RoutingCabinetRow(LayoutChild, Base):
    __tablename__ = "routing_cabinet_rows"
    __table_args__ = (UniqueConstraint("row_pair_uid", "position_in_pair", name="uq_routing_row_position"),
                      CheckConstraint("position_in_pair IN ('A','B')", name="ck_routing_row_position"),
                      CheckConstraint("(cabinet_number_start IS NULL AND cabinet_number_end IS NULL) OR (cabinet_number_start IS NOT NULL AND cabinet_number_end IS NOT NULL AND cabinet_number_start > 0 AND cabinet_number_end >= cabinet_number_start)", name="ck_routing_row_cabinets"),
                      CheckConstraint("cold_route_face_offset_in >= 0", name="ck_routing_row_offset"))
    row_pair_uid: Mapped[str] = mapped_column(ForeignKey("routing_row_pairs.uid", ondelete="CASCADE"), index=True)
    position_in_pair: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    existing_row_reference: Mapped[str | None] = mapped_column(Text)
    cabinet_number_start: Mapped[int | None] = mapped_column(Integer)
    cabinet_number_end: Mapped[int | None] = mapped_column(Integer)
    cold_route_face_offset_in: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingCrossRoute(LayoutChild, Base):
    __tablename__ = "routing_cross_routes"
    __table_args__ = (
        UniqueConstraint("cabinet_row_uid", name="uq_routing_cross_cabinet"),
        UniqueConstraint("section_boundary_after_section_uid", name="uq_routing_cross_boundary"),
        CheckConstraint("width_in > 0 AND width_in % 2 = 0", name="ck_routing_cross_width"),
        CheckConstraint("(kind = 'CABINET_COLD_AISLE' AND cabinet_row_uid IS NOT NULL AND section_boundary_after_section_uid IS NULL) OR (kind = 'SECTION_GAP' AND cabinet_row_uid IS NULL AND section_boundary_after_section_uid IS NOT NULL)", name="ck_routing_cross_association"),
        CheckConstraint("(station_source = 'DERIVED' AND manual_station_in IS NULL) OR (station_source IN ('MANUAL','FIELD_MEASURED') AND manual_station_in IS NOT NULL AND manual_station_in >= 0)", name="ck_routing_cross_station"),
    )
    kind: Mapped[str] = mapped_column(Text)
    cabinet_row_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_cabinet_rows.uid", ondelete="CASCADE"))
    section_boundary_after_section_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_sections.uid", ondelete="CASCADE"))
    width_in: Mapped[int] = mapped_column(Integer, default=24)
    station_source: Mapped[str] = mapped_column(Text, default="DERIVED")
    manual_station_in: Mapped[int | None] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingCrossRouteTier(LayoutChild, Base):
    __tablename__ = "routing_cross_route_tiers"
    __table_args__ = (UniqueConstraint("cross_route_uid", "tier", name="uq_routing_cross_tier"),
                      CheckConstraint("tier BETWEEN 1 AND 3", name="ck_routing_cross_tier"),
                      CheckConstraint("pathway_type IN ('LADDER_RACK','BASKET_TRAY')", name="ck_routing_cross_type"))
    cross_route_uid: Mapped[str] = mapped_column(ForeignKey("routing_cross_routes.uid", ondelete="CASCADE"), index=True)
    tier: Mapped[int] = mapped_column(Integer)
    pathway_type: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingPassageTier(LayoutChild, Base):
    __tablename__ = "routing_passage_tiers"
    __table_args__ = (UniqueConstraint("passage_band_uid", "tier", name="uq_routing_passage_tier"),
                      CheckConstraint("tier BETWEEN 1 AND 3", name="ck_routing_passage_tier"),
                      CheckConstraint("pathway_type IN ('LADDER_RACK','BASKET_TRAY')", name="ck_routing_passage_type"))
    passage_band_uid: Mapped[str] = mapped_column(ForeignKey("routing_bands.uid", ondelete="CASCADE"), index=True)
    tier: Mapped[int] = mapped_column(Integer)
    pathway_type: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingVerticalTransition(LayoutChild, Base):
    __tablename__ = "routing_vertical_transitions"
    __table_args__ = (CheckConstraint("lower_tier >= 1 AND upper_tier <= 3 AND upper_tier = lower_tier + 1", name="ck_routing_vertical_adjacent"),
                      CheckConstraint("station_in >= 0", name="ck_routing_vertical_station"))
    passage_band_uid: Mapped[str] = mapped_column(ForeignKey("routing_bands.uid", ondelete="CASCADE"), index=True)
    station_in: Mapped[int] = mapped_column(Integer)
    lower_tier: Mapped[int] = mapped_column(Integer)
    upper_tier: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
