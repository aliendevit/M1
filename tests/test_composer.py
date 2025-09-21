from m1.composer.service import Composer
from m1.schemas import EvidenceChip, EvidenceKind, VisitJSON, HPI


def build_visit() -> VisitJSON:
    return VisitJSON(
        chief_complaint="chest pain",
        hpi=HPI(onset="2h ago", quality="pressure", modifiers=[], associated_symptoms=[], red_flags=[]),
        exam_bits={"cv": "regular", "lungs": "clear"},
        risks=["hypertension"],
        plan_intents=[],
        language_pref="en",
    )


def build_evidence() -> list[EvidenceChip]:
    return [
        EvidenceChip(
            id="obs/1",
            kind=EvidenceKind.lab,
            name="Troponin I",
            value="0.04 ng/mL",
            delta="↔",
            time="2025-01-01T08:00",
            source_id="obs/1",
        )
    ]


def test_note_contains_citation():
    composer = Composer()
    rendered = composer.render_note(build_visit(), build_evidence())
    assert "[^1]" in rendered.content
    assert rendered.citations == ["obs/1"]
