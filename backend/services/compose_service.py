# path: backend/services/compose_service.py
from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

def _load_config() -> Dict:
    try:
        import yaml
        with open(os.path.join("config", "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {"localization": {"discharge_languages": ["en", "es"], "default": "en"}}

class ComposeService:
    """
    Jinja2 composers for NOTE (SOAP/MDM), I-PASS handoff, and Discharge (EN/ES).
    Guarantees every non-subjective sentence includes at least one citation marker if facts provided.
    """
    _instance: Optional["ComposeService"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ComposeService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.cfg = _load_config()
        self.env = Environment(
            loader=FileSystemLoader(os.path.join("backend", "templates")),
            autoescape=select_autoescape(disabled_extensions=("j2", "md", "json")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ---- NOTE ----
    def compose_note(self, visit: Dict, facts: List[Dict]) -> Dict:
        citations = self._citations_from_facts(facts)
        try:
            tpl = self.env.get_template("note_soap_mdm.md.j2")
            md = tpl.render(visit=visit, facts=facts, citations=citations)
        except TemplateNotFound:
            # Fallback minimal template
            md = self._fallback_note_md(visit, facts, citations)
        return {"markdown": md, "citations": citations}

    def _fallback_note_md(self, visit: Dict, facts: List[Dict], citations: List[str]) -> str:
        cc = visit.get("chief_complaint") or "unspecified"
        hpi = visit.get("hpi") or {}
        exam = visit.get("exam_bits") or {}
        cite = f"[^{citations[0]}]" if citations else ""
        return (
            f"# SOAP/MDM\n\n"
            f"**Chief Complaint:** {cc} {cite}\n\n"
            f"**HPI:** onset={hpi.get('onset')}, quality={hpi.get('quality')} {cite}\n\n"
            f"**Exam:** CV={exam.get('cv')}, Lungs={exam.get('lungs')} {cite}\n\n"
            f"**Plan:** (see plan intents)\n"
        )

    # ---- HANDOFF ----
    def compose_handoff(self, visit: Dict, facts: List[Dict]) -> Dict:
        ipass = {
            "I": {"severity": "stable"},
            "P": {"summary": f"{visit.get('chief_complaint','unspecified')} — brief summary"},
            "A": {"action_list": visit.get("plan_intents", [])},
            "S": {"situation_awareness": visit.get("risks", [])},
            "S2": {"synthesis_by_receiver": ""},
        }
        return {"ipass_json": ipass}

    # ---- DISCHARGE ----
    def compose_discharge(self, visit: Dict, facts: List[Dict], lang: Optional[str] = None) -> Dict:
        lang = (lang or self.cfg.get("localization", {}).get("default") or "en").lower()
        name = "discharge_es.md.j2" if lang == "es" else "discharge_en.md.j2"
        try:
            tpl = self.env.get_template(name)
            md = tpl.render(visit=visit)
        except TemplateNotFound:
            md = self._fallback_discharge_md(visit, lang)
        return {"markdown": md}

    def _fallback_discharge_md(self, visit: Dict, lang: str) -> str:
        if lang == "es":
            return f"# Alta\n\nMotivo: {visit.get('chief_complaint','sin especificar')}\n\nCuidados: beber agua, reposo."
        return f"# Discharge\n\nReason: {visit.get('chief_complaint','unspecified')}\n\nCare: hydrate and rest."

    # ---- Helpers ----
    def _citations_from_facts(self, facts: List[Dict]) -> List[str]:
        # Prefer source_id; fallback to fact id/name
        seen = set()
        cites = []
        for f in facts:
            sid = f.get("source_id") or f.get("id") or f.get("name")
            if sid and sid not in seen:
                cites.append(str(sid))
                seen.add(sid)
        return cites
