from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from backend.api.auth import AuthUser, current_user, require_editor, require_manager
from backend.core.config import DEFAULT_PROJECT_UID, use_postgresql_topology_storage
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.session import session_factory
from backend.services.change_orders import approve_change_order, create_change_order, generate_change_order_tasks


router = APIRouter(prefix="/change-orders", tags=["change-orders"])


class ChangeOrderItemRequest(BaseModel):
    uid: str | None = None
    intent: str
    entity_uid: str | None = None
    old_entity_uid: str | None = None
    new_entity_uid: str | None = None
    old_cable_uid: str | None = None
    new_cable_uid: str | None = None
    cable_uid: str | None = None
    before_definition: dict[str, Any] = Field(default_factory=dict)
    after_definition: dict[str, Any] = Field(default_factory=dict)
    task_plan: list[dict[str, Any]] | None = None


class CreateChangeOrderRequest(BaseModel):
    uid: str | None = None
    project_uid: str = DEFAULT_PROJECT_UID
    change_order_number: int | None = None
    title: str = ""
    description: str = ""
    source_type: str = "manual"
    source_uid: str = ""
    items: list[ChangeOrderItemRequest] = Field(default_factory=list)


class ChangeOrderItemRecord(BaseModel):
    uid: str
    sequence: int
    entity_type: str
    entity_uid: str
    intent: str
    status: str
    old_entity_uid: str | None = None
    new_entity_uid: str | None = None
    before_definition: dict[str, Any] = Field(default_factory=dict)
    after_definition: dict[str, Any] = Field(default_factory=dict)
    task_plan: list[dict[str, Any]] = Field(default_factory=list)
    result_payload: dict[str, Any] = Field(default_factory=dict)


class ChangeOrderTaskLinkRecord(BaseModel):
    change_order_uid: str
    change_order_item_uid: str
    task_uid: str
    effect_type: str


class ChangeOrderEventRecord(BaseModel):
    id: int
    event_type: str
    change_order_item_uid: str | None = None
    actor_user_uid: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChangeOrderRecord(BaseModel):
    uid: str
    project_uid: str
    change_order_number: int
    title: str
    description: str
    status: str
    source_type: str
    source_uid: str
    requested_by_user_uid: str | None = None
    reviewed_by_user_uid: str | None = None
    approved_at: datetime | None = None
    completed_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    items: list[ChangeOrderItemRecord] = Field(default_factory=list)
    task_links: list[ChangeOrderTaskLinkRecord] = Field(default_factory=list)
    events: list[ChangeOrderEventRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=ChangeOrderRecord)
def create_change_order_endpoint(request: CreateChangeOrderRequest, user: AuthUser = Depends(current_user)) -> ChangeOrderRecord:
    _require_postgresql()
    require_editor(user)
    with session_factory()() as session:
        with session.begin():
            _ensure_user(session, user)
            order = create_change_order(
                session,
                project_uid=request.project_uid,
                uid=request.uid,
                change_order_number=request.change_order_number,
                title=request.title,
                description=request.description,
                source_type=request.source_type,
                source_uid=request.source_uid,
                requested_by_user_uid=user.uid,
                items=[_model_payload(item) for item in request.items],
            )
        return _change_order_record(session, order.uid)


@router.get("", response_model=list[ChangeOrderRecord])
def list_change_orders(project_uid: str = DEFAULT_PROJECT_UID, include_initial: bool = False, user: AuthUser = Depends(current_user)) -> list[ChangeOrderRecord]:
    _require_postgresql()
    require_editor(user)
    with session_factory()() as session:
        clauses = [db.ChangeOrder.project_uid == project_uid]
        if not include_initial:
            clauses.append(db.ChangeOrder.change_order_number != 0)
        try:
            rows = session.execute(
                select(db.ChangeOrder).where(*clauses).order_by(db.ChangeOrder.change_order_number.desc(), db.ChangeOrder.created_at.desc())
            ).scalars().all()
        except ProgrammingError as exc:
            if "change_orders" not in str(exc):
                raise
            return []
        return [_change_order_record(session, row.uid) for row in rows]


@router.get("/{change_order_uid}", response_model=ChangeOrderRecord)
def get_change_order(change_order_uid: str, user: AuthUser = Depends(current_user)) -> ChangeOrderRecord:
    _require_postgresql()
    require_editor(user)
    with session_factory()() as session:
        return _change_order_record(session, change_order_uid)


@router.post("/{change_order_uid}/approve", response_model=ChangeOrderRecord)
def approve_change_order_endpoint(change_order_uid: str, user: AuthUser = Depends(current_user)) -> ChangeOrderRecord:
    _require_postgresql()
    require_manager(user)
    with session_factory()() as session:
        with session.begin():
            _ensure_user(session, user)
            order = approve_change_order(session, change_order_uid=change_order_uid, reviewed_by_user_uid=user.uid)
        return _change_order_record(session, order.uid)


@router.post("/{change_order_uid}/generate-tasks", response_model=ChangeOrderRecord)
def generate_change_order_tasks_endpoint(change_order_uid: str, user: AuthUser = Depends(current_user)) -> ChangeOrderRecord:
    _require_postgresql()
    require_editor(user)
    with session_factory()() as session:
        with session.begin():
            _ensure_user(session, user)
            order = generate_change_order_tasks(session, change_order_uid=change_order_uid, user_uid=user.uid)
        return _change_order_record(session, order.uid)


def _change_order_record(session, change_order_uid: str) -> ChangeOrderRecord:
    order = session.get(db.ChangeOrder, change_order_uid)
    if order is None:
        raise HTTPException(status_code=404, detail="Change order was not found.")
    items = session.execute(
        select(db.ChangeOrderItem)
        .where(db.ChangeOrderItem.change_order_uid == order.uid)
        .order_by(db.ChangeOrderItem.sequence, db.ChangeOrderItem.uid)
    ).scalars().all()
    links = session.execute(
        select(db.ChangeOrderTaskLink).where(db.ChangeOrderTaskLink.change_order_uid == order.uid).order_by(db.ChangeOrderTaskLink.task_uid)
    ).scalars().all()
    events = session.execute(
        select(db.ChangeOrderEvent).where(db.ChangeOrderEvent.change_order_uid == order.uid).order_by(db.ChangeOrderEvent.created_at, db.ChangeOrderEvent.id)
    ).scalars().all()
    return ChangeOrderRecord(
        uid=order.uid,
        project_uid=order.project_uid,
        change_order_number=order.change_order_number,
        title=order.title,
        description=order.description,
        status=order.status,
        source_type=order.source_type,
        source_uid=order.source_uid,
        requested_by_user_uid=order.requested_by_user_uid,
        reviewed_by_user_uid=order.reviewed_by_user_uid,
        approved_at=order.approved_at,
        completed_at=order.completed_at,
        summary=order.summary,
        items=[ChangeOrderItemRecord(**_item_payload(item)) for item in items],
        task_links=[
            ChangeOrderTaskLinkRecord(
                change_order_uid=link.change_order_uid,
                change_order_item_uid=link.change_order_item_uid,
                task_uid=link.task_uid,
                effect_type=link.effect_type,
            )
            for link in links
        ],
        events=[
            ChangeOrderEventRecord(
                id=event.id,
                event_type=event.event_type,
                change_order_item_uid=event.change_order_item_uid,
                actor_user_uid=event.actor_user_uid,
                payload=event.payload,
                created_at=event.created_at,
            )
            for event in events
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _item_payload(item: db.ChangeOrderItem) -> dict[str, Any]:
    return {
        "uid": item.uid,
        "sequence": item.sequence,
        "entity_type": item.entity_type,
        "entity_uid": item.entity_uid,
        "intent": item.intent,
        "status": item.status,
        "old_entity_uid": item.old_entity_uid,
        "new_entity_uid": item.new_entity_uid,
        "before_definition": item.before_definition,
        "after_definition": item.after_definition,
        "task_plan": item.task_plan,
        "result_payload": item.result_payload,
    }


def _ensure_user(session, user: AuthUser) -> None:
    existing = session.get(db.User, user.uid)
    if existing is None:
        session.add(db.User(uid=user.uid, display_name=user.display_name or user.uid, role=user.role.value))
        session.flush()
    elif existing.role != user.role.value:
        existing.role = user.role.value


def _model_payload(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", exclude_none=True)
    return model.dict(exclude_none=True)


def _require_postgresql() -> None:
    if not use_postgresql_topology_storage():
        raise HTTPException(status_code=422, detail="Change order APIs require PostgreSQL storage mode.")

