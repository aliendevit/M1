from __future__ import annotations

from datetime import datetime, timezone

from m1.api.main import ComposeNoteRequest, _build_citations, get_template_env
from m1.models import VisitJSON


def test_note_renders_with_citation() -> None:
    visit = VisitJSON(
        chief_complaint="Chest pain",
        hpi={"onset": "1 hour ago", "quality": "pressure", "modifiers": [], "associated_symptoms": [], "red_flags": []},
        exam_bits={"cv": "Regular rhythm", "lungs": "Clear"},
        risks=["Diabetes"],
        plan_intents=[],
        language_pref="en",
    )
    facts = {
        "labs": [
            {
                "code": "trop",
                "label": "Troponin I",
                "display_value": "0.05 ng/mL (+0.03)",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }
    payload = ComposeNoteRequest(visit=visit, facts=facts, assessment_summary="Stable")
    citations = _build_citations(payload)
    env = get_template_env()
    note = env.get_template("note.j2").render(
        visit=visit,
        assessment_summary="Stable",
        citations=citations,
    )
    assert "[^src:lab-trop]" in note
    assert note.count("[^src:") >= 2
