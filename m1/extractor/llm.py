"""Hybrid extractor that uses rules first and a tiny LLM as a backstop."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import ValidationError

from ..config import LLMConfig
from ..schemas import HPI, PlanIntent, PlanIntentType, SlotScore, VisitJSON

try:  # pragma: no cover - optional dependency
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Llama = None  # type: ignore


@dataclass
class ExtractionResult:
    visit: VisitJSON
    slot_scores: Dict[str, SlotScore]


CHIEF_COMPLAINT_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"chief complaint[:\s]+(?P<value>[^\.;\n]+)", re.I),
    re.compile(r"here for (?P<value>[^\.;\n]+)", re.I),
    re.compile(r"presenting with (?P<value>[^\.;\n]+)", re.I),
)

ONSET_PATTERN = re.compile(r"(symptoms?|pain) (?:started|began) (?P<value>[^\.;\n]+)", re.I)
QUALITY_PATTERN = re.compile(r"(?:describes|described) (?:it|pain) as (?P<value>[^\.;\n]+)", re.I)
MODIFIER_PATTERN = re.compile(r"worse with (?P<value>[^\.;\n]+)", re.I)
ASSOCIATED_PATTERN = re.compile(r"associated with (?P<value>[^\.;\n]+)", re.I)
RED_FLAG_PATTERN = re.compile(r"denies (?P<value>[^\.;\n]+ red flags?)", re.I)
LANG_PREF_PATTERN = re.compile(r"prefers spanish|spanish interpreter", re.I)

RISK_KEYWORDS = {
    "smoker": "tobacco use",
    "afib": "atrial fibrillation",
    "diabetes": "diabetes",
    "bleeding": "active bleed",
    "pregnant": "pregnancy",
}

PLAN_LINE_PATTERN = re.compile(
    r"(?P<type>labs?|tests?|meds?|medication|education)[:\s]+(?P<value>.+)", re.I
)


def _normalise_list(value: str) -> List[str]:
    return [item.strip() for item in re.split(r",|;| and ", value) if item.strip()]


def _first_match(text: str, patterns: Sequence[re.Pattern[str]]) -> Optional[str]:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group("value").strip()
    return None


def _extract_plan_intents(lines: Iterable[str]) -> Tuple[List[PlanIntent], Dict[str, SlotScore]]:
    intents: List[PlanIntent] = []
    slot_scores: Dict[str, SlotScore] = {}
    for line in lines:
        match = PLAN_LINE_PATTERN.search(line)
        if not match:
            continue
        plan_type = match.group("type").lower()
        payload = match.group("value").strip().rstrip(".")
        if plan_type.startswith("lab"):
            intent_type = PlanIntentType.lab_series
        elif plan_type.startswith("test"):
            intent_type = PlanIntentType.test
        elif plan_type.startswith("med"):
            intent_type = PlanIntentType.med_admin
        else:
            intent_type = PlanIntentType.education
        schedule: List[str] = []
        dose: Optional[str] = None
        if intent_type is PlanIntentType.med_admin:
            dose_match = re.search(r"(\d+\s?mg|\d+\s?mcg|\d+\s?g)", payload, re.I)
            if dose_match:
                dose = dose_match.group(0)
        if intent_type is PlanIntentType.lab_series:
            schedule = _normalise_list(payload)
        intents.append(
            PlanIntent(type=intent_type, name=payload.split(" ")[0].strip(","), dose=dose, schedule=schedule)
        )
        slot_scores[f"plan_intent_{len(intents)}"] = SlotScore(rule_hit=1.0, s_ctx=0.5)
    return intents, slot_scores


class VisitJSONExtractor:
    """Extractor that prefers deterministic parsing with an optional LLM."""

    def __init__(self, config: LLMConfig, *, enable_llm: bool = True) -> None:
        self.config = config
        self.enable_llm = enable_llm and Llama is not None
        self._llm = None
        if self.enable_llm:  # pragma: no cover - optional dependency
            try:
                self._llm = Llama(
                    model_path=config.path,
                    n_threads=config.threads,
                    n_ctx=config.ctx,
                    n_gpu_layers=config.n_gpu_layers,
                )
            except Exception:
                self._llm = None

    def extract(self, transcript: str, chart_facts: Iterable[str] | None = None) -> ExtractionResult:
        chart_facts = list(chart_facts or [])
        draft_visit, slot_scores = self._rule_extract(transcript)
        if self.enable_llm and self._llm is not None:  # pragma: no cover - requires optional dep
            draft_visit, slot_scores = self._llm_fill(draft_visit, transcript, chart_facts, slot_scores)
        return ExtractionResult(visit=draft_visit, slot_scores=slot_scores)

    # ------------------------------------------------------------------
    # Deterministic extraction
    # ------------------------------------------------------------------
    def _rule_extract(self, transcript: str) -> Tuple[VisitJSON, Dict[str, SlotScore]]:
        text = transcript or ""
        lower_text = text.lower()
        chief_complaint = _first_match(text, CHIEF_COMPLAINT_PATTERNS) or "unspecified concern"

        onset = match.group("value").strip() if (match := ONSET_PATTERN.search(text)) else None
        quality = match.group("value").strip() if (match := QUALITY_PATTERN.search(text)) else None
        modifiers = _normalise_list(match.group("value")) if (match := MODIFIER_PATTERN.search(text)) else []
        associated = _normalise_list(match.group("value")) if (match := ASSOCIATED_PATTERN.search(text)) else []
        red_flags = _normalise_list(match.group("value")) if (match := RED_FLAG_PATTERN.search(text)) else []

        language_pref = "es" if LANG_PREF_PATTERN.search(lower_text) else None

        risks: List[str] = []
        slot_scores: Dict[str, SlotScore] = {
            "chief_complaint": SlotScore(rule_hit=1.0, s_ctx=0.4),
        }
        for keyword, canonical in RISK_KEYWORDS.items():
            if keyword in lower_text:
                risks.append(canonical)
        if risks:
            slot_scores["risks"] = SlotScore(rule_hit=1.0, s_ctx=0.2)

        plan_lines = [match.group(0).strip() for match in PLAN_LINE_PATTERN.finditer(text)]
        plan_intents, plan_scores = _extract_plan_intents(plan_lines)
        slot_scores.update(plan_scores)

        visit = VisitJSON(
            chief_complaint=chief_complaint,
            hpi=HPI(
                onset=onset,
                quality=quality,
                modifiers=modifiers,
                associated_symptoms=associated,
                red_flags=red_flags,
            ),
            exam_bits={"cv": None, "lungs": None},
            risks=risks,
            plan_intents=plan_intents,
            language_pref=language_pref,
        )
        return visit, slot_scores

    # ------------------------------------------------------------------
    # Optional LLM backfill
    # ------------------------------------------------------------------
    def _llm_fill(
        self,
        visit: VisitJSON,
        transcript: str,
        chart_facts: List[str],
        slot_scores: Dict[str, SlotScore],
    ) -> Tuple[VisitJSON, Dict[str, SlotScore]]:
        """Use llama.cpp to backfill clearly structured JSON."""

        missing_fields: List[str] = []
        if not visit.hpi.onset:
            missing_fields.append("hpi.onset")
        if not visit.hpi.quality:
            missing_fields.append("hpi.quality")
        if missing_fields:
            prompt = self._build_prompt(transcript, chart_facts, missing_fields)
            response = self._invoke_llm(prompt)
            if response:
                visit, slot_scores = self._merge_llm_json(visit, response, slot_scores, missing_fields)
        return visit, slot_scores

    def _build_prompt(self, transcript: str, chart_facts: List[str], fields: List[str]) -> str:
        payload = {
            "transcript": transcript,
            "chart_facts": chart_facts,
            "fields": fields,
        }
        return json.dumps(payload)

    def _invoke_llm(self, prompt: str) -> Optional[str]:
        if self._llm is None:
            return None
        # pragma: no cover - heavy dependency path
        output = self._llm.create_completion(
            prompt=prompt,
            max_tokens=256,
            temperature=self.config.temperature,
            stop=["\n"]
        )
        text = output.get("choices", [{}])[0].get("text", "")
        return text.strip()

    def _merge_llm_json(
        self,
        visit: VisitJSON,
        response: str,
        slot_scores: Dict[str, SlotScore],
        missing_fields: List[str],
    ) -> Tuple[VisitJSON, Dict[str, SlotScore]]:
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return visit, slot_scores
        updates = {}
        for field in missing_fields:
            value = data
            for part in field.split("."):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            updates[field] = value
        visit_dict = visit.model_dump()
        for field, value in updates.items():
            if value in (None, "", []):
                continue
            target = visit_dict
            parts = field.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
            slot_scores[field] = SlotScore(rule_hit=0.0, p_llm=1.0)
        try:
            visit = VisitJSON.model_validate(visit_dict)
        except ValidationError:
            return visit, slot_scores
        return visit, slot_scores


def extract_with_llm(config: LLMConfig, transcript: str, chart_facts: Iterable[str] | None = None) -> ExtractionResult:
    extractor = VisitJSONExtractor(config=config)
    return extractor.extract(transcript, chart_facts)
