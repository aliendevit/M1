"""Rule-centric extraction with a lightweight heuristic fallback."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(slots=True)
class ExtractionResult:
    problems: List[str]
    medications: List[str]
    vitals: Dict[str, str]
    plan: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "problems": self.problems,
            "medications": self.medications,
            "vitals": self.vitals,
            "plan": self.plan,
        }


class VisitExtractor:
    """Very small heuristic extractor used until an LLM backend is wired in."""

    def __init__(self, model_path: str | None = None, ctx: int | None = None) -> None:
        self.model_path = model_path
        self.ctx = ctx or 2048

    @classmethod
    def from_config(cls, config: Dict[str, object]) -> "VisitExtractor":
        return cls(
            model_path=str(config.get("path", "rule-only")) if config else None,
            ctx=int(config.get("ctx", 2048)) if config else 2048,
        )

    def extract(self, transcript: str) -> Dict[str, object]:
        cleaned = transcript.strip()
        if not cleaned:
            return ExtractionResult([], [], {}, []).to_dict()

        problems = self._extract_problems(cleaned)
        medications = self._extract_medications(cleaned)
        vitals = self._extract_vitals(cleaned)
        plan = self._extract_plan(cleaned)
        return ExtractionResult(problems, medications, vitals, plan).to_dict()

    def _extract_problems(self, text: str) -> List[str]:
        patterns = [
            r"chest pain",
            r"shortness of breath",
            r"fever",
            r"cough",
            r"seizure",
        ]
        findings = {match.lower() for pattern in patterns for match in re.findall(pattern, text, flags=re.I)}
        if "pain" in text.lower() and "chest pain" not in findings:
            findings.add("pain")
        return sorted(findings)

    def _extract_medications(self, text: str) -> List[str]:
        meds = []
        for med in ["aspirin", "nitro", "metoprolol", "insulin"]:
            if re.search(rf"\b{med}\b", text, flags=re.I):
                meds.append(med)
        return meds

    def _extract_vitals(self, text: str) -> Dict[str, str]:
        vitals: Dict[str, str] = {}
        hr = re.search(r"hr\s*(\d{2,3})", text, flags=re.I)
        if hr:
            vitals["heart_rate"] = hr.group(1)
        bp = re.search(r"bp\s*(\d{2,3})/(\d{2,3})", text, flags=re.I)
        if bp:
            vitals["blood_pressure"] = f"{bp.group(1)}/{bp.group(2)}"
        temp = re.search(r"temp\s*(\d{2}(?:\.\d)?)", text, flags=re.I)
        if temp:
            vitals["temperature"] = temp.group(1)
        return vitals

    def _extract_plan(self, text: str) -> List[str]:
        plan_phrases = re.findall(r"plan[:\-]\s*([^\.]+)", text, flags=re.I)
        if not plan_phrases and "plan" in text.lower():
            plan_phrases.append("monitor and follow up")
        return [phrase.strip() for phrase in plan_phrases if phrase.strip()]
