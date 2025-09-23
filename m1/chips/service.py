from __future__ import annotations

from typing import Iterable

from m1.models import EvidenceChip, SlotScore

DEFAULT_WEIGHTS = {
    "rule_hit": 0.35,
    "p_llm": 0.25,
    "c_asr": 0.15,
    "s_ont": 0.10,
    "s_ctx": 0.15,
}

BAND_THRESHOLDS = {
    "A": 0.90,
    "B": 0.70,
    "C": 0.45,
}


def compute_confidence(score: SlotScore, weights: dict[str, float] | None = None, bump: float = 0.0) -> float:
    """Compute blended confidence score using configured weights."""

    weights = weights or DEFAULT_WEIGHTS
    total = 0.0
    for field, weight in weights.items():
        value = getattr(score, field, 0.0)
        total += float(value) * weight
    total = max(0.0, min(1.0, total + bump))
    return round(total, 3)


def band(confidence: float) -> str:
    """Return band letter for a given confidence."""

    if confidence >= BAND_THRESHOLDS["A"]:
        return "A"
    if confidence >= BAND_THRESHOLDS["B"]:
        return "B"
    if confidence >= BAND_THRESHOLDS["C"]:
        return "C"
    return "D"


def build_chip(score: SlotScore, weights: dict[str, float] | None = None, bump: float = 0.0) -> EvidenceChip:
    conf = compute_confidence(score, weights=weights, bump=bump)
    chip_band = band(conf)
    return EvidenceChip(
        chip_id=score.slot_id,
        label=score.label,
        band=chip_band,
        confidence=conf,
        rationale=score.rationale,
        guard=score.guard,
        metadata=score.metadata,
    )


def build_chips(
    slot_scores: Iterable[SlotScore],
    weights: dict[str, float] | None = None,
    risk_overrides: dict[str, float] | None = None,
) -> list[EvidenceChip]:
    """Construct chips from score inputs with optional risk overrides."""

    risk_overrides = risk_overrides or {}
    chips: list[EvidenceChip] = []
    for score in slot_scores:
        bump = risk_overrides.get(score.slot_id, 0.0)
        chips.append(build_chip(score, weights=weights, bump=bump))
    return chips
