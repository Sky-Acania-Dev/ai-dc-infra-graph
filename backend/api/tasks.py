from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.api.auth import AuthUser, current_user, require_editor, require_manager
from backend.core.config import DEFAULT_PROJECT_UID, use_postgresql_topology_storage
from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.filter_presets import FILTER_FIELD_DEFINITIONS, FilterPayload, validate_filter_payload
from backend.persistence.postgresql.mutations import MutationUser, PersistedOperation, bulk_update_status
from backend.persistence.postgresql.session import session_factory
from backend.services.change_orders import apply_change_order_task_completion


router = APIRouter(tags=["tasks"])

TASK_TYPES = {
    "cable_pull",
    "cable_dress",
    "cable_termination",
    "cable_test",
    "cable_label",
    "cable_rework",
    "cable_retirement",
    "cable_removal",
    "inspection",
}
TASK_STATUSES = {"draft", "assigned", "in_progress", "submitted", "approved", "denied", "cancelled", "abandoned", "superseded"}
TASK_PRIORITIES = {"low", "normal", "high", "urgent"}
TASK_ENTITY_TYPES = {"cable", "cabinet", "device", "port", "bundle"}
CREW_ROLES = {"lead", "member", "foreman"}

TASK_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"assigned", "cancelled", "abandoned", "superseded"},
    "assigned": {"in_progress", "submitted", "cancelled", "abandoned", "superseded"},
    "in_progress": {"submitted", "cancelled", "abandoned", "superseded"},
    "submitted": {"approved", "denied", "cancelled", "abandoned", "superseded"},
    "denied": {"assigned", "in_progress", "cancelled", "abandoned", "superseded"},
    "approved": set(),
    "cancelled": set(),
    "abandoned": set(),
    "superseded": set(),
}


class PersonnelRecord(BaseModel):
    uid: str
    project_uid: str
    employee_uid: str
    user_uid: str | None = None
    display_name: str
    email: str | None = None
    phone: str | None = None
    trade: str = ""
    company: str = ""
    active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CreatePersonnelRequest(BaseModel):
    uid: str | None = None
    project_uid: str = DEFAULT_PROJECT_UID
    employee_uid: str
    user_uid: str | None = None
    display_name: str
    email: str | None = None
    phone: str | None = None
    trade: str = ""
    company: str = ""
    active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class UpdatePersonnelRequest(BaseModel):
    employee_uid: str | None = None
    user_uid: str | None = None
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    trade: str | None = None
    company: str | None = None
    active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class CrewMemberRecord(BaseModel):
    personnel_uid: str
    role_in_crew: str = "member"
    active: bool = True
    personnel: PersonnelRecord | None = None


class CrewRecord(BaseModel):
    uid: str
    project_uid: str
    name: str
    crew_type: str = ""
    active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    members: list[CrewMemberRecord] = Field(default_factory=list)


class CreateCrewRequest(BaseModel):
    uid: str | None = None
    project_uid: str = DEFAULT_PROJECT_UID
    name: str
    crew_type: str = ""
    active: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class UpdateCrewRequest(BaseModel):
    name: str | None = None
    crew_type: str | None = None
    active: bool | None = None
    metadata_json: dict[str, Any] | None = None


class UpsertCrewMemberRequest(BaseModel):
    personnel_uid: str
    role_in_crew: str = "member"
    active: bool = True


class TaskEntityRecord(BaseModel):
    entity_type: str
    entity_uid: str
    sequence: int | None = None


class TaskEventRecord(BaseModel):
    id: int
    event_type: str
    actor_user_uid: str | None = None
    actor_personnel_uid: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TaskRecord(BaseModel):
    uid: str
    project_uid: str
    title: str
    description: str = ""
    task_type: str
    status: str
    priority: str = "normal"
    created_by_user_uid: str | None = None
    assigned_crew_uid: str | None = None
    assigned_personnel_uid: str | None = None
    submitted_by_personnel_uid: str | None = None
    reviewed_by_user_uid: str | None = None
    applied_by_user_uid: str | None = None
    entity_type: str
    entity_filter_payload: dict[str, Any] = Field(default_factory=dict)
    target_payload: dict[str, Any] = Field(default_factory=dict)
    submission_payload: dict[str, Any] = Field(default_factory=dict)
    review_note: str = ""
    due_at: datetime | None = None
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    applied_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    entities: list[TaskEntityRecord] = Field(default_factory=list)


class CreateTaskRequest(BaseModel):
    uid: str | None = None
    project_uid: str = DEFAULT_PROJECT_UID
    title: str
    description: str = ""
    task_type: str
    priority: str = "normal"
    assigned_crew_uid: str | None = None
    assigned_personnel_uid: str | None = None
    entity_type: str = "cable"
    entity_uids: list[str] = Field(default_factory=list)
    filter_preset_uid: str | None = None
    entity_filter_payload: dict[str, Any] = Field(default_factory=dict)
    target_payload: dict[str, Any] = Field(default_factory=dict)
    due_at: datetime | None = None


class AssignTaskRequest(BaseModel):
    assigned_crew_uid: str | None = None
    assigned_personnel_uid: str | None = None
    note: str = ""


class UpdateTaskStatusRequest(BaseModel):
    status: str
    actor_personnel_uid: str | None = None
    submission_payload: dict[str, Any] | None = None
    review_note: str = ""


class CrewMemberUpdateRecord(BaseModel):
    crew_uid: str
    personnel_uid: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)


class AppliedTaskResult(BaseModel):
    task_uid: str
    operation_group_uid: str
    entity_type: str
    entity_uids: list[str]
    operations: list[PersistedOperation] = Field(default_factory=list)
    crew_member_updates: list[CrewMemberUpdateRecord] = Field(default_factory=list)
    already_applied: bool = False


class TaskDetailRecord(BaseModel):
    task: TaskRecord
    assigned_crew: CrewRecord | None = None
    assigned_personnel: PersonnelRecord | None = None
    events: list[TaskEventRecord] = Field(default_factory=list)


class PersonnelCrewStatus(BaseModel):
    crew_uid: str
    crew_name: str
    crew_type: str = ""
    role_in_crew: str
    active: bool


class PersonnelTaskStatus(BaseModel):
    task_uid: str
    title: str
    task_type: str
    status: str
    role: str
    assigned_crew_uid: str | None = None
    due_at: datetime | None = None


class PersonnelCurrentStatusRecord(BaseModel):
    personnel: PersonnelRecord
    project_uid: str
    crews: list[PersonnelCrewStatus] = Field(default_factory=list)
    assigned_tasks: list[PersonnelTaskStatus] = Field(default_factory=list)


class EntityFilterResolveRequest(BaseModel):
    project_uid: str = DEFAULT_PROJECT_UID
    entity_type: str
    filter_payload: dict[str, Any] = Field(default_factory=dict)
    filter_preset_uid: str | None = None
    limit: int = Field(default=1000, ge=1, le=5000)


class EntityFilterResolveResponse(BaseModel):
    project_uid: str
    entity_type: str
    entity_uids: list[str]


def _require_postgresql() -> None:
    if not use_postgresql_topology_storage():
        raise HTTPException(status_code=422, detail="Task, crew, and personnel APIs require PostgreSQL storage mode.")


def _new_uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_choice(value: str, allowed: set[str], field: str) -> None:
    if value not in allowed:
        raise HTTPException(status_code=422, detail=f"Unsupported {field}: {value}")


def _session() -> Session:
    return session_factory()()


@router.get("/personnel/search", response_model=list[PersonnelRecord])
def search_personnel(
    q: str = "",
    project_uid: str = DEFAULT_PROJECT_UID,
    trade: str | None = None,
    company: str | None = None,
    active: bool | None = True,
    limit: int = 25,
    user: AuthUser = Depends(current_user),
) -> list[PersonnelRecord]:
    _require_postgresql()
    require_editor(user)
    search_term = q.strip().lower()
    with _session() as session:
        statement = select(db.Personnel).where(db.Personnel.project_uid == project_uid, db.Personnel.deleted_at.is_(None))
        if active is not None:
            statement = statement.where(db.Personnel.active == active)
        if trade:
            statement = statement.where(func.lower(db.Personnel.trade) == trade.strip().lower())
        if company:
            statement = statement.where(func.lower(db.Personnel.company) == company.strip().lower())
        if search_term:
            pattern = f"%{search_term}%"
            statement = statement.where(
                or_(
                    func.lower(db.Personnel.uid).like(pattern),
                    func.lower(db.Personnel.employee_uid).like(pattern),
                    func.lower(db.Personnel.display_name).like(pattern),
                    func.lower(db.Personnel.email).like(pattern),
                    func.lower(db.Personnel.trade).like(pattern),
                    func.lower(db.Personnel.company).like(pattern),
                )
            )
        rows = session.execute(statement.order_by(db.Personnel.display_name, db.Personnel.uid).limit(limit)).scalars()
        return [_personnel_record(row) for row in rows]


@router.post("/personnel", response_model=PersonnelRecord)
def create_personnel(request: CreatePersonnelRequest, user: AuthUser = Depends(current_user)) -> PersonnelRecord:
    _require_postgresql()
    require_manager(user)
    row = db.Personnel(
        uid=request.uid or _new_uid("personnel"),
        project_uid=request.project_uid,
        employee_uid=request.employee_uid,
        user_uid=request.user_uid,
        display_name=request.display_name,
        email=request.email,
        phone=request.phone,
        trade=request.trade,
        company=request.company,
        active=request.active,
        metadata_json=request.metadata_json,
    )
    with _session() as session:
        try:
            with session.begin():
                session.add(row)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Personnel record conflicts with an existing employee or linked user.") from exc
        return _personnel_record(row)


@router.patch("/personnel/{personnel_uid}", response_model=PersonnelRecord)
def update_personnel(
    personnel_uid: str,
    request: UpdatePersonnelRequest,
    user: AuthUser = Depends(current_user),
) -> PersonnelRecord:
    _require_postgresql()
    require_manager(user)
    with _session() as session:
        try:
            with session.begin():
                personnel = _get_active(session, db.Personnel, personnel_uid, "Personnel")
                if request.employee_uid is not None:
                    personnel.employee_uid = request.employee_uid
                if request.user_uid is not None:
                    personnel.user_uid = request.user_uid
                if request.display_name is not None:
                    personnel.display_name = request.display_name
                if request.email is not None:
                    personnel.email = request.email
                if request.phone is not None:
                    personnel.phone = request.phone
                if request.trade is not None:
                    personnel.trade = request.trade
                if request.company is not None:
                    personnel.company = request.company
                if request.active is not None:
                    personnel.active = request.active
                if request.metadata_json is not None:
                    personnel.metadata_json = request.metadata_json
                personnel.updated_at = _now()
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Personnel update conflicts with an existing record.") from exc
        return _personnel_record(personnel)


@router.get("/personnel/{personnel_uid}/status", response_model=PersonnelCurrentStatusRecord)
def personnel_current_status(
    personnel_uid: str,
    project_uid: str = DEFAULT_PROJECT_UID,
    include_completed_tasks: bool = False,
    user: AuthUser = Depends(current_user),
) -> PersonnelCurrentStatusRecord:
    _require_postgresql()
    require_editor(user)
    with _session() as session:
        personnel = _get_active(session, db.Personnel, personnel_uid, "Personnel")
        if personnel.project_uid != project_uid:
            raise HTTPException(status_code=404, detail="Personnel was not found in this project.")
        return _personnel_current_status_record(
            session,
            personnel,
            include_completed_tasks=include_completed_tasks,
        )


@router.delete("/personnel/{personnel_uid}", response_model=PersonnelRecord)
def deactivate_personnel(personnel_uid: str, user: AuthUser = Depends(current_user)) -> PersonnelRecord:
    _require_postgresql()
    require_manager(user)
    with _session() as session:
        with session.begin():
            personnel = _get_active(session, db.Personnel, personnel_uid, "Personnel")
            personnel.active = False
            personnel.updated_at = _now()
        return _personnel_record(personnel)


@router.get("/crews", response_model=list[CrewRecord])
def list_crews(
    project_uid: str = DEFAULT_PROJECT_UID,
    active: bool | None = True,
    include_members: bool = True,
    user: AuthUser = Depends(current_user),
) -> list[CrewRecord]:
    _require_postgresql()
    require_editor(user)
    with _session() as session:
        statement = select(db.Crew).where(db.Crew.project_uid == project_uid, db.Crew.deleted_at.is_(None))
        if active is not None:
            statement = statement.where(db.Crew.active == active)
        rows = session.execute(statement.order_by(db.Crew.name, db.Crew.uid)).scalars().all()
        return [_crew_record(session, row, include_members=include_members) for row in rows]


@router.get("/crews/{crew_uid}", response_model=CrewRecord)
def crew_detail(
    crew_uid: str,
    include_members: bool = True,
    user: AuthUser = Depends(current_user),
) -> CrewRecord:
    _require_postgresql()
    require_editor(user)
    with _session() as session:
        crew = _get_active(session, db.Crew, crew_uid, "Crew")
        return _crew_record(session, crew, include_members=include_members)


@router.post("/crews", response_model=CrewRecord)
def create_crew(request: CreateCrewRequest, user: AuthUser = Depends(current_user)) -> CrewRecord:
    _require_postgresql()
    require_manager(user)
    row = db.Crew(
        uid=request.uid or _new_uid("crew"),
        project_uid=request.project_uid,
        name=request.name,
        crew_type=request.crew_type,
        active=request.active,
        metadata_json=request.metadata_json,
    )
    with _session() as session:
        try:
            with session.begin():
                session.add(row)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Crew conflicts with an existing crew in this project.") from exc
        return _crew_record(session, row, include_members=True)


@router.patch("/crews/{crew_uid}", response_model=CrewRecord)
def update_crew(crew_uid: str, request: UpdateCrewRequest, user: AuthUser = Depends(current_user)) -> CrewRecord:
    _require_postgresql()
    require_manager(user)
    with _session() as session:
        try:
            with session.begin():
                crew = _get_active(session, db.Crew, crew_uid, "Crew")
                if request.name is not None:
                    crew.name = request.name
                if request.crew_type is not None:
                    crew.crew_type = request.crew_type
                if request.active is not None:
                    crew.active = request.active
                if request.metadata_json is not None:
                    crew.metadata_json = request.metadata_json
                crew.updated_at = _now()
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Crew update conflicts with an existing crew in this project.") from exc
        return _crew_record(session, crew, include_members=True)


@router.put("/crews/{crew_uid}/members/{personnel_uid}", response_model=CrewRecord)
def upsert_crew_member(
    crew_uid: str,
    personnel_uid: str,
    request: UpsertCrewMemberRequest,
    user: AuthUser = Depends(current_user),
) -> CrewRecord:
    _require_postgresql()
    require_manager(user)
    if request.personnel_uid != personnel_uid:
        raise HTTPException(status_code=422, detail="personnel_uid in body must match the path.")
    _validate_choice(request.role_in_crew, CREW_ROLES, "crew role")
    with _session() as session:
        with session.begin():
            crew = _get_active(session, db.Crew, crew_uid, "Crew")
            personnel = _get_active(session, db.Personnel, personnel_uid, "Personnel")
            if crew.project_uid != personnel.project_uid:
                raise HTTPException(status_code=422, detail="Crew and personnel must belong to the same project.")
            member = session.get(db.CrewMember, {"crew_uid": crew_uid, "personnel_uid": personnel_uid})
            if member is None:
                member = db.CrewMember(
                    crew_uid=crew_uid,
                    personnel_uid=personnel_uid,
                    role_in_crew=request.role_in_crew,
                    active=request.active,
                )
                session.add(member)
            else:
                member.role_in_crew = request.role_in_crew
                member.active = request.active
            crew.updated_at = _now()
        return _crew_record(session, crew, include_members=True)


@router.delete("/crews/{crew_uid}/members/{personnel_uid}", response_model=CrewRecord)
def deactivate_crew_member(
    crew_uid: str,
    personnel_uid: str,
    user: AuthUser = Depends(current_user),
) -> CrewRecord:
    _require_postgresql()
    require_manager(user)
    with _session() as session:
        with session.begin():
            crew = _get_active(session, db.Crew, crew_uid, "Crew")
            member = session.get(db.CrewMember, {"crew_uid": crew_uid, "personnel_uid": personnel_uid})
            if member is None:
                raise HTTPException(status_code=404, detail="Crew member was not found.")
            member.active = False
            crew.updated_at = _now()
        return _crew_record(session, crew, include_members=True)


@router.post("/entity-filters/resolve", response_model=EntityFilterResolveResponse)
def resolve_entity_filter(
    request: EntityFilterResolveRequest,
    user: AuthUser = Depends(current_user),
) -> EntityFilterResolveResponse:
    _require_postgresql()
    require_editor(user)
    with _session() as session:
        entity_uids, filter_payload = _resolve_entity_filter_request(
            session,
            project_uid=request.project_uid,
            entity_type=request.entity_type,
            filter_payload=request.filter_payload,
            filter_preset_uid=request.filter_preset_uid,
            limit=request.limit,
        )
        return EntityFilterResolveResponse(
            project_uid=request.project_uid,
            entity_type=request.entity_type.strip().lower(),
            entity_uids=entity_uids,
        )


@router.post("/tasks", response_model=TaskRecord)
def create_task(request: CreateTaskRequest, user: AuthUser = Depends(current_user)) -> TaskRecord:
    _require_postgresql()
    require_editor(user)
    _validate_choice(request.task_type, TASK_TYPES, "task type")
    _validate_choice(request.priority, TASK_PRIORITIES, "task priority")
    _validate_choice(request.entity_type, TASK_ENTITY_TYPES, "task entity type")
    task_uid = request.uid or _new_uid("task")
    status = "assigned" if request.assigned_crew_uid or request.assigned_personnel_uid else "draft"
    with _session() as session:
        with session.begin():
            _ensure_user(session, user)
            _validate_task_assignment(session, request.project_uid, request.assigned_crew_uid, request.assigned_personnel_uid)
            entity_uids, entity_filter_payload = _task_entity_uids(session, request)
            task = db.Task(
                uid=task_uid,
                project_uid=request.project_uid,
                title=request.title,
                description=request.description,
                task_type=request.task_type,
                status=status,
                priority=request.priority,
                created_by_user_uid=user.uid,
                assigned_crew_uid=request.assigned_crew_uid,
                assigned_personnel_uid=request.assigned_personnel_uid,
                entity_type=request.entity_type,
                entity_filter_payload=entity_filter_payload,
                target_payload=request.target_payload,
                due_at=request.due_at,
            )
            session.add(task)
            seen: set[str] = set()
            for sequence, entity_uid in enumerate(entity_uids):
                if entity_uid in seen:
                    continue
                seen.add(entity_uid)
                session.add(db.TaskEntity(task_uid=task_uid, entity_type=request.entity_type, entity_uid=entity_uid, sequence=sequence))
            _add_task_event(session, task_uid, "created", user, payload={"status": status, "entity_count": len(seen)})
            if status == "assigned":
                _add_task_event(
                    session,
                    task_uid,
                    "assigned",
                    user,
                    payload={"assigned_crew_uid": request.assigned_crew_uid, "assigned_personnel_uid": request.assigned_personnel_uid},
                )
        return _task_record(session, task)


@router.get("/tasks", response_model=list[TaskRecord])
def list_tasks(
    project_uid: str = DEFAULT_PROJECT_UID,
    status: str | None = None,
    assigned_crew_uid: str | None = None,
    assigned_personnel_uid: str | None = None,
    limit: int = 100,
    user: AuthUser = Depends(current_user),
) -> list[TaskRecord]:
    _require_postgresql()
    require_editor(user)
    if status is not None:
        _validate_choice(status, TASK_STATUSES, "task status")
    with _session() as session:
        statement = select(db.Task).where(db.Task.project_uid == project_uid, db.Task.deleted_at.is_(None))
        if status:
            statement = statement.where(db.Task.status == status)
        if assigned_crew_uid:
            statement = statement.where(db.Task.assigned_crew_uid == assigned_crew_uid)
        if assigned_personnel_uid:
            statement = statement.where(db.Task.assigned_personnel_uid == assigned_personnel_uid)
        rows = session.execute(statement.order_by(db.Task.created_at.desc(), db.Task.uid).limit(limit)).scalars().all()
        return [_task_record(session, row) for row in rows]


@router.get("/tasks/review-queue", response_model=list[TaskRecord])
def task_review_queue(
    project_uid: str = DEFAULT_PROJECT_UID,
    limit: int = 100,
    user: AuthUser = Depends(current_user),
) -> list[TaskRecord]:
    _require_postgresql()
    require_manager(user)
    with _session() as session:
        rows = session.execute(
            select(db.Task)
            .where(db.Task.project_uid == project_uid, db.Task.status == "submitted", db.Task.deleted_at.is_(None))
            .order_by(db.Task.submitted_at, db.Task.created_at, db.Task.uid)
            .limit(limit)
        ).scalars()
        return [_task_record(session, row) for row in rows]


@router.get("/tasks/{task_uid}", response_model=TaskDetailRecord)
def task_detail(task_uid: str, user: AuthUser = Depends(current_user)) -> TaskDetailRecord:
    _require_postgresql()
    require_editor(user)
    with _session() as session:
        task = _get_active(session, db.Task, task_uid, "Task")
        return _task_detail_record(session, task)


@router.get("/tasks/{task_uid}/events", response_model=list[TaskEventRecord])
def task_events(task_uid: str, user: AuthUser = Depends(current_user)) -> list[TaskEventRecord]:
    _require_postgresql()
    require_editor(user)
    with _session() as session:
        _get_active(session, db.Task, task_uid, "Task")
        return _task_event_records(session, task_uid)


@router.post("/tasks/{task_uid}/apply", response_model=AppliedTaskResult)
def apply_task(
    task_uid: str,
    expected_version: int | None = None,
    user: AuthUser = Depends(current_user),
) -> AppliedTaskResult:
    return apply_completed_task_content(task_uid, user=user, expected_version=expected_version)


@router.patch("/tasks/{task_uid}/assignment", response_model=TaskRecord)
def assign_task(task_uid: str, request: AssignTaskRequest, user: AuthUser = Depends(current_user)) -> TaskRecord:
    _require_postgresql()
    require_editor(user)
    with _session() as session:
        with session.begin():
            _ensure_user(session, user)
            task = _get_active(session, db.Task, task_uid, "Task")
            _validate_task_assignment(session, task.project_uid, request.assigned_crew_uid, request.assigned_personnel_uid)
            if task.status in {"approved", "cancelled"}:
                raise HTTPException(status_code=409, detail=f"Cannot assign a {task.status} task.")
            task.assigned_crew_uid = request.assigned_crew_uid
            task.assigned_personnel_uid = request.assigned_personnel_uid
            if task.status == "draft" and (request.assigned_crew_uid or request.assigned_personnel_uid):
                task.status = "assigned"
            task.updated_at = _now()
            _add_task_event(
                session,
                task_uid,
                "assigned",
                user,
                payload={
                    "assigned_crew_uid": request.assigned_crew_uid,
                    "assigned_personnel_uid": request.assigned_personnel_uid,
                    "note": request.note,
                },
            )
        return _task_record(session, task)


@router.patch("/tasks/{task_uid}/status", response_model=TaskRecord)
def update_task_status(
    task_uid: str,
    request: UpdateTaskStatusRequest,
    user: AuthUser = Depends(current_user),
) -> TaskRecord:
    _require_postgresql()
    require_editor(user)
    _validate_choice(request.status, TASK_STATUSES, "task status")
    with _session() as session:
        with session.begin():
            _ensure_user(session, user)
            task = _get_active(session, db.Task, task_uid, "Task")
            if request.status not in TASK_TRANSITIONS[task.status]:
                raise HTTPException(status_code=409, detail=f"Cannot move task from {task.status} to {request.status}.")
            if request.status in {"approved", "denied"}:
                require_manager(user)
            task.status = request.status
            now = _now()
            task.updated_at = now
            event_payload: dict[str, Any] = {}
            event_type = "started" if request.status == "in_progress" else request.status
            if request.status == "in_progress":
                task.started_at = task.started_at or now
            elif request.status == "submitted":
                if request.actor_personnel_uid:
                    _validate_personnel_project(session, task.project_uid, request.actor_personnel_uid)
                task.submitted_by_personnel_uid = request.actor_personnel_uid
                task.submission_payload = request.submission_payload or {}
                task.submitted_at = now
                event_payload["submission_payload"] = task.submission_payload
            elif request.status in {"approved", "denied"}:
                task.reviewed_by_user_uid = user.uid
                task.reviewed_at = now
                task.review_note = request.review_note
                event_payload["review_note"] = request.review_note
            elif request.status == "cancelled":
                task.cancelled_at = now
                event_payload["review_note"] = request.review_note
            _add_task_event(
                session,
                task_uid,
                event_type,
                user,
                actor_personnel_uid=request.actor_personnel_uid,
                payload=event_payload,
            )
        return _task_record(session, task)


def apply_completed_task_content(
    task_uid: str,
    *,
    user: AuthUser,
    expected_version: int | None = None,
) -> AppliedTaskResult:
    """Apply an approved task's target payload to its selected entities.

    Supported target payload:
    - cable task: {"status": "..."}
    - cabinet/device task: {"lifecycle_status": "..."}
    - optional crew membership changes:
      {"crew_member_updates": [{"personnel_uid": "...", "active": false, "role_in_crew": "member"}]}
    """
    _require_postgresql()
    require_manager(user)
    mutation_user = MutationUser(uid=user.uid, display_name=user.display_name, role=user.role.value)
    operation_group_uid = f"task:{task_uid}:apply"
    with _session() as session:
        with session.begin():
            _ensure_user(session, user)
            task = _locked_task(session, task_uid)
            operation_group_uid = f"task:{task.uid}:apply"
            if task.applied_at is not None:
                return _applied_task_result_from_history(session, task=task, operation_group_uid=operation_group_uid)
            if task.status != "approved":
                raise HTTPException(status_code=409, detail="Only approved tasks can be applied.")
            entity_rows = session.execute(
                select(db.TaskEntity)
                .where(db.TaskEntity.task_uid == task.uid)
                .order_by(db.TaskEntity.sequence, db.TaskEntity.entity_uid)
            ).scalars().all()
            entity_uids = [row.entity_uid for row in entity_rows]
            if not entity_uids:
                raise HTTPException(status_code=422, detail="Task has no target entities to apply.")

            operations = _apply_task_entity_targets(
                session,
                task=task,
                entity_uids=entity_uids,
                expected_version=expected_version,
                user=mutation_user,
                operation_group_uid=operation_group_uid,
            )
            crew_member_updates = _apply_task_crew_member_updates(session, task=task)
            task.applied_by_user_uid = user.uid
            task.applied_at = _now()
            task.updated_at = task.applied_at
            _add_task_event(
                session,
                task.uid,
                "applied",
                user,
                payload={
                    "operation_group_uid": operation_group_uid,
                    "operation_ids": [operation.id for operation in operations],
                    "crew_member_updates": [_model_payload(update) for update in crew_member_updates],
                },
            )
            apply_change_order_task_completion(session, task=task, actor_user_uid=user.uid)
            return AppliedTaskResult(
                task_uid=task.uid,
                operation_group_uid=operation_group_uid,
                entity_type=task.entity_type,
                entity_uids=entity_uids,
                operations=operations,
                crew_member_updates=crew_member_updates,
            )


def _get_active(session: Session, model: type[Any], uid: str, label: str) -> Any:
    row = session.get(model, uid)
    if row is None or getattr(row, "deleted_at", None) is not None:
        raise HTTPException(status_code=404, detail=f"{label} was not found.")
    return row


def _locked_task(session: Session, task_uid: str) -> db.Task:
    try:
        task = session.execute(
            select(db.Task)
            .where(db.Task.uid == task_uid, db.Task.deleted_at.is_(None))
            .with_for_update(nowait=True)
        ).scalar_one_or_none()
    except OperationalError as exc:
        if _is_lock_not_available(exc):
            raise HTTPException(status_code=409, detail="Task is currently being applied or edited.") from exc
        raise
    if task is None:
        raise HTTPException(status_code=404, detail="Task was not found.")
    return task


def _task_entity_uids(session: Session, request: CreateTaskRequest) -> tuple[list[str], dict[str, Any]]:
    if request.entity_uids:
        entity_uids = _normalized_entity_uids(request.entity_type, request.entity_uids)
        _validate_entity_uids_exist(session, project_uid=request.project_uid, entity_type=request.entity_type, entity_uids=entity_uids)
        return entity_uids, request.entity_filter_payload
    if request.filter_preset_uid or request.entity_filter_payload.get("rules"):
        return _resolve_entity_filter_request(
            session,
            project_uid=request.project_uid,
            entity_type=request.entity_type,
            filter_payload=request.entity_filter_payload,
            filter_preset_uid=request.filter_preset_uid,
            limit=5000,
        )
    return [], request.entity_filter_payload


def _resolve_entity_filter_request(
    session: Session,
    *,
    project_uid: str,
    entity_type: str,
    filter_payload: dict[str, Any],
    filter_preset_uid: str | None,
    limit: int,
) -> tuple[list[str], dict[str, Any]]:
    normalized_entity_type = entity_type.strip().lower()
    payload = filter_payload
    if filter_preset_uid:
        preset = _get_active(session, db.FilterPreset, filter_preset_uid, "Filter preset")
        if preset.project_uid != project_uid or preset.entity_type != normalized_entity_type:
            raise HTTPException(status_code=422, detail="Filter preset does not match the requested project/entity type.")
        payload = dict(preset.filter_payload)
    try:
        validated_payload = validate_filter_payload(normalized_entity_type, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _resolve_entity_filter(session, project_uid=project_uid, entity_type=normalized_entity_type, filter_payload=validated_payload, limit=limit), payload


def _resolve_entity_filter(
    session: Session,
    *,
    project_uid: str,
    entity_type: str,
    filter_payload: FilterPayload,
    limit: int,
) -> list[str]:
    model_type = _entity_model(entity_type)
    statement = select(model_type.uid).where(model_type.project_uid == project_uid, model_type.deleted_at.is_(None))
    clauses = [_filter_rule_clause(entity_type, rule) for rule in filter_payload.rules]
    if clauses:
        statement = statement.where(or_(*clauses) if filter_payload.logic == "or" else and_(*clauses))
    rows = session.execute(statement.order_by(model_type.uid).limit(limit)).scalars()
    return list(rows)


def _filter_rule_clause(entity_type: str, rule) -> Any:
    column = _filter_column(entity_type, rule.field)
    operator = rule.operator.strip().lower()
    value = rule.value
    if operator == "equals":
        return column == value
    if operator == "not_equals":
        return column != value
    if operator == "in":
        return column.in_(value)
    if operator == "not_in":
        return column.notin_(value)
    if operator == "contains":
        return func.lower(column).like(f"%{str(value).lower()}%")
    if operator == "starts_with":
        return func.lower(column).like(f"{str(value).lower()}%")
    if operator == "between":
        return column.between(value[0], value[1])
    if operator == "gt":
        return column > value
    if operator == "gte":
        return column >= value
    if operator == "lt":
        return column < value
    if operator == "lte":
        return column <= value
    if operator == "is_blank":
        if _filter_field_type(entity_type, rule.field) == "text":
            return or_(column.is_(None), column == "")
        return column.is_(None)
    if operator == "is_not_blank":
        if _filter_field_type(entity_type, rule.field) == "text":
            return and_(column.is_not(None), column != "")
        return column.is_not(None)
    raise HTTPException(status_code=422, detail=f"Unsupported filter operator '{rule.operator}'.")


def _filter_column(entity_type: str, field: str) -> Any:
    model_type = _entity_model(entity_type)
    field_map = {
        "cable": {"status": "import_status", "group": "cable_group"},
        "bundle": {"lifecycle_status": "lifecycle_status"},
    }
    column_name = field_map.get(entity_type, {}).get(field, field)
    if not hasattr(model_type, column_name):
        raise HTTPException(status_code=422, detail=f"Unsupported filter field '{field}'.")
    return getattr(model_type, column_name)


def _filter_field_type(entity_type: str, field: str) -> str:
    field_definition = FILTER_FIELD_DEFINITIONS[entity_type][field]
    return field_definition.field_type


def _entity_model(entity_type: str) -> type[Any]:
    model_map = {
        "cabinet": db.Cabinet,
        "device": db.Device,
        "cable": db.Cable,
        "port": db.Port,
        "bundle": db.CableBundle,
    }
    model_type = model_map.get(entity_type.strip().lower())
    if model_type is None:
        raise HTTPException(status_code=422, detail="entity_type must be one of: cabinet, device, cable, port, bundle.")
    return model_type


def _normalized_entity_uids(entity_type: str, entity_uids: list[str]) -> list[str]:
    normalized_entity_type = entity_type.strip().lower()
    if normalized_entity_type == "device":
        normalized = []
        for uid in entity_uids:
            data_hall_id, cabinet_id, rack_unit = uid.upper().split(":", 2)
            normalized.append(f"{data_hall_id}:{cabinet_id}:{int(rack_unit)}")
    elif normalized_entity_type in {"cabinet", "cable"}:
        normalized = [uid.upper() for uid in entity_uids]
    else:
        normalized = [uid.strip() for uid in entity_uids]
    return sorted({uid for uid in normalized if uid})


def _validate_entity_uids_exist(
    session: Session,
    *,
    project_uid: str,
    entity_type: str,
    entity_uids: list[str],
) -> None:
    model_type = _entity_model(entity_type)
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
        raise HTTPException(status_code=422, detail={"message": "Some entity UIDs were not found.", "missing_entity_uids": missing})


def _apply_task_entity_targets(
    session: Session,
    *,
    task: db.Task,
    entity_uids: list[str],
    expected_version: int | None,
    user: MutationUser,
    operation_group_uid: str,
) -> list[PersistedOperation]:
    target_payload = dict(task.target_payload)
    entity_type = task.entity_type
    if entity_type == "cable":
        status = target_payload.get("status")
        if not isinstance(status, str) or not status:
            raise HTTPException(status_code=422, detail="Cable task target_payload.status is required.")
        return bulk_update_status(
            session,
            entity_type=entity_type,
            entity_uids=entity_uids,
            status=status,
            expected_version=expected_version,
            user=user,
            operation_group_uid=operation_group_uid,
            source_type="task_apply",
            source_uid=task.uid,
        )
    if entity_type in {"cabinet", "device"}:
        lifecycle_status = target_payload.get("lifecycle_status")
        if not isinstance(lifecycle_status, str) or not lifecycle_status:
            raise HTTPException(status_code=422, detail=f"{entity_type.title()} task target_payload.lifecycle_status is required.")
        return bulk_update_status(
            session,
            entity_type=entity_type,
            entity_uids=entity_uids,
            lifecycle_status=lifecycle_status,
            expected_version=expected_version,
            user=user,
            operation_group_uid=operation_group_uid,
            source_type="task_apply",
            source_uid=task.uid,
        )
    raise HTTPException(status_code=422, detail="Task apply currently supports cable, cabinet, and device entities.")


def _apply_task_crew_member_updates(session: Session, *, task: db.Task) -> list[CrewMemberUpdateRecord]:
    updates_payload = task.target_payload.get("crew_member_updates", [])
    if updates_payload is None:
        return []
    if not isinstance(updates_payload, list):
        raise HTTPException(status_code=422, detail="target_payload.crew_member_updates must be a list.")
    crew_uid = task.assigned_crew_uid
    if updates_payload and not crew_uid:
        raise HTTPException(status_code=422, detail="Crew member updates require assigned_crew_uid.")

    applied_updates: list[CrewMemberUpdateRecord] = []
    for item in updates_payload:
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail="Each crew member update must be an object.")
        personnel_uid = item.get("personnel_uid")
        if not isinstance(personnel_uid, str) or not personnel_uid:
            raise HTTPException(status_code=422, detail="Crew member update personnel_uid is required.")
        member = session.get(db.CrewMember, {"crew_uid": crew_uid, "personnel_uid": personnel_uid})
        if member is None:
            raise HTTPException(status_code=404, detail=f"Crew member '{personnel_uid}' was not found on crew '{crew_uid}'.")

        before = {"active": member.active, "role_in_crew": member.role_in_crew}
        if "active" in item:
            if not isinstance(item["active"], bool):
                raise HTTPException(status_code=422, detail="Crew member update active must be boolean.")
            member.active = item["active"]
        if "status" in item:
            member.active = _crew_member_status_to_active(item["status"])
        if "role_in_crew" in item:
            role = item["role_in_crew"]
            if not isinstance(role, str):
                raise HTTPException(status_code=422, detail="Crew member update role_in_crew must be a string.")
            _validate_choice(role, CREW_ROLES, "crew role")
            member.role_in_crew = role
        after = {"active": member.active, "role_in_crew": member.role_in_crew}
        if before != after:
            applied_updates.append(CrewMemberUpdateRecord(crew_uid=crew_uid or "", personnel_uid=personnel_uid, before=before, after=after))
    return applied_updates


def _crew_member_status_to_active(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Crew member update status must be active/inactive or boolean.")
    normalized = value.strip().lower()
    if normalized in {"active", "available", "assigned"}:
        return True
    if normalized in {"inactive", "unavailable", "released", "off"}:
        return False
    raise HTTPException(status_code=422, detail="Crew member update status must be active/inactive, available/unavailable, assigned/released, or off.")


def _applied_task_result_from_history(
    session: Session,
    *,
    task: db.Task,
    operation_group_uid: str,
) -> AppliedTaskResult:
    entity_uids = [
        row.entity_uid
        for row in session.execute(
            select(db.TaskEntity)
            .where(db.TaskEntity.task_uid == task.uid)
            .order_by(db.TaskEntity.sequence, db.TaskEntity.entity_uid)
        ).scalars()
    ]
    operation_rows = session.execute(
        select(db.OperationLog)
        .where(db.OperationLog.operation_group_uid == operation_group_uid)
        .order_by(db.OperationLog.id)
    ).scalars()
    applied_event = session.execute(
        select(db.TaskEvent)
        .where(db.TaskEvent.task_uid == task.uid, db.TaskEvent.event_type == "applied")
        .order_by(db.TaskEvent.created_at.desc(), db.TaskEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    crew_member_updates = []
    if applied_event is not None:
        crew_member_updates = [
            CrewMemberUpdateRecord(**item)
            for item in applied_event.payload.get("crew_member_updates", [])
            if isinstance(item, dict)
        ]
    return AppliedTaskResult(
        task_uid=task.uid,
        operation_group_uid=operation_group_uid,
        entity_type=task.entity_type,
        entity_uids=entity_uids,
        operations=[_persisted_operation_record(row) for row in operation_rows],
        crew_member_updates=crew_member_updates,
        already_applied=True,
    )


def _persisted_operation_record(row: db.OperationLog) -> PersistedOperation:
    return PersistedOperation(
        id=row.id,
        operation_type=row.operation_type,
        entity_type=row.entity_type,
        entity_uid=row.entity_uid,
        operation_group_uid=row.operation_group_uid,
        source_type=row.source_type,
        source_uid=row.source_uid,
        before=row.before,
        after=row.after,
        user_uid=row.user_uid,
        user_role=row.user_role,
        created_at=row.created_at,
        version=row.id,
    )


def _task_event_records(session: Session, task_uid: str) -> list[TaskEventRecord]:
    rows = session.execute(
        select(db.TaskEvent)
        .where(db.TaskEvent.task_uid == task_uid)
        .order_by(db.TaskEvent.created_at, db.TaskEvent.id)
    ).scalars()
    return [
        TaskEventRecord(
            id=row.id,
            event_type=row.event_type,
            actor_user_uid=row.actor_user_uid,
            actor_personnel_uid=row.actor_personnel_uid,
            payload=dict(row.payload),
            created_at=row.created_at,
        )
        for row in rows
    ]


def _task_detail_record(session: Session, task: db.Task) -> TaskDetailRecord:
    assigned_crew = None
    if task.assigned_crew_uid:
        crew = session.get(db.Crew, task.assigned_crew_uid)
        if crew is not None and crew.deleted_at is None:
            assigned_crew = _crew_record(session, crew, include_members=True)
    assigned_personnel = None
    if task.assigned_personnel_uid:
        personnel = session.get(db.Personnel, task.assigned_personnel_uid)
        if personnel is not None and personnel.deleted_at is None:
            assigned_personnel = _personnel_record(personnel)
    return TaskDetailRecord(
        task=_task_record(session, task),
        assigned_crew=assigned_crew,
        assigned_personnel=assigned_personnel,
        events=_task_event_records(session, task.uid),
    )


def _personnel_current_status_record(
    session: Session,
    personnel: db.Personnel,
    *,
    include_completed_tasks: bool,
) -> PersonnelCurrentStatusRecord:
    crew_rows = session.execute(
        select(db.CrewMember, db.Crew)
        .join(db.Crew, db.CrewMember.crew_uid == db.Crew.uid)
        .where(
            db.CrewMember.personnel_uid == personnel.uid,
            db.Crew.project_uid == personnel.project_uid,
            db.Crew.deleted_at.is_(None),
        )
        .order_by(db.CrewMember.active.desc(), db.Crew.name)
    ).all()
    crew_statuses = [
        PersonnelCrewStatus(
            crew_uid=crew.uid,
            crew_name=crew.name,
            crew_type=crew.crew_type,
            role_in_crew=member.role_in_crew,
            active=member.active,
        )
        for member, crew in crew_rows
    ]
    active_crew_uids = [crew.uid for member, crew in crew_rows if member.active]

    terminal_statuses = {"approved", "cancelled", "abandoned", "superseded"}
    assignment_clause = db.Task.assigned_personnel_uid == personnel.uid
    if active_crew_uids:
        assignment_clause = or_(assignment_clause, db.Task.assigned_crew_uid.in_(active_crew_uids))
    task_clauses = [
        db.Task.project_uid == personnel.project_uid,
        db.Task.deleted_at.is_(None),
        assignment_clause,
    ]
    if not include_completed_tasks:
        task_clauses.append(db.Task.status.notin_(terminal_statuses))
    task_rows = session.execute(
        select(db.Task)
        .where(*task_clauses)
        .order_by(db.Task.due_at, db.Task.created_at.desc(), db.Task.uid)
    ).scalars()
    tasks = [
        PersonnelTaskStatus(
            task_uid=task.uid,
            title=task.title,
            task_type=task.task_type,
            status=task.status,
            role="assignee" if task.assigned_personnel_uid == personnel.uid else "crew_member",
            assigned_crew_uid=task.assigned_crew_uid,
            due_at=task.due_at,
        )
        for task in task_rows
    ]
    return PersonnelCurrentStatusRecord(
        personnel=_personnel_record(personnel),
        project_uid=personnel.project_uid,
        crews=crew_statuses,
        assigned_tasks=tasks,
    )


def _model_payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _is_lock_not_available(exc: OperationalError) -> bool:
    original = getattr(exc, "orig", None)
    return getattr(original, "sqlstate", None) == "55P03" or getattr(original, "pgcode", None) == "55P03"


def _validate_personnel_project(session: Session, project_uid: str, personnel_uid: str) -> None:
    personnel = _get_active(session, db.Personnel, personnel_uid, "Personnel")
    if personnel.project_uid != project_uid:
        raise HTTPException(status_code=422, detail="Personnel must belong to the task project.")


def _validate_task_assignment(
    session: Session,
    project_uid: str,
    crew_uid: str | None,
    personnel_uid: str | None,
) -> None:
    if crew_uid:
        crew = _get_active(session, db.Crew, crew_uid, "Crew")
        if crew.project_uid != project_uid:
            raise HTTPException(status_code=422, detail="Crew must belong to the task project.")
    if personnel_uid:
        _validate_personnel_project(session, project_uid, personnel_uid)


def _add_task_event(
    session: Session,
    task_uid: str,
    event_type: str,
    user: AuthUser,
    *,
    actor_personnel_uid: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    _ensure_user(session, user)
    session.add(
        db.TaskEvent(
            task_uid=task_uid,
            event_type=event_type,
            actor_user_uid=user.uid,
            actor_personnel_uid=actor_personnel_uid,
            payload=payload or {},
        )
    )


def _ensure_user(session: Session, user: AuthUser) -> None:
    existing = session.get(db.User, user.uid)
    if existing is None:
        session.add(
            db.User(
                uid=user.uid,
                display_name=user.display_name or user.uid,
                role=user.role.value,
            )
        )
        session.flush()
        return
    if existing.role != user.role.value:
        existing.role = user.role.value


def _personnel_record(row: db.Personnel) -> PersonnelRecord:
    return PersonnelRecord(
        uid=row.uid,
        project_uid=row.project_uid,
        employee_uid=row.employee_uid,
        user_uid=row.user_uid,
        display_name=row.display_name,
        email=row.email,
        phone=row.phone,
        trade=row.trade,
        company=row.company,
        active=row.active,
        metadata_json=dict(row.metadata_json),
    )


def _crew_record(session: Session, row: db.Crew, *, include_members: bool) -> CrewRecord:
    members: list[CrewMemberRecord] = []
    if include_members:
        member_rows = session.execute(
            select(db.CrewMember, db.Personnel)
            .join(db.Personnel, db.CrewMember.personnel_uid == db.Personnel.uid)
            .where(db.CrewMember.crew_uid == row.uid)
            .order_by(db.CrewMember.active.desc(), db.CrewMember.role_in_crew, db.Personnel.display_name)
        ).all()
        members = [
            CrewMemberRecord(
                personnel_uid=member.personnel_uid,
                role_in_crew=member.role_in_crew,
                active=member.active,
                personnel=_personnel_record(personnel),
            )
            for member, personnel in member_rows
        ]
    return CrewRecord(
        uid=row.uid,
        project_uid=row.project_uid,
        name=row.name,
        crew_type=row.crew_type,
        active=row.active,
        metadata_json=dict(row.metadata_json),
        members=members,
    )


def _task_record(session: Session, row: db.Task) -> TaskRecord:
    entities = session.execute(
        select(db.TaskEntity)
        .where(db.TaskEntity.task_uid == row.uid)
        .order_by(db.TaskEntity.sequence, db.TaskEntity.entity_type, db.TaskEntity.entity_uid)
    ).scalars()
    return TaskRecord(
        uid=row.uid,
        project_uid=row.project_uid,
        title=row.title,
        description=row.description,
        task_type=row.task_type,
        status=row.status,
        priority=row.priority,
        created_by_user_uid=row.created_by_user_uid,
        assigned_crew_uid=row.assigned_crew_uid,
        assigned_personnel_uid=row.assigned_personnel_uid,
        submitted_by_personnel_uid=row.submitted_by_personnel_uid,
        reviewed_by_user_uid=row.reviewed_by_user_uid,
        applied_by_user_uid=row.applied_by_user_uid,
        entity_type=row.entity_type,
        entity_filter_payload=dict(row.entity_filter_payload),
        target_payload=dict(row.target_payload),
        submission_payload=dict(row.submission_payload),
        review_note=row.review_note,
        due_at=row.due_at,
        started_at=row.started_at,
        submitted_at=row.submitted_at,
        reviewed_at=row.reviewed_at,
        applied_at=row.applied_at,
        cancelled_at=row.cancelled_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        entities=[
            TaskEntityRecord(entity_type=entity.entity_type, entity_uid=entity.entity_uid, sequence=entity.sequence)
            for entity in entities
        ],
    )
