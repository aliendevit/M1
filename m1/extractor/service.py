"""Rule-first extractor that produces VisitJSON payloads."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from ..schemas import HPI, PlanIntent, PlanIntentType, SlotScore, VisitJSON

CHIEF_COMPLAINT_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"chief complaint[:\s]+(?P<value>[^\.;\n]+)", re.I),
    re.compile(r"here for (?P<value>[^\.;\n]+)", re.I),
)

ONSET_PATTERN = re.compile(r"(symptoms?|pain) (?:started|began) (?P<value>[^\.;\n]+)", re.I)
QUALITY_PATTERN = re.compile(r"(?:describes|described) (?:it|pain) as (?P<value>[^\.;\n]+)", re.I)
MODIFIER_PATTERN = re.compile(r"worse with (?P<value>[^\.;\n]+)", re.I)
ASSOCIATED_PATTERN = re.compile(r"associated with (?P<value>[^\.;\n]+)", re.I)
RED_FLAG_PATTERN = re.compile(r"denies (?P<value>[^\.;\n]+ red flags?)", re.I)

RISK_KEYWORDS = {
    "smoker": "tobacco use",
    "afib": "atrial fibrillation",
    "diabetes": "diabetes",
}

PLAN_LINE_PATTERN = re.compile(
    r"(?P<type>labs?|tests?|meds?|education)[:\s]+(?P<value>.+)", re.I
)


@dataclass
class ExtractionResult:
    visit: VisitJSON
    slot_scores: Dict[str, SlotScore]


def _normalise_list(value: str) -> List[str]:
    return [item.strip() for item in re.split(r",|;| and ", value) if item.strip()]


def _first_match(text: str, patterns: Sequence[re.Pattern[str]]) -> str | None:
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
        payload = match.group("value").strip()
        if plan_type.startswith("lab"):
            intent_type = PlanIntentType.lab_series
        elif plan_type.startswith("test"):
            intent_type = PlanIntentType.test
        elif plan_type.startswith("med"):
            intent_type = PlanIntentType.med_admin
        else:
            intent_type = PlanIntentType.education
        schedule = []
        dose = None
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


def extract_visit(transcript: str, chart_facts: Iterable[str] | None = None) -> ExtractionResult:
    """Produce a VisitJSON structure from transcript snippets.

    The extractor is intentionally conservative: when a slot cannot be
    filled deterministically we leave it empty so a chip can surface the
    ambiguity to the clinician.
    """

    text = transcript or ""
    lower_text = text.lower()

    chief_complaint = _first_match(text, CHIEF_COMPLAINT_PATTERNS) or "unspecified concern"

    onset = match.group("value").strip() if (match := ONSET_PATTERN.search(text)) else None
    quality = match.group("value").strip() if (match := QUALITY_PATTERN.search(text)) else None
    modifiers = _normalise_list(match.group("value")) if (match := MODIFIER_PATTERN.search(text)) else []
    associated = _normalise_list(match.group("value")) if (match := ASSOCIATED_PATTERN.search(text)) else []
    red_flags = _normalise_list(match.group("value")) if (match := RED_FLAG_PATTERN.search(text)) else []

    risks: List[str] = []
    slot_scores: Dict[str, SlotScore] = {
        "chief_complaint": SlotScore(rule_hit=1.0, s_ctx=0.4),
    }
    for keyword, canonical in RISK_KEYWORDS.items():
        if keyword in lower_text:
            risks.append(canonical)
    if risks:
        slot_scores["risks"] = SlotScore(rule_hit=1.0, s_ctx=0.2)

    plan_lines = [line.strip() for line in text.splitlines() if line.strip().lower().startswith(("lab", "test", "med", "education"))]
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
        language_pref=None,
    )

    return ExtractionResult(visit=visit, slot_scores=slot_scores)
