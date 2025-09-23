# path: backend/api/routes_compose.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field, ConfigDict

router = APIRouter()

# --- Reuse VisitJSON pieces (local minimal copy) ---
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
    id: Optional[str] = None
    kind: str
    name: str
    value: Optional[str] = None
    delta: Optional[str] = None
    time: Optional[str] = None
    source_id: Optional[str] = None


class ComposeNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    VisitJSON: VisitJSON
    facts: List[EvidenceFact] = Field(default_factory=list)


class ComposeNoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markdown: str
    citations: List[str] = Field(default_factory=list)


class ComposeDischargeRequest(ComposeNoteRequest):
    lang: Optional[str] = Field(None, description="Language code: 'en' or 'es' (default in config)")


class ComposeDischargeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markdown: str


class ComposeHandoffRequest(ComposeNoteRequest):
    pass


class ComposeHandoffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ipass_json: Dict[str, Any]


def _compose_note(V: VisitJSON, facts: List[EvidenceFact]) -> ComposeNoteResponse:
    try:
        from ..services.compose_service import ComposeService  # type: ignore
    except Exception:
        # Deterministic stub
        body = f"# NOTE (STUB)\n\nChief complaint: {V.chief_complaint}\n"
        return ComposeNoteResponse(markdown=body, citations=[])

    svc = ComposeService.instance()
    out = svc.compose_note(V.model_dump(), [f.model_dump() for f in facts])
    return ComposeNoteResponse.model_validate(out)


def _compose_handoff(V: VisitJSON, facts: List[EvidenceFact]) -> ComposeHandoffResponse:
    try:
        from ..services.compose_service import ComposeService  # type: ignore
    except Exception:
        return ComposeHandoffResponse(ipass_json={"I": {}, "P": {}, "A": {}, "S": {}, "S2": {}})

    svc = ComposeService.instance()
    out = svc.compose_handoff(V.model_dump(), [f.model_dump() for f in facts])
    return ComposeHandoffResponse.model_validate(out)


def _compose_discharge(V: VisitJSON, facts: List[EvidenceFact], lang: Optional[str]) -> ComposeDischargeResponse:
    try:
        from ..services.compose_service import ComposeService  # type: ignore
    except Exception:
        return ComposeDischargeResponse(markdown=f"Discharge (STUB) — lang={lang or 'en'}")

    svc = ComposeService.instance()
    out = svc.compose_discharge(V.model_dump(), [f.model_dump() for f in facts], lang=lang)
    return ComposeDischargeResponse.model_validate(out)


@router.post(
    "/compose/note",
    response_model=ComposeNoteResponse,
    response_class=ORJSONResponse,
    summary="Compose SOAP/MDM markdown with inline citations",
)
async def compose_note(body: ComposeNoteRequest = Body(...)):
    try:
        return _compose_note(body.VisitJSON, body.facts)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compose note failed: {e}") from e


@router.post(
    "/compose/handoff",
    response_model=ComposeHandoffResponse,
    response_class=ORJSONResponse,
    summary="Compose I-PASS handoff JSON",
)
async def compose_handoff(body: ComposeHandoffRequest = Body(...)):
    try:
        return _compose_handoff(body.VisitJSON, body.facts)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compose handoff failed: {e}") from e


@router.post(
    "/compose/discharge",
    response_model=ComposeDischargeResponse,
    response_class=ORJSONResponse,
    summary="Compose Discharge markdown (EN/ES)",
)
async def compose_discharge(body: ComposeDischargeRequest = Body(...)):
    try:
        return _compose_discharge(body.VisitJSON, body.facts, body.lang)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compose discharge failed: {e}") from e
