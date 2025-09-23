from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import ValidationError

from m1.models import PlanIntent, VisitJSON

try:  # pragma: no cover - optional dependency during tests
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover - optional dependency during tests
    Llama = None  # type: ignore

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMConfig:
    """Configuration for the local llama.cpp model."""

    model_path: Path
    n_ctx: int = 2048
    n_threads: int = 4
    n_gpu_layers: int = 0
    seed: int = 42
    deterministic: bool = True
    max_tokens: int = 512
    system_prompt: str = (
        "You are a structured data assistant for MinuteOne. "
        "Return only strict JSON matching the provided schema."
    )
    temperature: float = 0.0


@dataclass(slots=True)
class LLMExtractor:
    """Hybrid rule + local LLM extractor for VisitJSON."""

    config: LLMConfig
    _llm: Llama | None = field(default=None, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def _load(self) -> Llama | None:
        if self._llm is not None:
            return self._llm
        if Llama is None:
            LOGGER.warning("llama-cpp-python unavailable; falling back to deterministic rules")
            return None
        with self._lock:
            if self._llm is not None:
                return self._llm
            if not self.config.model_path.exists():
                LOGGER.warning("LLM model path %s missing; using rules only", self.config.model_path)
                return None
            LOGGER.info("Loading llama.cpp model from %s", self.config.model_path)
            self._llm = Llama(
                model_path=str(self.config.model_path),
                n_ctx=self.config.n_ctx,
                n_threads=self.config.n_threads,
                n_gpu_layers=self.config.n_gpu_layers,
                seed=self.config.seed,
            )
        return self._llm

    def _rule_extract(self, transcript: str) -> dict[str, Any]:
        """Simple rule-based extraction to minimise LLM dependency."""

        text = transcript.strip()
        complaint = self._infer_chief_complaint(text)
        plan_intents = self._infer_plan_intents(text)
        risks = self._infer_risks(text)
        exam_bits = {
            "cv": self._find_section(text, ["cardiac exam", "heart", "cardiology"]),
            "lungs": self._find_section(text, ["lungs", "respiratory", "pulmonary"]),
        }
        language = self._infer_language_pref(text)
        hpi = {
            "onset": self._capture_fragment(text, r"onset (?:was|is|at) (?P<value>[^\.;]+)"),
            "quality": self._capture_fragment(text, r"quality (?:is|was) (?P<value>[^\.;]+)"),
            "modifiers": self._collect_list(text, ["relieved", "worse with", "better with"]),
            "associated_symptoms": self._collect_list(text, ["associated", "also notes", "denies"]),
            "red_flags": self._collect_list(text, ["red flag", "danger", "emergent"]),
        }
        return {
            "chief_complaint": complaint or "Undifferentiated presentation",
            "hpi": hpi,
            "exam_bits": exam_bits,
            "risks": risks,
            "plan_intents": plan_intents,
            "language_pref": language,
        }

    @staticmethod
    def _infer_chief_complaint(text: str) -> str | None:
        patterns = [
            r"chief complaint (?:is|:) (?P<val>[^\n\.;]+)",
            r"presenting with (?P<val>[^\n\.;]+)",
            r"reports (?P<val>[^\n\.;]+)",
        ]
        lowered = text.lower()
        for pat in patterns:
            match = re.search(pat, lowered)
            if match:
                value = match.group("val").strip().strip('. ')
                return value.capitalize()
        if not text:
            return None
        first_sentence = re.split(r"[\n\.]", text, maxsplit=1)[0]
        return first_sentence.strip().capitalize() or None

    @staticmethod
    def _infer_language_pref(text: str) -> str | None:
        lowered = text.lower()
        if "speaks spanish" in lowered or "spanish interpreter" in lowered:
            return "es"
        if "prefers english" in lowered or "english only" in lowered:
            return "en"
        return None

    @staticmethod
    def _collect_list(text: str, cues: list[str]) -> list[str]:
        results: list[str] = []
        lowered = text.lower()
        for cue in cues:
            idx = lowered.find(cue)
            if idx == -1:
                continue
            snippet = text[idx : idx + 160]
            parts = re.split(r"[,;]\s*", snippet)
            for part in parts:
                cleaned = part.replace(cue, "").strip().strip('. ')
                if cleaned:
                    results.append(cleaned)
        deduped: list[str] = []
        for value in results:
            if value not in deduped:
                deduped.append(value)
        return deduped

    @staticmethod
    def _find_section(text: str, keywords: list[str], max_len: int = 160) -> str | None:
        lowered = text.lower()
        for keyword in keywords:
            idx = lowered.find(keyword)
            if idx != -1:
                snippet = text[idx : idx + max_len].split('\n')[0].strip()
                return snippet
        return None

    @staticmethod
    def _capture_fragment(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group("value").strip().strip('. ')
            return value
        return None

    @staticmethod
    def _infer_plan_intents(text: str) -> list[dict[str, Any]]:
        intents: list[dict[str, Any]] = []
        mappings = {
            "troponin": ("lab_series", "Serial troponin"),
            "ekg": ("test", "12-lead ECG"),
            "ecg": ("test", "12-lead ECG"),
            "lactate": ("lab_series", "Lactate"),
            "glucose": ("lab_series", "Finger-stick glucose"),
            "education": ("education", "Patient education"),
        }
        lowered = text.lower()
        for key, (ptype, name) in mappings.items():
            if key in lowered:
                intents.append({"type": ptype, "name": name, "dose": None, "schedule": []})
        return intents

    @staticmethod
    def _infer_risks(text: str) -> list[str]:
        risks: list[str] = []
        lowered = text.lower()
        if "diabetic" in lowered:
            risks.append("Diabetes")
        if "hypertension" in lowered:
            risks.append("Hypertension")
        if "anticoag" in lowered:
            risks.append("Anticoagulation")
        if "pregnant" in lowered:
            risks.append("Pregnancy")
        return risks

    def _run_llm(self, transcript: str) -> dict[str, Any] | None:
        llm = self._load()
        if llm is None:
            return None
        prompt = self._build_prompt(transcript)
        try:
            response = llm.create_completion(
                prompt=prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=0.8 if self.config.temperature else 1.0,
            )
        except Exception as exc:  # pragma: no cover - hardware/runtime failure
            LOGGER.exception("LLM inference failed: %s", exc)
            return None
        if not response:
            return None
        text = response.get("choices", [{}])[0].get("text", "").strip()
        if not text:
            return None
        text = self._extract_json_block(text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            LOGGER.warning("Failed to parse LLM JSON; falling back")
            return None
        return data

    @staticmethod
    def _extract_json_block(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    def _build_prompt(self, transcript: str) -> str:
        schema = json.dumps(
            {
                "chief_complaint": "string",
                "hpi": {
                    "onset": "string|null",
                    "quality": "string|null",
                    "modifiers": ["string"],
                    "associated_symptoms": ["string"],
                    "red_flags": ["string"],
                },
                "exam_bits": {"cv": "string|null", "lungs": "string|null"},
                "risks": ["string"],
                "plan_intents": [
                    {
                        "type": "lab_series|test|med_admin|education",
                        "name": "string",
                        "dose": "string|null",
                        "schedule": ["string"],
                    }
                ],
                "language_pref": "string|null",
            },
            indent=2,
        )
        return (
            f"{self.config.system_prompt}\n"
            f"Transcript:\n{transcript}\n"
            "Respond with valid JSON only matching this schema:\n"
            f"{schema}\n"
        )

    def extract(self, transcript: str) -> VisitJSON:
        """Extract VisitJSON using rules with optional LLM refinement."""

        rule_data = self._rule_extract(transcript)
        llm_data = self._run_llm(transcript)
        merged = self._merge(rule_data, llm_data)
        try:
            visit = VisitJSON.model_validate(merged)
        except ValidationError as exc:
            LOGGER.error("VisitJSON validation failed: %s", exc)
            minimal = {
                "chief_complaint": rule_data.get("chief_complaint", "Clinical review"),
                "hpi": {},
                "exam_bits": {},
                "risks": [],
                "plan_intents": [],
                "language_pref": None,
            }
            visit = VisitJSON.model_validate(minimal)
        return visit

    @staticmethod
    def _merge(primary: dict[str, Any], secondary: dict[str, Any] | None) -> dict[str, Any]:
        if not secondary:
            return primary
        merged: dict[str, Any] = primary.copy()
        for key, value in secondary.items():
            if value in (None, "", [], {}):
                continue
            if key == "plan_intents":
                merged[key] = [
                    intent
                    for intent in (value or [])
                    if isinstance(intent, dict) and intent.get("name")
                ] or primary.get("plan_intents", [])
            else:
                merged[key] = value
        return merged

    def to_plan_intents(self, visit: VisitJSON) -> list[PlanIntent]:
        """Return validated plan intents for downstream consumers."""

        intents: list[PlanIntent] = []
        for intent in visit.plan_intents:
            if isinstance(intent, PlanIntent):
                intents.append(intent)
            else:
                try:
                    intents.append(PlanIntent.model_validate(intent))
                except ValidationError:
                    continue
        return intents
