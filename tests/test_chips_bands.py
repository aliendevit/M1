from __future__ import annotations

from m1.chips.service import band, build_chips, compute_confidence
from m1.models import SlotScore


def test_confidence_formula_bounds() -> None:
    score = SlotScore(
        slot_id="s1",
        label="All signals",
        rule_hit=1.0,
        p_llm=1.0,
        c_asr=1.0,
        s_ont=1.0,
        s_ctx=1.0,
    )
    assert compute_confidence(score) == 1.0


def test_band_thresholds() -> None:
    high = band(0.95)
    mid = band(0.75)
    low = band(0.5)
    blocked = band(0.1)
    assert high == "A"
    assert mid == "B"
    assert low == "C"
    assert blocked == "D"


def test_build_chips_respects_bands() -> None:
    scores = [
        SlotScore(slot_id="a", label="Auto", rule_hit=0.95, p_llm=0.95, c_asr=0.95, s_ont=0.95, s_ctx=0.95),
        SlotScore(slot_id="b", label="Soft", rule_hit=0.85, p_llm=0.75, c_asr=0.7, s_ont=0.7, s_ctx=0.7),
        SlotScore(slot_id="c", label="Needs confirm", rule_hit=0.6, p_llm=0.6, c_asr=0.5, s_ont=0.5, s_ctx=0.5),
    ]
    chips = build_chips(scores)
    bands = {chip.chip_id: chip.band for chip in chips}
    assert bands["a"] == "A"
    assert bands["b"] == "B"
    assert bands["c"] == "C"
