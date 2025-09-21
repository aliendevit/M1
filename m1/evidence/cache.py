"""Local chart cache helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from ..schemas import EvidenceChip, EvidenceKind


@dataclass
class ChartFact:
    source_id: str
    name: str
    value: str
    kind: EvidenceKind
    time: str
    delta: str | None = None

    def to_chip(self) -> EvidenceChip:
        return EvidenceChip(
            id=self.source_id,
            kind=self.kind,
            name=self.name,
            value=self.value,
            delta=self.delta,
            time=self.time,
            source_id=self.source_id,
        )


@dataclass
class ChartCache:
    """In-memory cache used for unit tests and offline development."""

    facts: Dict[str, ChartFact] = field(default_factory=dict)

    def add_fact(self, fact: ChartFact) -> None:
        self.facts[fact.source_id] = fact

    def context_window(self, window_hours: int) -> List[EvidenceChip]:
        return [fact.to_chip() for fact in self.facts.values()]

    def load_from_iterable(self, entries: Iterable[dict]) -> None:
        for entry in entries:
            kind = EvidenceKind(entry.get("kind", "note"))
            fact = ChartFact(
                source_id=entry["source_id"],
                name=entry["name"],
                value=entry["value"],
                kind=kind,
                time=entry["time"],
                delta=entry.get("delta"),
            )
            self.add_fact(fact)
