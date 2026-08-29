from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def jsonb_dict() -> Any:
    return mapped_column(JSONB, nullable=False, server_default="{}")


def jsonb_list() -> Any:
    return mapped_column(JSONB, nullable=False, server_default="[]")


class TimestampColumns:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(TimestampColumns, Base):
    __tablename__ = "projects"

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()


class Building(TimestampColumns, Base):
    __tablename__ = "buildings"
    __table_args__ = (
        UniqueConstraint("project_uid", "building_id", name="uq_buildings_project_building_id"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_id: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()


class Room(TimestampColumns, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("building_uid", "room_id", name="uq_rooms_building_room_id"),
        Index("ix_rooms_scope", "project_uid", "building_uid", "room_id"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_id: Mapped[str] = mapped_column(Text, nullable=False)
    room_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="data_hall")
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    construction_phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="Management & Ethernet")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()


class Cabinet(TimestampColumns, Base):
    __tablename__ = "cabinets"
    __table_args__ = (
        UniqueConstraint("room_uid", "cabinet_id", name="uq_cabinets_room_cabinet_id"),
        Index("ix_cabinets_room_layout", "room_uid", "source_row", "source_col"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_uid: Mapped[str] = mapped_column(ForeignKey("rooms.uid"), nullable=False)
    cabinet_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cabinet_group: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="not_installed")
    construction_phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="Management & Ethernet")
    max_rack_unit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="48")
    source_row: Mapped[int | None] = mapped_column(Integer)
    source_col: Mapped[int | None] = mapped_column(Integer)
    layout: Mapped[dict[str, Any]] = jsonb_dict()
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class DeviceModel(TimestampColumns, Base):
    __tablename__ = "device_models"

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    manufacturer: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    rack_units: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    front_panel_svg: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    back_panel_svg: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    port_layout: Mapped[list[dict[str, Any]]] = jsonb_list()
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class DeviceVariant(TimestampColumns, Base):
    __tablename__ = "device_variants"
    __table_args__ = (
        Index("ix_device_variants_project_model", "project_uid", "device_model_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str | None] = mapped_column(ForeignKey("projects.uid"))
    device_model_uid: Mapped[str | None] = mapped_column(ForeignKey("device_models.uid"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    variant: Mapped[dict[str, Any]] = jsonb_dict()


class Device(TimestampColumns, Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("cabinet_uid", "rack_unit", name="uq_devices_cabinet_rack_unit"),
        Index("ix_devices_room", "room_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_uid: Mapped[str] = mapped_column(ForeignKey("rooms.uid"), nullable=False)
    cabinet_uid: Mapped[str] = mapped_column(ForeignKey("cabinets.uid"), nullable=False)
    rack_unit: Mapped[int] = mapped_column(Integer, nullable=False)
    device_model_uid: Mapped[str | None] = mapped_column(ForeignKey("device_models.uid"))
    device_variant_uid: Mapped[str | None] = mapped_column(ForeignKey("device_variants.uid"))
    device_model_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    rack_units: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="not_installed")
    construction_phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="Management & Ethernet")
    aliases: Mapped[list[str]] = jsonb_list()
    model_aliases: Mapped[list[str]] = jsonb_list()
    port_layout_overrides: Mapped[list[dict[str, Any]]] = jsonb_list()
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class Port(TimestampColumns, Base):
    __tablename__ = "ports"
    __table_args__ = (
        Index("ix_ports_device_port_name", "device_uid", "port_name"),
        Index("ix_ports_cabinet", "cabinet_uid"),
        Index("ix_ports_room", "room_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_uid: Mapped[str] = mapped_column(ForeignKey("rooms.uid"), nullable=False)
    cabinet_uid: Mapped[str] = mapped_column(ForeignKey("cabinets.uid"), nullable=False)
    device_uid: Mapped[str | None] = mapped_column(ForeignKey("devices.uid"))
    port_name: Mapped[str] = mapped_column(Text, nullable=False)
    connector_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="other")
    side: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    position: Mapped[dict[str, Any]] = jsonb_dict()
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class Cable(TimestampColumns, Base):
    __tablename__ = "cables"
    __table_args__ = (
        Index("ix_cables_a_port", "a_port_uid"),
        Index("ix_cables_z_port", "z_port_uid"),
        Index("ix_cables_project_type", "project_uid", "cable_type"),
        Index(
            "ix_cables_project_type_a_z_ports",
            "project_uid",
            "cable_type",
            "a_port_uid",
            "z_port_uid",
            postgresql_ops={"a_port_uid": "text_pattern_ops", "z_port_uid": "text_pattern_ops"},
        ),
        Index("ix_cables_project_phase", "project_uid", "construction_phase"),
        Index("ix_cables_building_import_status", "building_uid", "import_status"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_uid: Mapped[str | None] = mapped_column(ForeignKey("rooms.uid"))
    a_port_uid: Mapped[str] = mapped_column(ForeignKey("ports.uid"), nullable=False)
    z_port_uid: Mapped[str] = mapped_column(ForeignKey("ports.uid"), nullable=False)
    cable_type: Mapped[str] = mapped_column(Text, nullable=False)
    cable_group: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    import_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    construction_phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="Management & Ethernet")
    a_label_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    z_label_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    progress: Mapped[dict[str, Any]] = jsonb_dict()
    current_phase: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    designed_length_meters: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    length_used_meters: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, server_default="0")
    a_optic: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    z_optic: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class LadderRackJunction(TimestampColumns, Base):
    __tablename__ = "ladder_rack_junctions"
    __table_args__ = (
        Index("ix_ladder_rack_junctions_room", "room_uid"),
        Index("ix_ladder_rack_junctions_scope", "project_uid", "building_uid", "junction_id"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_uid: Mapped[str | None] = mapped_column(ForeignKey("rooms.uid"))
    junction_id: Mapped[str] = mapped_column(Text, nullable=False)
    junction_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    point: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    width: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    height: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    height_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    construction_phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="Management & Ethernet")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class LadderRackSegment(TimestampColumns, Base):
    __tablename__ = "ladder_rack_segments"
    __table_args__ = (
        CheckConstraint("junction_a_uid <> junction_z_uid", name="ck_ladder_rack_segments_distinct_junctions"),
        CheckConstraint("design_length_meters is null or design_length_meters >= 0", name="ck_ladder_rack_segments_design_length_non_negative"),
        CheckConstraint("actual_length_meters is null or actual_length_meters >= 0", name="ck_ladder_rack_segments_actual_length_non_negative"),
        Index("ix_ladder_rack_segments_room", "room_uid"),
        Index("ix_ladder_rack_segments_junction_a", "junction_a_uid"),
        Index("ix_ladder_rack_segments_junction_z", "junction_z_uid"),
        Index("ix_ladder_rack_segments_scope", "project_uid", "building_uid", "segment_id"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_uid: Mapped[str | None] = mapped_column(ForeignKey("rooms.uid"))
    segment_id: Mapped[str] = mapped_column(Text, nullable=False)
    polyline: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    design_length_meters: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    actual_length_meters: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    width: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    height: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    height_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    junction_a_uid: Mapped[str] = mapped_column(ForeignKey("ladder_rack_junctions.uid"), nullable=False)
    junction_z_uid: Mapped[str] = mapped_column(ForeignKey("ladder_rack_junctions.uid"), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    construction_phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="Management & Ethernet")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class CableBundle(TimestampColumns, Base):
    __tablename__ = "cable_bundles"
    __table_args__ = (
        UniqueConstraint("scoped_uid", name="uq_cable_bundles_scoped_uid"),
        Index("ix_cable_bundles_room", "room_uid"),
        Index("ix_cable_bundles_primary_segment", "primary_ladder_rack_segment_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    scoped_uid: Mapped[str] = mapped_column(Text, nullable=False)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    building_uid: Mapped[str] = mapped_column(ForeignKey("buildings.uid"), nullable=False)
    room_uid: Mapped[str | None] = mapped_column(ForeignKey("rooms.uid"))
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    primary_ladder_rack_segment_uid: Mapped[str | None] = mapped_column(ForeignKey("ladder_rack_segments.uid"))
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    construction_phase: Mapped[str] = mapped_column(Text, nullable=False, server_default="Management & Ethernet")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class CableBundleCable(Base):
    __tablename__ = "cable_bundle_cables"
    __table_args__ = (
        Index("ix_cable_bundle_cables_cable", "cable_uid"),
    )

    cable_bundle_uid: Mapped[str] = mapped_column(ForeignKey("cable_bundles.uid", ondelete="CASCADE"), primary_key=True)
    cable_uid: Mapped[str] = mapped_column(ForeignKey("cables.uid", ondelete="CASCADE"), primary_key=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CableBundleLadderRackSegment(Base):
    __tablename__ = "cable_bundle_ladder_rack_segments"
    __table_args__ = (
        Index("ix_cable_bundle_ladder_rack_segments_segment", "ladder_rack_segment_uid"),
    )

    cable_bundle_uid: Mapped[str] = mapped_column(ForeignKey("cable_bundles.uid", ondelete="CASCADE"), primary_key=True)
    ladder_rack_segment_uid: Mapped[str] = mapped_column(ForeignKey("ladder_rack_segments.uid", ondelete="CASCADE"), primary_key=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(TimestampColumns, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('manager', 'editor', 'viewer')", name="ck_users_role"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()


Index(
    "ix_users_email_lower",
    func.lower(User.email),
    unique=True,
    postgresql_where=User.deleted_at.is_(None),
)


class Personnel(TimestampColumns, Base):
    __tablename__ = "personnel"
    __table_args__ = (
        UniqueConstraint("project_uid", "employee_uid", name="uq_personnel_project_employee_uid"),
        Index("ix_personnel_project_active", "project_uid", "active"),
        Index("ix_personnel_user", "user_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    employee_uid: Mapped[str] = mapped_column(Text, nullable=False)
    user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    trade: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    company: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()


class Crew(TimestampColumns, Base):
    __tablename__ = "crews"
    __table_args__ = (
        UniqueConstraint("project_uid", "name", name="uq_crews_project_name"),
        Index("ix_crews_project_active", "project_uid", "active"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    crew_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()


class CrewMember(Base):
    __tablename__ = "crew_members"
    __table_args__ = (
        CheckConstraint("role_in_crew in ('lead', 'member', 'foreman')", name="ck_crew_members_role"),
        Index("ix_crew_members_personnel", "personnel_uid", "active"),
    )

    crew_uid: Mapped[str] = mapped_column(ForeignKey("crews.uid", ondelete="CASCADE"), primary_key=True)
    personnel_uid: Mapped[str] = mapped_column(ForeignKey("personnel.uid", ondelete="CASCADE"), primary_key=True)
    role_in_crew: Mapped[str] = mapped_column(Text, nullable=False, server_default="member")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PendingChange(Base):
    __tablename__ = "pending_changes"
    __table_args__ = (
        Index("ix_pending_changes_status_created", "status", "created_at"),
        Index("ix_pending_changes_target", "target_entity_type", "target_entity_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    requested_by_user_uid: Mapped[str] = mapped_column(ForeignKey("users.uid"), nullable=False)
    reviewed_by_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    target_entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_entity_uid: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    payload: Mapped[dict[str, Any]] = jsonb_dict()
    review_note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FilterPreset(TimestampColumns, Base):
    __tablename__ = "filter_presets"
    __table_args__ = (
        CheckConstraint("entity_type in ('cabinet', 'device', 'cable', 'port', 'bundle')", name="ck_filter_presets_entity_type"),
        CheckConstraint("visibility in ('private', 'project')", name="ck_filter_presets_visibility"),
        Index("ix_filter_presets_project_entity", "project_uid", "entity_type", "visibility"),
        Index("ix_filter_presets_owner_entity", "owner_user_uid", "entity_type"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    owner_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default="private")
    filter_payload: Mapped[dict[str, Any]] = jsonb_dict()
    sort_payload: Mapped[dict[str, Any]] = jsonb_dict()
    column_payload: Mapped[dict[str, Any]] = jsonb_dict()
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class LabelExtractionConfig(TimestampColumns, Base):
    __tablename__ = "label_extraction_configs"
    __table_args__ = (
        UniqueConstraint("project_uid", "name", name="uq_label_extraction_configs_project_name"),
        Index("ix_label_extraction_configs_project", "project_uid", "created_at"),
        Index("ix_label_extraction_configs_owner", "owner_user_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    owner_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source_payload: Mapped[dict[str, Any]] = jsonb_dict()
    pair_scope_payload: Mapped[dict[str, Any]] = jsonb_dict()
    cable_filter_payload: Mapped[dict[str, Any]] = jsonb_dict()
    label_fields_payload: Mapped[dict[str, Any]] = jsonb_dict()
    output_layout_payload: Mapped[dict[str, Any]] = jsonb_dict()
    validation_payload: Mapped[dict[str, Any]] = jsonb_dict()


class EntityGroup(TimestampColumns, Base):
    __tablename__ = "entity_groups"
    __table_args__ = (
        CheckConstraint("entity_type in ('cable', 'cabinet', 'device', 'port', 'bundle')", name="ck_entity_groups_entity_type"),
        UniqueConstraint("project_uid", "entity_type", "name", name="uq_entity_groups_project_entity_name"),
        Index("ix_entity_groups_project_entity", "project_uid", "entity_type", "created_at"),
        Index("ix_entity_groups_owner", "owner_user_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    entity_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="cable")
    owner_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()


class EntityGroupMember(Base):
    __tablename__ = "entity_group_members"
    __table_args__ = (
        CheckConstraint("entity_type in ('cable', 'cabinet', 'device', 'port', 'bundle')", name="ck_entity_group_members_entity_type"),
        Index("ix_entity_group_members_entity", "entity_type", "entity_uid"),
    )

    group_uid: Mapped[str] = mapped_column(ForeignKey("entity_groups.uid", ondelete="CASCADE"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_uid: Mapped[str] = mapped_column(Text, primary_key=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

Index(
    "uq_filter_presets_private_owner_name",
    FilterPreset.project_uid,
    FilterPreset.owner_user_uid,
    FilterPreset.entity_type,
    FilterPreset.name,
    unique=True,
    postgresql_where=FilterPreset.owner_user_uid.is_not(None),
)
Index(
    "uq_filter_presets_project_name",
    FilterPreset.project_uid,
    FilterPreset.entity_type,
    FilterPreset.name,
    unique=True,
    postgresql_where=FilterPreset.owner_user_uid.is_(None),
)


class Task(TimestampColumns, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "task_type in ('cable_pull', 'cable_dress', 'cable_termination', 'cable_test', 'cable_label', 'cable_rework', 'cable_retirement', 'cable_removal', 'inspection')",
            name="ck_tasks_task_type",
        ),
        CheckConstraint(
            "status in ('draft', 'assigned', 'in_progress', 'submitted', 'approved', 'denied', 'cancelled', 'abandoned', 'superseded')",
            name="ck_tasks_status",
        ),
        CheckConstraint("priority in ('low', 'normal', 'high', 'urgent')", name="ck_tasks_priority"),
        CheckConstraint("entity_type in ('cable', 'cabinet', 'device', 'port', 'bundle')", name="ck_tasks_entity_type"),
        Index("ix_tasks_project_status", "project_uid", "status", "created_at"),
        Index("ix_tasks_assigned_crew", "assigned_crew_uid", "status"),
        Index("ix_tasks_assigned_personnel", "assigned_personnel_uid", "status"),
        Index("ix_tasks_review_queue", "project_uid", "status", "submitted_at"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default="normal")
    created_by_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    assigned_crew_uid: Mapped[str | None] = mapped_column(ForeignKey("crews.uid"))
    assigned_personnel_uid: Mapped[str | None] = mapped_column(ForeignKey("personnel.uid"))
    submitted_by_personnel_uid: Mapped[str | None] = mapped_column(ForeignKey("personnel.uid"))
    reviewed_by_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    applied_by_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    entity_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="cable")
    entity_filter_payload: Mapped[dict[str, Any]] = jsonb_dict()
    target_payload: Mapped[dict[str, Any]] = jsonb_dict()
    submission_payload: Mapped[dict[str, Any]] = jsonb_dict()
    review_note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskEntity(Base):
    __tablename__ = "task_entities"
    __table_args__ = (
        Index("ix_task_entities_entity", "entity_type", "entity_uid"),
    )

    task_uid: Mapped[str] = mapped_column(ForeignKey("tasks.uid", ondelete="CASCADE"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_uid: Mapped[str] = mapped_column(Text, primary_key=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        CheckConstraint(
            "event_type in ('created', 'assigned', 'started', 'submitted', 'approved', 'denied', 'cancelled', 'abandoned', 'superseded', 'applied')",
            name="ck_task_events_type",
        ),
        Index("ix_task_events_task_created", "task_uid", "created_at"),
        Index("ix_task_events_actor", "actor_user_uid", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_uid: Mapped[str] = mapped_column(ForeignKey("tasks.uid", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    actor_personnel_uid: Mapped[str | None] = mapped_column(ForeignKey("personnel.uid"))
    payload: Mapped[dict[str, Any]] = jsonb_dict()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChangeOrder(TimestampColumns, Base):
    __tablename__ = "change_orders"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft', 'resolved', 'review_ready', 'approved', 'executing', 'partially_complete', 'complete', 'rejected', 'cancelled', 'blocked', 'superseded')",
            name="ck_change_orders_status",
        ),
        UniqueConstraint("project_uid", "change_order_number", name="uq_change_orders_project_number"),
        Index("ix_change_orders_project_status", "project_uid", "status", "created_at"),
        Index("ix_change_orders_source", "source_type", "source_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    change_order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    source_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source_uid: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    requested_by_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    reviewed_by_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict[str, Any]] = jsonb_dict()
    items_payload: Mapped[list[dict[str, Any]]] = jsonb_list()


class ChangeOrderItem(TimestampColumns, Base):
    __tablename__ = "change_order_items"
    __table_args__ = (
        CheckConstraint("entity_type in ('cable')", name="ck_change_order_items_entity_type"),
        Index("ix_change_order_items_order", "change_order_uid", "sequence"),
        Index("ix_change_order_items_entity", "entity_type", "entity_uid"),
        Index("ix_change_order_items_status", "change_order_uid", "status"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    change_order_uid: Mapped[str] = mapped_column(ForeignKey("change_orders.uid", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    entity_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="cable")
    entity_uid: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    old_entity_uid: Mapped[str | None] = mapped_column(Text)
    new_entity_uid: Mapped[str | None] = mapped_column(Text)
    before_definition: Mapped[dict[str, Any]] = jsonb_dict()
    after_definition: Mapped[dict[str, Any]] = jsonb_dict()
    task_plan: Mapped[list[dict[str, Any]]] = jsonb_list()
    result_payload: Mapped[dict[str, Any]] = jsonb_dict()


class ChangeOrderTaskLink(Base):
    __tablename__ = "change_order_task_links"
    __table_args__ = (
        Index("ix_change_order_task_links_task", "task_uid"),
        Index("ix_change_order_task_links_order", "change_order_uid"),
    )

    change_order_uid: Mapped[str] = mapped_column(ForeignKey("change_orders.uid", ondelete="CASCADE"), primary_key=True)
    change_order_item_uid: Mapped[str] = mapped_column(ForeignKey("change_order_items.uid", ondelete="CASCADE"), primary_key=True)
    task_uid: Mapped[str] = mapped_column(ForeignKey("tasks.uid", ondelete="CASCADE"), primary_key=True)
    effect_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChangeOrderEvent(Base):
    __tablename__ = "change_order_events"
    __table_args__ = (
        Index("ix_change_order_events_order", "change_order_uid", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    change_order_uid: Mapped[str] = mapped_column(ForeignKey("change_orders.uid", ondelete="CASCADE"), nullable=False)
    change_order_item_uid: Mapped[str | None] = mapped_column(ForeignKey("change_order_items.uid", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    payload: Mapped[dict[str, Any]] = jsonb_dict()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class OperationLog(Base):
    __tablename__ = "operation_log"
    __table_args__ = (
        Index("ix_operation_log_project_id", "project_uid", "id"),
        Index("ix_operation_log_entity_id", "entity_type", "entity_uid", "id"),
        Index("ix_operation_log_user_id", "user_uid", "id"),
        Index("ix_operation_log_group", "operation_group_uid", "id"),
        Index("ix_operation_log_source", "source_type", "source_uid", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_uid: Mapped[str | None] = mapped_column(ForeignKey("projects.uid"))
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_uid: Mapped[str] = mapped_column(Text, nullable=False)
    operation_type: Mapped[str] = mapped_column(Text, nullable=False)
    operation_group_uid: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(Text)
    source_uid: Mapped[str | None] = mapped_column(Text)
    source_operator: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict[str, Any]] = jsonb_dict()
    after: Mapped[dict[str, Any]] = jsonb_dict()
    user_uid: Mapped[str | None] = mapped_column(ForeignKey("users.uid"))
    user_role: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceImport(Base):
    __tablename__ = "source_imports"

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str | None] = mapped_column(ForeignKey("projects.uid"))
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    version_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    version_date: Mapped[date | None] = mapped_column(Date)
    source_operator: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    summary: Mapped[dict[str, Any]] = jsonb_dict()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TopologyVersion(Base):
    __tablename__ = "topology_versions"
    __table_args__ = (
        UniqueConstraint("project_uid", "version_name", name="uq_topology_versions_project_name"),
        Index("ix_topology_versions_project_date", "project_uid", "version_date"),
        Index("ix_topology_versions_source_import", "source_import_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    version_name: Mapped[str] = mapped_column(Text, nullable=False)
    version_date: Mapped[date | None] = mapped_column(Date)
    source_operator: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source_import_uid: Mapped[str | None] = mapped_column(ForeignKey("source_imports.uid"))
    operation_group_uid: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict[str, Any]] = jsonb_dict()
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EntityHistory(Base):
    __tablename__ = "entity_history"
    __table_args__ = (
        UniqueConstraint("project_uid", "entity_type", "entity_uid", name="uq_entity_history_entity"),
        Index("ix_entity_history_first_version", "first_version_uid"),
        Index("ix_entity_history_last_version", "last_version_uid"),
        Index("ix_entity_history_entity", "entity_type", "entity_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str] = mapped_column(ForeignKey("projects.uid"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_uid: Mapped[str] = mapped_column(Text, nullable=False)
    first_version_uid: Mapped[str | None] = mapped_column(ForeignKey("topology_versions.uid"))
    first_operation_id: Mapped[int | None] = mapped_column(ForeignKey("operation_log.id"))
    last_version_uid: Mapped[str | None] = mapped_column(ForeignKey("topology_versions.uid"))
    last_operation_id: Mapped[int | None] = mapped_column(ForeignKey("operation_log.id"))
    metadata_json: Mapped[dict[str, Any]] = jsonb_dict()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceCableRow(Base):
    __tablename__ = "source_cable_rows"
    __table_args__ = (
        Index("ix_source_cable_rows_import_row", "source_import_uid", "row_number"),
        Index("ix_source_cable_rows_cable", "cable_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    source_import_uid: Mapped[str] = mapped_column(ForeignKey("source_imports.uid", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    cable_uid: Mapped[str | None] = mapped_column(ForeignKey("cables.uid"))


class ValidationFinding(Base):
    __tablename__ = "validation_findings"
    __table_args__ = (
        Index("ix_validation_findings_project_type", "project_uid", "finding_type"),
        Index("ix_validation_findings_entity", "entity_type", "entity_uid"),
    )

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    project_uid: Mapped[str | None] = mapped_column(ForeignKey("projects.uid"))
    finding_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    entity_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    entity_uid: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    payload: Mapped[dict[str, Any]] = jsonb_dict()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
