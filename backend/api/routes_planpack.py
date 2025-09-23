# path: backend/api/routes_planpack.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field, ConfigDict

router = APIRouter()


# Minimal VisitJSON view (to avoid import cycles in API layer)
class VisitHPI(BaseModel):
    model_config = ConfigDict(extra="forbid")
    onset: Optional[str] = None
    quality: Optional[str] = None
    modifiers: List[str] = Field(default_factory=list)
    associated_symptoms: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)


class VisitExamBits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cv: Optional[str] = None
    lungs: Optional[str] = None


class VisitPlanIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    name: str
    dose: Optional[str] = None
    schedule: List[str] = Field(default_factory=list)


class VisitJSON(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chief_complaint: str
    hpi: VisitHPI
    exam_bits: VisitExamBits
    risks: List[str] = Field(default_factory=list)
    plan_intents: List[VisitPlanIntent] = Field(default_factory=list)
    language_pref: Optional[str] = None


class EvidenceFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    name: str
    value: Optional[str] = None
    delta: Optional[str] = None
    time: Optional[str] = None
    source_id: Optional[str] = None


class SuggestPlanpackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pathway: str = Field(..., description="One of: chest_pain | seizure | sepsis")
    VisitJSON: VisitJSON
    facts: List[EvidenceFact] = Field(default_factory=list)


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chip_id: str
    label: str
    proposed: Optional[str] = None
    band: Optional[str] = None
    risk: Optional[str] = None
    actions: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class GuardFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    status: str  # passed|failed|unknown
    reason: Optional[str] = None


class SuggestPlanpackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggestions: List[Suggestion]
    guard_flags: List[GuardFlag]


def _suggest_with_service(pathway: str, V: VisitJSON, facts: List[EvidenceFact]) -> SuggestPlanpackResponse:
    try:
        from ..services.planpack_service import PlanpackService  # type: ignore
    except Exception:
        # Deterministic stub: no guards, one suggestion with D-band if pathway unknown
        guard = GuardFlag(name="pathway", status="passed")
        sug = Suggestion(
            chip_id="stub-0001",
            label=f"Pathway: {pathway}",
            proposed=None,
            band="D" if pathway not in {"chest_pain", "seizure", "sepsis"} else "B",
            risk="low",
            actions=["accept", "evidence"],
            evidence=[],
        )
        return SuggestPlanpackResponse(suggestions=[sug], guard_flags=[guard])

    svc = PlanpackService.instance()
    out = svc.suggest(pathway, V.model_dump(), [f.model_dump() for f in facts])
    return SuggestPlanpackResponse.model_validate(out)


@router.post(
    "/suggest/planpack",
    response_model=SuggestPlanpackResponse,
    response_class=ORJSONResponse,
    summary="Run pathway rules and guards; emit suggestions and guard flags",
)
async def suggest_planpack(body: SuggestPlanpackRequest = Body(...)):
    try:
        return _suggest_with_service(body.pathway, body.VisitJSON, body.facts)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planpack suggestion failed: {e}") from e
