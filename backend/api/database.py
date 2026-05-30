from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from backend.ingest.cutsheet import CutsheetSummary
from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH, load_topology_database, save_topology_database


router = APIRouter(prefix="/database", tags=["database"])


class LoadJsonDatabaseRequest(BaseModel):
    json_path: str
    runtime_path: str | None = None


class LoadJsonDatabaseResponse(BaseModel):
    runtime_path: str
    summary: CutsheetSummary
    has_port_collisions: bool


@router.post("/load-json", response_model=LoadJsonDatabaseResponse)
def load_json_database(request: LoadJsonDatabaseRequest) -> LoadJsonDatabaseResponse:
    database = load_topology_database(request.json_path)
    runtime_path = Path(request.runtime_path) if request.runtime_path else DEFAULT_RUNTIME_DATABASE_PATH
    saved_path = save_topology_database(database, runtime_path)
    return LoadJsonDatabaseResponse(
        runtime_path=str(saved_path),
        summary=database.summary,
        has_port_collisions=database.has_port_collisions,
    )
