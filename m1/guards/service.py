from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

GuardStatus = Literal["pass", "fail", "unknown"]


@dataclass(slots=True)
class GuardResult:
    guard: str
    status: GuardStatus
    band: Literal["A", "B", "C", "D"]
    rationale: str

    @property
    def requires_override(self) -> bool:
        return self.status in {"fail", "unknown"}


def guard_allergy(facts: dict[str, Any], substance: str) -> GuardResult:
    allergies = [item.lower() for item in facts.get("allergies", [])]
    if not allergies:
        return GuardResult("allergy", "unknown", "D", "Allergy history unavailable")
    if substance.lower() in allergies:
        return GuardResult("allergy", "fail", "D", f"Recorded allergy to {substance}")
    return GuardResult("allergy", "pass", "B", "No matching allergy documented")


def guard_active_bleed(facts: dict[str, Any]) -> GuardResult:
    conditions = [item.lower() for item in facts.get("conditions", [])]
    if not conditions:
        return GuardResult("active_bleed", "unknown", "D", "Bleeding status unknown")
    if any("bleed" in cond or "hemorrh" in cond for cond in conditions):
        return GuardResult("active_bleed", "fail", "D", "Active bleeding documented")
    return GuardResult("active_bleed", "pass", "B", "No active bleeding in record")


def guard_pregnancy(facts: dict[str, Any]) -> GuardResult:
    demographics = facts.get("demographics", {})
    sex = (demographics.get("sex") or "").lower()
    pregnant = demographics.get("pregnant")
    if pregnant is True:
        return GuardResult("pregnancy", "fail", "D", "Pregnancy confirmed")
    if pregnant is False:
        return GuardResult("pregnancy", "pass", "B", "Not pregnant per chart")
    if sex not in {"female", "f"}:
        return GuardResult("pregnancy", "pass", "B", "Pregnancy not applicable")
    return GuardResult("pregnancy", "unknown", "D", "Pregnancy status not documented")


def guard_renal(facts: dict[str, Any], need_contrast: bool = False) -> GuardResult:
    labs = facts.get("labs", {})
    egfr = labs.get("egfr")
    if egfr is None:
        rationale = "No eGFR on file; contrast requires confirmation" if need_contrast else "Renal status unknown"
        return GuardResult("renal", "unknown", "D", rationale)
    try:
        egfr_value = float(egfr)
    except (TypeError, ValueError):
        return GuardResult("renal", "unknown", "D", "Invalid eGFR value")
    if egfr_value < 30:
        rationale = "eGFR < 30; high risk for contrast" if need_contrast else "eGFR severely reduced"
        return GuardResult("renal", "fail", "D", rationale)
    band = "C" if egfr_value < 60 else "B"
    rationale = f"eGFR {egfr_value:.0f} ml/min"
    return GuardResult("renal", "pass", band, rationale)


def guard_anticoag(facts: dict[str, Any]) -> GuardResult:
    meds = [item.lower() for item in facts.get("medications", [])]
    anticoag_agents = {"warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban", "heparin"}
    if not meds:
        return GuardResult("anticoag", "unknown", "D", "Medication list unavailable")
    if anticoag_agents.intersection(meds):
        agent = next(iter(anticoag_agents.intersection(meds)))
        return GuardResult("anticoag", "fail", "D", f"Active anticoagulant: {agent}")
    return GuardResult("anticoag", "pass", "B", "No anticoagulants documented")
