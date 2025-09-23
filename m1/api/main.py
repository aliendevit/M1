from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from m1 import __version__
from m1.chips.service import BAND_THRESHOLDS, build_chips
from m1.config import load_config
from m1.evidence.sqlite_cache import SQLiteChartCache
from m1.extractor.llm import LLMConfig, LLMExtractor
from m1.guards.service import (
    GuardResult,
    guard_active_bleed,
    guard_allergy,
    guard_anticoag,
    guard_pregnancy,
    guard_renal,
)
from m1.models import ChipActionAudit, EvidenceChip, SlotScore, VisitJSON
from m1.planpack import PlanpackService

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="MinuteOne API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._timers: dict[str, float] = {}
        self._chip_counts = {band: 0 for band in ["A", "B", "C", "D"]}

    def record_timer(self, name: str, duration_s: float) -> None:
        with self._lock:
            existing = self._timers.get(name, 0.0)
            self._timers[name] = round(existing + duration_s, 3)

    def record_chips(self, chips: list[EvidenceChip]) -> None:
        with self._lock:
            for chip in chips:
                self._chip_counts[chip.band] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "timers": dict(self._timers),
                "chip_counts": dict(self._chip_counts),
            }


metrics_store = MetricsStore()


class ExtractRequest(BaseModel):
    transcript: str
    patient_id: str = "demo-patient"


class ExtractResponse(BaseModel):
    visit: VisitJSON
    slot_scores: list[SlotScore]
    chips: list[EvidenceChip]


class ComposeNoteRequest(BaseModel):
    visit: VisitJSON
    facts: dict[str, Any] = Field(default_factory=dict)
    assessment_summary: str | None = None


class ComposeNoteResponse(BaseModel):
    markdown: str
    citations: list[dict[str, Any]]


class ComposeHandoffRequest(BaseModel):
    visit: VisitJSON
    facts: dict[str, Any] = Field(default_factory=dict)


class ComposeHandoffResponse(BaseModel):
    handoff: dict[str, Any]
    text: str


class ComposeDischargeRequest(BaseModel):
    visit: VisitJSON
    patient_name: str = "Patient"
    follow_up: list[str] = Field(default_factory=list)
    lang: str = "en"


class ComposeDischargeResponse(BaseModel):
    markdown: str
    language: str


class PlanpackRequest(BaseModel):
    plan_id: str
    facts: dict[str, Any] = Field(default_factory=dict)
    guard_context: dict[str, Any] = Field(default_factory=dict)


class PlanpackResponse(BaseModel):
    suggestion: dict[str, Any] | None
    available: list[str]
    guard_results: dict[str, dict[str, Any]]


class ChipResolveRequest(BaseModel):
    chip_id: str
    action: Literal["accept", "reject", "override", "dismiss"]
    value: str | None = None
    reason: str | None = None


@lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    return load_config()


@lru_cache(maxsize=1)
def get_cache() -> SQLiteChartCache:
    config = get_config()
    db_path = Path(config.get("cache", {}).get("db", "m1_cache.db"))
    cache = SQLiteChartCache(db_path)
    cache.initialise()
    return cache


@lru_cache(maxsize=1)
def get_extractor() -> LLMExtractor:
    config = get_config().get("llm", {})
    model_path = Path(config.get("path", "models/llama-3.2-3b-instruct-q4_ks.gguf"))
    llm_config = LLMConfig(
        model_path=model_path,
        n_ctx=int(config.get("ctx", 2048)),
        n_threads=int(config.get("threads", 4)),
        n_gpu_layers=int(config.get("n_gpu_layers", 0)),
        seed=int(config.get("seed", 42)),
        max_tokens=int(config.get("max_tokens", 512)),
        temperature=float(config.get("temperature", 0.0)),
    )
    return LLMExtractor(llm_config)


@lru_cache(maxsize=1)
def get_template_env() -> Environment:
    template_root = Path(__file__).resolve().parents[1] / "templates"
    return Environment(
        loader=FileSystemLoader(template_root),
        autoescape=select_autoescape(enabled_extensions=(".j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


@lru_cache(maxsize=1)
def get_planpack_service() -> PlanpackService:
    root = Path(__file__).resolve().parents[1] / "planpacks"
    return PlanpackService(root)


def _assessment_from_visit(visit: VisitJSON) -> str:
    if visit.risks:
        return f"Monitoring for {', '.join(visit.risks)}"
    return "Stable pending clinician reassessment"


def _score_visit(visit: VisitJSON, config: dict[str, Any]) -> list[SlotScore]:
    scores: list[SlotScore] = []
    risk_bump_cfg = config.get("confidence", {}).get("risk_bumps", {})
    for risk in visit.risks:
        slot_id = f"risk-{risk.lower().replace(' ', '-') }"
        score = SlotScore(
            slot_id=slot_id,
            label=f"Risk: {risk}",
            rule_hit=0.8,
            p_llm=0.4,
            c_asr=0.5,
            s_ont=0.6,
            s_ctx=0.5,
            rationale="History extraction",
        )
        bump = float(risk_bump_cfg.get(risk.lower(), 0.0))
        if bump:
            score.metadata["bump"] = bump
        scores.append(score)
    for intent in visit.plan_intents:
        slot_id = f"plan-{intent.name.lower().replace(' ', '-') }"
        score = SlotScore(
            slot_id=slot_id,
            label=f"Plan: {intent.name}",
            rule_hit=0.6,
            p_llm=0.4,
            c_asr=0.5,
            s_ont=0.4,
            s_ctx=0.5,
            rationale="Plan candidate from transcript",
        )
        scores.append(score)
    if not scores:
        scores.append(
            SlotScore(
                slot_id="summary-anchor",
                label="Pending clinician confirmation",
                rule_hit=0.2,
                p_llm=0.1,
                c_asr=0.0,
                s_ont=0.0,
                s_ctx=0.2,
                rationale="No structured items extracted",
            )
        )
    return scores


def _risk_overrides(config: dict[str, Any]) -> dict[str, float]:
    return {key: float(value) for key, value in config.get("confidence", {}).get("risk_bumps", {}).items()}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/facts/context")
def facts_context(
    window_hours: int = 72,
    patient_id: str = "demo-patient",
    cache: SQLiteChartCache = Depends(get_cache),
) -> dict[str, Any]:
    context = cache.context_window(window_hours, patient_id=patient_id)
    chips = cache.build_evidence_chips(patient_id, window_hours)
    return {
        "window_hours": window_hours,
        "labs": context["labs"],
        "vitals": context["vitals"],
        "notes": context["notes"],
        "chips": [chip.model_dump(mode="json") for chip in chips],
    }


@app.post("/extract/visit", response_model=ExtractResponse)
def extract_visit(
    payload: ExtractRequest,
    config: dict[str, Any] = Depends(get_config),
    extractor: LLMExtractor = Depends(get_extractor),
) -> ExtractResponse:
    start = time.perf_counter()
    visit = extractor.extract(payload.transcript)
    elapsed = time.perf_counter() - start
    metrics_store.record_timer("extract_s", elapsed)
    slot_scores = _score_visit(visit, config)
    overrides = _risk_overrides(config)
    chips = build_chips(slot_scores, risk_overrides=overrides)
    metrics_store.record_chips(chips)
    return ExtractResponse(visit=visit, slot_scores=slot_scores, chips=chips)


@app.post("/compose/note", response_model=ComposeNoteResponse)
def compose_note(
    payload: ComposeNoteRequest,
) -> ComposeNoteResponse:
    env = get_template_env()
    template = env.get_template("note.j2")
    assessment = payload.assessment_summary or _assessment_from_visit(payload.visit)
    citations = _build_citations(payload)
    markdown = template.render(
        visit=payload.visit,
        assessment_summary=assessment,
        citations=citations,
    )
    return ComposeNoteResponse(markdown=markdown, citations=citations)


def _build_citations(payload: ComposeNoteRequest) -> list[dict[str, Any]]:
    citations = [
        {"id": "chief", "text": "Clinician transcript", "ts": datetime.now(timezone.utc).isoformat()},
    ]
    labs = payload.facts.get("labs", [])
    for lab in labs:
        cid = f"lab-{lab.get('code', lab.get('id', 'unknown'))}"
        citations.append(
            {
                "id": cid,
                "text": f"{lab.get('label')} {lab.get('display_value')}",
                "ts": lab.get("ts"),
            }
        )
    return citations


@app.post("/compose/handoff", response_model=ComposeHandoffResponse)
def compose_handoff(payload: ComposeHandoffRequest) -> ComposeHandoffResponse:
    env = get_template_env()
    template = env.get_template("handoff_ipass.j2")
    handoff = _build_handoff(payload.visit, payload.facts)
    text = template.render(handoff=handoff)
    return ComposeHandoffResponse(handoff=handoff, text=text)


def _build_handoff(visit: VisitJSON, facts: dict[str, Any]) -> dict[str, Any]:
    severity = "Watcher" if visit.risks else "Stable"
    actions = [intent.name for intent in visit.plan_intents]
    pending = []
    for lab in facts.get("labs", []):
        pending.append({"name": lab.get("label"), "due": lab.get("ts")})
    contingency = "Escalate to attending if new red flags emerge."
    return {
        "illness_severity": severity,
        "summary": f"{visit.chief_complaint} with {', '.join(visit.risks) if visit.risks else 'no high-risk findings'}.",
        "actions": actions or ["Confirm plan with bedside team"],
        "pending": pending,
        "contingency": contingency,
    }


@app.post("/compose/discharge", response_model=ComposeDischargeResponse)
def compose_discharge(payload: ComposeDischargeRequest) -> ComposeDischargeResponse:
    env = get_template_env()
    template_name = "discharge_es.j2" if payload.lang.lower().startswith("es") else "discharge_en.j2"
    template = env.get_template(template_name)
    markdown = template.render(
        visit=payload.visit,
        patient_name=payload.patient_name,
        follow_up=payload.follow_up,
    )
    return ComposeDischargeResponse(markdown=markdown, language=payload.lang)


@app.post("/suggest/planpack", response_model=PlanpackResponse)
def suggest_planpack(
    payload: PlanpackRequest,
    service: PlanpackService = Depends(get_planpack_service),
) -> PlanpackResponse:
    guard_results = _evaluate_guards(payload.guard_context, payload.facts)
    triggered = {name for name, result in guard_results.items() if result.requires_override}
    suggestion = service.suggest(payload.plan_id, triggered)
    suggestion_dict = suggestion.model_dump(mode="json") if suggestion else None
    guard_dump = {
        name: {
            "status": result.status,
            "band": result.band,
            "rationale": result.rationale,
        }
        for name, result in guard_results.items()
    }
    return PlanpackResponse(
        suggestion=suggestion_dict,
        available=service.available(),
        guard_results=guard_dump,
    )


def _evaluate_guards(context: dict[str, Any], facts: dict[str, Any]) -> dict[str, GuardResult]:
    results: dict[str, GuardResult] = {}
    allergy_target = context.get("allergy_substance", "aspirin")
    results["allergy"] = guard_allergy(facts, allergy_target)
    results["active_bleed"] = guard_active_bleed(facts)
    results["pregnancy"] = guard_pregnancy(facts)
    need_contrast = bool(context.get("need_contrast", False))
    results["renal"] = guard_renal(facts, need_contrast=need_contrast)
    results["anticoag"] = guard_anticoag(facts)
    return results


@app.post("/chips/resolve")
def chips_resolve(payload: ChipResolveRequest, config: dict[str, Any] = Depends(get_config)) -> dict[str, Any]:
    log_path = Path(config.get("audit", {}).get("log", "logs/audit.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = ChipActionAudit(
        ts=datetime.now(timezone.utc),
        chip_id=payload.chip_id,
        action=payload.action,
        value=payload.value,
        reason=payload.reason,
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.model_dump(mode="json")) + "\n")
    return {"ok": True}


@app.get("/metrics/session")
def metrics() -> dict[str, Any]:
    thresholds = {band: BAND_THRESHOLDS.get(band) for band in ["A", "B", "C"]}
    snapshot = metrics_store.snapshot()
    snapshot["thresholds"] = thresholds
    return snapshot


