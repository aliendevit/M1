"""Pydantic models exposed via the FastAPI application."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from ..evidence.sqlite_cache import EvidenceItem


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
