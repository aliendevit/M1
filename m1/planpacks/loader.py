"""Plan pack loader and evaluator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import yaml

from ..guards.service import GuardService, evaluate_planpack_with_guards
from ..schemas import EvidenceChip, PlanpackResponse, VisitJSON


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


def evaluate_planpack(
    pack: PlanPack,
    visit: VisitJSON,
    evidence: Iterable[EvidenceChip],
    *,
    guard_service: GuardService | None = None,
) -> PlanpackResponse:
    guard_service = guard_service or GuardService()
    return evaluate_planpack_with_guards(guard_service, pack, visit, evidence)
