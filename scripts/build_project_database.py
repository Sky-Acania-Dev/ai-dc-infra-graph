from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.projects import get_project
from backend.core.enums import ConstructionPhase
from backend.ingest.cleaners.lbb01 import (
    LBB01_DEFAULT_MAX_RACK_UNIT,
    apply_lbb01_rack_unit_rule,
    ingest_lbb01_non_roce_cutsheet,
    ingest_lbb01_overhead,
    ingest_lbb01_vr_roce_cutsheets,
    ingest_lbb01_workbook,
)
from backend.ingest.cutsheet_pipeline import CutsheetIngestionPipelineResult, CutsheetSourceResult
from backend.persistence import save_topology_database
from backend.services import build_topology_database_from_pipeline_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a topology database for a configured project.")
    parser.add_argument("--project-uid", required=True)
    parser.add_argument("--source-path", default=None, help="Override the source workbook path from data/projects.json.")
    parser.add_argument("--runtime-path", default=None, help="Override the runtime database output path from data/projects.json.")
    parser.add_argument("--default-max-rack-unit", type=int, default=LBB01_DEFAULT_MAX_RACK_UNIT)
    args = parser.parse_args()

    project = get_project(args.project_uid)
    if project is None:
        raise ValueError(f"Project '{args.project_uid}' was not found in data/projects.json.")
    source = project.source_files[0] if project.source_files else None
    source_path = args.source_path or (source.path if source else None)
    if not source_path:
        raise ValueError(f"Project '{project.uid}' does not define a source file.")

    if project.uid.upper() != "LBB01":
        raise ValueError(f"No project-specific ingestion cleaner is registered for '{project.uid}'.")

    non_roce_path = _source_path_by_kind(project, "non_roce_cutsheet")
    overhead_path = _source_path_by_kind(project, "overhead") or non_roce_path or source_path
    overhead = ingest_lbb01_overhead(overhead_path)
    roce_sample = ingest_lbb01_workbook(
        source_path,
        project_uid=project.uid,
        building_id=project.building_id,
    )
    non_roce = (
        ingest_lbb01_non_roce_cutsheet(
            non_roce_path,
            project_uid=project.uid,
            building_id=project.building_id,
        )
        if non_roce_path
        else None
    )
    vr_roce_path = _source_path_by_kind(project, "vr_roce_cutsheet")
    vr_roce = (
        ingest_lbb01_vr_roce_cutsheets(
            vr_roce_path,
            project_uid=project.uid,
            building_id=project.building_id,
        )
        if vr_roce_path
        else None
    )
    sources = [
        CutsheetSourceResult(
            source_name="lbb01:roce_sample",
            path=str(source_path),
            construction_phase=ConstructionPhase.ROCE,
            result=roce_sample.cutsheet,
        )
    ]
    if non_roce and non_roce_path:
        sources.append(
            CutsheetSourceResult(
                source_name="lbb01:non_roce",
                path=str(non_roce_path),
                construction_phase=ConstructionPhase.MANAGEMENT_ETHERNET,
                result=non_roce,
            )
        )
    if vr_roce and vr_roce_path:
        sources.append(
            CutsheetSourceResult(
                source_name="lbb01:vr_roce",
                path=str(vr_roce_path),
                construction_phase=ConstructionPhase.ROCE,
                result=vr_roce,
            )
        )
    pipeline_result = CutsheetIngestionPipelineResult(
        project_uid=project.uid,
        building_id=project.building_id,
        sources=sources,
    )
    database = build_topology_database_from_pipeline_result(
        cutsheet_pipeline_result=pipeline_result,
        overhead_result=overhead,
        project_uid=project.uid,
        building_id=project.building_id,
        default_max_rack_unit=args.default_max_rack_unit,
    )
    apply_lbb01_rack_unit_rule(database.cabinets, database.rows)
    saved_path = save_topology_database(database, args.runtime_path or project.runtime_database_path)
    print(json.dumps({
        "runtime_database": str(saved_path),
        "project_uid": database.project_uid,
        "rows": database.summary.rows,
        "data_halls": database.summary.data_halls,
        "cabinets": database.summary.cabinets,
        "ports": database.summary.ports,
        "cables": database.summary.cables,
        "port_collision_findings": database.summary.port_collision_findings,
        "device_model_mismatches": len(database.device_model_mismatches),
        "device_model_format_issues": len(database.device_model_format_issues),
        "overhead_source": str(overhead_path),
        "source_summaries": {
            source.source_name: {
                "rows": len(source.result.rows),
                "ports": len(source.result.ports),
                "cables": len(source.result.cables),
                "findings": len(source.result.findings),
            }
            for source in sources
        },
        "lbb_summary": _model_to_payload(roce_sample.summary),
    }, indent=2))


def _model_to_payload(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _source_path_by_kind(project, kind: str) -> str | None:
    for source in project.source_files:
        if source.kind == kind:
            return source.path
    return None


if __name__ == "__main__":
    main()
