from __future__ import annotations

from enum import StrEnum


class ConnectorType(StrEnum):
    CAT6 = "CAT6"
    LC = "LC"
    SC = "SC"
    MPO = "MPO"
    POWER = "power"
    OTHER = "other"


class LifecycleStatus(StrEnum):
    UNKNOWN = "unknown"
    NOT_CONSTRUCTED = "not_constructed"
    NOT_INSTALLED = "not_installed"
    NOT_POWERED = "not_powered"
    INSTALLED = "installed"
    POWERED = "powered"
    ACTIVE = "active"
    NOT_PLANNED = "not_planned"


class ConstructionPhase(StrEnum):
    MANAGEMENT_ETHERNET = "Management & Ethernet"
    ROCE = "RoCE"


class CableProgressStep(StrEnum):
    PURCHASED = "purchased"
    RECEIVED = "received"
    CATEGORIZED_STORED = "categorized_stored"
    LABELED = "labeled"
    BUNDLED_ON_GROUND = "bundled_on_ground"
    PULLED = "pulled"
    DRESSED = "dressed"
    A_SIDE_TERMINATED = "a_side_terminated"
    Z_SIDE_TERMINATED = "z_side_terminated"
    A_SIDE_DRESSED_IN_CABINET = "a_side_dressed_in_cabinet"
    Z_SIDE_DRESSED_IN_CABINET = "z_side_dressed_in_cabinet"
    VALIDATED = "validated"
    BROKEN = "broken"


class CableProgressState(StrEnum):
    NOT_STARTED = "not_started"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class CableProgressPhaseType(StrEnum):
    SINGLE_PERCENT = "single_percent"
    PARALLEL_PERCENT = "parallel_percent"
    ENUM_STATE = "enum_state"


class CableProgressTaskType(StrEnum):
    PERCENT = "percent"
    ENUM = "enum"
