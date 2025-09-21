"""Pydantic schemas shared across services and API layers."""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PlanIntentType(str, Enum):
    lab_series = "lab_series"
    test = "test"
    med_admin = "med_admin"
    education = "education"


class PlanIntent(BaseModel):
    type: PlanIntentType
    name: str
    dose: Optional[str] = None
    schedule: List[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name must be provided")
        return value


class HPI(BaseModel):
    onset: Optional[str] = None
    quality: Optional[str] = None
    modifiers: List[str] = Field(default_factory=list)
    associated_symptoms: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)


class VisitJSON(BaseModel):
    chief_complaint: str
    hpi: HPI
    exam_bits: Dict[str, Optional[str]] = Field(default_factory=dict)
    risks: List[str] = Field(default_factory=list)
    plan_intents: List[PlanIntent] = Field(default_factory=list)
    language_pref: Optional[str] = None

    @field_validator("chief_complaint")
    @classmethod
    def validate_chief_complaint(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("chief_complaint must not be empty")
        return value


class EvidenceKind(str, Enum):
    lab = "lab"
    vital = "vital"
    note = "note"
    image = "image"


class EvidenceChip(BaseModel):
    id: str
    kind: EvidenceKind
    name: str
    value: str
    delta: Optional[str] = None
    time: str
    source_id: str


class ChipBand(str, Enum):
    auto = "A"
    soft = "B"
    must = "C"
    blocked = "D"


class ChipType(str, Enum):
    value = "value"
    missing = "missing"
    guard = "guard"
    ambiguity = "ambiguity"
    timer = "timer"
    unit = "unit"


class ChipAction(str, Enum):
    accept = "accept"
    edit = "edit"
    override_blocked = "override_blocked"
    evidence = "evidence"


class Chip(BaseModel):
    chip_id: str
    slot: str
    type: ChipType
    band: ChipBand
    label: str
    options: List[str] = Field(default_factory=list)
    proposed: Optional[str] = None
    confidence: float = 0.0
    risk: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    actions: List[ChipAction] = Field(default_factory=list)


class SlotScore(BaseModel):
    rule_hit: float = 0.0
    p_llm: float = 0.0
    c_asr: float = 0.0
    s_ont: float = 0.0
    s_ctx: float = 0.0

    def confidence(self, weights: "ConfidenceWeights") -> float:
        return (
            self.rule_hit * weights.rule_hit
            + self.p_llm * weights.p_llm
            + self.c_asr * weights.asr
            + self.s_ont * weights.ontology
            + self.s_ctx * weights.context
        )


class ExtractVisitResponse(BaseModel):
    visit: VisitJSON
    slot_scores: Dict[str, SlotScore]


class PlanpackGuardFlag(BaseModel):
    guard: str
    status: str
    detail: Optional[str] = None


class PlanpackSuggestion(BaseModel):
    kind: str
    payload: Dict[str, str]
    guard: Optional[str] = None


class PlanpackResponse(BaseModel):
    suggestions: List[PlanpackSuggestion]
    guard_flags: List[PlanpackGuardFlag]


# Forward declaration for typing (avoids circular import).
from .config import ConfidenceWeights  # noqa  E402
