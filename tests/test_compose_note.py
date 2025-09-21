from m1.composer.service import Composer
from m1.schemas import EvidenceChip, EvidenceKind, HPI, PlanIntent, PlanIntentType, VisitJSON


def test_note_composer_matches_golden_output():
    visit = VisitJSON(
        chief_complaint="Chest pain",
        hpi=HPI(
            onset="this morning",
            quality="pressure",
            modifiers=["exertion"],
            associated_symptoms=["nausea"],
            red_flags=[],
        ),
        exam_bits={"cv": "regular", "lungs": "clear"},
        risks=["tobacco use"],
        plan_intents=[
            PlanIntent(
                type=PlanIntentType.lab_series,
                name="Troponin",
                schedule=["now", "+3h"],
            )
        ],
        language_pref="en",
    )
    evidence = [
        EvidenceChip(
            id="obs/1",
            kind=EvidenceKind.lab,
            name="Troponin I",
            value="0.05 ng/mL",
            delta="↔",
            time="2024-01-02T11:00:00Z",
            source_id="obs/1",
        )
    ]
    composer = Composer()
    rendered = composer.render_note(visit, evidence)
    expected = (
        "# SOAP/MDM Note\n\n"
        "## Subjective\n"
        "- Chief complaint: Chest pain\n"
        "- Onset: this morning\n"
        "- Quality: pressure\n"
        "- Modifiers: exertion\n"
        "- Associated symptoms: nausea\n"
        "- Red flags: none elicited\n\n"
        "## Objective\n"
        "- Troponin I 0.05 ng/mL (↔) [^1]\n\n"
        "## Assessment & Plan\n"
        "- Lab Series: Troponin (now, +3h)\n\n\n"
        "[^1]: Troponin I 0.05 ng/mL at 2024-01-02T11:00:00Z (obs/1)"
    )
    assert rendered.content == expected
