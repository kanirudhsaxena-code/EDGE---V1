from src.release_gate import ReleaseApproval, evaluate_release_gate


def test_default_release_state_is_fail_closed():
    r=evaluate_release_gate(ReleaseApproval(),recommendation_text="SHADOW ONLY — production action not released.")
    assert r.ready is False
    assert len(r.blockers) == 4


def test_shadow_only_output_still_blocks_even_if_flags_are_true():
    r=evaluate_release_gate(
        ReleaseApproval(True,True,True),
        recommendation_text="SHADOW ONLY — production action not released.",
    )
    assert r.ready is False
    assert any("shadow-only" in b for b in r.blockers)


def test_release_requires_all_explicit_governance_flags_and_production_text():
    r=evaluate_release_gate(
        ReleaseApproval(True,True,True),
        recommendation_text="HOLD existing delivery; NO OPTION TRADE.",
    )
    assert r.ready is True
    assert r.blockers == ()
