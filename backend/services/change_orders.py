from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.config import DEFAULT_PROJECT_UID
from backend.persistence.postgresql import models as db


TERMINAL_TASK_STATUSES = {"approved", "cancelled", "abandoned", "superseded"}
INACTIVE_CABLE_STATUSES = {"removed", "retired", "replaced", "canceled", "cancelled"}
CHANGE_ORDER_TERMINAL_STATUSES = {"complete", "rejected", "cancelled", "blocked", "superseded"}
CABLE_CHANGE_INTENTS = {
    "label_change",
    "port_change",
    "replace_cable",
    "retire_cable",
    "remove_cable",
    "add_cable",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def create_change_order(
    session: Session,
    *,
    project_uid: str = DEFAULT_PROJECT_UID,
    uid: str | None = None,
    change_order_number: int | None = None,
    title: str = "",
    description: str = "",
    source_type: str = "manual",
    source_uid: str = "",
    requested_by_user_uid: str | None = None,
    items: list[dict[str, Any]],
) -> db.ChangeOrder:
    if not items:
        raise HTTPException(status_code=422, detail="Change order requires at least one cable item.")
    if change_order_number is None:
        max_number = session.execute(
            select(func.max(db.ChangeOrder.change_order_number)).where(db.ChangeOrder.project_uid == project_uid)
        ).scalar_one()
        change_order_number = int(max_number or 0) + 1
    if change_order_number == 0:
        raise HTTPException(status_code=422, detail="Change order #0 is reserved for initial topology ingestion.")

    order = db.ChangeOrder(
        uid=uid or new_uid("co"),
        project_uid=project_uid,
        change_order_number=change_order_number,
        title=title,
        description=description,
        status="resolved",
        source_type=source_type,
        source_uid=source_uid,
        requested_by_user_uid=requested_by_user_uid,
    )
    session.add(order)
    session.flush()

    normalized_items = []
    for sequence, payload in enumerate(items, start=1):
        item = _create_item(session, order, sequence, payload)
        normalized_items.append(_item_payload(item))
    order.items_payload = normalized_items
    order.summary = _summary_for_items(normalized_items)
    _add_event(session, order.uid, "created", requested_by_user_uid, {"item_count": len(normalized_items)})
    return order


def approve_change_order(session: Session, *, change_order_uid: str, reviewed_by_user_uid: str | None) -> db.ChangeOrder:
    order = _locked_order(session, change_order_uid)
    if order.change_order_number == 0:
        raise HTTPException(status_code=409, detail="Change order #0 cannot be approved for execution.")
    if order.status not in {"resolved", "review_ready"}:
        raise HTTPException(status_code=409, detail=f"Cannot approve a {order.status} change order.")
    order.status = "approved"
    order.reviewed_by_user_uid = reviewed_by_user_uid
    order.approved_at = now_utc()
    order.updated_at = order.approved_at
    _add_event(session, order.uid, "approved", reviewed_by_user_uid, {})
    return order


def generate_change_order_tasks(session: Session, *, change_order_uid: str, user_uid: str | None) -> db.ChangeOrder:
    order = _locked_order(session, change_order_uid)
    if order.status not in {"approved", "executing", "partially_complete"}:
        raise HTTPException(status_code=409, detail="Only approved change orders can generate tasks.")
    items = session.execute(
        select(db.ChangeOrderItem)
        .where(db.ChangeOrderItem.change_order_uid == order.uid)
        .order_by(db.ChangeOrderItem.sequence, db.ChangeOrderItem.uid)
    ).scalars().all()
    if not items:
        raise HTTPException(status_code=422, detail="Change order has no items.")

    for item in items:
        _apply_immediate_definition_changes(session, order, item, user_uid=user_uid)
        _supersede_existing_tasks(session, order, item, user_uid=user_uid)
        _ensure_tasks_for_item(session, order, item, user_uid=user_uid)
        if item.status == "pending":
            item.status = "ready"
    order.status = "executing"
    order.updated_at = now_utc()
    _sync_order_payload(session, order)
    _add_event(session, order.uid, "tasks_generated", user_uid, {"item_count": len(items)})
    return order


def apply_change_order_task_completion(session: Session, *, task: db.Task, actor_user_uid: str | None) -> None:
    links = session.execute(
        select(db.ChangeOrderTaskLink).where(db.ChangeOrderTaskLink.task_uid == task.uid)
    ).scalars().all()
    if not links:
        return
    for link in links:
        order = session.get(db.ChangeOrder, link.change_order_uid)
        item = session.get(db.ChangeOrderItem, link.change_order_item_uid)
        if order is None or item is None:
            continue
        if link.effect_type in {"label_update", "port_update", "definition_update"}:
            _apply_item_definition(session, order, item, actor_user_uid=actor_user_uid, effect_type=link.effect_type)
        _maybe_complete_item(session, item, actor_user_uid=actor_user_uid)
        _maybe_complete_order(session, order, actor_user_uid=actor_user_uid)


def _create_item(session: Session, order: db.ChangeOrder, sequence: int, payload: dict[str, Any]) -> db.ChangeOrderItem:
    intent = _required_str(payload, "intent")
    if intent not in CABLE_CHANGE_INTENTS:
        raise HTTPException(status_code=422, detail=f"Unsupported cable change intent '{intent}'.")
    old_uid = _optional_uid(payload.get("old_entity_uid") or payload.get("old_cable_uid") or payload.get("cable_uid"))
    new_uid_value = _optional_uid(payload.get("new_entity_uid") or payload.get("new_cable_uid"))
    entity_uid = _optional_uid(payload.get("entity_uid")) or new_uid_value or old_uid
    if not entity_uid:
        raise HTTPException(status_code=422, detail="Cable change item requires an entity_uid, old cable UID, or new cable UID.")
    before_definition = _definition_with_default_labels(dict(payload.get("before_definition") or {}))
    after_definition = _definition_with_default_labels(dict(payload.get("after_definition") or {}))
    task_plan = list(payload.get("task_plan") or _default_task_plan(intent, before_definition, after_definition))
    item = db.ChangeOrderItem(
        uid=str(payload.get("uid") or new_uid("co-item")),
        change_order_uid=order.uid,
        sequence=sequence,
        entity_type="cable",
        entity_uid=entity_uid,
        intent=intent,
        status="pending",
        old_entity_uid=old_uid,
        new_entity_uid=new_uid_value,
        before_definition=before_definition,
        after_definition=after_definition,
        task_plan=task_plan,
    )
    session.add(item)
    session.flush()
    return item


def _default_task_plan(intent: str, before_definition: dict[str, Any], after_definition: dict[str, Any]) -> list[dict[str, Any]]:
    if intent == "label_change":
        return [{"task_type": "cable_label", "effect_type": "label_update", "target_status": "relabeled"}]
    if intent == "port_change":
        plan = []
        if _labels_changed(before_definition, after_definition):
            plan.append({"task_type": "cable_label", "effect_type": "label_update", "target_status": "relabeled"})
        plan.append({"task_type": "cable_termination", "effect_type": "port_update", "target_status": "relabeled"})
        if _cabinet_side_changed(before_definition, after_definition):
            plan.append({"task_type": "cable_dress", "effect_type": "port_update", "target_status": "relabeled"})
        return plan
    if intent == "replace_cable":
        return _full_cycle_plan()
    if intent == "retire_cable":
        return [{"task_type": "cable_retirement", "effect_type": "status_update", "target_status": "retired"}]
    if intent == "remove_cable":
        return [{"task_type": "cable_removal", "effect_type": "status_update", "target_status": "removed"}]
    if intent == "add_cable":
        return _full_cycle_plan()
    return []


def _full_cycle_plan() -> list[dict[str, Any]]:
    return [
        {"task_type": "cable_pull", "effect_type": "status_update", "target_status": "Cable Not Run"},
        {"task_type": "cable_dress", "effect_type": "status_update", "target_status": "Cable Is Ran: Complete"},
        {"task_type": "cable_termination", "effect_type": "status_update", "target_status": "Cable Is Ran: Complete"},
        {"task_type": "cable_test", "effect_type": "status_update", "target_status": "Cable Is Ran: Complete"},
        {"task_type": "cable_label", "effect_type": "status_update", "target_status": "Cable Is Ran: Complete"},
    ]


def _apply_immediate_definition_changes(session: Session, order: db.ChangeOrder, item: db.ChangeOrderItem, *, user_uid: str | None) -> None:
    if item.result_payload.get("immediate_definition_applied"):
        return
    if item.intent == "replace_cable":
        old_uid = item.old_entity_uid or item.entity_uid
        new_uid_value = item.new_entity_uid or str(item.after_definition.get("uid") or item.entity_uid).upper()
        if old_uid:
            old_cable = _locked_cable(session, old_uid)
            _set_cable_status(session, order, old_cable, "replaced", user_uid=user_uid, payload={"new_cable_uid": new_uid_value})
        _create_cable_if_missing(session, order, item, user_uid=user_uid)
        item.result_payload = {**item.result_payload, "immediate_definition_applied": True, "new_cable_uid": new_uid_value}
    elif item.intent == "add_cable":
        _create_cable_if_missing(session, order, item, user_uid=user_uid)
        item.result_payload = {**item.result_payload, "immediate_definition_applied": True}


def _create_cable_if_missing(session: Session, order: db.ChangeOrder, item: db.ChangeOrderItem, *, user_uid: str | None) -> db.Cable:
    definition = dict(item.after_definition)
    cable_uid = str(item.new_entity_uid or definition.get("uid") or item.entity_uid).upper()
    existing = session.get(db.Cable, cable_uid)
    if existing is not None:
        if _is_active_status(existing.import_status):
            raise HTTPException(status_code=409, detail=f"Active cable '{cable_uid}' already exists.")
        return existing
    a_port_uid = _required_definition_uid(definition, "a_port_uid")
    z_port_uid = _required_definition_uid(definition, "z_port_uid")
    a_port = _port(session, a_port_uid)
    z_port = _port(session, z_port_uid)
    cable = db.Cable(
        uid=cable_uid,
        project_uid=order.project_uid,
        building_uid=a_port.building_uid,
        room_uid=a_port.room_uid if a_port.room_uid == z_port.room_uid else None,
        a_port_uid=a_port.uid,
        z_port_uid=z_port.uid,
        cable_type=str(definition.get("cable_type") or ""),
        cable_group=str(definition.get("cable_group") or definition.get("group") or ""),
        import_status=str(definition.get("status") or "Cable Not Run"),
        construction_phase=str(definition.get("construction_phase") or "Management & Ethernet"),
        a_label_text=str(_definition_with_default_labels(definition).get("a_label_text") or ""),
        z_label_text=str(_definition_with_default_labels(definition).get("z_label_text") or ""),
        designed_length_meters=_decimal_or_none(definition.get("designed_length_meters")),
        length_used_meters=_decimal_or_zero(definition.get("length_used_meters")),
        a_optic=definition.get("a_optic"),
        z_optic=definition.get("z_optic"),
        note=str(definition.get("note") or ""),
    )
    session.add(cable)
    session.flush()
    _append_operation(
        session,
        order,
        entity_uid=cable.uid,
        operation_type="change_order_create",
        before={},
        after=_definition_from_cable(cable),
        user_uid=user_uid,
    )
    return cable


def _ensure_tasks_for_item(session: Session, order: db.ChangeOrder, item: db.ChangeOrderItem, *, user_uid: str | None) -> None:
    existing_links = session.execute(
        select(db.ChangeOrderTaskLink).where(db.ChangeOrderTaskLink.change_order_item_uid == item.uid)
    ).scalars().all()
    if existing_links:
        return
    target_cable_uid = item.new_entity_uid if item.intent in {"replace_cable", "add_cable"} else item.old_entity_uid or item.entity_uid
    target_cable_uid = str(target_cable_uid or item.entity_uid).upper()
    for index, plan in enumerate(item.task_plan, start=1):
        task_uid = new_uid("task")
        task_type = str(plan.get("task_type") or "cable_rework")
        effect_type = str(plan.get("effect_type") or "status_update")
        target_status = str(plan.get("target_status") or item.after_definition.get("status") or "Cable Not Run")
        task = db.Task(
            uid=task_uid,
            project_uid=order.project_uid,
            title=str(plan.get("title") or _task_title(order, item, task_type, index)),
            description=str(plan.get("description") or f"Generated from change order {order.change_order_number} item {item.sequence}."),
            task_type=task_type,
            status="draft",
            priority=str(plan.get("priority") or "normal"),
            created_by_user_uid=user_uid,
            entity_type="cable",
            target_payload={
                "status": target_status,
                "change_order_uid": order.uid,
                "change_order_item_uid": item.uid,
                "effect_type": effect_type,
            },
        )
        session.add(task)
        session.add(db.TaskEntity(task_uid=task_uid, entity_type="cable", entity_uid=target_cable_uid, sequence=0))
        session.add(db.ChangeOrderTaskLink(change_order_uid=order.uid, change_order_item_uid=item.uid, task_uid=task_uid, effect_type=effect_type))
        _add_task_event(session, task_uid, "created", user_uid, {"change_order_uid": order.uid, "change_order_item_uid": item.uid})


def _supersede_existing_tasks(session: Session, order: db.ChangeOrder, item: db.ChangeOrderItem, *, user_uid: str | None) -> None:
    entity_uids = {uid for uid in [item.old_entity_uid, item.new_entity_uid, item.entity_uid] if uid}
    if not entity_uids:
        return
    task_rows = session.execute(
        select(db.Task)
        .join(db.TaskEntity, db.TaskEntity.task_uid == db.Task.uid)
        .where(
            db.Task.project_uid == order.project_uid,
            db.Task.entity_type == "cable",
            db.TaskEntity.entity_uid.in_(entity_uids),
            db.Task.status.notin_(TERMINAL_TASK_STATUSES),
            db.Task.deleted_at.is_(None),
        )
    ).scalars().all()
    for task in task_rows:
        task.status = "superseded"
        task.updated_at = now_utc()
        _add_task_event(session, task.uid, "superseded", user_uid, {"change_order_uid": order.uid, "change_order_item_uid": item.uid})


def _apply_item_definition(session: Session, order: db.ChangeOrder, item: db.ChangeOrderItem, *, actor_user_uid: str | None, effect_type: str) -> None:
    if item.result_payload.get(f"{effect_type}_applied"):
        return
    cable_uid = item.old_entity_uid or item.entity_uid
    if not cable_uid:
        return
    cable = _locked_cable(session, cable_uid)
    before = _definition_from_cable(cable)
    _apply_definition_to_cable(cable, item.after_definition, effect_type=effect_type)
    after = _definition_from_cable(cable)
    if before != after:
        _append_operation(
            session,
            order,
            entity_uid=cable.uid,
            operation_type="change_order_definition_update",
            before=before,
            after=after,
            user_uid=actor_user_uid,
        )
    item.result_payload = {**item.result_payload, f"{effect_type}_applied": True}
    _add_event(session, order.uid, "definition_updated", actor_user_uid, {"item_uid": item.uid, "effect_type": effect_type})


def _apply_definition_to_cable(cable: db.Cable, definition: dict[str, Any], *, effect_type: str) -> None:
    definition = _definition_with_default_labels(
        {
            "a_port_uid": cable.a_port_uid,
            "z_port_uid": cable.z_port_uid,
            **definition,
        }
    )
    if effect_type in {"label_update", "definition_update"}:
        if "a_label_text" in definition:
            cable.a_label_text = str(definition.get("a_label_text") or "")
        if "z_label_text" in definition:
            cable.z_label_text = str(definition.get("z_label_text") or "")
    if effect_type in {"port_update", "definition_update"}:
        for field in ("a_port_uid", "z_port_uid", "cable_type", "construction_phase"):
            if field in definition:
                setattr(cable, field, str(definition.get(field) or ""))
        if "cable_group" in definition or "group" in definition:
            cable.cable_group = str(definition.get("cable_group") or definition.get("group") or "")
        if "designed_length_meters" in definition:
            cable.designed_length_meters = _decimal_or_none(definition.get("designed_length_meters"))
    cable.updated_at = now_utc()


def _maybe_complete_item(session: Session, item: db.ChangeOrderItem, *, actor_user_uid: str | None) -> None:
    linked_tasks = session.execute(
        select(db.Task)
        .join(db.ChangeOrderTaskLink, db.ChangeOrderTaskLink.task_uid == db.Task.uid)
        .where(db.ChangeOrderTaskLink.change_order_item_uid == item.uid)
    ).scalars().all()
    if linked_tasks and all(task.applied_at is not None for task in linked_tasks):
        if item.status != "complete":
            item.status = "complete"
            item.updated_at = now_utc()
            order_uid = item.change_order_uid
            _add_event(session, order_uid, "item_complete", actor_user_uid, {"item_uid": item.uid})


def _maybe_complete_order(session: Session, order: db.ChangeOrder, *, actor_user_uid: str | None) -> None:
    items = session.execute(select(db.ChangeOrderItem).where(db.ChangeOrderItem.change_order_uid == order.uid)).scalars().all()
    if items and all(item.status == "complete" for item in items):
        order.status = "complete"
        order.completed_at = now_utc()
    elif any(item.status == "complete" for item in items):
        order.status = "partially_complete"
    else:
        order.status = "executing"
    order.updated_at = now_utc()
    _sync_order_payload(session, order)
    if order.status == "complete":
        _add_event(session, order.uid, "complete", actor_user_uid, {})


def _sync_order_payload(session: Session, order: db.ChangeOrder) -> None:
    items = session.execute(
        select(db.ChangeOrderItem)
        .where(db.ChangeOrderItem.change_order_uid == order.uid)
        .order_by(db.ChangeOrderItem.sequence, db.ChangeOrderItem.uid)
    ).scalars().all()
    payload = [_item_payload(item) for item in items]
    order.items_payload = payload
    order.summary = _summary_for_items(payload)


def _set_cable_status(session: Session, order: db.ChangeOrder, cable: db.Cable, status: str, *, user_uid: str | None, payload: dict[str, Any]) -> None:
    before = {"status": cable.import_status}
    cable.import_status = status
    cable.updated_at = now_utc()
    after = {"status": cable.import_status, **payload}
    _append_operation(
        session,
        order,
        entity_uid=cable.uid,
        operation_type="change_order_status_update",
        before=before,
        after=after,
        user_uid=user_uid,
    )


def _append_operation(
    session: Session,
    order: db.ChangeOrder,
    *,
    entity_uid: str,
    operation_type: str,
    before: dict[str, Any],
    after: dict[str, Any],
    user_uid: str | None,
) -> db.OperationLog:
    operation = db.OperationLog(
        project_uid=order.project_uid,
        entity_type="cable",
        entity_uid=entity_uid,
        operation_type=operation_type,
        operation_group_uid=f"change_order:{order.uid}",
        source_type="change_order",
        source_uid=order.uid,
        before=before,
        after=after,
        user_uid=user_uid,
    )
    session.add(operation)
    session.flush()
    return operation


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


def _summary_for_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_intent: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in items:
        by_intent[str(item.get("intent") or "unknown")] = by_intent.get(str(item.get("intent") or "unknown"), 0) + 1
        by_status[str(item.get("status") or "unknown")] = by_status.get(str(item.get("status") or "unknown"), 0) + 1
    return {"item_count": len(items), "by_intent": by_intent, "by_status": by_status}


def _definition_from_cable(cable: db.Cable) -> dict[str, Any]:
    return {
        "uid": cable.uid,
        "a_port_uid": cable.a_port_uid,
        "z_port_uid": cable.z_port_uid,
        "cable_type": cable.cable_type,
        "cable_group": cable.cable_group,
        "status": cable.import_status,
        "construction_phase": cable.construction_phase,
        "a_label_text": cable.a_label_text,
        "z_label_text": cable.z_label_text,
        "designed_length_meters": float(cable.designed_length_meters) if cable.designed_length_meters is not None else None,
        "length_used_meters": float(cable.length_used_meters or 0),
        "note": cable.note,
    }


def _locked_order(session: Session, uid: str) -> db.ChangeOrder:
    order = session.execute(select(db.ChangeOrder).where(db.ChangeOrder.uid == uid).with_for_update()).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Change order was not found.")
    if order.status in CHANGE_ORDER_TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail=f"Cannot modify a {order.status} change order.")
    return order


def _locked_cable(session: Session, uid: str) -> db.Cable:
    cable = session.execute(select(db.Cable).where(db.Cable.uid == uid.upper()).with_for_update()).scalar_one_or_none()
    if cable is None:
        raise HTTPException(status_code=404, detail=f"Cable '{uid}' was not found.")
    return cable


def _port(session: Session, uid: str) -> db.Port:
    port = session.get(db.Port, uid.upper())
    if port is None:
        raise HTTPException(status_code=404, detail=f"Port '{uid}' was not found.")
    return port


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"Change order item requires {key}.")
    return value.strip()


def _required_definition_uid(definition: dict[str, Any], key: str) -> str:
    value = definition.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"Cable definition requires {key}.")
    return value.strip().upper()


def _optional_uid(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    return normalized or None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _decimal_or_zero(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _is_active_status(status: str | None) -> bool:
    return str(status or "").strip().lower() not in INACTIVE_CABLE_STATUSES


def _definition_with_default_labels(definition: dict[str, Any]) -> dict[str, Any]:
    a_port_uid = str(definition.get("a_port_uid") or "").strip()
    z_port_uid = str(definition.get("z_port_uid") or "").strip()
    if not a_port_uid or not z_port_uid:
        return definition
    a_position = _label_position(a_port_uid)
    z_position = _label_position(z_port_uid)
    next_definition = dict(definition)
    if not str(next_definition.get("a_label_text") or "").strip():
        next_definition["a_label_text"] = f"{a_position}\n{z_position}"
    if not str(next_definition.get("z_label_text") or "").strip():
        next_definition["z_label_text"] = f"{z_position}\n{a_position}"
    return next_definition


def _label_position(port_uid: str) -> str:
    parts = [part.strip() for part in str(port_uid or "").split(":", 3)]
    if len(parts) != 4:
        return str(port_uid or "").strip()
    data_hall, cabinet, rack_unit, port_name = parts
    data_hall = data_hall.lower()
    cabinet = cabinet.zfill(3) if cabinet.isdigit() else cabinet
    if rack_unit.isdigit():
        rack_unit = str(int(rack_unit)).zfill(2)
    return f"{data_hall}:{cabinet}:{rack_unit}:{port_name}"

def _labels_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    before = _definition_with_default_labels(before)
    after = _definition_with_default_labels(after)
    return any(before.get(field) != after.get(field) for field in ("a_label_text", "z_label_text"))


def _cabinet_side_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return any(_cabinet_key(before.get(field)) != _cabinet_key(after.get(field)) for field in ("a_port_uid", "z_port_uid"))


def _cabinet_key(port_uid: Any) -> str:
    parts = str(port_uid or "").split(":")
    return ":".join(parts[:2]) if len(parts) >= 2 else ""


def _task_title(order: db.ChangeOrder, item: db.ChangeOrderItem, task_type: str, index: int) -> str:
    label = task_type.replace("_", " ").title()
    return f"CO {order.change_order_number} item {item.sequence}: {label} {index}"


def _add_event(session: Session, change_order_uid: str, event_type: str, actor_user_uid: str | None, payload: dict[str, Any]) -> None:
    session.add(db.ChangeOrderEvent(change_order_uid=change_order_uid, event_type=event_type, actor_user_uid=actor_user_uid, payload=payload))


def _add_task_event(session: Session, task_uid: str, event_type: str, actor_user_uid: str | None, payload: dict[str, Any]) -> None:
    session.add(db.TaskEvent(task_uid=task_uid, event_type=event_type, actor_user_uid=actor_user_uid, payload=payload))
