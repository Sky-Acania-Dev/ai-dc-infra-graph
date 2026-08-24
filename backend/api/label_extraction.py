from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.api.auth import AuthUser, current_user, require_manager
from backend.core.config import DEFAULT_PROJECT_UID, use_postgresql_topology_storage
from backend.persistence.postgresql.session import session_factory
from backend.services.label_extraction import (
    DEFAULT_LABEL_EXTRACTION_CONFIG_PATH,
    LabelExtractionConfig,
    LabelExtractionPreview,
    build_label_workbook_bytes,
    built_in_label_extraction_configs,
    load_label_extraction_configs,
    preview_label_extraction_rows,
    resolve_label_cable_rows,
    resolve_label_extraction_config,
    save_label_extraction_config,
)


router = APIRouter(prefix="/label-extraction", tags=["label-extraction"])


class LabelExtractionPreviewRequest(BaseModel):
    config: LabelExtractionConfig | None = None
    config_uid: str | None = None
    project_uid: str = DEFAULT_PROJECT_UID
    limit: int = Field(default=100_000, ge=1, le=500_000)
    sample_size: int = Field(default=25, ge=0, le=500)


class LabelExtractionRunRequest(BaseModel):
    config: LabelExtractionConfig | None = None
    config_uid: str | None = None
    project_uid: str = DEFAULT_PROJECT_UID
    limit: int = Field(default=100_000, ge=1, le=500_000)


class LabelExtractionRunResponse(BaseModel):
    filename: str
    content_type: str
    bytes: int
    preview: LabelExtractionPreview


@router.get("/configs", response_model=list[LabelExtractionConfig])
def list_label_extraction_configs(
    project_uid: str = DEFAULT_PROJECT_UID,
    include_builtin: bool = True,
    user: AuthUser = Depends(current_user),
) -> list[LabelExtractionConfig]:
    configs = [config for config in load_label_extraction_configs(DEFAULT_LABEL_EXTRACTION_CONFIG_PATH) if config.project_uid == project_uid]
    if include_builtin:
        existing_uids = {config.uid for config in configs if config.uid}
        configs.extend(config for config in built_in_label_extraction_configs(project_uid) if config.uid not in existing_uids)
    return sorted(configs, key=lambda config: (config.name, config.uid or ""))


@router.post("/configs", response_model=LabelExtractionConfig)
def upsert_label_extraction_config(
    config: LabelExtractionConfig,
    user: AuthUser = Depends(current_user),
) -> LabelExtractionConfig:
    require_manager(user)
    return save_label_extraction_config(config, DEFAULT_LABEL_EXTRACTION_CONFIG_PATH)


@router.post("/preview", response_model=LabelExtractionPreview)
def preview_label_extraction(
    request: LabelExtractionPreviewRequest,
    user: AuthUser = Depends(current_user),
) -> LabelExtractionPreview:
    config = _request_config(request.config, request.config_uid, project_uid=request.project_uid)
    rows = _resolve_rows(config, limit=request.limit)
    return preview_label_extraction_rows(config, rows, sample_size=request.sample_size)


@router.post("/runs", response_model=LabelExtractionRunResponse)
def create_label_extraction_run(
    request: LabelExtractionRunRequest,
    user: AuthUser = Depends(current_user),
) -> LabelExtractionRunResponse:
    config = _request_config(request.config, request.config_uid, project_uid=request.project_uid)
    rows = _resolve_rows(config, limit=request.limit)
    workbook = build_label_workbook_bytes(config, rows)
    return LabelExtractionRunResponse(
        filename=_workbook_filename(config),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        bytes=len(workbook),
        preview=preview_label_extraction_rows(config, rows),
    )


@router.post("/runs/download")
def download_label_extraction_run(
    request: LabelExtractionRunRequest,
    user: AuthUser = Depends(current_user),
) -> StreamingResponse:
    config = _request_config(request.config, request.config_uid, project_uid=request.project_uid)
    rows = _resolve_rows(config, limit=request.limit)
    filename = _workbook_filename(config)
    return StreamingResponse(
        BytesIO(build_label_workbook_bytes(config, rows)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _request_config(config: LabelExtractionConfig | None, config_uid: str | None, *, project_uid: str) -> LabelExtractionConfig:
    if config is not None and config_uid:
        raise HTTPException(status_code=422, detail="Provide either config or config_uid, not both.")
    if config is not None:
        return config
    if config_uid:
        resolved = resolve_label_extraction_config(config_uid, project_uid=project_uid, path=DEFAULT_LABEL_EXTRACTION_CONFIG_PATH)
        if resolved is None:
            raise HTTPException(status_code=404, detail=f"Label extraction config '{config_uid}' was not found.")
        return resolved
    raise HTTPException(status_code=422, detail="config or config_uid is required.")


def _resolve_rows(config: LabelExtractionConfig, *, limit: int):
    if not use_postgresql_topology_storage():
        raise HTTPException(status_code=400, detail="Label extraction currently requires PostgreSQL topology storage.")
    with session_factory()() as session:
        return resolve_label_cable_rows(session, config, limit=limit)


def _workbook_filename(config: LabelExtractionConfig) -> str:
    safe_name = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in config.name.strip())
    safe_name = safe_name.strip("_") or "label_extraction"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{safe_name}_{timestamp}.xlsx"
