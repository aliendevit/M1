# path: backend/db/models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Fact:
    id: str
    kind: str                  # lab|vital|med|note|image
    name: str
    value: Optional[str]
    time: Optional[str]        # ISO8601
    source_id: Optional[str]

    @staticmethod
    def from_row(r: Any) -> "Fact":
        return Fact(
            id=r["id"], kind=r["kind"], name=r["name"],
            value=r["value"], time=r["time"], source_id=r["source_id"]
        )

    def to_tuple(self):
        return (self.id, self.kind, self.name, self.value, self.time, self.source_id)


@dataclass
class ChipRow:
    chip_id: str
    slot: Optional[str]
    type: Optional[str]
    band: Optional[str]
    label: Optional[str]
    proposed: Optional[str]
    confidence: Optional[float]
    risk: Optional[str]
    evidence_json: Optional[str]   # JSON string
    actions_json: Optional[str]    # JSON string
    state: str
    reason: Optional[str]
    created_at: str
    updated_at: str

    @staticmethod
    def from_row(r: Any) -> "ChipRow":
        return ChipRow(
            chip_id=r["chip_id"], slot=r["slot"], type=r["type"], band=r["band"],
            label=r["label"], proposed=r["proposed"], confidence=r["confidence"], risk=r["risk"],
            evidence_json=r["evidence"], actions_json=r["actions"],
            state=r["state"], reason=r["reason"],
            created_at=r["created_at"], updated_at=r["updated_at"]
        )

    def to_tuple(self):
        return (
            self.chip_id, self.slot, self.type, self.band, self.label, self.proposed,
            self.confidence, self.risk, self.evidence_json, self.actions_json,
            self.state, self.reason, self.created_at, self.updated_at
        )


@dataclass
class SessionRow:
    session_id: str
    started_at: str
    last_seen_at: str
    keystrokes: int
    timers_json: Optional[str]         # JSON string
    chip_counts_json: Optional[str]    # JSON string

    @staticmethod
    def from_row(r: Any) -> "SessionRow":
        return SessionRow(
            session_id=r["session_id"], started_at=r["started_at"], last_seen_at=r["last_seen_at"],
            keystrokes=r["keystrokes"], timers_json=r["timers"], chip_counts_json=r["chip_counts"]
        )

    def to_tuple(self):
        return (
            self.session_id, self.started_at, self.last_seen_at,
            self.keystrokes, self.timers_json, self.chip_counts_json
        )


@dataclass
class KVPair:
    k: str
    v: Optional[str]
    updated_at: str

    @staticmethod
    def from_row(r: Any) -> "KVPair":
        return KVPair(k=r["k"], v=r["v"], updated_at=r["updated_at"])

    def to_tuple(self):
        return (self.k, self.v, self.updated_at)
