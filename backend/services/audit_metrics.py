# path: backend/services/audit_metrics.py
from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

class MetricsService:
    """
    Local JSONL audit + simple session metrics.
    """
    _instance: "MetricsService" | None = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "MetricsService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.path = os.path.join("data", "audit", "session.jsonl")
        _ensure_dir(self.path)
        # in-memory counters
        self.timers = {"decode_ms": 0, "extract_ms": 0, "compose_ms": 0}
        self.keystrokes = 0
        self.chip_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        self._wlock = threading.Lock()

    def _log(self, rec: Dict):
        with self._wlock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def log_chip_action(self, chip_id: str, action: str):
        self._log({"ts": time.time(), "kind": "chip_action", "chip_id": chip_id, "action": action})

    def add_timer(self, key: str, ms: int):
        self.timers[key] = self.timers.get(key, 0) + int(ms)
        self._log({"ts": time.time(), "kind": "timer", "name": key, "ms": ms})

    def inc_keystrokes(self, n: int = 1):
        self.keystrokes += n
        self._log({"ts": time.time(), "kind": "keystrokes", "n": n})

    def count_chip_band(self, band: str, n: int = 1):
        if band in self.chip_counts:
            self.chip_counts[band] += n
        self._log({"ts": time.time(), "kind": "chip_band", "band": band, "n": n})

    def session_snapshot(self) -> Dict:
        return {
            "timers": dict(self.timers),
            "keystrokes": int(self.keystrokes),
            "chip_counts": dict(self.chip_counts),
        }
