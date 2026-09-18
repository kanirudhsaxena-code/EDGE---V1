"""Frozen V13 acceptance scenarios for the implemented EDGE V1 core."""
from src.decision_execution import decide_action
from src.frozen_engine import ComponentInput, compute_des


def test_v13_03_optionable_without_option_evidence_equity_allowed_options_gated():
    r=decide_action(
        forecast="BULLISH",bot_grade="A",market_trust=75,
        execution_quality_score=75,holding_status_known=False,rr=1.6,
        options_data=None,
    )
    assert r.definitive_recommendation=="BUY"
    assert r.options_suitability_status=="NO OPTION TRADE"


def test_v13_05_conflicting_high_weight_evidence_is_retained():
    d=compute_des((
        ComponentInput("PRICE_STRUCTURE",-2),
        ComponentInput("PV_PVPO",-2),
        ComponentInput("BUSINESS_FUNDAMENTALS",2),
        ComponentInput("NEWS_EVENTS_CATALYSTS",2),
    ))
    assert d.positive_contribution > 0
    assert d.negative_contribution_abs > 0
    assert d.directional_agreement < 100


def test_v13_06_o3_override_blocks_aggressive_action():
    r=decide_action(
        forecast="BULLISH",bot_grade="A++",market_trust=90,
        execution_quality_score=95,holding_status_known=False,rr=3.0,
        override="O3",
    )
    assert r.definitive_recommendation=="AVOID"
    assert r.options_suitability_status=="NO OPTION TRADE"


def test_v13_07_strong_forecast_poor_rr_downgrades_to_no_trade():
    r=decide_action(
        forecast="BULLISH",bot_grade="A++",market_trust=90,
        execution_quality_score=90,holding_status_known=False,rr=1.1,
    )
    assert r.definitive_recommendation=="NO TRADE"


def test_v13_12_same_inputs_are_repeatable():
    kwargs=dict(
        forecast="BEARISH",bot_grade="B",market_trust=78.3,
        execution_quality_score=60,holding_status_known=False,rr=1.5,
    )
    assert decide_action(**kwargs)==decide_action(**kwargs)
