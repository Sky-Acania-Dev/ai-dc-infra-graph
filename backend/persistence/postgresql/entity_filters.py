from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from backend.persistence.postgresql import models as db
from backend.persistence.postgresql.filter_presets import FILTER_FIELD_DEFINITIONS, FilterPayload


SUPPORTED_ENTITY_TYPES = {"cable", "cabinet", "device", "port", "bundle"}


def resolve_entity_filter(session, *, project_uid: str, entity_type: str, filter_payload: FilterPayload, limit: int) -> list[str]:
    model_type = entity_model(entity_type)
    statement = select(model_type.uid).where(model_type.project_uid == project_uid, model_type.deleted_at.is_(None))
    clauses = [filter_rule_clause(entity_type, rule) for rule in filter_payload.rules]
    if clauses:
        statement = statement.where(or_(*clauses) if filter_payload.logic == "or" else and_(*clauses))
    return list(session.execute(statement.order_by(model_type.uid).limit(limit)).scalars())


def filter_rule_clause(entity_type: str, rule) -> Any:
    column = filter_column(entity_type, rule.field)
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
        if filter_field_type(entity_type, rule.field) == "text":
            return or_(column.is_(None), column == "")
        return column.is_(None)
    if operator == "is_not_blank":
        if filter_field_type(entity_type, rule.field) == "text":
            return and_(column.is_not(None), column != "")
        return column.is_not(None)
    raise HTTPException(status_code=422, detail=f"Unsupported filter operator '{rule.operator}'.")


def filter_column(entity_type: str, field: str) -> Any:
    model_type = entity_model(entity_type)
    field_map = {
        "cable": {"status": "import_status", "group": "cable_group"},
        "bundle": {"lifecycle_status": "lifecycle_status"},
    }
    column_name = field_map.get(entity_type, {}).get(field, field)
    if not hasattr(model_type, column_name):
        raise HTTPException(status_code=422, detail=f"Unsupported filter field '{field}'.")
    return getattr(model_type, column_name)


def filter_field_type(entity_type: str, field: str) -> str:
    return FILTER_FIELD_DEFINITIONS[entity_type][field].field_type


def entity_model(entity_type: str) -> type[Any]:
    model_map = {
        "cabinet": db.Cabinet,
        "device": db.Device,
        "cable": db.Cable,
        "port": db.Port,
        "bundle": db.CableBundle,
    }
    model_type = model_map.get(entity_type.strip().lower())
    if model_type is None:
        raise HTTPException(status_code=422, detail="entity_type must be one of: cable, cabinet, device, port, bundle.")
    return model_type
