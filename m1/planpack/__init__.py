from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from m1.models import PlanpackSuggestion


@dataclass(slots=True)
class Planpack:
    plan_id: str
    summary: str
    actions: list[dict[str, Any]]


class PlanpackService:
    """Loads conservative plan pack suggestions."""

    def __init__(self, root: Path):
        self.root = root
        self._packs = self._load_all()

    def _load_all(self) -> dict[str, Planpack]:
        packs: dict[str, Planpack] = {}
        for path in self.root.glob("*.yaml"):
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            plan_id = data.get("id", path.stem)
            packs[plan_id] = Planpack(
                plan_id=plan_id,
                summary=data.get("summary", ""),
                actions=data.get("actions", []),
            )
        return packs

    def suggest(self, plan_id: str, guard_flags: set[str] | None = None) -> PlanpackSuggestion | None:
        pack = self._packs.get(plan_id)
        if not pack:
            return None
        guard_flags = guard_flags or set()
        actions: list[str] = []
        triggered: list[str] = []
        for action in pack.actions:
            flags = set(action.get("guard_flags", []))
            if flags & guard_flags:
                triggered.extend(sorted(flags & guard_flags))
                continue
            for step in action.get("steps", []):
                actions.append(step)
        return PlanpackSuggestion(
            plan_id=plan_id,
            title=pack.summary or plan_id.replace("_", " ").title(),
            summary=pack.summary or "Conservative guidance",
            guard_flags=sorted(set(triggered)),
            actions=actions,
        )

    def available(self) -> list[str]:
        return sorted(self._packs)
