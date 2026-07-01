from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, ProgrammingError

from backend.api.auth import AuthUser, current_user, require_manager
from backend.api.topology import (
    CabinetCableDetailResponse,
    _postgres_cable_detail,
    _postgres_cable_detail_columns,
    _postgres_source_update_statuses,
)
from backend.core.config import DEFAULT_PROJECT_UID, use_postgresql_topology_storage
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.session import session_factory


router = APIRouter(prefix="/entity-groups", tags=["entity-groups"])
SUPPORTED_ENTITY_TYPES = {"cable", "cabinet", "device", "port", "bundle"}


class EntityGroupMemberRecord(BaseModel):
    entity_type: str
    entity_uid: str
    sequence: int | None = None
    created_at: datetime | None = None


class EntityGroupRecord(BaseModel):
    uid: str
    project_uid: str
    name: str
    description: str = ""
    entity_type: str
    owner_user_uid: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    members: list[EntityGroupMemberRecord] = Field(default_factory=list)
    member_count: int = 0
    associated_cabinet_uids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EntityGroupCreateRequest(BaseModel):
    uid: str | None = None
    project_uid: str = DEFAULT_PROJECT_UID
    name: str
    description: str = ""
    entity_type: str = "cable"
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    member_uids: list[str] = Field(default_factory=list)


class EntityGroupUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    metadata_json: dict[str, Any] | None = None
    member_uids: list[str] | None = None


class EntityGroupMembersRequest(BaseModel):
    member_uids: list[str] = Field(min_length=1)


@router.get("", response_model=list[EntityGroupRecord])
def list_entity_groups(
    project_uid: str = DEFAULT_PROJECT_UID,
    entity_type: str | None = None,
    user: AuthUser = Depends(current_user),
) -> list[EntityGroupRecord]:
    _require_postgresql()
    normalized_entity_type = _optional_entity_type(entity_type)
    with session_factory()() as session:
        clauses = [db.EntityGroup.project_uid == project_uid, db.EntityGroup.deleted_at.is_(None)]
        if normalized_entity_type:
            clauses.append(db.EntityGroup.entity_type == normalized_entity_type)
        try:
            rows = session.execute(
                select(db.EntityGroup).where(*clauses).order_by(db.EntityGroup.entity_type, db.EntityGroup.name)
            ).scalars().all()
        except ProgrammingError as exc:
            if "entity_groups" not in str(exc):
                raise
            return []
        return [_record(session, row) for row in rows]


@router.post("", response_model=EntityGroupRecord)
def create_entity_group(request: EntityGroupCreateRequest, user: AuthUser = Depends(current_user)) -> EntityGroupRecord:
    _require_postgresql()
    require_manager(user)
    entity_type = _entity_type(request.entity_type)
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Group name is required.")
    with session_factory()() as session:
        with session.begin():
            _ensure_user(session, user)
            group = db.EntityGroup(
                uid=request.uid or f"eg-{uuid4().hex}",
                project_uid=request.project_uid,
                name=name,
                description=request.description.strip(),
                entity_type=entity_type,
                owner_user_uid=user.uid,
                metadata_json=request.metadata_json,
            )
            session.add(group)
            try:
                session.flush()
            except IntegrityError as exc:
                raise HTTPException(status_code=409, detail="A group with this name already exists.") from exc
            _replace_members(session, group, request.member_uids)
        return _record(session, group)


@router.get("/{group_uid}", response_model=EntityGroupRecord)
def get_entity_group(group_uid: str, user: AuthUser = Depends(current_user)) -> EntityGroupRecord:
    _require_postgresql()
    with session_factory()() as session:
        group = _group_or_404(session, group_uid)
        return _record(session, group)


@router.get("/{group_uid}/cables", response_model=CabinetCableDetailResponse)
def get_entity_group_cables(group_uid: str, user: AuthUser = Depends(current_user)) -> CabinetCableDetailResponse:
    _require_postgresql()
    with session_factory()() as session:
        group = _group_or_404(session, group_uid)
        if group.entity_type != "cable":
            raise HTTPException(status_code=422, detail="Cable detail is only available for cable groups.")
        cable_uids = [member.entity_uid for member in _members(session, group.uid)]
        if not cable_uids:
            return CabinetCableDetailResponse(
                source_cabinet_uid=group.uid,
                target_cabinet_uid=group.name,
                cables=[],
                total_cables=0,
                limit=0,
                offset=0,
                has_more=False,
            )

        rows = session.execute(
            select(*_postgres_cable_detail_columns()).where(
                db.Cable.uid.in_(cable_uids),
                db.Cable.deleted_at.is_(None),
            )
        ).all()
        row_by_uid = {row.uid: row for row in rows}
        change_statuses = _postgres_source_update_statuses(session, cable_uids)
        cables = [
            _postgres_cable_detail(row_by_uid[cable_uid], change_status=change_statuses.get(cable_uid, "green"))
            for cable_uid in cable_uids
            if cable_uid in row_by_uid
        ]
        return CabinetCableDetailResponse(
            source_cabinet_uid=group.uid,
            target_cabinet_uid=group.name,
            cables=cables,
            total_cables=len(cables),
            limit=len(cables),
            offset=0,
            has_more=False,
        )


@router.patch("/{group_uid}", response_model=EntityGroupRecord)
def update_entity_group(
    group_uid: str,
    request: EntityGroupUpdateRequest,
    user: AuthUser = Depends(current_user),
) -> EntityGroupRecord:
    _require_postgresql()
    require_manager(user)
    with session_factory()() as session:
        with session.begin():
            _ensure_user(session, user)
            group = _group_or_404(session, group_uid)
            if request.name is not None:
                name = request.name.strip()
                if not name:
                    raise HTTPException(status_code=422, detail="Group name is required.")
                group.name = name
            if request.description is not None:
                group.description = request.description.strip()
            if request.metadata_json is not None:
                group.metadata_json = request.metadata_json
            if request.member_uids is not None:
                _replace_members(session, group, request.member_uids)
            group.updated_at = datetime.now(timezone.utc)
            try:
                session.flush()
            except IntegrityError as exc:
                raise HTTPException(status_code=409, detail="A group with this name already exists.") from exc
        return _record(session, group)


@router.post("/{group_uid}/members", response_model=EntityGroupRecord)
def add_entity_group_members(
    group_uid: str,
    request: EntityGroupMembersRequest,
    user: AuthUser = Depends(current_user),
) -> EntityGroupRecord:
    _require_postgresql()
    require_manager(user)
    with session_factory()() as session:
        with session.begin():
            group = _group_or_404(session, group_uid)
            existing = [member.entity_uid for member in _members(session, group.uid)]
            _replace_members(session, group, [*existing, *request.member_uids])
            group.updated_at = datetime.now(timezone.utc)
        return _record(session, group)


@router.delete("/{group_uid}", response_model=dict[str, bool])
def delete_entity_group(group_uid: str, user: AuthUser = Depends(current_user)) -> dict[str, bool]:
    _require_postgresql()
    require_manager(user)
    with session_factory()() as session:
        with session.begin():
            group = _group_or_404(session, group_uid)
            group.deleted_at = datetime.now(timezone.utc)
            group.updated_at = group.deleted_at
        return {"ok": True}


def _record(session, group: db.EntityGroup) -> EntityGroupRecord:
    members = _members(session, group.uid)
    return EntityGroupRecord(
        uid=group.uid,
        project_uid=group.project_uid,
        name=group.name,
        description=group.description,
        entity_type=group.entity_type,
        owner_user_uid=group.owner_user_uid,
        metadata_json=group.metadata_json,
        members=[
            EntityGroupMemberRecord(
                entity_type=member.entity_type,
                entity_uid=member.entity_uid,
                sequence=member.sequence,
                created_at=member.created_at,
            )
            for member in members
        ],
        member_count=len(members),
        associated_cabinet_uids=_associated_cabinet_uids(session, members),
        created_at=group.created_at,
        updated_at=group.updated_at,
    )

def _associated_cabinet_uids(session, members: list[db.EntityGroupMember]) -> list[str]:
    cabinet_uids: set[str] = set()
    members_by_type: dict[str, list[str]] = {}
    for member in members:
        members_by_type.setdefault(member.entity_type, []).append(member.entity_uid)

    cable_uids = members_by_type.get("cable", [])
    if cable_uids:
        cable_rows = session.execute(
            select(db.Cable.a_port_uid, db.Cable.z_port_uid).where(
                db.Cable.uid.in_(cable_uids),
                db.Cable.deleted_at.is_(None),
            )
        ).all()
        for a_port_uid, z_port_uid in cable_rows:
            for cabinet_uid in (_cabinet_uid_from_port_uid(a_port_uid), _cabinet_uid_from_port_uid(z_port_uid)):
                if cabinet_uid:
                    cabinet_uids.add(cabinet_uid)

    cabinet_uids.update(members_by_type.get("cabinet", []))

    device_uids = members_by_type.get("device", [])
    if device_uids:
        cabinet_uids.update(
            session.execute(
                select(db.Device.cabinet_uid).where(
                    db.Device.uid.in_(device_uids),
                    db.Device.deleted_at.is_(None),
                )
            ).scalars()
        )

    port_uids = members_by_type.get("port", [])
    if port_uids:
        cabinet_uids.update(
            session.execute(
                select(db.Port.cabinet_uid).where(
                    db.Port.uid.in_(port_uids),
                    db.Port.deleted_at.is_(None),
                )
            ).scalars()
        )

    bundle_uids = members_by_type.get("bundle", [])
    if bundle_uids:
        bundle_cable_rows = session.execute(
            select(db.Cable.a_port_uid, db.Cable.z_port_uid)
            .join(db.CableBundleCable, db.CableBundleCable.cable_uid == db.Cable.uid)
            .where(
                db.CableBundleCable.cable_bundle_uid.in_(bundle_uids),
                db.Cable.deleted_at.is_(None),
            )
        ).all()
        for a_port_uid, z_port_uid in bundle_cable_rows:
            for cabinet_uid in (_cabinet_uid_from_port_uid(a_port_uid), _cabinet_uid_from_port_uid(z_port_uid)):
                if cabinet_uid:
                    cabinet_uids.add(cabinet_uid)

    return sorted(cabinet_uids)


def _cabinet_uid_from_port_uid(port_uid: str | None) -> str | None:
    if not port_uid:
        return None
    parts = port_uid.split(":", 2)
    if len(parts) < 2:
        return None
    return f"{parts[0].upper()}:{parts[1].upper()}"

def _members(session, group_uid: str) -> list[db.EntityGroupMember]:
    return session.execute(
        select(db.EntityGroupMember)
        .where(db.EntityGroupMember.group_uid == group_uid)
        .order_by(db.EntityGroupMember.sequence, db.EntityGroupMember.entity_uid)
    ).scalars().all()


def _replace_members(session, group: db.EntityGroup, member_uids: list[str]) -> None:
    normalized_uids = _normalized_member_uids(group.entity_type, member_uids)
    _validate_members_exist(session, group.project_uid, group.entity_type, normalized_uids)
    session.execute(delete(db.EntityGroupMember).where(db.EntityGroupMember.group_uid == group.uid))
    for sequence, entity_uid in enumerate(normalized_uids, start=1):
        session.add(
            db.EntityGroupMember(
                group_uid=group.uid,
                entity_type=group.entity_type,
                entity_uid=entity_uid,
                sequence=sequence,
            )
        )
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A group with this name already exists.") from exc


def _validate_members_exist(session, project_uid: str, entity_type: str, entity_uids: list[str]) -> None:
    if not entity_uids:
        return
    model_map = {
        "cable": db.Cable,
        "cabinet": db.Cabinet,
        "device": db.Device,
        "port": db.Port,
        "bundle": db.CableBundle,
    }
    model_type = model_map[entity_type]
    existing = set(
        session.execute(
            select(model_type.uid).where(
                model_type.project_uid == project_uid,
                model_type.uid.in_(entity_uids),
                model_type.deleted_at.is_(None),
            )
        ).scalars()
    )
    missing = [uid for uid in entity_uids if uid not in existing]
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown {entity_type} UIDs: {', '.join(missing[:20])}")


def _group_or_404(session, group_uid: str) -> db.EntityGroup:
    group = session.execute(
        select(db.EntityGroup).where(db.EntityGroup.uid == group_uid, db.EntityGroup.deleted_at.is_(None))
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail=f"Entity group '{group_uid}' was not found.")
    return group


def _ensure_user(session, user: AuthUser) -> None:
    existing = session.get(db.User, user.uid)
    if existing is None:
        session.add(db.User(uid=user.uid, display_name=user.display_name or user.uid, role=user.role.value))
    elif existing.role != user.role.value:
        existing.role = user.role.value


def _normalized_member_uids(entity_type: str, member_uids: list[str]) -> list[str]:
    normalized = []
    for uid in member_uids:
        value = uid.strip()
        if not value:
            continue
        if entity_type in {"cable", "cabinet", "device", "port"}:
            value = value.upper()
        normalized.append(value)
    return list(dict.fromkeys(normalized))


def _entity_type(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if normalized not in SUPPORTED_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity_type must be one of: cable, cabinet, device, port, bundle.")
    return normalized


def _optional_entity_type(entity_type: str | None) -> str | None:
    return _entity_type(entity_type) if entity_type else None


def _require_postgresql() -> None:
    if not use_postgresql_topology_storage():
        raise HTTPException(status_code=400, detail="Entity groups require PostgreSQL topology storage.")