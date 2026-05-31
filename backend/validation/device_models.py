from __future__ import annotations

import re
from collections import Counter, defaultdict

from pydantic import BaseModel, Field


class DeviceModelRowExample(BaseModel):
    side: str
    status: str
    group: str
    port_uid: str
    cable_type: str
    device_name: str = ""
    device_model: str


class DeviceModelCount(BaseModel):
    value: str
    count: int


class DeviceModelFinding(BaseModel):
    device_uid: str
    classification: str
    models: list[DeviceModelCount]
    normalized_models: list[DeviceModelCount]
    examples: list[DeviceModelRowExample] = Field(default_factory=list)


def detect_device_model_findings(rows) -> tuple[list[DeviceModelFinding], list[DeviceModelFinding]]:
    model_observations: dict[str, list[DeviceModelRowExample]] = defaultdict(list)

    for row in rows:
        for side in ("a", "z"):
            device_model = getattr(row, f"{side}_device_model")
            if not device_model:
                continue

            device_uid = _device_uid(
                getattr(row, f"{side}_data_hall_id"),
                getattr(row, f"{side}_cabinet_id"),
                getattr(row, f"{side}_rack_unit"),
            )
            model_observations[device_uid].append(
                DeviceModelRowExample(
                    side=side,
                    status=row.status,
                    group=row.group,
                    port_uid=getattr(row, f"{side}_port_uid"),
                    cable_type=row.cable_type,
                    device_name=getattr(row, f"{side}_device_name"),
                    device_model=device_model,
                )
            )

    mismatches: list[DeviceModelFinding] = []
    format_issues: list[DeviceModelFinding] = []
    for device_uid, examples in sorted(model_observations.items()):
        model_counts = Counter(example.device_model for example in examples)
        if len(model_counts) <= 1:
            continue

        normalized_counts = Counter()
        for model, count in model_counts.items():
            normalized_counts[normalize_device_model(model)] += count

        finding = DeviceModelFinding(
            device_uid=device_uid,
            classification="model_mismatch" if len(normalized_counts) > 1 else "trivial_format_issue",
            models=_model_counts(model_counts),
            normalized_models=_model_counts(normalized_counts),
            examples=examples[:10],
        )
        if len(normalized_counts) > 1:
            mismatches.append(finding)
        else:
            format_issues.append(finding)

    return mismatches, format_issues


def normalize_device_model(model: str) -> str:
    normalized = model.upper().strip()
    normalized = re.sub(r"\b(NVIDIA|MELLANOX|NOKIA|CW)\b", "", normalized)
    normalized = re.sub(r"[^A-Z0-9]+", "", normalized)
    return normalized


def _model_counts(counter: Counter[str]) -> list[DeviceModelCount]:
    return [DeviceModelCount(value=value, count=count) for value, count in sorted(counter.items())]


def _device_uid(data_hall_id: str, cabinet_id: str, rack_unit: int) -> str:
    return f"{data_hall_id}:{cabinet_id}:{rack_unit}".upper()
