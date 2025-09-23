# path: tests/test_schemas.py
import json
import pytest
from pydantic import ValidationError

from backend.models.schemas import VisitJSON, VisitHPI, VisitExamBits, VisitPlanIntent, EvidenceChip, Chip


def test_visitjson_strict_success():
    v = VisitJSON(
        chief_complaint="chest pain",
        hpi=VisitHPI(onset="since 2 hours", quality="pressure", modifiers=[], associated_symptoms=["nausea"], red_flags=[]),
        exam_bits=VisitExamBits(cv="regular rate and rhythm", lungs="clear to auscultation"),
        risks=["htn"],
        plan_intents=[VisitPlanIntent(type="lab_series", name="Troponin series", dose=None, schedule=["now","q3h ×2"])],
        language_pref="en",
    )
    js = v.model_dump()
    assert js["chief_complaint"] == "chest pain"
    assert js["hpi"]["onset"] == "since 2 hours"
    assert js["plan_intents"][0]["type"] == "lab_series"


def test_visitjson_rejects_extra_fields():
    with pytest.raises(ValidationError):
        VisitJSON(  # extra field "foo" should be rejected
            chief_complaint="seizure",
            foo="bar",
            hpi=VisitHPI(),
            exam_bits=VisitExamBits(),
        )


def test_evidencechip_enum_delta():
    ok = EvidenceChip(
        id="u1",
        kind="lab",
        name="Troponin I",
        value="0.06 ng/mL",
        delta="↔",
        time="2025-09-21T10:45",
        source_id="obs/124",
    )
    assert ok.delta == "↔"
    with pytest.raises(ValidationError):
        EvidenceChip(
            id="u2", kind="lab", name="X", value="1", delta="UP", time="2025-09-21T10:45", source_id="obs/999"
        )


def test_chip_actions_and_confidence_bounds():
    c = Chip(
        chip_id="cp-1",
        slot="troponin_series",
        type="value",
        band="B",
        label="Troponin cadence",
        options=["q3h ×2","q3h ×3"],
        proposed="q3h ×2",
        confidence=0.78,
        risk="medium",
        evidence=["obs/123","obs/124"],
        actions=["accept","evidence"],
    )
    assert 0.0 <= c.confidence <= 1.0
    with pytest.raises(ValidationError):
        Chip(**{**c.model_dump(), "band": "Z"})
