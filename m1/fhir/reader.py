"""FHIR bundle ingestion utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

import json

from .slice import bundle_to_rows


class FHIRReader:
    """Read FHIR bundles from disk and yield row-oriented structures."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else None

    def read_bundle(self, path: str | Path) -> Dict[str, List[Dict[str, object]]]:
        bundle_path = Path(path)
        if not bundle_path.is_absolute() and self.root:
            bundle_path = self.root / bundle_path
        with bundle_path.open("r", encoding="utf-8") as handle:
            bundle = json.load(handle)
        return bundle_to_rows(bundle)

    def iter_entries(self, bundle: dict) -> Iterable[dict]:
        for entry in bundle.get("entry", []) or []:
            resource = entry.get("resource") if isinstance(entry, dict) else None
            if isinstance(resource, dict):
                yield resource
