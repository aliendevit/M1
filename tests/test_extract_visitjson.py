from __future__ import annotations

from pathlib import Path

from m1.extractor.llm import LLMConfig, LLMExtractor


def test_visitjson_structure_without_model() -> None:
    config = LLMConfig(model_path=Path("missing-model.gguf"))
    extractor = LLMExtractor(config)
    transcript = (
        "Chief complaint is chest pain radiating to left arm. "
        "Patient reports diaphoresis and nausea. Onset was sudden." 
        "Plan includes serial troponin and ECG."
    )
    visit = extractor.extract(transcript)
    assert visit.chief_complaint.lower().startswith("chief complaint") or "chest" in visit.chief_complaint.lower()
    assert isinstance(visit.hpi.modifiers, list)
    assert isinstance(visit.plan_intents, list)
    for intent in visit.plan_intents:
        assert intent.name
        assert intent.type in {"lab_series", "test", "med_admin", "education"}
