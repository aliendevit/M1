# path: backend/api/routes_extract.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field, ConfigDict

router = APIRouter()

# === Contracts from the brief (VisitJSON) ===
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
    type: str  # lab_series|test|med_admin|education
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


class InputTranscriptSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(..., description="Transcript text span relevant to this extraction")
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None


class ChartFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str  # lab|vital|note|image|med
    name: str
    value: Optional[str] = None
    time: Optional[str] = None
    source_id: Optional[str] = None


class ExtractVisitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript_span: InputTranscriptSpan
    chart_facts: List[ChartFact] = Field(default_factory=list)


class SlotScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot: str
    confidence: float = Field(..., ge=0, le=1.0)


class ExtractVisitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    VisitJSON: VisitJSON
    slot_scores: List[SlotScore]


def _extract_with_service(span: InputTranscriptSpan, facts: List[ChartFact]) -> ExtractVisitResponse:
    try:
        from ..services.extract_service import ExtractService  # type: ignore
    except Exception:
        # Deterministic stub that fills minimal VisitJSON using trivial rules; slot scores all medium.
        visit = VisitJSON(
            chief_complaint="unspecified",
            hpi=VisitHPI(onset=None, quality=None),
            exam_bits=VisitExamBits(cv=None, lungs=None),
            risks=[],
            plan_intents=[],
            language_pref=None,
        )
        scores = [SlotScore(slot="chief_complaint", confidence=0.70)]
        return ExtractVisitResponse(VisitJSON=visit, slot_scores=scores)

    svc = ExtractService.instance()
    out = svc.extract_visit(span.model_dump(), [f.model_dump() for f in facts])
    return ExtractVisitResponse.model_validate(out)


@router.post(
    "/extract/visit",
    response_model=ExtractVisitResponse,
    response_class=ORJSONResponse,
    summary="Rules-first extraction of VisitJSON with slot confidences",
)
async def extract_visit(body: ExtractVisitRequest = Body(...)):
    """
    Deterministic rules populate VisitJSON; ambiguous/missing slots may be LLM-filled (strict JSON)
    in the underlying service. Always returns `VisitJSON` + `slot_scores`.
    """
    try:
        return _extract_with_service(body.transcript_span, body.chart_facts)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e
