# path: tests/test_guard_resolver.py
import json
import pytest

from backend.services.planpack_service import PlanpackService
from backend.services.chips_engine import ChipsEngine


def test_planpack_guard_blocks_on_pregnancy_chest_pain(fixtures_dir):
    with open(fixtures_dir / "sample_facts.json", "r", encoding="utf-8") as f:
        facts = json.load(f)
    visit = {
        "chief_complaint": "chest pain",
        "hpi": {"onset": "since 2 hours", "quality": "pressure", "modifiers": [], "associated_symptoms": [], "red_flags": []},
        "exam_bits": {"cv": None, "lungs": None},
        "risks": [],
        "plan_intents": [],
        "language_pref": "en",
    }
    svc = PlanpackService.instance()
    out = svc.suggest("chest_pain", visit, facts)
    # aspirin should be D-banded when pregnancy/bleed conflicts exist (guard failure or unknown)
    d_bands = [s for s in out["suggestions"] if s["band"] == "D"]
    assert any("Aspirin" in s["label"] for s in d_bands)


def test_override_requires_reason():
    eng = ChipsEngine.instance()
    with pytest.raises(ValueError):
        eng.resolve(chip_id="x", action="override_blocked", value=None, reason=None)


# ---- pytest fixtures ----
import pathlib
import pytest

@pytest.fixture(scope="session")
def fixtures_dir():
    return pathlib.Path("tests/fixtures")
