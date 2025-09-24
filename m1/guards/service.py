"""Safety guards enforcing conservative behavior."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(slots=True)
class GuardConfig:
    hard_blocks: List[str]
    soft_flags: List[str]

    @classmethod
    def default(cls) -> "GuardConfig":
        return cls(
            hard_blocks=["call code", "cardiac arrest"],
            soft_flags=["seizure", "suicide", "fall", "septic"],
        )


@dataclass(slots=True)
class GuardDecision:
    blocked: bool
    reason: str | None
    flags: List[str]


class GuardService:
    """Simple substring guards until a policy engine is integrated."""

    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig.default()

    @classmethod
    def from_config(cls, data: Dict[str, object] | None) -> "GuardService":
        if not data:
            return cls()
        hard_blocks = data.get("hard_blocks") if isinstance(data.get("hard_blocks"), list) else None
        soft_flags = data.get("soft_flags") if isinstance(data.get("soft_flags"), list) else None
        config = GuardConfig(
            hard_blocks=hard_blocks or GuardConfig.default().hard_blocks,
            soft_flags=soft_flags or GuardConfig.default().soft_flags,
        )
        return cls(config)

    def evaluate(self, bundle: Dict[str, object]) -> GuardDecision:
        transcript = self._transcript(bundle)
        lowered = transcript.lower()
        for term in self.config.hard_blocks:
            if term.lower() in lowered:
                return GuardDecision(
                    blocked=True,
                    reason=f"Manual override required for high-risk term: '{term}'",
                    flags=[term],
                )
        flags = [term for term in self.config.soft_flags if term.lower() in lowered]
        return GuardDecision(blocked=False, reason=None, flags=flags)

    def _transcript(self, bundle: Dict[str, object]) -> str:
        sections = bundle.get("sections") if isinstance(bundle, dict) else None
        subjective = sections.get("subjective") if isinstance(sections, dict) else {}
        transcript = subjective.get("transcript") if isinstance(subjective, dict) else ""
        return transcript or ""
