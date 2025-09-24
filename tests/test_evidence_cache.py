from m1.evidence.sqlite_cache import SQLiteEvidenceCache, bundle_from_transcript


def test_bundle_roundtrip(tmp_path):
    db_path = tmp_path / "cache.db"
    cache = SQLiteEvidenceCache(db_path)
    patient_id = "test-patient"
    transcript = "Chest pain with HR 120"
    extraction = {
        "problems": ["chest pain"],
        "medications": [],
        "vitals": {"heart_rate": "120"},
        "plan": ["Admit"]
    }
    bundle = bundle_from_transcript(patient_id, transcript, extraction)

    cache.upsert_bundle(bundle)
    items = cache.fetch_items(patient_id)

    assert len(items) == 2
    structured = next(item for item in items if item.section == "structured")
    assert structured.payload["problems"] == ["chest pain"]
