from datetime import datetime, timezone

from src.autonomous_evidence_acquisition import AcquiredEvidenceBundle
from src.evidence_gate import EvidenceGateResult, EvidenceItem
from src.frozen_engine import ComponentInput
from src.shadow_pipeline import AnalystInterpretation, compute_shadow_recommendation

RUN_AT = datetime(2026,9,17,11,17,tzinfo=timezone.utc)


def ready_bundle():
    cats = (
        "PRICE_STRUCTURE","PV_PVPO","SPECIFIC_CHART_PATTERN",
        "NEWS_EVENTS_CATALYSTS","BUSINESS_FUNDAMENTALS",
        "INSTITUTIONAL_BEHAVIOUR","RELATIVE_STRENGTH","VALUATION","EVENT_SHOCK",
    )
    evidence = tuple(
        EvidenceItem(c,"LTF",RUN_AT,f"ref:{c}",True)
        for c in cats
    )
    return AcquiredEvidenceBundle(
        ticker="LTF",
        instrument_key="NSE_EQ|INE498L01015",
        evidence=evidence,
        payloads={f"ref:{c}":{"ok":True} for c in cats},
        gate=EvidenceGateResult(True,(),(),cats),
    )


def ltf_17_sep_analyst(ticker,evidence,payloads,run_at):
    return AnalystInterpretation(
        component_scores=(
            ComponentInput("PRICE_STRUCTURE",1),
            ComponentInput("PV_PVPO",1),
            ComponentInput("SPECIFIC_CHART_PATTERN",1),
            ComponentInput("NEWS_EVENTS_CATALYSTS",-1),
            ComponentInput("BUSINESS_FUNDAMENTALS",2),
            ComponentInput("INSTITUTIONAL_BEHAVIOUR",1),
            ComponentInput("RELATIVE_STRENGTH",2),
            ComponentInput("VALUATION",0),
            ComponentInput("EVENT_SHOCK",-1),
        ),
        evidence_quality_score=97,
        freshness_score=100,
        completeness_score=100,
        market_confirmation_score=100,
        structure_pattern_quality=75,
        pv_pvpo_confirmation=80,
        catalyst_asymmetry=45,
        execution_quality=60,
        expected_price_zone_low=298,
        expected_price_zone_high=315,
        horizon_trading_days=5,
        definitive_recommendation="HOLD existing delivery; NO OPTION TRADE.",
        event_override="O1",
    )


def test_ltf_17_sep_shadow_replay_matches_canonical_math():
    result = compute_shadow_recommendation(
        ready_bundle(),
        RUN_AT,
        ltf_17_sep_analyst,
    )
    assert abs(result.des - 38.5) < 1e-9
    assert abs(result.directional_agreement - 69.369) < 0.01
    assert abs(result.market_trust - 92.974) < 0.01
    assert result.market_trust_band == "VERY HIGH"
    assert abs(result.bull_probability - 43.117) < 0.01
    assert abs(result.base_probability - 55.313) < 0.01
    assert abs(result.bear_probability - 1.570) < 0.01
    assert result.definitive_forecast == "BASE_RANGE"
    assert abs(result.bot_score - 65.80) < 0.02
    assert result.bot_grade == "B"


def test_analyst_cannot_override_probabilities_or_des():
    result = compute_shadow_recommendation(
        ready_bundle(),
        RUN_AT,
        ltf_17_sep_analyst,
    )
    # Analyst contract contains no DES, MT, probability, forecast, BOT score or grade fields.
    fields = AnalystInterpretation.__dataclass_fields__
    for forbidden in (
        "des","market_trust","bull_probability","base_probability",
        "bear_probability","definitive_forecast","bot_score","bot_grade",
    ):
        assert forbidden not in fields
    assert result.recommendation.framework_version == "EDGE_V1"


def test_shadow_pipeline_refuses_unready_evidence_gate():
    b = ready_bundle()
    blocked = AcquiredEvidenceBundle(
        ticker=b.ticker,
        instrument_key=b.instrument_key,
        evidence=b.evidence,
        payloads=b.payloads,
        gate=EvidenceGateResult(False,("missing fresh evidence",),(),()),
    )
    try:
        compute_shadow_recommendation(blocked,RUN_AT,ltf_17_sep_analyst)
    except ValueError as exc:
        assert "evidence gate" in str(exc)
    else:
        raise AssertionError("blocked evidence must not reach analyst")
