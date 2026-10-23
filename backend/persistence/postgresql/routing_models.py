"""Persist routing facts only; graph nodes and edges are derived at read time."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

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
        CheckConstraint("longitudinal_direction IS NULL OR longitudinal_direction IN ('EAST','WEST')", name="ck_routing_longitudinal_direction"),
        CheckConstraint("(bottom_basket_elevation_in IS NULL OR bottom_basket_elevation_in >= 0) AND (north_south_top_elevation_in IS NULL OR north_south_top_elevation_in >= 0)", name="ck_routing_measured_elevations"),
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
    bottom_basket_elevation_in: Mapped[int | None] = mapped_column(Integer)
    north_south_top_elevation_in: Mapped[int | None] = mapped_column(Integer)
    longitudinal_direction: Mapped[str | None] = mapped_column(Text)


class RoutingManualCableRoute(LayoutChild, Base):
    """An explicit group route expressed as domain pathway intervals, never generated edges."""
    __tablename__ = 'routing_manual_cable_routes'
    __table_args__ = (
        UniqueConstraint('routing_layout_uid', 'source_cabinet_uid', 'destination_cabinet_uid', 'cable_type', name='uq_routing_manual_group'),
        CheckConstraint('source_cabinet_uid != destination_cabinet_uid AND revision > 0 AND start_tier BETWEEN 1 AND 3 AND end_tier BETWEEN 1 AND 3', name='ck_routing_manual_group'),
    )
    # Like cabinet attachments, retain identities across project-scoped cutsheet replacement.
    source_cabinet_uid: Mapped[str] = mapped_column(Text, index=True)
    destination_cabinet_uid: Mapped[str] = mapped_column(Text, index=True)
    start_tier: Mapped[int] = mapped_column(Integer, default=1)
    end_tier: Mapped[int] = mapped_column(Integer, default=1)
    cable_type: Mapped[str] = mapped_column(Text)
    legs: Mapped[list] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default='')


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
                      CheckConstraint("pathway_type IN ('LADDER_RACK','BASKET_TRAY')", name="ck_routing_cross_type"),
                      CheckConstraint("elevation_in IS NULL OR elevation_in >= 0", name="ck_routing_cross_elevation"),
                      CheckConstraint("elevation_reference IS NULL OR elevation_reference IN ('BOTTOM_BASKET','NORTH_SOUTH_TOP')", name="ck_routing_cross_route_tiers_elevation_reference"))
    cross_route_uid: Mapped[str] = mapped_column(ForeignKey("routing_cross_routes.uid", ondelete="CASCADE"), index=True)
    tier: Mapped[int] = mapped_column(Integer)
    pathway_type: Mapped[str] = mapped_column(Text)
    elevation_in: Mapped[int | None] = mapped_column(Integer)
    elevation_reference: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingPassageTier(LayoutChild, Base):
    __tablename__ = "routing_passage_tiers"
    __table_args__ = (UniqueConstraint("passage_band_uid", "tier", name="uq_routing_passage_tier"),
                      CheckConstraint("tier BETWEEN 1 AND 3", name="ck_routing_passage_tier"),
                      CheckConstraint("pathway_type IN ('LADDER_RACK','BASKET_TRAY')", name="ck_routing_passage_type"),
                      CheckConstraint("elevation_in IS NULL OR elevation_in >= 0", name="ck_routing_passage_elevation"),
                      CheckConstraint("elevation_reference IS NULL OR elevation_reference IN ('BOTTOM_BASKET','NORTH_SOUTH_TOP')", name="ck_routing_passage_tiers_elevation_reference"))
    passage_band_uid: Mapped[str] = mapped_column(ForeignKey("routing_bands.uid", ondelete="CASCADE"), index=True)
    tier: Mapped[int] = mapped_column(Integer)
    pathway_type: Mapped[str] = mapped_column(Text)
    elevation_in: Mapped[int | None] = mapped_column(Integer)
    elevation_reference: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingVerticalTransition(LayoutChild, Base):
    __tablename__ = "routing_vertical_transitions"
    __table_args__ = (CheckConstraint("lower_tier >= 1 AND upper_tier <= 3 AND upper_tier = lower_tier + 1", name="ck_routing_vertical_adjacent"),
                      CheckConstraint("station_in >= 0", name="ck_routing_vertical_station"))
    passage_band_uid: Mapped[str] = mapped_column(ForeignKey("routing_bands.uid", ondelete="CASCADE"), index=True)
    # A row-end opening joins an upper cross-route landing to a lower passage tier.
    # Its station follows the row; it does not create another longitudinal tier.
    cross_route_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_cross_routes.uid", ondelete="CASCADE"), index=True)
    station_in: Mapped[int] = mapped_column(Integer)
    lower_tier: Mapped[int] = mapped_column(Integer)
    upper_tier: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingSegmentAnnotation(LayoutChild, Base):
    """Manual design markings on domain pathway spans, never generated edge IDs."""
    __tablename__ = "routing_segment_annotations"
    __table_args__ = (
        CheckConstraint("tier IS NULL OR tier BETWEEN 1 AND 3", name="ck_routing_annotation_tier"),
        CheckConstraint("grid_columns BETWEEN 1 AND 64 AND grid_rows BETWEEN 1 AND 64", name="ck_routing_section_grid"),
        CheckConstraint("section_height_in IS NULL OR section_height_in > 0", name="ck_routing_section_height"),
        CheckConstraint("section_inner_direction IS NULL OR section_inner_direction IN ('NORTH','SOUTH','EAST','WEST')", name="ck_routing_section_direction"),
        CheckConstraint("(passage_band_uid IS NOT NULL AND cross_route_uid IS NULL AND start_station_in IS NOT NULL AND end_station_in IS NOT NULL AND end_station_in > start_station_in AND start_station_in >= 0 AND from_passage_band_uid IS NULL AND to_passage_band_uid IS NULL) OR (passage_band_uid IS NULL AND cross_route_uid IS NOT NULL AND start_station_in IS NULL AND end_station_in IS NULL AND from_passage_band_uid IS NOT NULL AND to_passage_band_uid IS NOT NULL AND from_passage_band_uid <> to_passage_band_uid)", name="ck_routing_annotation_span"),
    )
    passage_band_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_bands.uid", ondelete="CASCADE"), index=True)
    cross_route_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_cross_routes.uid", ondelete="CASCADE"), index=True)
    start_station_in: Mapped[int | None] = mapped_column(Integer)
    end_station_in: Mapped[int | None] = mapped_column(Integer)
    from_passage_band_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_bands.uid", ondelete="CASCADE"))
    to_passage_band_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_bands.uid", ondelete="CASCADE"))
    tier: Mapped[int | None] = mapped_column(Integer)
    usable: Mapped[bool] = mapped_column(Boolean, default=True)
    cable_classes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    section_reference: Mapped[str | None] = mapped_column(Text)
    grid_columns: Mapped[int] = mapped_column(Integer, default=12)
    grid_rows: Mapped[int] = mapped_column(Integer, default=8)
    section_height_in: Mapped[int | None] = mapped_column(Integer)
    section_inner_direction: Mapped[str | None] = mapped_column(Text)


class RoutingBundlePlacement(LayoutChild, Base):
    """Optional multi-cell grid footprint and/or physical sectional rectangle."""
    __tablename__ = "routing_bundle_placements"
    __table_args__ = (
        UniqueConstraint("segment_annotation_uid", "tier", "layer", "position", name="uq_routing_bundle_position"),
        CheckConstraint("tier BETWEEN 1 AND 3", name="ck_routing_bundle_position"),
        CheckConstraint("(layer IS NULL AND position IS NULL AND slot_width IS NULL AND slot_height IS NULL) OR (layer IS NOT NULL AND position IS NOT NULL AND slot_width IS NOT NULL AND slot_height IS NOT NULL AND layer BETWEEN 1 AND 64 AND position BETWEEN 1 AND 64 AND slot_width BETWEEN 1 AND 64 AND slot_height BETWEEN 1 AND 64)", name="ck_routing_bundle_slots"),
        CheckConstraint("(offset_across_in IS NULL AND offset_up_in IS NULL AND occupied_width_in IS NULL AND occupied_height_in IS NULL) OR (offset_across_in IS NOT NULL AND offset_up_in IS NOT NULL AND occupied_width_in IS NOT NULL AND occupied_height_in IS NOT NULL AND offset_across_in >= 0 AND offset_up_in >= 0 AND occupied_width_in > 0 AND occupied_height_in > 0)", name="ck_routing_bundle_rectangle"),
        CheckConstraint("layer IS NOT NULL OR offset_across_in IS NOT NULL", name="ck_routing_bundle_occupation"),
        CheckConstraint("(source_kind = 'MANUAL' AND source_uid IS NULL AND label IS NOT NULL AND length(label) > 0) OR (source_kind IN ('BUNDLE','GROUP') AND source_uid IS NOT NULL)", name="ck_routing_bundle_source"),
    )
    segment_annotation_uid: Mapped[str] = mapped_column(ForeignKey("routing_segment_annotations.uid", ondelete="CASCADE"), index=True)
    tier: Mapped[int] = mapped_column(Integer)
    layer: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int | None] = mapped_column(Integer)
    slot_width: Mapped[int | None] = mapped_column(Integer().evaluates_none(), default=1)
    slot_height: Mapped[int | None] = mapped_column(Integer().evaluates_none(), default=1)
    offset_across_in: Mapped[int | None] = mapped_column(Integer)
    offset_up_in: Mapped[int | None] = mapped_column(Integer)
    occupied_width_in: Mapped[int | None] = mapped_column(Integer)
    occupied_height_in: Mapped[int | None] = mapped_column(Integer)
    source_kind: Mapped[str] = mapped_column(Text, default="MANUAL")
    source_uid: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    cable_class: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingBundleConnection(LayoutChild, Base):
    """Bundle movement between domain span endpoints; never generated graph IDs."""
    __tablename__ = "routing_bundle_connections"
    __table_args__ = (
        CheckConstraint("from_end IN ('START','END') AND to_end IN ('START','END') AND from_placement_uid <> to_placement_uid", name="ck_routing_connection_ends"),
        CheckConstraint("(from_turn_start_in IS NULL AND to_turn_start_in IS NULL) OR (from_turn_start_in >= 0 AND to_turn_start_in >= 0 AND from_turn_start_in IS NOT NULL AND to_turn_start_in IS NOT NULL)", name="ck_routing_connection_turn_starts"),
    )
    from_placement_uid: Mapped[str] = mapped_column(ForeignKey("routing_bundle_placements.uid", ondelete="CASCADE"), index=True)
    from_end: Mapped[str] = mapped_column(Text)
    to_placement_uid: Mapped[str] = mapped_column(ForeignKey("routing_bundle_placements.uid", ondelete="CASCADE"), index=True)
    to_end: Mapped[str] = mapped_column(Text)
    vertical_transition_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_vertical_transitions.uid"), index=True)
    junction_area_uid: Mapped[str | None] = mapped_column(ForeignKey("routing_junction_areas.uid", ondelete="SET NULL"), index=True)
    from_turn_start_in: Mapped[int | None] = mapped_column(Integer)
    to_turn_start_in: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingBundleContents(LayoutChild, Base):
    """Bundle-local ordinal packing of rack-pair or explicit cable-list units."""
    __tablename__ = 'routing_bundle_contents'
    __table_args__ = (
        UniqueConstraint('bundle_placement_uid', 'section_end', name='uq_routing_bundle_contents_end'),
        CheckConstraint("section_end IN ('SPAN','START','END')", name='ck_routing_bundle_contents_end'),
        CheckConstraint('grid_columns BETWEEN 1 AND 64 AND grid_rows BETWEEN 1 AND 64', name='ck_routing_bundle_contents_grid'),
    )
    bundle_placement_uid: Mapped[str] = mapped_column(ForeignKey('routing_bundle_placements.uid', ondelete='CASCADE'), index=True)
    section_end: Mapped[str] = mapped_column(Text)
    grid_columns: Mapped[int] = mapped_column(Integer, default=12)
    grid_rows: Mapped[int] = mapped_column(Integer, default=8)
    units: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text)


class RoutingJunctionArea(LayoutChild, Base):
    """Physical working area anchored to domain topology, never a generated node FK."""
    __tablename__ = 'routing_junction_areas'
    __table_args__ = (
        CheckConstraint('tier BETWEEN 1 AND 3', name='ck_routing_junction_tier'),
        UniqueConstraint('passage_band_uid', 'cross_route_uid', 'tier', name='uq_routing_junction_cross_anchor'),
        UniqueConstraint('passage_band_uid', 'station_in', 'tier', name='uq_routing_junction_station_anchor'),
        CheckConstraint('(cross_route_uid IS NOT NULL AND station_in IS NULL) OR (cross_route_uid IS NULL AND station_in IS NOT NULL AND station_in >= 0)', name='ck_routing_junction_anchor'),
        CheckConstraint('west_extension_in >= 0 AND east_extension_in >= 0 AND north_extension_in >= 0 AND south_extension_in >= 0 AND (usable_height_in IS NULL OR usable_height_in > 0)', name='ck_routing_junction_dimensions'),
        CheckConstraint("provenance IN ('SCHEMATIC','MANUAL','FIELD_MEASURED')", name='ck_routing_junction_provenance'),
    )
    passage_band_uid: Mapped[str] = mapped_column(ForeignKey('routing_bands.uid', ondelete='CASCADE'), index=True)
    cross_route_uid: Mapped[str | None] = mapped_column(ForeignKey('routing_cross_routes.uid', ondelete='CASCADE'), index=True)
    station_in: Mapped[int | None] = mapped_column(Integer)
    tier: Mapped[int] = mapped_column(Integer)
    west_extension_in: Mapped[int] = mapped_column(Integer, default=0)
    east_extension_in: Mapped[int] = mapped_column(Integer, default=0)
    north_extension_in: Mapped[int] = mapped_column(Integer, default=0)
    south_extension_in: Mapped[int] = mapped_column(Integer, default=0)
    usable_height_in: Mapped[int | None] = mapped_column(Integer)
    provenance: Mapped[str] = mapped_column(Text, default='SCHEMATIC')
    label: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingJunctionCrossing(LayoutChild, Base):
    __tablename__ = 'routing_junction_crossings'
    __table_args__ = (
        UniqueConstraint('above_connection_uid', 'below_connection_uid', name='uq_routing_junction_crossing'),
        CheckConstraint('above_connection_uid <> below_connection_uid AND (clearance_in IS NULL OR clearance_in >= 0)', name='ck_routing_junction_crossing'),
    )
    above_connection_uid: Mapped[str] = mapped_column(ForeignKey('routing_bundle_connections.uid', ondelete='CASCADE'), index=True)
    below_connection_uid: Mapped[str] = mapped_column(ForeignKey('routing_bundle_connections.uid', ondelete='CASCADE'), index=True)
    clearance_in: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingCabinetAttachment(LayoutChild, Base):
    """Cabinet takeoff along a domain span, without inserting a graph node."""
    __tablename__ = "routing_cabinet_attachments"
    __table_args__ = (CheckConstraint("offset_in >= 0 AND (tier IS NULL OR tier BETWEEN 1 AND 3)", name="ck_routing_attachment_position"),)
    segment_annotation_uid: Mapped[str] = mapped_column(ForeignKey("routing_segment_annotations.uid", ondelete="CASCADE"), index=True)
    # Like group/bundle source references: a reimport may retire the Cabinet UID.
    cabinet_uid: Mapped[str] = mapped_column(Text, index=True)
    offset_in: Mapped[int] = mapped_column(Integer)
    tier: Mapped[int | None] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
