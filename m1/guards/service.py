"""Guard checks for clinical plan suggestions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..schemas import EvidenceChip, PlanpackGuardFlag, PlanpackResponse, PlanpackSuggestion, VisitJSON


@dataclass
class GuardContext:
    allergies: List[str]
    risks: List[str]
    labs: dict[str, float]
    pregnancy: Optional[bool]
    anticoagulants: List[str]


class GuardService:
    def build_context(self, visit: VisitJSON, evidence: Iterable[EvidenceChip]) -> GuardContext:
        allergies = []
        labs: dict[str, float] = {}
        for chip in evidence:
            match = re.search(r"(-?\d+(?:\.\d+)?)", chip.value)
            if match:
                labs[chip.name.lower()] = float(match.group(1))
        anticoagulants = [intent.name.lower() for intent in visit.plan_intents if "heparin" in intent.name.lower()]
        pregnancy = any("pregnancy" in risk.lower() for risk in visit.risks) or None
        return GuardContext(
            allergies=allergies,
            risks=visit.risks,
            labs=labs,
            pregnancy=pregnancy,
            anticoagulants=anticoagulants,
        )

    def evaluate_guard(self, guard: dict, context: GuardContext) -> PlanpackGuardFlag:
        guard_type = next(iter(guard))
        payload = guard[guard_type]
        if guard_type == "require_absent":
            prohibited = {item.lower() for item in payload}
            conflicts = [risk for risk in context.risks if risk.lower() in prohibited]
            status = "blocked" if conflicts else "clear"
            detail = ", ".join(conflicts) if conflicts else None
            return PlanpackGuardFlag(guard="require_absent", status=status, detail=detail)
        if guard_type == "check_allergy":
            targets = {item.lower() for item in payload}
            conflicts = [allergy for allergy in context.allergies if allergy.lower() in targets]
            status = "blocked" if conflicts else "clear"
            detail = ", ".join(conflicts) if conflicts else None
            return PlanpackGuardFlag(guard="check_allergy", status=status, detail=detail)
        if guard_type == "check_renal":
            creatinine = context.labs.get("creatinine", 0.0)
            status = "blocked" if creatinine and creatinine > 2.0 else "clear"
            detail = f"Cr {creatinine}" if status == "blocked" else None
            return PlanpackGuardFlag(guard="check_renal", status=status, detail=detail)
        if guard_type == "check_pregnancy":
            if context.pregnancy:
                return PlanpackGuardFlag(guard="check_pregnancy", status="blocked", detail="pregnancy noted")
            return PlanpackGuardFlag(guard="check_pregnancy", status="clear", detail=None)
        if guard_type == "check_anticoag":
            targets = {item.lower() for item in payload}
            conflicts = [drug for drug in context.anticoagulants if drug in targets]
            status = "blocked" if conflicts else "clear"
            detail = ", ".join(conflicts) if conflicts else None
            return PlanpackGuardFlag(guard="check_anticoag", status=status, detail=detail)
        return PlanpackGuardFlag(guard=guard_type, status="unknown", detail=None)

    def evaluate(self, guards: List[dict], visit: VisitJSON, evidence: Iterable[EvidenceChip]) -> List[PlanpackGuardFlag]:
        context = self.build_context(visit, evidence)
        return [self.evaluate_guard(guard, context) for guard in guards]

    def suggestions(self, suggest: dict, guard_flags: List[PlanpackGuardFlag]) -> List[PlanpackSuggestion]:
        if any(flag.status == "blocked" for flag in guard_flags):
            return []
        suggestions: List[PlanpackSuggestion] = []
        for kind, entries in (suggest or {}).items():
            for entry in entries:
                suggestions.append(PlanpackSuggestion(kind=kind, payload={k: str(v) for k, v in entry.items()}))
        return suggestions


def evaluate_planpack_with_guards(
    guard_service: GuardService,
    pack,
    visit: VisitJSON,
    evidence: Iterable[EvidenceChip],
) -> PlanpackResponse:
    guard_flags = guard_service.evaluate(pack.guards, visit, evidence)
    suggestions = guard_service.suggestions(pack.suggest, guard_flags)
    return PlanpackResponse(suggestions=suggestions, guard_flags=guard_flags)
