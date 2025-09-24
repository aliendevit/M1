from m1.extractor.llm import VisitExtractor


def test_visit_extractor_identifies_problems_and_plan():
    extractor = VisitExtractor()
    transcript = "Patient with chest pain. HR 110, BP 150/90. Plan: admit for telemetry."
    result = extractor.extract(transcript)

    assert "chest pain" in result["problems"]
    assert result["vitals"]["heart_rate"] == "110"
    assert any("telemetry" in item for item in result["plan"])
