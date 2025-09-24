"""FastAPI application for the MinuteOne backend."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..config import Config
from ..evidence.sqlite_cache import SQLiteEvidenceCache, bundle_from_transcript
from ..extractor.llm import VisitExtractor
from ..chips.service import ChipService
from ..guards.service import GuardDecision, GuardService
from .models import (
    EvidenceItemModel,
    EvidenceResponse,
    GuardReport,
    HealthResponse,
    IngestRequest,
    IngestResponse,
)


@lru_cache(maxsize=1)
def load_config() -> Config:
    config_path = os.environ.get("M1_CONFIG")
    return Config.load(path=Path(config_path) if config_path else None)


@lru_cache(maxsize=1)
def build_cache() -> SQLiteEvidenceCache:
    config = load_config()
    cache_config = config.get("cache", {})
    db_path = cache_config.get("db", "data/m1_cache.db")
    return SQLiteEvidenceCache(db_path)


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


async def get_cache() -> AsyncIterator[SQLiteEvidenceCache]:
    yield build_cache()


async def get_extractor() -> AsyncIterator[VisitExtractor]:
    yield build_extractor()


async def get_chip_service() -> AsyncIterator[ChipService]:
    yield build_chip_service()


async def get_guard_service() -> AsyncIterator[GuardService]:
    yield build_guard_service()


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
    cache: SQLiteEvidenceCache = Depends(get_cache),
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
    cache: SQLiteEvidenceCache = Depends(get_cache),
) -> EvidenceResponse:
    items = await cache.a_fetch_items(patient_id)
    return EvidenceResponse(
        patient_id=patient_id,
        evidence=[EvidenceItemModel.from_item(item) for item in items],
    )
