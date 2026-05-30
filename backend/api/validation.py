from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.ingest.cutsheet import CutsheetCableRow
from backend.validation import BreakoutFanoutRule, PortConnectionFinding, detect_port_collisions


router = APIRouter(prefix="/validation", tags=["validation"])


class PortCollisionRequest(BaseModel):
    rows: list[CutsheetCableRow]
    breakout_rules: list[BreakoutFanoutRule] | None = None


@router.post("/port-collisions", response_model=list[PortConnectionFinding])
def find_port_collisions(request: PortCollisionRequest) -> list[PortConnectionFinding]:
    return detect_port_collisions(request.rows, breakout_rules=request.breakout_rules)
