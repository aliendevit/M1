# path: scripts/sbom_cyclonedx.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Dict

try:
    from importlib import metadata as im
except Exception:
    import importlib_metadata as im  # type: ignore


def _purl(name: str, version: str) -> str:
    return f"pkg:pypi/{name}@{version}"

def build_bom() -> Dict:
    comps = []
    for dist in im.distributions():
        try:
            name = dist.metadata["Name"] or dist.metadata["Summary"]  # type: ignore
            version = dist.version
            if not name or not version:
                continue
            name = str(name)
            comps.append({
                "type": "library",
                "name": name,
                "version": version,
                "purl": _purl(name.lower(), version),
                "licenses": [],  # optional for MVP
                "properties": [
                    {"name":"installed_location","value": str(getattr(dist, 'locate_file', lambda p='': '')())}
                ]
            })
        except Exception:
            continue
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": "urn:uuid:auto-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"vendor":"MinuteOne","name":"sbom_cyclonedx.py","version":"0.1.0"}]
        },
        "components": sorted(comps, key=lambda x: x["name"].lower()),
    }
    return bom

def main():
    import argparse, sys
    p = argparse.ArgumentParser(description="Generate CycloneDX SBOM (JSON) from local Python env.")
    p.add_argument("-o", "--out", default="exports/sbom.json", help="Output path (JSON)")
    args = p.parse_args()
    bom = build_bom()
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(bom, f, ensure_ascii=False, indent=2)
    print(f"Wrote SBOM: {args.out}")

if __name__ == "__main__":
    main()
