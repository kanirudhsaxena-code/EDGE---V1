from datetime import date, datetime, timezone

from src.persistence import (
    BotScoreWrite, CanonicalRecommendationWrite, ComponentScoreWrite,
    ExecutionPlanWrite, MarketTrustWrite,
)
from src.report import render_standard_edge_report


def bundle():
    names=[
        "BUSINESS_FUNDAMENTALS","VALUATION","PRICE_STRUCTURE","SPECIFIC_CHART_PATTERN",
        "PV_PVPO","RELATIVE_STRENGTH","INSTITUTIONAL_BEHAVIOUR",
        "NEWS_EVENTS_CATALYSTS","EVENT_SHOCK",
    ]
    comps=tuple(ComponentScoreWrite(n,10,0,0,"VERIFIED","AVAILABLE",10,0) for n in names)
    return CanonicalRecommendationWrite(
        recommendation_id="EDGE-LTF-20260918-01",
        parent_recommendation_id="EDGE-LTF-20260917-01",
        ticker="LTF",company_name="L&T Finance",
        run_timestamp=datetime(2026,9,18,6,0,tzinfo=timezone.utc),
        forecast_horizon="D+5",bull_probability=3.806,base_probability=64.876,
        bear_probability=31.318,definitive_forecast="BASE_RANGE",
        expected_price_zone_low=297.15,expected_price_zone_high=312.105,
        des=-23.5,market_trust_score=78.33,market_trust_band="HIGH",
        bot_score=66.838,bot_grade="B",decision_ladder="PILOT",
        definitive_recommendation="HOLD existing delivery; NO OPTION TRADE.",
        holding_status_known=True,event_shock_level="LOW",active_override=None,
        evidence_gate_status="PASS",rationale=None,tracking_policy="EDGE_D5_V2",
        horizon_days=5,expiry_trading_date=date(2026,9,25),reference_price=302.3,
        evidence_source_refs=("a",),component_scores=comps,
        market_trust=MarketTrustWrite(100,100,100,51.648,20,78.33,"HIGH"),
        bot=BotScoreWrite(55,78.33,75,75,50,60,66.838,"B","PILOT"),
        execution_plan=ExecutionPlanWrite(
            instrument="NONE",risk_unit_category="0",
            execution_quality_score=60,execution_quality_level="ADEQUATE",
            option_suitability_status="NO OPTION TRADE",
        ),
        checkpoint_dates=(date(2026,9,21),date(2026,9,22),date(2026,9,23),date(2026,9,24),date(2026,9,25)),
    )


def test_standard_report_contains_exactly_two_markdown_tables():
    text=render_standard_edge_report(bundle())
    assert text.count("|---|---|---|---|")==2
    assert text.startswith("| Field | EDGE Output | Execution / Level | Interpretation |")
    assert "\n\n| EDGE Component | Score / Level | Key Outcome | Interpretation |" in text


def test_report_has_no_narrative_outside_tables():
    text=render_standard_edge_report(bundle())
    for line in text.splitlines():
        if not line.strip():
            continue
        assert line.startswith("|")


def test_no_trade_or_hold_plan_can_leave_entry_stop_targets_na():
    text=render_standard_edge_report(bundle())
    assert "| Entry | N/A | N/A |" in text
    assert "| Options Contract | N/A | NO OPTION TRADE |" in text
