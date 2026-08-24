from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_PROJECT_CATALOG_PATH = Path("data/projects.json")


class ProjectLocation(BaseModel):
    city: str = ""
    state: str = ""
    country: str = "USA"
    latitude: float
    longitude: float


class ProjectSourceFile(BaseModel):
    kind: str
    path: str
    sheets: list[str] = Field(default_factory=list)


class ProjectMetadata(BaseModel):
    uid: str
    name: str
    campus: str = ""
    owner: str = ""
    status: str = "active"
    location: ProjectLocation
    address: str = ""
    building_id: str = "A"
    data_halls: list[str] = Field(default_factory=list)
    runtime_database_path: str = "data/runtime/current_database.json"
    source_files: list[ProjectSourceFile] = Field(default_factory=list)
    loading_instructions: list[str] = Field(default_factory=list)


class ProjectCatalog(BaseModel):
    default_project_uid: str
    projects: list[ProjectMetadata]


def project_catalog_path() -> Path:
    return Path(os.environ.get("PROJECT_CATALOG_PATH", DEFAULT_PROJECT_CATALOG_PATH))


def load_project_catalog(path: str | Path | None = None) -> ProjectCatalog:
    catalog_path = Path(path) if path is not None else project_catalog_path()
    with catalog_path.open(encoding="utf-8") as catalog_file:
        payload = json.load(catalog_file)
    if hasattr(ProjectCatalog, "model_validate"):
        catalog = ProjectCatalog.model_validate(payload)
    else:
        catalog = ProjectCatalog.parse_obj(payload)
    active_project_uid = os.environ.get("ACTIVE_PROJECT_UID", catalog.default_project_uid).strip().upper()
    if active_project_uid:
        catalog.default_project_uid = active_project_uid
        for project in catalog.projects:
            if project.uid.upper() == active_project_uid:
                project.status = "active"
            elif project.status == "active":
                project.status = "standby"
    project_uids = {project.uid.upper() for project in catalog.projects}
    if catalog.default_project_uid.upper() not in project_uids:
        raise ValueError(f"Default project '{catalog.default_project_uid}' is not present in the project catalog.")
    return catalog


def get_project(project_uid: str, path: str | Path | None = None) -> ProjectMetadata | None:
    normalized_uid = project_uid.upper()
    for project in load_project_catalog(path).projects:
        if project.uid.upper() == normalized_uid:
            return project
    return None
