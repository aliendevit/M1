from m1.evidence.sqlite_cache import SQLiteChartCache


def test_lab_deltas(tmp_path):
    db_path = tmp_path / "cache.db"
    cache = SQLiteChartCache(db_path)
    cache.initialize()
    bundle = {
        "patient_id": "demo",
        "sections": {
            "structured": {
                "labs": [
                    {"name": "troponin", "value": 0.01, "unit": "ng/mL", "ts": "1"},
                    {"name": "troponin", "value": 0.05, "unit": "ng/mL", "ts": "2"},
                    {"name": "troponin", "value": 0.07, "unit": "ng/mL", "ts": "3"},
                ]
            }
        }
    }

    cache.ingest_bundle(bundle)
    deltas = cache.lab_deltas("demo", "troponin")

    assert deltas == [0.04, 0.020000000000000004]
