from m1.extractor.service import extract_visit


SAMPLE_TRANSCRIPT = """
Chief complaint: chest pain and shortness of breath
Symptoms started two hours ago after walking up stairs
Patient describes it as pressure radiating to left arm
Associated with nausea and sweating
Labs: Troponin now, +3h, +6h
Meds: Aspirin 325 mg PO now
"""


def test_extract_visit_minimum_fields():
    result = extract_visit(SAMPLE_TRANSCRIPT)
    assert result.visit.chief_complaint.startswith("chest pain")
    assert result.visit.hpi.onset is not None
    assert any(intent.name.lower().startswith("troponin") for intent in result.visit.plan_intents)
    assert "chief_complaint" in result.slot_scores
