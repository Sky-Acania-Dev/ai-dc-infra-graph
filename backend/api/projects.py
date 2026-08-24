from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.core.projects import ProjectCatalog, ProjectMetadata, get_project, load_project_catalog


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectCatalog)
def list_projects() -> ProjectCatalog:
    return load_project_catalog()


@router.get("/{project_uid}", response_model=ProjectMetadata)
def project_detail(project_uid: str) -> ProjectMetadata:
    project = get_project(project_uid)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_uid}' was not found.")
    return project
