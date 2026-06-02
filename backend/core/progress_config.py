from __future__ import annotations

from dataclasses import dataclass

from backend.core.enums import CableProgressPhaseType, CableProgressTaskType
from backend.models.topology import CableProgressPhase, CableProgressTask


@dataclass(frozen=True)
class CableProgressTaskDefinition:
    name: str
    task_type: CableProgressTaskType
    enum_values: tuple[str, ...] = ()
    default_value: float | str | None = None


@dataclass(frozen=True)
class CableProgressPhaseDefinition:
    name: str
    tasks: tuple[CableProgressTaskDefinition, ...]


DEFAULT_CABLE_PROGRESS_PHASES: tuple[CableProgressPhaseDefinition, ...] = (
    CableProgressPhaseDefinition(
        name="preparation",
        tasks=(
            CableProgressTaskDefinition(
                name="preparation",
                task_type=CableProgressTaskType.ENUM,
                enum_values=("ordered", "received", "labeled", "bundled", "pulled"),
                default_value="ordered",
            ),
        ),
    ),
    CableProgressPhaseDefinition(
        name="dress_termination",
        tasks=(
            CableProgressTaskDefinition(
                name="routing_dress",
                task_type=CableProgressTaskType.PERCENT,
                default_value=0.0,
            ),
            CableProgressTaskDefinition(
                name="a_side",
                task_type=CableProgressTaskType.ENUM,
                enum_values=("not_terminated", "terminated", "dressed"),
                default_value="not_terminated",
            ),
            CableProgressTaskDefinition(
                name="z_side",
                task_type=CableProgressTaskType.ENUM,
                enum_values=("not_terminated", "terminated", "dressed"),
                default_value="not_terminated",
            ),
        ),
    ),
    CableProgressPhaseDefinition(
        name="validation",
        tasks=(
            CableProgressTaskDefinition(
                name="validation",
                task_type=CableProgressTaskType.ENUM,
                enum_values=("validated", "failed", "broken"),
                default_value="validated",
            ),
        ),
    ),
)


_PHASES_BY_NAME = {phase.name: phase for phase in DEFAULT_CABLE_PROGRESS_PHASES}


def cable_progress_phase_definitions() -> tuple[CableProgressPhaseDefinition, ...]:
    return DEFAULT_CABLE_PROGRESS_PHASES


def cable_progress_phase_definition(name: str) -> CableProgressPhaseDefinition | None:
    return _PHASES_BY_NAME.get(name)


def default_cable_progress_phase(name: str | None = None) -> CableProgressPhase:
    definition = cable_progress_phase_definition(name or DEFAULT_CABLE_PROGRESS_PHASES[0].name)
    if definition is None:
        definition = DEFAULT_CABLE_PROGRESS_PHASES[0]
    return CableProgressPhase(
        name=definition.name,
        phase_type=_legacy_phase_type(definition),
        value=None,
        tasks={},
        enum_values=[],
        task_values={
            task.name: CableProgressTask(
                task_type=task.task_type,
                value=task.default_value,
                enum_values=list(task.enum_values),
            )
            for task in definition.tasks
        },
    )


def normalize_cable_progress_phase(phase: CableProgressPhase | None) -> CableProgressPhase:
    if phase is None:
        return default_cable_progress_phase()
    definition = cable_progress_phase_definition(phase.name)
    if definition is None:
        return _legacy_phase_to_current(phase)
    normalized = default_cable_progress_phase(definition.name)
    normalized.task_values = {
        task.name: _normalize_task(task, phase.task_values.get(task.name))
        for task in definition.tasks
    }
    return normalized


def cable_endpoint_termination_and_dress_percent(phase: CableProgressPhase | None, side: str) -> tuple[float, float]:
    normalized = normalize_cable_progress_phase(phase)
    if normalized.name == "validation":
        return 100.0, 100.0
    if normalized.name != "dress_termination":
        return 0.0, 0.0
    task = normalized.task_values.get(f"{side.lower()}_side")
    state = task.value if task else "not_terminated"
    if state == "dressed":
        return 100.0, 100.0
    if state == "terminated":
        return 100.0, 0.0
    return 0.0, 0.0


def _normalize_task(
    definition: CableProgressTaskDefinition,
    task: CableProgressTask | None,
) -> CableProgressTask:
    if task is None:
        return CableProgressTask(
            task_type=definition.task_type,
            value=definition.default_value,
            enum_values=list(definition.enum_values),
        )
    if definition.task_type == CableProgressTaskType.ENUM:
        value = task.value if isinstance(task.value, str) else definition.default_value
        if value not in definition.enum_values:
            value = definition.default_value
        return CableProgressTask(
            task_type=definition.task_type,
            value=value,
            enum_values=list(definition.enum_values),
        )
    value = task.value if isinstance(task.value, int | float) else definition.default_value
    return CableProgressTask(
        task_type=definition.task_type,
        value=_clamp_percent(float(value or 0.0)),
        enum_values=[],
    )


def _legacy_phase_to_current(phase: CableProgressPhase) -> CableProgressPhase:
    if phase.name == "termination" or phase.tasks:
        return normalize_cable_progress_phase(
            CableProgressPhase(
                name="dress_termination",
                task_values={
                    "routing_dress": CableProgressTask(
                        task_type=CableProgressTaskType.PERCENT,
                        value=phase.tasks.get("dressed", 0.0),
                    ),
                    "a_side": CableProgressTask(
                        task_type=CableProgressTaskType.ENUM,
                        value=_legacy_percent_to_endpoint_state(
                            phase.tasks.get("a_side_dressed_in_cabinet", phase.tasks.get("a_side_terminated", 0.0)),
                            phase.tasks.get("a_side_dressed_in_cabinet"),
                        ),
                    ),
                    "z_side": CableProgressTask(
                        task_type=CableProgressTaskType.ENUM,
                        value=_legacy_percent_to_endpoint_state(
                            phase.tasks.get("z_side_dressed_in_cabinet", phase.tasks.get("z_side_terminated", 0.0)),
                            phase.tasks.get("z_side_dressed_in_cabinet"),
                        ),
                    ),
                },
            )
        )
    if phase.name == "final_result":
        return normalize_cable_progress_phase(
            CableProgressPhase(
                name="validation",
                task_values={
                    "validation": CableProgressTask(
                        task_type=CableProgressTaskType.ENUM,
                        value="broken" if phase.value == "broken" else "validated",
                    )
                },
            )
        )
    return normalize_cable_progress_phase(
        CableProgressPhase(
            name="preparation",
            task_values={
                "preparation": CableProgressTask(
                    task_type=CableProgressTaskType.ENUM,
                    value=_legacy_preparation_value(phase.name),
                )
            },
        )
    )


def _legacy_phase_type(definition: CableProgressPhaseDefinition) -> CableProgressPhaseType:
    if len(definition.tasks) > 1:
        return CableProgressPhaseType.PARALLEL_PERCENT
    if definition.tasks[0].task_type == CableProgressTaskType.ENUM:
        return CableProgressPhaseType.ENUM_STATE
    return CableProgressPhaseType.SINGLE_PERCENT


def _legacy_preparation_value(name: str) -> str:
    if name == "purchased":
        return "ordered"
    if name in {"received", "labeled", "pulled"}:
        return name
    if name == "bundled_on_ground":
        return "bundled"
    return "ordered"


def _legacy_percent_to_endpoint_state(terminated_value: float | None, dressed_value: float | None) -> str:
    if dressed_value is not None and dressed_value >= 100:
        return "dressed"
    if terminated_value is not None and terminated_value >= 100:
        return "terminated"
    return "not_terminated"


def _clamp_percent(value: float | int) -> float:
    return min(100.0, max(0.0, float(value)))
