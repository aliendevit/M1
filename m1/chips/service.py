"""Confidence helpers for chip generation."""
from __future__ import annotations

from typing import Dict, List

from ..config import ConfidenceConfig
from ..schemas import Chip, ChipAction, ChipBand, ChipType, SlotScore

def score_slot(slot: str, slot_score: SlotScore, confidence: ConfidenceConfig, *, label: str, risk: str = "low") -> Chip:
    value = slot_score.confidence(confidence.weights)
    thresholds = confidence.thresholds
    if value >= thresholds.auto_accept:
        band = ChipBand.auto
    elif value >= thresholds.soft_confirm:
        band = ChipBand.soft
    elif value >= thresholds.must_confirm:
        band = ChipBand.must
    else:
        band = ChipBand.blocked
    if risk == "high":
        value += confidence.risk_bumps.high
    elif risk == "medium":
        value += confidence.risk_bumps.medium
    band_actions = {
        ChipBand.auto: [ChipAction.accept],
        ChipBand.soft: [ChipAction.accept, ChipAction.evidence],
        ChipBand.must: [ChipAction.accept, ChipAction.edit, ChipAction.evidence],
        ChipBand.blocked: [ChipAction.edit, ChipAction.evidence],
    }
    return Chip(
        chip_id=f"chip_{slot}",
        slot=slot,
        type=ChipType.value,
        band=band,
        label=label,
        options=[],
        proposed=None,
        confidence=round(value, 3),
        risk=risk,
        evidence=[],
        actions=band_actions[band],
    )


def build_chips(slot_scores: Dict[str, SlotScore], confidence: ConfidenceConfig) -> List[Chip]:
    chips: List[Chip] = []
    for slot, slot_score in slot_scores.items():
        chips.append(score_slot(slot, slot_score, confidence, label=slot.replace("_", " ")))
    return chips
