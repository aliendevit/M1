# path: tests/test_scoring.py
from backend.services.chips_engine import ChipsEngine


def test_confidence_formula_and_band_thresholds():
    eng = ChipsEngine.instance()
    c = eng.score(rule_hit=1.0, p_llm=0.9, c_asr=0.9, s_ont=0.8, s_ctx=0.9, risk="high")
    assert 0.0 <= c <= 1.0
    band = eng.band(c)
    assert band in {"A","B","C"}  # high score should not be D

    low = eng.score(0.0,0.0,0.0,0.0,0.0,risk="low")
    assert eng.band(low) == "D"


def test_batch_accept_visibility():
    eng = ChipsEngine.instance()
    chips = [
        {"type":"value","band":"B"},
        {"type":"value","band":"B"},
        {"type":"value","band":"B"},
        {"type":"guard","band":"C"},
    ]
    assert eng.batch_accept_visible(chips) is True
    chips.pop()  # still >=3 B of same type
    assert eng.batch_accept_visible(chips) is True
    chips.pop()  # now only 2
    assert eng.batch_accept_visible(chips) is False
