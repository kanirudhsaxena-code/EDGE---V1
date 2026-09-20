from datetime import datetime, timezone

from src.frozen_engine import ComponentInput
from src.research_bundle import (
    GovernedResearchBundle,
    ResearchReconciliationError,
    apply_independent_research_validation,
    validate_research_bundle_payload,
)
from src.shadow_pipeline import AnalystInterpretation


RUN_AT=datetime(2026,9,19,9,0,tzinfo=timezone.utc)


def payload():
    return {
        "contract_version":"EDGE_RESEARCH_BUNDLE_V1",
        "bundle_id":"EDGE-RESEARCH-TITAN-20260919-085500",
        "ticker":"TITAN",
        "command":"EDGE TITAN",
        "created_at":"2026-09-19T08:55:00+00:00",
        "research_fresh_at":"2026-09-19T08:55:00+00:00",
        "research_authority":"CHATGPT",
        "retrieval_providers":["CHATGPT_WEB","EXA","UPSTOX"],
        "sources":[
            {"source_id":"s1","provider":"UPSTOX","authority":"BROKER_PROVIDER","url":"https://api.upstox.com/example","title":"Upstox evidence","retrieved_at":"2026-09-19T08:54:00+00:00"},
            {"source_id":"s2","provider":"CHATGPT_WEB","authority":"EXCHANGE","url":"https://www.nseindia.com/example","title":"NSE evidence","retrieved_at":"2026-09-19T08:54:30+00:00"},
        ],
        "claims":[
            {"claim_id":"c1","evidence_category":"NEWS_EVENTS_CATALYSTS","statement":"No unresolved adverse catalyst found in current exchange/company evidence.","materiality":"HIGH","direction":"NEUTRAL","source_ids":["s1","s2"],"verification_status":"VERIFIED","independent_validation":True},
            {"claim_id":"c2","evidence_category":"BUSINESS_FUNDAMENTALS","statement":"Latest reported fundamentals independently checked.","materiality":"MODERATE","direction":"POSITIVE","source_ids":["s1","s2"],"verification_status":"VERIFIED","independent_validation":True},
        ],
        "limitations":[],
    }


def interpretation():
    return AnalystInterpretation(
        component_scores=(
            ComponentInput("PRICE_STRUCTURE",1,True),
            ComponentInput("PV_PVPO",0,True),
            ComponentInput("SPECIFIC_CHART_PATTERN",1,True),
            ComponentInput("NEWS_EVENTS_CATALYSTS",0,True),
            ComponentInput("BUSINESS_FUNDAMENTALS",1,True),
            ComponentInput("INSTITUTIONAL_BEHAVIOUR",1,True),
            ComponentInput("RELATIVE_STRENGTH",1,True),
            ComponentInput("VALUATION",-1,True),
            ComponentInput("EVENT_SHOCK",0,True),
        ),
        evidence_quality_score=90,
        freshness_score=100,
        completeness_score=100,
        market_confirmation_score=70,
        structure_pattern_quality=75,
        pv_pvpo_confirmation=60,
        catalyst_asymmetry=50,
        execution_quality=60,
        expected_price_zone_low=100,
        expected_price_zone_high=110,
        horizon_trading_days=5,
        definitive_recommendation="NO TRADE",
        component_summaries={},
    )


def governed(verified=("NEWS_EVENTS_CATALYSTS","BUSINESS_FUNDAMENTALS")):
    refs={name:("https://www.nseindia.com/example",) for name in verified}
    return GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-20260919-085500",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=payload(),
        verified_components=frozenset(verified),
        source_refs_by_component=refs,
    )


def test_bundle_requires_chatgpt_web_authority():
    p=payload()
    p["retrieval_providers"]=["EXA","UPSTOX"]
    gate=validate_research_bundle_payload(p,ticker="TITAN",run_at=RUN_AT)
    assert gate.ready is False
    assert any("CHATGPT_WEB" in b for b in gate.blockers)


def test_material_provider_only_claim_is_blocked():
    p=payload()
    p["claims"][0]["source_ids"]=["s1"]
    gate=validate_research_bundle_payload(p,ticker="TITAN",run_at=RUN_AT)
    assert gate.ready is False
    assert any("independent web validation" in b for b in gate.blockers)


def test_material_conflict_is_blocked():
    p=payload()
    p["claims"][0]["verification_status"]="CONFLICTED"
    p["claims"][0]["conflict_note"]="Sources disagree"
    gate=validate_research_bundle_payload(p,ticker="TITAN",run_at=RUN_AT)
    assert gate.ready is False
    assert any("unresolved material conflict" in b for b in gate.blockers)


def test_missing_independent_component_validation_excludes_provider_score():
    out=apply_independent_research_validation(interpretation(),governed())
    by_name={x.component:x for x in out.component_scores}
    assert by_name["NEWS_EVENTS_CATALYSTS"].verified is True
    assert by_name["BUSINESS_FUNDAMENTALS"].verified is True
    assert by_name["VALUATION"].verified is False
    assert by_name["VALUATION"].raw_score is None
    assert "fresh independent ChatGPT web validation was unavailable" in out.component_summaries["VALUATION"][1]


def test_independently_validated_component_keeps_frozen_provider_score():
    p=payload()
    p["claims"].extend([
        {"claim_id":"c3","evidence_category":"VALUATION","statement":"Independent valuation evidence is negative.","materiality":"MODERATE","direction":"NEGATIVE","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
        {"claim_id":"c4","evidence_category":"INSTITUTIONAL_BEHAVIOUR","statement":"Independent institutional evidence is positive.","materiality":"MODERATE","direction":"POSITIVE","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
        {"claim_id":"c5","evidence_category":"EVENT_SHOCK","statement":"No event shock is independently verified.","materiality":"HIGH","direction":"NEUTRAL","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
    ])
    research=GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-20260919-085500",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=p,
        verified_components=frozenset({"NEWS_EVENTS_CATALYSTS","BUSINESS_FUNDAMENTALS","VALUATION","INSTITUTIONAL_BEHAVIOUR","EVENT_SHOCK"}),
        source_refs_by_component={
            name:("https://www.nseindia.com/example",)
            for name in {"NEWS_EVENTS_CATALYSTS","BUSINESS_FUNDAMENTALS","VALUATION","INSTITUTIONAL_BEHAVIOUR","EVENT_SHOCK"}
        },
    )
    out=apply_independent_research_validation(interpretation(),research)
    by_name={x.component:x for x in out.component_scores}
    assert by_name["VALUATION"].raw_score == -1
    assert by_name["VALUATION"].verified is True
    assert "Independent ChatGPT web research validated" in out.component_summaries["VALUATION"][1]


def test_high_materiality_direction_conflict_fails_closed():
    p=payload()
    p["claims"][1]["materiality"]="HIGH"
    p["claims"][1]["direction"]="NEGATIVE"
    research=GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-20260919-085500",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=p,
        verified_components=frozenset({"BUSINESS_FUNDAMENTALS"}),
        source_refs_by_component={"BUSINESS_FUNDAMENTALS":("https://www.nseindia.com/example",)},
    )
    try:
        apply_independent_research_validation(interpretation(),research)
    except ResearchReconciliationError as exc:
        assert any("BUSINESS_FUNDAMENTALS" in blocker for blocker in exc.blockers)
        assert any("HIGH:NEGATIVE" in blocker for blocker in exc.blockers)
    else:
        raise AssertionError("HIGH research/provider contradiction must fail closed")


def test_moderate_direction_conflict_is_excluded_not_neutralized():
    p=payload()
    p["claims"].append({
        "claim_id":"c3",
        "evidence_category":"VALUATION",
        "statement":"Independent valuation evidence is positive.",
        "materiality":"MODERATE",
        "direction":"POSITIVE",
        "source_ids":["s2"],
        "verification_status":"VERIFIED",
        "independent_validation":True,
    })
    research=GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-20260919-085500",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=p,
        verified_components=frozenset({"VALUATION"}),
        source_refs_by_component={"VALUATION":("https://www.nseindia.com/example",)},
    )
    out=apply_independent_research_validation(interpretation(),research)
    by_name={x.component:x for x in out.component_scores}
    assert by_name["VALUATION"].verified is False
    assert by_name["VALUATION"].raw_score is None
    assert out.component_summaries["VALUATION"][0]=="CONFLICTED"
    assert "excluded rather than neutralized or overwritten" in out.component_summaries["VALUATION"][1]


def test_compatible_research_preserves_exact_provider_score():
    p=payload()
    p["claims"].append({
        "claim_id":"c3",
        "evidence_category":"VALUATION",
        "statement":"Independent valuation evidence is negative.",
        "materiality":"MODERATE",
        "direction":"NEGATIVE",
        "source_ids":["s2"],
        "verification_status":"VERIFIED",
        "independent_validation":True,
    })
    research=GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-20260919-085500",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=p,
        verified_components=frozenset({"VALUATION"}),
        source_refs_by_component={"VALUATION":("https://www.nseindia.com/example",)},
    )
    out=apply_independent_research_validation(interpretation(),research)
    by_name={x.component:x for x in out.component_scores}
    assert by_name["VALUATION"].verified is True
    assert by_name["VALUATION"].raw_score == -1


def test_binary_uncertain_research_excludes_directional_provider_without_conflict():
    p=payload()
    p["claims"][1]["materiality"]="HIGH"
    p["claims"][1]["direction"]="BINARY_UNCERTAIN"
    research=GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-20260919-085500",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=p,
        verified_components=frozenset({"BUSINESS_FUNDAMENTALS"}),
        source_refs_by_component={"BUSINESS_FUNDAMENTALS":("https://www.nseindia.com/example",)},
    )
    out=apply_independent_research_validation(interpretation(),research)
    row=next(x for x in out.component_scores if x.component=="BUSINESS_FUNDAMENTALS")
    assert row.raw_score is None
    assert row.verified is False
    assert out.component_summaries["BUSINESS_FUNDAMENTALS"][0]=="NOT VERIFIED"
    assert "not independently confirmed" in out.component_summaries["BUSINESS_FUNDAMENTALS"][1]


def test_neutral_research_validates_neutral_provider_score():
    out=apply_independent_research_validation(
        interpretation(),
        governed(("NEWS_EVENTS_CATALYSTS","BUSINESS_FUNDAMENTALS")),
    )
    row=next(x for x in out.component_scores if x.component=="NEWS_EVENTS_CATALYSTS")
    assert row.raw_score == 0
    assert row.verified is True
    assert "Research direction(s): NEUTRAL" in out.component_summaries["NEWS_EVENTS_CATALYSTS"][1]


def test_directional_research_does_not_falsely_validate_neutral_provider():
    p=payload()
    p["claims"][0]["direction"]="POSITIVE"
    research=GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-20260919-085500",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=p,
        verified_components=frozenset({"NEWS_EVENTS_CATALYSTS"}),
        source_refs_by_component={"NEWS_EVENTS_CATALYSTS":("https://www.nseindia.com/example",)},
    )
    out=apply_independent_research_validation(interpretation(),research)
    row=next(x for x in out.component_scores if x.component=="NEWS_EVENTS_CATALYSTS")
    assert row.raw_score is None
    assert row.verified is False
    assert out.component_summaries["NEWS_EVENTS_CATALYSTS"][0]=="NOT VERIFIED"
