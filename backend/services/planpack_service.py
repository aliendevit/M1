# path: backend/services/planpack_service.py
from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional

def _load_yaml(path: str) -> Dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _load_config() -> Dict:
    try:
        import yaml
        with open(os.path.join("config", "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {"pathways": {"enabled": ["chest_pain", "seizure", "sepsis"]}}

class PlanpackService:
    """
    Loads YAML plan packs and evaluates guards to emit suggestions and guard flags.
    Guard failure → D-band (blocked) with `override_blocked` action.
    """
    _instance: Optional["PlanpackService"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "PlanpackService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.cfg = _load_config()
        self._packs: Dict[str, Dict] = {}
        base = os.path.join("backend", "planpacks")
        # Load enabled packs if present; otherwise synthesize defaults
        enabled = set(self.cfg.get("pathways", {}).get("enabled", []))
        for name in ["chest_pain", "seizure", "sepsis"]:
            pp = {}
            path = os.path.join(base, f"{name}.yaml")
            if os.path.exists(path):
                try:
                    pp = _load_yaml(path)
                except Exception:
                    pp = {}
            if not pp:
                pp = self._default_pack(name)
            if not enabled or name in enabled:
                self._packs[name] = pp

    def _default_pack(self, name: str) -> Dict:
        if name == "chest_pain":
            return {
                "suggestions": [
                    {"label": "Troponin cadence", "proposed": "q3h ×2", "guards": ["pregnancy", "active_bleed"], "risk": "medium"},
                    {"label": "Aspirin 325 mg PO now", "guards": ["allergy_asa", "active_bleed"], "risk": "high"},
                ]
            }
        if name == "seizure":
            return {
                "suggestions": [
                    {"label": "Check anticonvulsant level", "guards": [], "risk": "medium"},
                    {"label": "Consult Neurology", "guards": [], "risk": "low"},
                ]
            }
        # sepsis
        return {
            "suggestions": [
                {"label": "Sepsis bundle: lactate, cultures, broad-spectrum abx", "guards": ["pregnancy"], "risk": "high"},
                {"label": "30 mL/kg fluids unless contraindicated", "guards": ["resp_depression", "active_bleed"], "risk": "high"},
            ]
        }

    # ---- Public API ----
    def suggest(self, pathway: str, visit: Dict, facts: List[Dict]) -> Dict:
        pack = self._packs.get(pathway)
        if not pack:
            # Unknown pathway → one informational suggestion, passed guard flag
            return {
                "suggestions": [{
                    "chip_id": f"{pathway}-info",
                    "label": f"Pathway: {pathway}",
                    "proposed": None,
                    "band": "D",
                    "risk": "low",
                    "actions": ["evidence"],
                    "evidence": []
                }],
                "guard_flags": [{"name": "pathway", "status": "unknown", "reason": "Pathway not enabled"}],
            }

        guard_results = self._evaluate_guards(facts, visit)
        suggestions = []
        for idx, s in enumerate(pack.get("suggestions", []), start=1):
            s_guards = s.get("guards", [])
            failed = any(guard_results.get(g) == "failed" for g in s_guards)
            unknown = any(guard_results.get(g) == "unknown" for g in s_guards)
            band = "D" if failed or unknown else "B"
            actions = ["accept", "evidence"]
            if band == "D":
                actions = ["override_blocked", "evidence"]
            suggestions.append({
                "chip_id": f"{pathway}-{idx}",
                "label": s.get("label"),
                "proposed": s.get("proposed"),
                "band": band,
                "risk": s.get("risk", "low"),
                "actions": actions,
                "evidence": self._collect_guard_evidence(s_guards, facts),
            })

        guard_flags = [{"name": k, "status": v, "reason": None} for k, v in guard_results.items()]
        return {"suggestions": suggestions, "guard_flags": guard_flags}

    # ---- Guard logic ----
    def _evaluate_guards(self, facts: List[Dict], visit: Dict) -> Dict[str, str]:
        # guards: allergy_asa, active_bleed, pregnancy, renal_function_for_contrast, anticoag_conflict, resp_depression
        result = {}
        names = {f.get("name", "").lower(): f for f in facts}
        textvals = " ".join([str(f.get("value","")).lower() for f in facts])
        # allergy_asa
        if "asa allergy" in textvals or "allergy: aspirin" in textvals:
            result["allergy_asa"] = "failed"
        elif "allergy" in textvals:
            result["allergy_asa"] = "unknown"
        else:
            result["allergy_asa"] = "passed"
        # active_bleed
        if "gi bleed" in textvals or "active bleed" in textvals or "melena" in textvals or "hematemesis" in textvals:
            result["active_bleed"] = "failed"
        else:
            result["active_bleed"] = "passed"
        # pregnancy
        if "pregnant" in textvals or "pregnancy" in textvals:
            result["pregnancy"] = "failed"
        else:
            result["pregnancy"] = "passed"
        # renal_function_for_contrast
        egfr = None
        for f in facts:
            if f.get("kind") == "lab" and f.get("name","").lower() in {"egfr","gfr","creatinine"}:
                try:
                    egfr = float(str(f.get("value")).split()[0])
                except Exception:
                    egfr = None
        if egfr is not None and egfr < 30:
            result["renal_function_for_contrast"] = "failed"
        elif egfr is None:
            result["renal_function_for_contrast"] = "unknown"
        else:
            result["renal_function_for_contrast"] = "passed"
        # anticoag_conflict
        if "warfarin" in textvals or "apixaban" in textvals or "rivaroxaban" in textvals:
            result["anticoag_conflict"] = "unknown"  # need INR/bleed data
        else:
            result["anticoag_conflict"] = "passed"
        # resp_depression
        if "hypoxia" in textvals or "respiratory depression" in textvals or "sat <" in textvals:
            result["resp_depression"] = "failed"
        else:
            result["resp_depression"] = "passed"
        return result

    def _collect_guard_evidence(self, guards: List[str], facts: List[Dict]) -> List[str]:
        e = []
        for g in guards:
            for f in facts:
                if g in (f.get("name","").lower() + " " + str(f.get("value","")).lower()):
                    if f.get("source_id"):
                        e.append(f.get("source_id"))
        return list(dict.fromkeys(e))
