from m1.chips.service import band_for_score, build_chip, compute_confidence, keyboard_action_for
from m1.config import ConfidenceConfig
from m1.schemas import ChipAction, ChipBand, SlotScore


def test_confidence_formula_auto_band():
    config = ConfidenceConfig()
    score = compute_confidence(
        SlotScore(rule_hit=1.0, p_llm=1.0, c_asr=1.0, s_ont=1.0, s_ctx=1.0),
        config,
        risk="high",
    )
    assert score > config.thresholds.auto_accept
    band = band_for_score(score, config)
    assert band is ChipBand.auto


def test_build_chip_with_risk_and_guard():
    config = ConfidenceConfig()
    slot_score = SlotScore(rule_hit=0.4, p_llm=0.2, c_asr=0.1, s_ont=0.1, s_ctx=0.2)
    chip = build_chip("troponin_series", slot_score, config, risk="high", guard_status="blocked")
    assert chip.band is ChipBand.blocked
    assert ChipAction.override_blocked in chip.actions


def test_keyboard_actions_respect_chip_actions():
    config = ConfidenceConfig()
    chip = build_chip("plan", SlotScore(rule_hit=1.0, p_llm=1.0), config)
    assert keyboard_action_for(chip, "enter") is ChipAction.accept
    assert keyboard_action_for(chip, "3") is None
