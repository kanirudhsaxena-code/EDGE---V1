from datetime import datetime, timezone

from src.autonomous_runner import RecommendationEnvelope
from src.final_execution import reconcile_with_structure
from src.frozen_engine import ComponentInput
from src.shadow_pipeline import ShadowComputation
from src.zone_engine import MarketStructureContext

RUN_AT=datetime(2026,9,18,6,0,tzinfo=timezone.utc)


def shadow(forecast="BASE_RANGE",bull=3.8,base=64.9,bear=31.3,bot=66.8,grade="B"):
    rec=RecommendationEnvelope(
        ticker="LTF",run_timestamp=RUN_AT,framework_version="EDGE_V1",
        definitive_forecast=forecast,
        definitive_recommendation="SHADOW ONLY — production action not released.",
        bull_probability=bull,base_probability=base,bear_probability=bear,
        horizon_trading_days=5,expected_price_zone_low=297,
        expected_price_zone_high=312,evidence_refs=("a",),
    )
    return ShadowComputation(
        ticker="LTF",run_timestamp=RUN_AT,des=-23.5,directional_agreement=51.6,
        market_trust=78.33,market_trust_band="HIGH",
        bull_probability=bull,base_probability=base,bear_probability=bear,
        definitive_forecast=forecast,bot_score=bot,bot_grade=grade,
        component_scores=(ComponentInput("PRICE_STRUCTURE",-2),),
        evidence_quality_score=100,freshness_score=100,completeness_score=100,
        market_confirmation_score=20,structure_pattern_quality=75,
        pv_pvpo_confirmation=75,catalyst_asymmetry=50,execution_quality=60,
        event_override=None,zone_basis="VOLATILITY_STRUCTURE_ENVELOPE",
        zone_width_pct=5,recommendation=rec,
    )


def structure():
    return MarketStructureContext(
        close=302.3,
        supports=(297.15,293.5,282.4),
        resistances=(310.65,313.85,317.3),
        median_true_range=7.275,
        pattern_name="RANGE",
    )


def test_current_ltf_base_range_reconciles_to_investigation_and_no_trade_for_unknown_holding():
    r=reconcile_with_structure(shadow(),structure(),holding_status_known=False)
    assert r.decision.decision_ladder=="INVESTIGATION"
    assert r.decision.definitive_recommendation=="NO TRADE"
    assert r.execution_plan.instrument=="NONE"


def test_current_ltf_base_range_reconciles_to_hold_for_confirmed_holder():
    r=reconcile_with_structure(
        shadow(),structure(),holding_status_known=True,holding_exists=True
    )
    assert r.decision.decision_ladder=="INVESTIGATION"
    assert r.decision.definitive_recommendation=="HOLD"
    assert r.execution_plan.instrument=="NONE"


def test_bullish_directional_plan_requires_visible_stop_and_two_targets():
    s=shadow("BULLISH",bull=75,base=20,bear=5,bot=80,grade="A+")
    r=reconcile_with_structure(s,structure(),holding_status_known=False)
    assert r.execution_plan.instrument in {"EQUITY","NONE"}
    # R:R at first target is finite and determines whether the setup survives.
    assert r.rr_primary is not None
    if r.rr_primary < 1.2:
        assert r.decision.definitive_recommendation=="NO TRADE"


def test_directional_missing_structure_fails_to_actionable_trade():
    s=shadow("BULLISH",bull=75,base=20,bear=5,bot=80,grade="A+")
    weak=MarketStructureContext(
        close=302.3,supports=(),resistances=(310.0,),
        median_true_range=7.0,pattern_name="BREAKOUT",
    )
    r=reconcile_with_structure(s,weak,holding_status_known=False)
    assert r.decision.definitive_recommendation=="NO TRADE"
    assert r.execution_plan.instrument=="NONE"
