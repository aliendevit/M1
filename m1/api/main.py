"""FastAPI application exposing the MinuteOne offline services."""
=======
"""FastAPI application exposing the local MinuteOne services."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..asr.service import ASRService, serialise_result
from ..chips.service import ChipResolution
from ..composer.service import Composer
from ..config import get_cached_config
from ..evidence.sqlite_cache import SQLiteChartCache
from ..export.exporter import Exporter
from ..extractor.service import extract_visit
from ..guards.service import GuardService
from ..planpacks.loader import PlanPack, evaluate_planpack, load_directory
from ..schemas import (
    EvidenceChip,
    ExtractVisitResponse,
    PlanpackResponse,
    VisitJSON,
)

app = FastAPI(title="MinuteOne (M1) Edge API", version="0.2.0")


class ASRRequest(BaseModel):
    audio_chunk: str = Field(..., description="Base64 audio or plaintext transcript snippet")
=======
from ..asr.service import ASRService
from ..chips.service import build_chips
from ..composer.service import Composer
from ..config import AppConfig, get_cached_config
from ..evidence.cache import ChartCache
from ..extractor.service import ExtractionResult, extract_visit
from ..metrics.state import session_metrics
from ..planpacks.loader import PlanPack, evaluate_planpack, load_directory
from ..schemas import EvidenceChip, ExtractVisitResponse, PlanpackResponse, VisitJSON

app = FastAPI(title="MinuteOne (M1) Edge API", version="0.1.0")


class ASRRequest(BaseModel):
    audio_chunk: str = Field(..., description="For the stub we accept plaintext audio transcripts")


class ASRSpan(BaseModel):
    start: float
    end: float
    speaker: str
    text: str


class ASRResponse(BaseModel):
    text: str
    spans: List[ASRSpan]


class ExtractRequest(BaseModel):
    transcript_span: str
    chart_facts: List[str] = Field(default_factory=list)


class ComposeRequest(BaseModel):
    visit: VisitJSON
    facts: List[EvidenceChip] = Field(default_factory=list)


class DischargeRequest(ComposeRequest):
    lang: Optional[str] = Field(default=None, description="Preferred discharge language")
=======
    lang: Optional[str] = None


class PlanpackRequest(BaseModel):
    pathway: str
    visit: VisitJSON
    facts: List[EvidenceChip] = Field(default_factory=list)


class ChipResolveRequest(BaseModel):
    chip_id: str
    action: str
    value: Optional[str] = None
    reason: Optional[str] = None
=======


@lru_cache(maxsize=1)
def get_planpacks() -> Dict[str, PlanPack]:
    directory = Path(__file__).resolve().parent / "../planpacks"
    return load_directory(directory)


@lru_cache(maxsize=1)
def get_composer() -> Composer:
    return Composer()


@lru_cache(maxsize=1)
def get_asr_service() -> ASRService:
    config = get_cached_config()
    return ASRService(config.asr)


@lru_cache(maxsize=1)
def get_cache() -> SQLiteChartCache:
    config = get_cached_config()
    cache = SQLiteChartCache(Path(config.cache.db))
    cache.initialise()
    return cache


@lru_cache(maxsize=1)
def get_guard_service() -> GuardService:
    return GuardService()
=======
    planpack_dir = Path(__file__).resolve().parent / "../planpacks"
    return load_directory(planpack_dir)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/asr/segment")
def asr_segment(request: ASRRequest, service: ASRService = Depends(get_asr_service)) -> dict:
    result = service.transcribe_segment(request.audio_chunk)
    return serialise_result(result)


@app.post("/extract/visit", response_model=ExtractVisitResponse)
def extract_visit_endpoint(request: ExtractRequest) -> ExtractVisitResponse:
    extraction = extract_visit(request.transcript_span, request.chart_facts)
=======
@app.post("/asr/segment", response_model=ASRResponse)
def asr_segment(request: ASRRequest, config: AppConfig = Depends(get_cached_config)) -> ASRResponse:
    service = ASRService(segment_length=config.asr.segment_ms / 1000)
    result = service.transcribe(request.audio_chunk)
    spans = [ASRSpan(**span.__dict__) for span in result.spans]
    return ASRResponse(text=result.text, spans=spans)


@app.post("/extract/visit", response_model=ExtractVisitResponse)
def extract_visit_endpoint(request: ExtractRequest, config: AppConfig = Depends(get_cached_config)) -> ExtractVisitResponse:
    extraction: ExtractionResult = extract_visit(request.transcript_span, request.chart_facts)
    chips = build_chips(extraction.slot_scores, config.confidence)
    # Track chip counts for metrics.
    for chip in chips:
        session_metrics.chip_counts[chip.band.value] += 1
    return ExtractVisitResponse(visit=extraction.visit, slot_scores=extraction.slot_scores)


@app.get("/facts/context", response_model=List[EvidenceChip])
def get_facts(window: int = 72, cache: SQLiteChartCache = Depends(get_cache)) -> List[EvidenceChip]:

def get_facts(window: int = 72) -> List[EvidenceChip]:
    cache = ChartCache()
    return cache.context_window(window)


@app.post("/compose/note")
def compose_note(request: ComposeRequest, composer: Composer = Depends(get_composer)) -> dict:
def compose_note(request: ComposeRequest) -> dict:
    composer = Composer()
    rendered = composer.render_note(request.visit, request.facts)
    return {"markdown": rendered.content, "citations": rendered.citations}


@app.post("/compose/handoff")
def compose_handoff(request: ComposeRequest, composer: Composer = Depends(get_composer)) -> dict:
def compose_handoff(request: ComposeRequest) -> dict:
    composer = Composer()
    rendered = composer.render_handoff(request.visit, request.facts)
    return {"markdown": rendered.content, "citations": rendered.citations}


@app.post("/compose/discharge")
def compose_discharge(request: DischargeRequest, composer: Composer = Depends(get_composer)) -> dict:
def compose_discharge(request: DischargeRequest) -> dict:
    composer = Composer()
    rendered = composer.render_discharge(request.visit, request.facts, language=request.lang)
    return {"markdown": rendered.content, "citations": rendered.citations}


@app.post("/suggest/planpack", response_model=PlanpackResponse)
def suggest_planpack(request: PlanpackRequest, guard_service: GuardService = Depends(get_guard_service)) -> PlanpackResponse:
    packs = get_planpacks()
    pack = packs.get(request.pathway)
    if pack is None:
        raise HTTPException(status_code=404, detail="Unknown pathway")
    response = evaluate_planpack(pack, request.visit, request.facts, guard_service=guard_service)
def suggest_planpack(request: PlanpackRequest) -> PlanpackResponse:
    packs = get_planpacks()
    pack = packs.get(request.pathway)
    if not pack:
        raise HTTPException(status_code=404, detail="Unknown pathway")
    response = evaluate_planpack(pack, request.visit, [fact.name for fact in request.facts])
    return response


@app.post("/chips/resolve")
def chips_resolve(request: ChipResolveRequest) -> dict:
    resolution = ChipResolution(
        chip_id=request.chip_id,
        action=request.action,
        value=request.value,
        reason=request.reason,
    )
    return resolution.model_dump()


@app.post("/export")
def export_artifacts(
    request: ComposeRequest,
    composer: Composer = Depends(get_composer),
) -> dict:
    exporter = Exporter(output_dir=Path("exports"))
    note = composer.render_note(request.visit, request.facts).content
    handoff = composer.render_handoff(request.visit, request.facts).content
    discharge = composer.render_discharge(request.visit, request.facts).content
    files = exporter.export_all("encounter", note, handoff, discharge)
    return {"files": [str(path) for path in files]}
    # In the MVP skeleton we simply acknowledge the action.
    return {"ok": True, "chip_id": request.chip_id, "action": request.action}


@app.get("/metrics/session")
def metrics_session() -> dict:
    return session_metrics.to_payload()
