from pathlib import Path

from m1.planpacks.loader import evaluate_planpack, load_planpack
from m1.schemas import HPI, VisitJSON


def build_visit(risks=None) -> VisitJSON:
    return VisitJSON(
        chief_complaint="chest pain",
        hpi=HPI(onset=None, quality=None, modifiers=[], associated_symptoms=[], red_flags=[]),
        exam_bits={"cv": None, "lungs": None},
        risks=risks or [],
        plan_intents=[],
        language_pref="en",
    )


def test_planpack_blocks_on_guard(tmp_path: Path):
    planpack_path = tmp_path / "pack.yaml"
    planpack_path.write_text(
        """
        pathway: chest_pain_low_intermediate
        guards:
          - require_absent: ["active_bleed"]
        suggest:
          labs:
            - name: Troponin
        """,
        encoding="utf-8",
    )

    pack = load_planpack(planpack_path)
    visit = build_visit(risks=["active_bleed"])
    response = evaluate_planpack(pack, visit, [])
    assert response.guard_flags[0].status == "blocked"
    assert response.suggestions == []
