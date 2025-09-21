"""In-memory session metrics used for pilot readiness."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class SessionMetrics:
    started_at: datetime = field(default_factory=datetime.utcnow)
    timers: Dict[str, float] = field(default_factory=dict)
    keystrokes: int = 0
    chip_counts: Dict[str, int] = field(default_factory=lambda: {"A": 0, "B": 0, "C": 0, "D": 0})

    def to_payload(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "timers": self.timers,
            "keystrokes": self.keystrokes,
            "chip_counts": self.chip_counts,
        }


session_metrics = SessionMetrics()
