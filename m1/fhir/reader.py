from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_bundle(path: str | Path) -> dict[str, Any]:
    """Load a FHIR-like bundle from disk."""

    bundle_path = Path(path)
    with bundle_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
