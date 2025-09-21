"""Utilities for loading YAML plan packs and evaluating guards."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import yaml

from ..schemas import PlanpackGuardFlag, PlanpackResponse, PlanpackSuggestion, VisitJSON


@dataclass
class PlanPack:
    pathway: str
    guards: List[dict]
    suggest: dict


def load_planpack(path: Path | str) -> PlanPack:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return PlanPack(
        pathway=data["pathway"],
        guards=data.get("guards", []),
        suggest=data.get("suggest", {}),
    )


def load_directory(directory: Path | str) -> Dict[str, PlanPack]:
    packs: Dict[str, PlanPack] = {}
    for file in Path(directory).glob("*.yaml"):
        pack = load_planpack(file)
        packs[pack.pathway] = pack
    return packs


def _guard_label(guard: dict, index: int) -> str:
    guard_type = next(iter(guard))
    return guard.get("label", f"guard_{index}_{guard_type}")


def _evaluate_guard(guard: dict, visit: VisitJSON, chart_facts: Iterable[str]) -> PlanpackGuardFlag:
    guard_type = next(iter(guard))
    if guard_type == "require_absent":
        prohibited = set(guard[guard_type])
        conflicts = prohibited.intersection(set(visit.risks))
        status = "blocked" if conflicts else "clear"
        detail = ", ".join(sorted(conflicts)) if conflicts else None
        return PlanpackGuardFlag(guard="require_absent", status=status, detail=detail)
    if guard_type == "check_allergy":
        allergies = set(chart_facts)
        conflicts = allergies.intersection(set(guard[guard_type]))
        status = "blocked" if conflicts else "clear"
        detail = ", ".join(sorted(conflicts)) if conflicts else None
        return PlanpackGuardFlag(guard="check_allergy", status=status, detail=detail)
    return PlanpackGuardFlag(guard=guard_type, status="unknown", detail="not evaluated")


def _build_suggestions(pack: PlanPack, guard_flags: List[PlanpackGuardFlag]) -> List[PlanpackSuggestion]:
    blocked = any(flag.status == "blocked" for flag in guard_flags)
    if blocked:
        return []
    suggestions: List[PlanpackSuggestion] = []
    suggest_section = pack.suggest or {}
    for key, entries in suggest_section.items():
        for entry in entries:
            suggestions.append(
                PlanpackSuggestion(kind=key, payload={k: str(v) for k, v in entry.items()}, guard=None)
            )
    return suggestions


def evaluate_planpack(pack: PlanPack, visit: VisitJSON, chart_facts: Iterable[str]) -> PlanpackResponse:
    guard_flags = [_evaluate_guard(guard, visit, chart_facts) for guard in pack.guards]
    suggestions = _build_suggestions(pack, guard_flags)
    return PlanpackResponse(suggestions=suggestions, guard_flags=guard_flags)
