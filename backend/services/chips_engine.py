# path: backend/services/chips_engine.py
from __future__ import annotations

import threading
from typing import Dict, List, Optional

def _load_config() -> Dict:
    try:
        import yaml, os
        with open(os.path.join("config", "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {
            "confidence": {
                "weights": {"rule_hit": 0.35, "p_llm": 0.25, "asr": 0.15, "ontology": 0.10, "context": 0.15},
                "thresholds": {"auto_accept": 0.90, "soft_confirm": 0.70, "must_confirm": 0.45},
                "risk_bumps": {"high": 0.05, "medium": 0.03},
            }
        }

class ChipsEngine:
    """
    Confidence scoring, bands, and chip resolution.
    """
    _instance: Optional["ChipsEngine"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ChipsEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.cfg = _load_config()
        self._chips: Dict[str, Dict] = {}  # optional in-memory registry

    def score(self, rule_hit: float, p_llm: float, c_asr: float, s_ont: float, s_ctx: float, risk: str = "low") -> float:
        w = self.cfg["confidence"]["weights"]
        rb = self.cfg["confidence"]["risk_bumps"]
        c = (
            0.35 * rule_hit
            + 0.25 * p_llm
            + 0.15 * c_asr
            + 0.10 * s_ont
            + 0.15 * s_ctx
        )
        if risk == "high":
            c += rb.get("high", 0.05)
        elif risk == "medium":
            c += rb.get("medium", 0.03)
        return max(0.0, min(1.0, c))

    def band(self, c: float, guard_failed: bool = False) -> str:
        th = self.cfg["confidence"]["thresholds"]
        if guard_failed or c < th["must_confirm"]:
            return "D"
        if c < th["soft_confirm"]:
            return "C"
        if c < th["auto_accept"]:
            return "B"
        return "A"

    def batch_accept_visible(self, chips: List[Dict]) -> bool:
        # Visible if ≥3 B-band chips of same 'type'
        from collections import Counter
        types = [c.get("type") for c in chips if c.get("band") == "B"]
        ctr = Counter(types)
        return any(v >= 3 for v in ctr.values())

    def resolve(self, chip_id: str, action: str, value: Optional[str], reason: Optional[str]) -> bool:
        if action == "override_blocked" and not reason:
            raise ValueError("Override requires reason")
        # Persist action could be added here (DB/audit). For MVP return True.
        return True
