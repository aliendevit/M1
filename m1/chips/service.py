"""Confidence scoring for structured chips."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(slots=True)
class ConfidenceConfig:
    thresholds: Dict[str, float]
    weights: Dict[str, float]

    @classmethod
    def default(cls) -> "ConfidenceConfig":
        return cls(
            thresholds={"A": 0.9, "B": 0.7, "C": 0.45},
            weights={"rule_hit": 0.35, "p_llm": 0.25, "c_asr": 0.15, "s_ont": 0.1, "s_ctx": 0.15},
        )


class ChipService:
    """Produce simple chips from extraction output."""

    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self.config = config or ConfidenceConfig.default()

    @classmethod
    def from_config(cls, data: Dict[str, object] | None) -> "ChipService":
        if not data:
            return cls()
        thresholds = data.get("thresholds") if isinstance(data.get("thresholds"), dict) else None
        weights = data.get("weights") if isinstance(data.get("weights"), dict) else None
        config = ConfidenceConfig(
            thresholds=thresholds or ConfidenceConfig.default().thresholds,
            weights=weights or ConfidenceConfig.default().weights,
        )
        return cls(config)

    def generate(self, bundle: Dict[str, object], extraction: Dict[str, object]) -> List[dict]:
        chips: List[dict] = []
        problems = extraction.get("problems") or []
        for item in problems:
            chips.append(self._chip("Problem", item, base_confidence=0.92))

        meds = extraction.get("medications") or []
        for item in meds:
            chips.append(self._chip("Medication", item, base_confidence=0.75))

        vitals = extraction.get("vitals") or {}
        for key, value in vitals.items():
            label = key.replace("_", " ").title()
            chips.append(self._chip(label, value, base_confidence=0.65))

        plan = extraction.get("plan") or []
        for item in plan:
            chips.append(self._chip("Plan", item, base_confidence=0.7))
        return chips

    def _chip(self, label: str, value: str, base_confidence: float) -> dict:
        band = self._band(base_confidence)
        return {"label": f"{label} ({band})", "value": value, "confidence": round(base_confidence, 3)}

    def _band(self, score: float) -> str:
        for band, threshold in sorted(self.config.thresholds.items(), key=lambda item: item[1], reverse=True):
            if score >= threshold:
                return band
        return "D"
