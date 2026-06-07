from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from backend.core.config import DEFAULT_BUILDING_ID, DEFAULT_PROJECT_UID
from backend.core.enums import ConstructionPhase
from backend.ingest.cutsheet import CutsheetIngestionResult, ingest_cutsheet
from backend.validation import BreakoutFanoutRule


class CutsheetSourceSpec(BaseModel):
    source_name: str
    path: str
    construction_phase: ConstructionPhase
    sheet_name: str | None = None


class CutsheetSourceResult(BaseModel):
    source_name: str
    path: str
    construction_phase: ConstructionPhase
    result: CutsheetIngestionResult


class CutsheetIngestionPipelineResult(BaseModel):
    project_uid: str = DEFAULT_PROJECT_UID
    building_id: str = DEFAULT_BUILDING_ID
    sources: list[CutsheetSourceResult] = Field(default_factory=list)


def ingest_cutsheet_sources(
    source_specs: list[CutsheetSourceSpec],
    project_uid: str = DEFAULT_PROJECT_UID,
    building_id: str = DEFAULT_BUILDING_ID,
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> CutsheetIngestionPipelineResult:
    return CutsheetIngestionPipelineResult(
        project_uid=project_uid,
        building_id=building_id,
        sources=[
            CutsheetSourceResult(
                source_name=source.source_name,
                path=str(Path(source.path)),
                construction_phase=source.construction_phase,
                result=ingest_cutsheet(
                    source.path,
                    project_uid=project_uid,
                    building_id=building_id,
                    sheet_name=source.sheet_name,
                    breakout_rules=breakout_rules,
                ),
            )
            for source in source_specs
        ],
    )
