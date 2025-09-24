"""Pydantic models exposed via the FastAPI application."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..evidence.sqlite_cache import EvidenceItem
from ..extractor.llm import VisitJSON


class HealthResponse(BaseModel):
    status: str = Field(default="ok")


class IngestRequest(BaseModel):
    patient_id: str = Field(..., example="patient-123")
    transcript: str = Field(..., example="Patient reports chest pain since yesterday...")


class GuardReport(BaseModel):
    blocked: bool = False
    reason: Optional[str] = None
    flags: List[str] = Field(default_factory=list)


class Chip(BaseModel):
    label: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)


class IngestResponse(BaseModel):
    patient_id: str
    sections: dict
    guard: GuardReport
    chips: List[Chip]


class EvidenceItemModel(BaseModel):
    patient_id: str
    section: str
    payload: dict

    @classmethod
    def from_item(cls, item: EvidenceItem) -> "EvidenceItemModel":
        return cls(patient_id=item.patient_id, section=item.section, payload=item.payload)


class EvidenceResponse(BaseModel):
    patient_id: str
    evidence: List[EvidenceItemModel]


class ExtractRequest(BaseModel):
    patient_id: Optional[str] = Field(default=None)
    transcript: str


class ExtractResponse(BaseModel):
    patient_id: Optional[str]
    visit: VisitJSON


class ComposeRequest(BaseModel):
    patient_id: str
    template: str = Field(pattern="^(note|handoff|discharge)$")
    bundle: Optional[dict] = None
    locale: str = Field(default="en")


class ComposeResponse(BaseModel):
    patient_id: str
    template: str
    content: str


class PlanpackRequest(BaseModel):
    planpack_id: str = Field(example="chest_pain")


class PlanpackResponse(BaseModel):
    id: str
    title: str
    checklist: List[str]
    contingencies: List[dict]
    notes: str


class ChipResolveRequest(BaseModel):
    bundle: dict
    extraction: VisitJSON


class ChipResolveResponse(BaseModel):
    chips: List[Chip]


class ContextResponse(BaseModel):
    patient_id: str
    context: List[str]


class MetricsResponse(BaseModel):
    session_id: str
    active_users: int
    processed_transcripts: int


class ExportRequest(BaseModel):
    patient_id: str
    bundle: dict
    format: str = Field(pattern="^(pdf|rtf)$")
    filename: Optional[str] = None


class ExportResponse(BaseModel):
    path: str
