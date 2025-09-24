from m1.guards.service import GuardService


def test_guard_blocks_high_risk_term():
    guard = GuardService()
    bundle = {"sections": {"subjective": {"transcript": "Call code blue for cardiac arrest"}}}

    decision = guard.evaluate(bundle)

    assert decision.blocked is True
    assert "cardiac arrest" in decision.flags[0].lower()


def test_guard_flags_soft_terms_without_block():
    guard = GuardService()
    bundle = {"sections": {"subjective": {"transcript": "Patient had seizure overnight."}}}

    decision = guard.evaluate(bundle)

    assert decision.blocked is False
    assert "seizure" in [flag.lower() for flag in decision.flags]
