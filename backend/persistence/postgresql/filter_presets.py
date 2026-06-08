from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


FilterFieldType = Literal["text", "number", "enum", "boolean"]
FilterLogic = Literal["and", "or"]


TEXT_OPERATORS = {"equals", "not_equals", "in", "not_in", "contains", "starts_with", "is_blank", "is_not_blank"}
ENUM_OPERATORS = {"equals", "not_equals", "in", "not_in", "is_blank", "is_not_blank"}
NUMBER_OPERATORS = {"equals", "not_equals", "in", "not_in", "between", "gt", "gte", "lt", "lte", "is_blank", "is_not_blank"}
BOOLEAN_OPERATORS = {"equals", "not_equals", "is_blank", "is_not_blank"}
BLANK_OPERATORS = {"is_blank", "is_not_blank"}
COMPARISON_OPERATORS = {"between", "gt", "gte", "lt", "lte"}


@dataclass(frozen=True)
class FilterFieldDefinition:
    field_type: FilterFieldType
    enum_values: frozenset[str] | None = None


FILTER_FIELD_DEFINITIONS: dict[str, dict[str, FilterFieldDefinition]] = {
    "cabinet": {
        "uid": FilterFieldDefinition("text"),
        "cabinet_id": FilterFieldDefinition("text"),
        "room_uid": FilterFieldDefinition("text"),
        "category": FilterFieldDefinition("text"),
        "cabinet_group": FilterFieldDefinition("text"),
        "lifecycle_status": FilterFieldDefinition("enum"),
        "construction_phase": FilterFieldDefinition("enum"),
        "source_row": FilterFieldDefinition("number"),
        "source_col": FilterFieldDefinition("number"),
    },
    "device": {
        "uid": FilterFieldDefinition("text"),
        "cabinet_uid": FilterFieldDefinition("text"),
        "device_model_name": FilterFieldDefinition("text"),
        "rack_unit": FilterFieldDefinition("number"),
        "rack_units": FilterFieldDefinition("number"),
        "lifecycle_status": FilterFieldDefinition("enum"),
        "construction_phase": FilterFieldDefinition("enum"),
        "note": FilterFieldDefinition("text"),
    },
    "cable": {
        "uid": FilterFieldDefinition("text"),
        "cable_type": FilterFieldDefinition("text"),
        "status": FilterFieldDefinition("text"),
        "construction_phase": FilterFieldDefinition("enum"),
        "length_used_meters": FilterFieldDefinition("number"),
        "designed_length_meters": FilterFieldDefinition("number"),
        "group": FilterFieldDefinition("text"),
        "a_port_uid": FilterFieldDefinition("text"),
        "z_port_uid": FilterFieldDefinition("text"),
        "note": FilterFieldDefinition("text"),
    },
    "port": {
        "uid": FilterFieldDefinition("text"),
        "connector_type": FilterFieldDefinition("enum"),
        "cabinet_uid": FilterFieldDefinition("text"),
        "device_uid": FilterFieldDefinition("text"),
        "room_uid": FilterFieldDefinition("text"),
        "note": FilterFieldDefinition("text"),
    },
    "bundle": {
        "uid": FilterFieldDefinition("text"),
        "scoped_uid": FilterFieldDefinition("text"),
        "room_uid": FilterFieldDefinition("text"),
        "name": FilterFieldDefinition("text"),
        "lifecycle_status": FilterFieldDefinition("enum"),
        "construction_phase": FilterFieldDefinition("enum"),
        "note": FilterFieldDefinition("text"),
    },
}


class FilterRule(BaseModel):
    field: str
    operator: str
    value: Any = None


class FilterPayload(BaseModel):
    version: int = 1
    logic: FilterLogic = "and"
    rules: list[FilterRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_version(self) -> "FilterPayload":
        if self.version != 1:
            raise ValueError("filter_payload version must be 1.")
        return self


def validate_filter_payload(entity_type: str, payload: dict[str, Any]) -> FilterPayload:
    normalized_entity_type = entity_type.strip().lower()
    field_definitions = FILTER_FIELD_DEFINITIONS.get(normalized_entity_type)
    if field_definitions is None:
        raise ValueError("entity_type must be one of: cabinet, device, cable, port, bundle.")

    filter_payload = FilterPayload.model_validate(payload)
    for rule in filter_payload.rules:
        _validate_rule(rule, field_definitions)
    return filter_payload


def _validate_rule(rule: FilterRule, field_definitions: dict[str, FilterFieldDefinition]) -> None:
    field_definition = field_definitions.get(rule.field)
    if field_definition is None:
        raise ValueError(f"Unsupported filter field '{rule.field}'.")

    operator = rule.operator.strip().lower()
    allowed_operators = _allowed_operators(field_definition.field_type)
    if operator not in allowed_operators:
        raise ValueError(f"Operator '{rule.operator}' is not valid for {field_definition.field_type} field '{rule.field}'.")

    if operator in BLANK_OPERATORS:
        if rule.value is not None:
            raise ValueError(f"Operator '{operator}' must not include a value.")
        return

    if operator in {"in", "not_in"}:
        if not isinstance(rule.value, list) or not rule.value:
            raise ValueError(f"Operator '{operator}' requires a non-empty list value.")
        for item in rule.value:
            _validate_scalar_value(rule.field, field_definition, item)
        return

    if operator == "between":
        if not isinstance(rule.value, list) or len(rule.value) != 2:
            raise ValueError("Operator 'between' requires a two-item numeric list value.")
        for item in rule.value:
            _validate_number_value(rule.field, item)
        return

    if operator in COMPARISON_OPERATORS:
        _validate_number_value(rule.field, rule.value)
        return

    _validate_scalar_value(rule.field, field_definition, rule.value)


def _allowed_operators(field_type: FilterFieldType) -> set[str]:
    if field_type == "text":
        return TEXT_OPERATORS
    if field_type == "number":
        return NUMBER_OPERATORS
    if field_type == "enum":
        return ENUM_OPERATORS
    if field_type == "boolean":
        return BOOLEAN_OPERATORS
    raise ValueError(f"Unsupported filter field type '{field_type}'.")


def _validate_scalar_value(field: str, field_definition: FilterFieldDefinition, value: Any) -> None:
    if field_definition.field_type == "number":
        _validate_number_value(field, value)
        return
    if field_definition.field_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"Field '{field}' requires a boolean value.")
        return
    if not isinstance(value, str):
        raise ValueError(f"Field '{field}' requires a string value.")
    if field_definition.enum_values is not None and value not in field_definition.enum_values:
        raise ValueError(f"Field '{field}' does not allow value '{value}'.")


def _validate_number_value(field: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"Field '{field}' requires a numeric value.")
