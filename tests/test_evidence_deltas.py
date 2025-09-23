from __future__ import annotations

from pathlib import Path

from m1.evidence.sqlite_cache import SQLiteChartCache
from m1.fhir.reader import load_bundle


def test_troponin_delta(tmp_path) -> None:
    db_path = tmp_path / "cache.sqlite"
    cache = SQLiteChartCache(db_path)
    cache.initialise()
    bundle = load_bundle(Path(__file__).resolve().parents[1] / "demo" / "patient_bundle.json")
    cache.ingest_bundle(bundle)
    labs = cache.context_window(72)["labs"]
    troponin = next(lab for lab in labs if lab["code"] == "TROP")
    assert troponin["delta_text"] == "+0.03"
    assert "+0.03" in troponin["display_value"]
