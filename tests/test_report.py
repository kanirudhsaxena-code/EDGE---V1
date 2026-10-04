from datetime import date, datetime, timezone

from src.assessment_context import ActiveCall, AssessmentContext, MasterAssessment, StockAssessment
from src.persistence import (
    BotScoreWrite, CanonicalRecommendationWrite, ComponentScoreWrite,
    ExecutionPlanWrite, MarketTrustWrite,
)
from src.report import render_standard_edge_report
from src.forecast_path import ForecastPathRow, ForecastPathWrite


def bundle():
    names=[
        "BUSINESS_FUNDAMENTALS","VALUATION","PRICE_STRUCTURE","SPECIFIC_CHART_PATTERN",
        "PV_PVPO","RELATIVE_STRENGTH","INSTITUTIONAL_BEHAVIOUR",
        "NEWS_EVENTS_CATALYSTS","EVENT_SHOCK",
    ]
    comps=tuple(ComponentScoreWrite(n,10,0,0,"HIGH","AVAILABLE",10,0) for n in names)
    return CanonicalRecommendationWrite(
        recommendation_id="EDGE-LTF-20260918-01",
        parent_recommendation_id="EDGE-LTF-20260917-01",
        ticker="LTF",company_name="L&T Finance",
        run_timestamp=datetime(2026,9,18,6,0,tzinfo=timezone.utc),
        forecast_horizon="D+5",bull_probability=3.806,base_probability=64.876,
        bear_probability=31.318,definitive_forecast="BASE_RANGE",
        expected_price_zone_low=297.15,expected_price_zone_high=312.105,
        des=-23.5,market_trust_score=78.33,market_trust_band="HIGH",
        bot_score=66.838,bot_grade="B",decision_ladder="INVESTIGATION",
        definitive_recommendation="NO TRADE; NO OPTION TRADE.",
        holding_status_known=False,event_shock_level="LOW",active_override=None,
        evidence_gate_status="PASS",rationale=None,tracking_policy="EDGE_D5_V2",
        horizon_days=5,expiry_trading_date=date(2026,9,25),reference_price=302.3,
        evidence_source_refs=("a",),component_scores=comps,
        market_trust=MarketTrustWrite(100,100,100,51.648,20,78.33,"HIGH"),
        bot=BotScoreWrite(55,78.33,75,75,50,60,66.838,"B","INVESTIGATION"),
        execution_plan=ExecutionPlanWrite(
            instrument="NONE",risk_unit_category="0",
            execution_quality_score=60,execution_quality_level="ADEQUATE",
            option_suitability_status="NO OPTION TRADE",
        ),
        checkpoint_dates=(date(2026,9,21),date(2026,9,22),date(2026,9,23),date(2026,9,24),date(2026,9,25)),
    )


def summaries():
    return {
        "BUSINESS_FUNDAMENTALS":("POSITIVE","Verified income-statement growth evidence produced governed fundamentals score +1."),
        "VALUATION":("NEGATIVE","Verified company-versus-sector valuation ratios produced governed valuation score -1."),
        "PRICE_STRUCTURE":("NEGATIVE","Price structure is negative under the frozen trend rules."),
        "SPECIFIC_CHART_PATTERN":("TREND_CONTINUATION","Verified daily candles classify the active pattern as TREND_CONTINUATION."),
        "PV_PVPO":("NEUTRAL","Price-volume confirmation produced governed score +0."),
        "RELATIVE_STRENGTH":("NEGATIVE","Relative performance versus Nifty 50 produced governed score -1."),
        "INSTITUTIONAL_BEHAVIOUR":("NEGATIVE","Verified FII / mutual-fund / DII holding changes produced governed institutional score -1."),
        "NEWS_EVENTS_CATALYSTS":("NEUTRAL","Verified recent-news catalyst classification produced governed score +0."),
        "EVENT_SHOCK":("NO MATERIAL SHOCK FLAG","Verified event-risk screen produced governed score +0."),
    }


def forecast_path():
    dates=(date(2026,9,18),date(2026,9,21),date(2026,9,22),date(2026,9,23),date(2026,9,24))
    labels=("D","D+1","D+2","D+3","D+4")
    rows=tuple(
        ForecastPathRow(
            horizon_label=label,
            target_trading_date=target,
            direction="BASE",
            bull_probability=20.0,
            base_probability=60.0,
            bear_probability=20.0,
            expected_centre=302.3,
            outer_expected_zone_low=297.15,
            outer_expected_zone_high=312.105,
            evidence_basis=f"governed evidence {label}",
            regime_context="TRANSITION",
            verification_state="VERIFIED",
            lineage={"row":label},
        )
        for label,target in zip(labels,dates)
    )
    return ForecastPathWrite(
        recommendation_id="EDGE-LTF-20260918-01",
        source_run_id="EDGE-LTF-20260918-01",
        issued_at=datetime(2026,9,18,6,0,tzinfo=timezone.utc),
        rows=rows,
    )


def render(*, component_summaries=None):
    return render_standard_edge_report(
        bundle(),
        assessment(),
        component_summaries=summaries() if component_summaries is None else component_summaries,
        forecast_path=forecast_path(),
    )


def assessment():
    master=MasterAssessment(
        recommendations=4,unique_stocks=1,open_recommendations=4,closed_recommendations=0,
        recommendation_hit_rate_pct=None,direction_hit_rate_pct=None,target_hit_rate_pct=None,
        avg_gain_pct=None,avg_loss_pct=None,avg_mfe_pct=None,avg_mae_pct=None,
        cumulative_model_pnl_units=None,official_scorable_recommendations=0,
        provisional_captured_checkpoints=3,provisional_due_checkpoints=17,
        provisional_forecast_scorable=3,provisional_forecast_hits=2,
        provisional_forecast_misses=1,provisional_forecast_accuracy_pct=66.7,
        provisional_zone_scorable=3,provisional_zone_hits=3,
        provisional_zone_misses=0,provisional_zone_accuracy_pct=100.0,
    )
    active=(ActiveCall(
        ticker="LTF",recommendation_id="EDGE-LTF-20260918-065954-AUTO",
        definitive_forecast="BASE_RANGE",definitive_recommendation="NO TRADE; NO OPTION TRADE.",
        zone_low=297.15,zone_high=312.105,expiry_trading_date="2026-09-25",
        current_price=302.3,current_return_pct=0.0,outcome_verdict="OPEN",
        open_recommendations=4,bull_probability=3.806,base_probability=64.876,bear_probability=31.318,
    ),)
    stock=StockAssessment(
        ticker="LTF",recommendations=4,open_recommendations=4,closed_recommendations=0,
        recommendation_hit_rate_pct=None,direction_hit_rate_pct=None,target_hit_rate_pct=None,
        official_scorable_recommendations=0,provisional_captured_checkpoints=3,
        provisional_due_checkpoints=17,provisional_forecast_scorable=3,
        provisional_forecast_hits=2,provisional_forecast_misses=1,
        provisional_forecast_accuracy_pct=66.7,provisional_zone_scorable=3,
        provisional_zone_hits=3,provisional_zone_misses=0,
        provisional_zone_accuracy_pct=100.0,
        latest_checkpoint_observed_at="2026-09-17T11:17:00+00:00",
    )
    return AssessmentContext(master,active,stock)


def test_standard_report_matches_mandatory_efficacy_v2_four_table_order():
    text=render()
    assert text.count("\n\n")==3
    i1=text.index("| EDGE MASTER ASSESSMENT |")
    i2=text.index("| ACTIVE CALLS |")
    i3=text.index("| CURRENT STOCK OUTCOME |")
    i4=text.index("| DRILL-DOWN |")
    assert i1 < i2 < i3 < i4


def test_assessment_section_surfaces_official_and_provisional_efficacy():
    text=render()
    assert "| Official Scorable Sample | 0 |" in text
    assert "| Recommendation Hit Rate | N/A |" in text
    assert "| Provisional Forecast Accuracy | 66.7% | 2 hit / 1 miss; 3 scorable checkpoints |" in text
    assert "| Provisional Zone Accuracy | 100.0% | 3 hit / 0 miss; 3 scorable checkpoints |" in text


def test_active_calls_precedes_new_current_stock_outcome():
    text=render()
    assert "EDGE-LTF-20260918-065954-AUTO" in text
    assert "EDGE-LTF-20260918-01" in text
    assert text.index("EDGE-LTF-20260918-065954-AUTO") < text.index("EDGE-LTF-20260918-01")


def test_report_has_no_narrative_outside_tables():
    text=render()
    for line in text.splitlines():
        if not line.strip():
            continue
        assert line.startswith("|")


def test_no_trade_plan_can_leave_entry_stop_targets_na():
    text=render()
    assert "| Entry | N/A | N/A |" in text
    assert "| Options Contract | N/A | NO OPTION TRADE |" in text


def test_verified_component_interpretations_are_meaningful():
    text=render(component_summaries=summaries())
    assert "Component evidence retained in immutable audit record" not in text
    assert "Verified income-statement growth evidence" in text
    assert "Relative performance versus Nifty 50" in text
    assert text.index("| EDGE MASTER ASSESSMENT |") < text.index("| DRILL-DOWN |")


def test_standard_report_visibly_contains_exact_dd4_regime_and_evidence():
    text=render()
    for label in ("D","D+1","D+2","D+3","D+4"):
        assert f"| Forecast {label} ·" in text
        assert f"governed evidence {label}" in text
    assert "Regime: TRANSITION" in text
    assert "Verification: VERIFIED" in text


def test_verified_component_without_persisted_semantics_fails_closed():
    bad=summaries()
    bad.pop("PRICE_STRUCTURE")
    try:
        render(component_summaries=bad)
    except ValueError as exc:
        assert "PRICE_STRUCTURE" in str(exc)
        assert "missing persisted evidence-grounded narrative" in str(exc)
    else:
        raise AssertionError("VERIFIED component without persisted semantics must fail closed")
