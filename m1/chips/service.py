"""Confidence helpers and chip UX scaffolding."""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel"""Confidence helpers for chip generation."""
from __future__ import annotations

from typing import Dict, List
from ..config import ConfidenceConfig
from ..schemas import Chip, ChipAction, ChipBand, ChipType, SlotScore
def compute_confidence(slot_score: SlotScore, confidence: ConfidenceConfig, risk: str = "low") -> float:
    value = (
        slot_score.rule_hit * confidence.weights.rule_hit
        + slot_score.p_llm * confidence.weights.p_llm
        + slot_score.c_asr * confidence.weights.asr
        + slot_score.s_ont * confidence.weights.ontology
        + slot_score.s_ctx * confidence.weights.context
    )def score_slot(slot: str, slot_score: SlotScore, confidence: ConfidenceConfig, *, label: str, risk: str = "low") -> Chip:
    value = slot_score.confidence(confidence.weights)
    thresholds = confidence.thresholds
    if value >= thresholds.auto_accept:
        band = ChipBand.auto
    elif value >= thresholds.soft_confirm:
        band = ChipBand.soft
    elif value >= thresholds.must_confirm:
        band = ChipBand.must
    else:
        band = ChipBand.blocked    if risk == "high":
        value += confidence.risk_bumps.high
    elif risk == "medium":
        value += confidence.risk_bumps.medium    return max(0.0, min(1.0, round(value, 3)))

def band_for_score(value: float, confidence: ConfidenceConfig, *, guard_status: Optional[str] = None) -> ChipBand:
    if guard_status in {"blocked", "unknown"}:
        return ChipBand.blocked
    thresholds = confidence.thresholds
    if value >= thresholds.auto_accept:
        return ChipBand.auto
    if value >= thresholds.soft_confirm:
        return ChipBand.soft
    if value >= thresholds.must_confirm:
        return ChipBand.must
    return ChipBand.blocked


def build_chip(
    slot: str,
    slot_score: SlotScore,
    confidence: ConfidenceConfig,
    *,
    label: Optional[str] = None,
    risk: str = "low",
    guard_status: Optional[str] = None,
) -> Chip:
    score = compute_confidence(slot_score, confidence, risk)
    band = band_for_score(score, confidence, guard_status=guard_status)
    actions = {
        ChipBand.auto: [ChipAction.accept],
        ChipBand.soft: [ChipAction.accept, ChipAction.evidence],
        ChipBand.must: [ChipAction.accept, ChipAction.edit, ChipAction.evidence],
        ChipBand.blocked: [ChipAction.edit, ChipAction.override_blocked, ChipAction.evidence],
    }[band]
    band_actions = {
        ChipBand.auto: [ChipAction.accept],
        ChipBand.soft: [ChipAction.accept, ChipAction.evidence],
        ChipBand.must: [ChipAction.accept, ChipAction.edit, ChipAction.evidence],
        ChipBand.blocked: [ChipAction.edit, ChipAction.evidence],
    }    return Chip(
        chip_id=f"chip_{slot}",
        slot=slot,
        type=ChipType.value,
        band=band,        label=label or slot.replace("_", " "),
        options=[],
        proposed=None,
        confidence=score,
        risk=risk,
        evidence=[],
        actions=actions,
    )


def build_chips(
    slot_scores: Dict[str, SlotScore],
    confidence: ConfidenceConfig,
    *,
    risk_overrides: Optional[Dict[str, str]] = None,
) -> List[Chip]:
    chips: List[Chip] = []
    risk_overrides = risk_overrides or {}
    for slot, slot_score in slot_scores.items():
        risk = risk_overrides.get(slot, "low")
        chips.append(build_chip(slot, slot_score, confidence, risk=risk))
    return chips


def compute_batch_actions(chips: Iterable[Chip]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = defaultdict(list)
    for chip in chips:
        if chip.band is ChipBand.soft:
            groups[chip.label].append(chip.chip_id)
    return {label: ids for label, ids in groups.items() if len(ids) >= 3}


KEYBOARD_ACTIONS: Dict[str, ChipAction] = {
    "enter": ChipAction.accept,
    "return": ChipAction.accept,
    "1": ChipAction.accept,
    "2": ChipAction.edit,
    "3": ChipAction.override_blocked,
    "e": ChipAction.evidence,
}


def keyboard_action_for(chip: Chip, key: str) -> Optional[ChipAction]:
    action = KEYBOARD_ACTIONS.get(key.lower())
    if action and action in chip.actions:
        return action
    return None


class ChipResolution(BaseModel):
    chip_id: str
    action: str
    value: Optional[str] = None
    reason: Optional[str] = None        label=label,
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