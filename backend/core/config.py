from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 2
DEFAULT_PROJECT_UID = "MSK01"
DEFAULT_BUILDING_ID = "A"
DEFAULT_RUNTIME_DATABASE_PATH = Path("data/runtime/current_database.json")
DEFAULT_STATUS_OVERRIDES_PATH = Path("data/status_overrides.json")
DEFAULT_MAX_RACK_UNIT = 48


@dataclass(frozen=True)
class AppConfig:
    project_uid: str = DEFAULT_PROJECT_UID
    building_id: str = DEFAULT_BUILDING_ID
    runtime_database_path: Path = DEFAULT_RUNTIME_DATABASE_PATH
    status_overrides_path: Path = DEFAULT_STATUS_OVERRIDES_PATH
    default_max_rack_unit: int = DEFAULT_MAX_RACK_UNIT


def default_config() -> AppConfig:
    return AppConfig()
