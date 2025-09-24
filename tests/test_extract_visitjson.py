from m1.extractor.llm import VisitExtractor, VisitJSON


def test_extractor_returns_visitjson_schema():
    extractor = VisitExtractor(model_path=None)
    transcript = "Patient reports chest pain. HR 110. Plan: admit for telemetry."

    data = extractor.extract(transcript)
    visit = VisitJSON.model_validate(data)

    assert "chest pain" in visit.problems
    assert visit.vitals["heart_rate"] == "110"
    assert any("telemetry" in item for item in visit.plan)
