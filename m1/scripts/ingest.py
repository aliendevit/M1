"""Utility to ingest a bundle or transcript into the local cache."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from ..config import Config
from ..evidence.sqlite_cache import SQLiteEvidenceCache, bundle_from_transcript
from ..extractor.llm import VisitExtractor


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a transcript or bundle into the M1 cache")
    parser.add_argument("input", help="Path to JSON file containing transcript or bundle data")
    parser.add_argument(
        "--patient-id",
        dest="patient_id",
        help="Override patient id when ingesting a transcript-only payload",
    )
    return parser.parse_args(argv)


def load_payload(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> str:
    args = parse_args(argv)
    payload_path = Path(args.input)
    payload = load_payload(payload_path)

    config = Config.load()
    cache = SQLiteEvidenceCache(config.get("cache", {}).get("db", "data/m1_cache.db"))
    extractor = VisitExtractor.from_config(config.get("llm", {}))

    if "sections" in payload:
        patient_id = payload.get("patient_id", args.patient_id or "unknown")
        bundle = {"patient_id": patient_id, "sections": payload["sections"]}
    else:
        transcript = payload.get("transcript", "")
        if not transcript:
            raise SystemExit("Input payload missing transcript or sections field")
        patient_id = args.patient_id or payload.get("patient_id", "unknown")
        extraction = extractor.extract(transcript)
        bundle = bundle_from_transcript(patient_id, transcript, extraction)

    cache.upsert_bundle(bundle)
    return patient_id


if __name__ == "__main__":  # pragma: no cover - manual execution
    pid = main()
    print(f"Ingested bundle for patient: {pid}")
