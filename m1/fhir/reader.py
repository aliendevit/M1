"""Lightweight FHIR bundle/NDJSON loader used for ingest tests."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from ..schemas import EvidenceKind
from ..evidence.sqlite_cache import Observation


@dataclass
class FHIRResource:
    resourceType: str
    raw: dict


def load_bundle(path: Path | str) -> List[FHIRResource]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    entries = data.get("entry", [])
    resources: List[FHIRResource] = []
    for entry in entries:
        resource = entry.get("resource", {})
        if resource:
            resources.append(FHIRResource(resourceType=resource.get("resourceType", ""), raw=resource))
    return resources


def load_ndjson(path: Path | str) -> List[FHIRResource]:
    file_path = Path(path)
    resources: List[FHIRResource] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            resources.append(FHIRResource(resourceType=raw.get("resourceType", ""), raw=raw))
    return resources


def iter_observations(resources: Iterable[FHIRResource]) -> Iterator[Observation]:
    for resource in resources:
        if resource.resourceType != "Observation":
            continue
        raw = resource.raw
        obs_id = raw.get("id")
        code = raw.get("code", {})
        name = code.get("text") or _first_display(code) or "Observation"
        effective = raw.get("effectiveDateTime") or raw.get("issued") or ""
        category = raw.get("category", [])
        kind = _determine_kind(category)
        value, unit, numeric = _extract_value(raw)
        if not obs_id or not effective:
            continue
        yield Observation(
            id=f"obs/{obs_id}",
            name=name,
            value=value,
            unit=unit,
            numeric_value=numeric,
            time=effective,
            kind=kind,
        )


def _first_display(code: dict) -> str:
    codings = code.get("coding", [])
    for coding in codings:
        if "display" in coding:
            return coding["display"]
    return "Observation"


def _determine_kind(category: list) -> EvidenceKind:
    for entry in category:
        coding = entry.get("coding", [{}])[0]
        code = coding.get("code", "")
        if code == "laboratory":
            return EvidenceKind.lab
        if code == "vital-signs":
            return EvidenceKind.vital
    return EvidenceKind.note


def _extract_value(raw: dict) -> tuple[str, str | None, float | None]:
    if "valueQuantity" in raw:
        value_quantity = raw["valueQuantity"]
        value = value_quantity.get("value")
        unit = value_quantity.get("unit")
        if isinstance(value, (int, float)):
            text_value = f"{value} {unit}".strip()
            return text_value, unit, float(value)
    if "valueString" in raw:
        return str(raw["valueString"]), None, None
    if "valueCodeableConcept" in raw:
        text = raw["valueCodeableConcept"].get("text") or _first_display(raw["valueCodeableConcept"])
        return text, None, None
    return "", None, None
