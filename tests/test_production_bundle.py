from datetime import date, datetime, timezone

from src.autonomous_runner import RecommendationEnvelope
from src.frozen_engine import ComponentInput
from src.persistence import ExecutionPlanWrite
from src.production_bundle import ProductionMetadata, build_canonical_bundle
from src.shadow_pipeline import ShadowComputation

RUN_AT=datetime(2026,9,18,5,30,tzinfo=timezone.utc)


def shadow():
    rec=RecommendationEnvelope(
        ticker="LTF",
        run_timestamp=RUN_AT,
        framework_version="EDGE_V1",
        definitive_forecast="BASE_RANGE",
        definitive_recommendation="SHADOW ONLY — production action not released.",
        bull_probability=3.806,
        base_probability=64.876,
        bear_probability=31.318,
        horizon_trading_days=5,
        expected_price_zone_low=297.15,
        expected_price_zone_high=312.105,
        evidence_refs=("ref:a","ref:b"),
    )
    rows=(
        ComponentInput("PRICE_STRUCTURE",-2),
        ComponentInput("PV_PVPO",-1),
        ComponentInput("SPECIFIC_CHART_PATTERN",1),
        ComponentInput("NEWS_EVENTS_CATALYSTS",0),
        ComponentInput("BUSINESS_FUNDAMENTALS",1),
        ComponentInput("INSTITUTIONAL_BEHAVIOUR",0),
        ComponentInput("RELATIVE_STRENGTH",-1),
        ComponentInput("VALUATION",-1),
        ComponentInput("EVENT_SHOCK",0),
    )
    return ShadowComputation(
        ticker="LTF",run_timestamp=RUN_AT,des=-23.5,directional_agreement=51.648,
        market_trust=78.33,market_trust_band="HIGH",
        bull_probability=3.806,base_probability=64.876,bear_probability=31.318,
        definitive_forecast="BASE_RANGE",bot_score=66.838,bot_grade="B",
        component_scores=rows,evidence_quality_score=100,freshness_score=100,
        completeness_score=100,market_confirmation_score=20,
        structure_pattern_quality=75,pv_pvpo_confirmation=75,
        catalyst_asymmetry=50,execution_quality=60,event_override=None,
        zone_basis="VOLATILITY_STRUCTURE_ENVELOPE",zone_width_pct=4.947,
        recommendation=rec,
    )


def meta(text="HOLD existing delivery; NO OPTION TRADE."):
    return ProductionMetadata(
        recommendation_id="EDGE-LTF-20260918-01",
        parent_recommendation_id="EDGE-LTF-20260917-01",
        company_name="L&T Finance",
        decision_ladder="INVESTIGATION",
        definitive_recommendation=text,
        holding_status_known=True,
        event_shock_level="NORMAL",
        reference_price=302.3,
        checkpoint_dates=(
            date(2026,9,21),date(2026,9,22),date(2026,9,23),
            date(2026,9,24),date(2026,9,25),
        ),
        execution_plan=ExecutionPlanWrite(
            instrument="NONE",
            risk_unit_category="0",
            execution_quality_score=60,
            execution_quality_level="MODERATE",
            option_suitability_status="NO_OPTION_TRADE",
        ),
    )


def test_builds_canonical_bundle_without_recomputing_methodology_differently():
    b=build_canonical_bundle(shadow(),meta())
    assert b.recommendation_id=="EDGE-LTF-20260918-01"
    assert b.parent_recommendation_id=="EDGE-LTF-20260917-01"
    assert abs(b.des+23.5)<1e-9
    assert abs(b.market_trust_score-78.33)<1e-9
    assert b.expected_price_zone_low==297.15
    assert b.expected_price_zone_high==312.105
    assert len(b.component_scores)==9
    assert b.expiry_trading_date==date(2026,9,25)


def test_shadow_only_text_is_blocked():
    try:
        build_canonical_bundle(shadow(),meta("SHADOW ONLY — production action not released."))
    except ValueError as exc:
        assert "shadow-only" in str(exc)
    else:
        raise AssertionError("shadow text must not enter canonical persistence")


def test_duplicate_or_unverified_calendar_dates_are_blocked():
    m=meta()
    bad=ProductionMetadata(**{**m.__dict__,"checkpoint_dates":(
        date(2026,9,21),date(2026,9,22),date(2026,9,22),
        date(2026,9,24),date(2026,9,25),
    )})
    try:
        build_canonical_bundle(shadow(),bad)
    except ValueError as exc:
        assert "ordered" in str(exc) or "unique" in str(exc)
    else:
        raise AssertionError("calendar dates must fail closed")


def test_canonical_bundle_deduplicates_shared_evidence_refs():
    s=shadow()
    dup_rec=RecommendationEnvelope(
        **{**s.recommendation.__dict__,"evidence_refs":("ref:a","ref:a","ref:b")}
    )
    s2=ShadowComputation(**{**s.__dict__,"recommendation":dup_rec})
    b=build_canonical_bundle(s2,meta())
    assert b.evidence_source_refs==("ref:a","ref:b")
