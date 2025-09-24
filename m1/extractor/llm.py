"""Rule-centric extraction with llama-cpp fallback."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover
    Llama = None  # type: ignore[misc, assignment]


class VisitJSON(BaseModel):
    problems: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    vitals: Dict[str, str] = Field(default_factory=dict)
    plan: List[str] = Field(default_factory=list)
    labs: List[Dict[str, str]] = Field(default_factory=list)


@dataclass(slots=True)
class ExtractionResult:
    problems: List[str]
    medications: List[str]
    vitals: Dict[str, str]
    plan: List[str]
    labs: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "problems": self.problems,
            "medications": self.medications,
            "vitals": self.vitals,
            "plan": self.plan,
            "labs": self.labs,
        }


class VisitExtractor:
    """LLM-first extractor with heuristic guardrails."""

    def __init__(self, model_path: str | None = None, ctx: int = 2048, threads: int = 4, n_gpu_layers: int = 0) -> None:
        self.model_path = model_path
        self.ctx = ctx
        self.threads = threads
        self.n_gpu_layers = n_gpu_layers
        self._llm = self._load_llm()

    @classmethod
    def from_config(cls, config: Dict[str, object] | None) -> "VisitExtractor":
        config = config or {}
        return cls(
            model_path=str(config.get("path")) if config.get("path") else None,
            ctx=int(config.get("ctx", 2048)),
            threads=int(config.get("threads", config.get("n_threads", 4))),
            n_gpu_layers=int(config.get("n_gpu_layers", 0)),
        )

    def extract(self, transcript: str) -> Dict[str, object]:
        cleaned = transcript.strip()
        if not cleaned:
            return VisitJSON().model_dump()
        if self._llm is not None:
            parsed = self._llm_extract(cleaned)
            if parsed is not None:
                return parsed.model_dump()
        result = self._heuristic_extract(cleaned)
        return VisitJSON.model_validate(result).model_dump()

    def _load_llm(self):
        if not self.model_path or Llama is None:
            return None
        try:
            return Llama(
                model_path=self.model_path,
                n_ctx=self.ctx,
                n_threads=self.threads,
                n_gpu_layers=self.n_gpu_layers,
                embedding=False,
            )
        except Exception:
            return None

    def _llm_extract(self, transcript: str) -> Optional[VisitJSON]:
        if self._llm is None:
            return None
        prompt = (
            "You are a clinical documentation system. "
            "Extract problems, medications, vitals, plan items, and labs from the transcript." \
            " Return strict JSON with keys problems, medications, vitals, plan, labs."
        )
        try:
            response = self._llm(
                prompt,
                max_tokens=512,
                stop=["\n\n"],
                temperature=0.0,
            )
        except Exception:
            return None
        text = response.get("choices", [{}])[0].get("text", "{}").strip()
        try:
            payload = json.loads(text)
            return VisitJSON.model_validate(payload)
        except (json.JSONDecodeError, ValueError):
            return None

    def _heuristic_extract(self, text: str) -> Dict[str, object]:
        problems = self._extract_problems(text)
        medications = self._extract_medications(text)
        vitals = self._extract_vitals(text)
        plan = self._extract_plan(text)
        labs = self._extract_labs(text)
        return ExtractionResult(problems, medications, vitals, plan, labs).to_dict()

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

    def _extract_labs(self, text: str) -> List[Dict[str, str]]:
        labs: List[Dict[str, str]] = []
        match = re.search(r"troponin\s*(\d+(?:\.\d+)?)", text, flags=re.I)
        if match:
            labs.append({"name": "troponin", "value": match.group(1), "unit": "ng/mL"})
        return labs
