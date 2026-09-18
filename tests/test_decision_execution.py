from src.decision_execution import (
    OptionsSuitabilityInput,
    decide_action,
    execution_quality_from_rr,
)


def test_rr_bands_match_frozen_execution_policy():
    assert execution_quality_from_rr(2.0)[0]=="STRONG"
    assert execution_quality_from_rr(1.5)[0]=="ACCEPTABLE"
    assert execution_quality_from_rr(1.2)[0]=="MARGINAL"
    assert execution_quality_from_rr(1.19)[0]=="POOR"


def test_ltf_live_shadow_maps_to_hold_and_no_option_trade_for_known_holder():
    r=decide_action(
        forecast="BASE_RANGE",
        bot_grade="B",
        market_trust=78.33,
        execution_quality_score=60,
        holding_status_known=True,
        holding_exists=True,
        rr=None,
    )
    assert r.decision_ladder=="PILOT"
    assert r.definitive_recommendation=="HOLD"
    assert r.options_suitability_status=="NO OPTION TRADE"
    assert r.actionable is False


def test_base_range_new_position_is_no_trade():
    r=decide_action(
        forecast="BASE_RANGE",bot_grade="A",market_trust=80,
        execution_quality_score=80,holding_status_known=False
    )
    assert r.definitive_recommendation=="NO TRADE"


def test_bullish_a_with_execution_is_buy_but_options_fail_closed_without_contract():
    r=decide_action(
        forecast="BULLISH",bot_grade="A",market_trust=75,
        execution_quality_score=75,holding_status_known=False,rr=1.6
    )
    assert r.definitive_recommendation=="BUY"
    assert r.options_direction_candidate is None
    assert r.options_suitability_status=="NO OPTION TRADE"


def test_bullish_a_plus_can_reach_full_and_buy():
    r=decide_action(
        forecast="BULLISH",bot_grade="A+",market_trust=80,
        execution_quality_score=80,holding_status_known=False,rr=2.1
    )
    assert r.decision_ladder=="FULL"
    assert r.definitive_recommendation=="BUY"


def test_bearish_high_quality_known_holder_reduces_or_sells():
    r=decide_action(
        forecast="BEARISH",bot_grade="A+",market_trust=80,
        execution_quality_score=80,holding_status_known=True,holding_exists=True,rr=1.8
    )
    assert r.definitive_recommendation=="SELL"


def test_bearish_high_quality_new_position_is_avoid_not_short_equity():
    r=decide_action(
        forecast="BEARISH",bot_grade="A",market_trust=70,
        execution_quality_score=75,holding_status_known=False,rr=1.6
    )
    assert r.definitive_recommendation=="AVOID"


def test_options_candidate_requires_every_suitability_condition_and_exact_contract():
    good=OptionsSuitabilityInput(
        True,True,True,True,True,True,True,
        contract_symbol="LTF26SEP300CE",strike=300,expiry="2026-09-24",observed_premium=5.5
    )
    r=decide_action(
        forecast="BULLISH",bot_grade="A+",market_trust=80,
        execution_quality_score=85,holding_status_known=False,rr=2.0,
        options_data=good,
    )
    assert r.options_direction_candidate=="BUY CALL"
    assert r.options_suitability_status=="SUITABLE"


def test_poor_rr_downgrades_directional_setup():
    r=decide_action(
        forecast="BULLISH",bot_grade="A+",market_trust=85,
        execution_quality_score=80,holding_status_known=False,rr=1.1
    )
    assert r.definitive_recommendation=="NO TRADE"


def test_o3_blocks_aggressive_action():
    r=decide_action(
        forecast="BULLISH",bot_grade="A++",market_trust=90,
        execution_quality_score=90,holding_status_known=False,rr=3.0,override="O3"
    )
    assert r.definitive_recommendation=="AVOID"
    assert r.options_suitability_status=="NO OPTION TRADE"
