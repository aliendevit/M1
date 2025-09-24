"""FastAPI application for the MinuteOne backend."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader, Template
import yaml

from ..asr import ASRService
from ..chips.service import ChipService
from ..config import Config
from ..evidence.sqlite_cache import (
    SQLiteChartCache,
    SQLiteEvidenceCache,
    bundle_from_transcript,
)
from ..export.exporter import Exporter
from ..extractor.llm import VisitExtractor
from ..fhir.reader import FHIRReader
from ..guards.service import GuardDecision, GuardService
from .models import (
    ChipResolveRequest,
    ChipResolveResponse,
    ComposeRequest,
    ComposeResponse,
    ContextResponse,
    EvidenceItemModel,
    EvidenceResponse,
    ExportRequest,
    ExportResponse,
    ExtractRequest,
    ExtractResponse,
    GuardReport,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    MetricsResponse,
    PlanpackRequest,
    PlanpackResponse,
)


@lru_cache(maxsize=1)
def load_config() -> Config:
    return Config.load()


@lru_cache(maxsize=1)
def build_cache() -> SQLiteChartCache:
    config = load_config()
    cache_config = config.get("cache", {})
    db_path = cache_config.get("db", "data/m1_cache.db")
    cache = SQLiteChartCache(db_path)
    cache.initialize()
    return cache


@lru_cache(maxsize=1)
def build_extractor() -> VisitExtractor:
    config = load_config()
    llm_config = config.get("llm", {})
    return VisitExtractor.from_config(llm_config)


@lru_cache(maxsize=1)
def build_chip_service() -> ChipService:
    config = load_config()
    confidence_config = config.get("confidence", {})
    return ChipService.from_config(confidence_config)


@lru_cache(maxsize=1)
def build_guard_service() -> GuardService:
    config = load_config()
    guard_config = config.get("guards", {})
    return GuardService.from_config(guard_config)


@lru_cache(maxsize=1)
def build_asr_service() -> ASRService:
    config = load_config()
    asr_config = config.get("asr", {})
    return ASRService.from_config(asr_config)


@lru_cache(maxsize=1)
def build_exporter() -> Exporter:
    config = load_config()
    export_root = config.get("export", {}).get("directory", "exports")
    return Exporter(output_dir=export_root)


@lru_cache(maxsize=1)
def build_fhir_reader() -> FHIRReader:
    return FHIRReader()


@lru_cache(maxsize=1)
def build_template_env() -> Environment:
    config = load_config()
    template_dir = config.get("templates", {}).get("directory", "m1/templates")
    search_path = Path(template_dir)
    return Environment(loader=FileSystemLoader(str(search_path)))


async def get_cache() -> AsyncIterator[SQLiteChartCache]:
    yield build_cache()


async def get_extractor() -> AsyncIterator[VisitExtractor]:
    yield build_extractor()


async def get_chip_service() -> AsyncIterator[ChipService]:
    yield build_chip_service()


async def get_guard_service() -> AsyncIterator[GuardService]:
    yield build_guard_service()


async def get_exporter() -> AsyncIterator[Exporter]:
    yield build_exporter()


async def get_template_env() -> AsyncIterator[Environment]:
    yield build_template_env()


app = FastAPI(title="MinuteOne API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    payload: IngestRequest,
    cache: SQLiteChartCache = Depends(get_cache),
    extractor: VisitExtractor = Depends(get_extractor),
    chip_service: ChipService = Depends(get_chip_service),
    guard_service: GuardService = Depends(get_guard_service),
) -> IngestResponse:
    extraction = extractor.extract(payload.transcript)
    bundle = bundle_from_transcript(payload.patient_id, payload.transcript, extraction)
    decision: GuardDecision = guard_service.evaluate(bundle)
    if decision.blocked:
        raise HTTPException(status_code=403, detail=decision.reason or "Guard policy blocked the action")
    await cache.a_upsert_bundle(bundle)
    cache.ingest_bundle(bundle)
    chips = chip_service.generate(bundle, extraction)
    return IngestResponse(
        patient_id=payload.patient_id,
        sections=bundle["sections"],
        guard=GuardReport(blocked=False, flags=decision.flags),
        chips=chips,
    )


@app.get("/evidence/{patient_id}", response_model=EvidenceResponse)
async def get_evidence(
    patient_id: str,
    cache: SQLiteChartCache = Depends(get_cache),
) -> EvidenceResponse:
    items = await cache.a_fetch_items(patient_id)
    return EvidenceResponse(
        patient_id=patient_id,
        evidence=[EvidenceItemModel.from_item(item) for item in items],
    )


@app.get("/facts/context", response_model=ContextResponse)
async def facts_context(
    patient_id: str,
    cache: SQLiteChartCache = Depends(get_cache),
) -> ContextResponse:
    context = cache.context_window(patient_id)
    return ContextResponse(patient_id=patient_id, context=context)


@app.post("/extract/visit", response_model=ExtractResponse)
async def extract_visit(
    request: ExtractRequest,
    extractor: VisitExtractor = Depends(get_extractor),
) -> ExtractResponse:
    visit = extractor.extract(request.transcript)
    return ExtractResponse(patient_id=request.patient_id, visit=visit)


@app.post("/chips/resolve", response_model=ChipResolveResponse)
async def chips_resolve(
    payload: ChipResolveRequest,
    chip_service: ChipService = Depends(get_chip_service),
) -> ChipResolveResponse:
    chips = chip_service.generate(payload.bundle, payload.extraction.model_dump())
    return ChipResolveResponse(chips=chips)


@app.post("/suggest/planpack", response_model=PlanpackResponse)
async def suggest_planpack(request: PlanpackRequest) -> PlanpackResponse:
    config = load_config()
    directory = config.get("planpacks", {}).get("directory", "m1/planpacks")
    path = Path(directory) / f"{request.planpack_id}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Planpack not found")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    metadata = data.get("metadata", {})
    return PlanpackResponse(
        id=metadata.get("id", request.planpack_id),
        title=metadata.get("title", request.planpack_id.title()),
        checklist=data.get("checklist", []),
        contingencies=data.get("contingencies", []),
        notes=data.get("notes", ""),
    )


@app.post("/compose/note", response_model=ComposeResponse)
async def compose_note(
    payload: ComposeRequest,
    cache: SQLiteChartCache = Depends(get_cache),
    env: Environment = Depends(get_template_env),
) -> ComposeResponse:
    return _compose_document("note", payload, cache, env)


@app.post("/compose/handoff", response_model=ComposeResponse)
async def compose_handoff(
    payload: ComposeRequest,
    cache: SQLiteChartCache = Depends(get_cache),
    env: Environment = Depends(get_template_env),
) -> ComposeResponse:
    return _compose_document("handoff", payload, cache, env)


@app.post("/compose/discharge", response_model=ComposeResponse)
async def compose_discharge(
    payload: ComposeRequest,
    cache: SQLiteChartCache = Depends(get_cache),
    env: Environment = Depends(get_template_env),
) -> ComposeResponse:
    return _compose_document("discharge", payload, cache, env)


@app.post("/compose/{template_name}", response_model=ComposeResponse)
async def compose_document(
    template_name: str,
    payload: ComposeRequest,
    cache: SQLiteChartCache = Depends(get_cache),
    env: Environment = Depends(get_template_env),
) -> ComposeResponse:
    if payload.template and payload.template != template_name:
        raise HTTPException(status_code=400, detail="Template mismatch between path and payload")
    return _compose_document(template_name, payload, cache, env)


@app.post("/export", response_model=ExportResponse)
async def export_document(
    payload: ExportRequest,
    exporter: Exporter = Depends(get_exporter),
) -> ExportResponse:
    destination = exporter.export(payload.bundle, format=payload.format, filename=payload.filename or payload.patient_id)
    return ExportResponse(path=str(destination))


@app.get("/metrics/session", response_model=MetricsResponse)
async def metrics_session() -> MetricsResponse:
    return MetricsResponse(session_id="local", active_users=1, processed_transcripts=0)


def _compose_document(
    template_key: str,
    payload: ComposeRequest,
    cache: SQLiteEvidenceCache,
    env: Environment,
) -> ComposeResponse:
    mapping = {
        "note": "note.j2",
        "handoff": "handoff_ipass.j2",
        "discharge": f"discharge_{payload.locale}.j2",
    }
    if template_key not in mapping:
        raise HTTPException(status_code=404, detail="Template not found")
    template_file = mapping[template_key]
    try:
        template: Template = env.get_template(template_file)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    bundle = payload.bundle or _bundle_from_cache(cache, payload.patient_id)
    rendered = template.render(bundle=bundle, locale=payload.locale)
    return ComposeResponse(patient_id=payload.patient_id, template=template_file, content=rendered)


def _bundle_from_cache(cache: SQLiteEvidenceCache, patient_id: str) -> dict:
    evidence = cache.fetch_items(patient_id)
    sections = {item.section: item.payload for item in evidence}
    return {"patient_id": patient_id, "sections": sections}
