from dataclasses import replace
from datetime import datetime, timezone

from src.evidence_gate import EvidenceItem
from src.frozen_engine import ComponentInput
from src.research_bundle import (
    GovernedResearchBundle,
    ResearchReconciliationError,
    apply_independent_research_validation,
    independently_verified_event_shock_g5_state,
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


def test_incomplete_research_sensitive_coverage_is_blocked():
    gate=validate_research_bundle_payload(payload(),ticker="TITAN",run_at=RUN_AT)
    assert gate.ready is False
    assert any("mandatory research-sensitive components" in b for b in gate.blockers)
    assert any("INSTITUTIONAL_BEHAVIOUR" in b for b in gate.blockers)
    assert any("VALUATION" in b for b in gate.blockers)
    assert any("EVENT_SHOCK" in b for b in gate.blockers)


def test_complete_five_dimension_research_coverage_is_ready():
    p=payload()
    p["claims"].extend([
        {"claim_id":"c3","evidence_category":"VALUATION","statement":"Valuation independently checked.","materiality":"MODERATE","direction":"NEGATIVE","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
        {"claim_id":"c4","evidence_category":"INSTITUTIONAL_BEHAVIOUR","statement":"Institutional behaviour independently checked.","materiality":"MODERATE","direction":"POSITIVE","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
        {"claim_id":"c5","evidence_category":"EVENT_SHOCK","statement":"No material event shock identified.","materiality":"HIGH","direction":"NEUTRAL","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
    ])
    gate=validate_research_bundle_payload(p,ticker="TITAN",run_at=RUN_AT)
    assert gate.ready is True
    assert not gate.blockers


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
    assert "fresh independent governed web validation was unavailable" in out.component_summaries["VALUATION"][1]
    assert out.completeness_score == 78.0


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
    assert "Independent governed web research validated" in out.component_summaries["VALUATION"][1]


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
    assert out.component_summaries["VALUATION"][0]=="CONFLICTED · EXCLUDED FROM SCORE"
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
    assert out.component_summaries["BUSINESS_FUNDAMENTALS"][0]=="VERIFIED · EXCLUDED FROM SCORE"
    assert "not independently confirmed" in out.component_summaries["BUSINESS_FUNDAMENTALS"][1]


def test_verified_research_with_missing_provider_score_remains_verified_but_excluded():
    base=interpretation()
    rows=tuple(
        ComponentInput(row.component,None,False)
        if row.component=="BUSINESS_FUNDAMENTALS" else row
        for row in base.component_scores
    )
    provider=replace(base,component_scores=rows)
    research=governed(("BUSINESS_FUNDAMENTALS",))
    out=apply_independent_research_validation(provider,research)
    row=next(x for x in out.component_scores if x.component=="BUSINESS_FUNDAMENTALS")
    assert row.raw_score is None
    assert row.verified is False
    assert out.component_summaries["BUSINESS_FUNDAMENTALS"][0]=="VERIFIED · EXCLUDED FROM SCORE"
    assert "provider component score is unavailable" in out.component_summaries["BUSINESS_FUNDAMENTALS"][1]
    assert "Evidence verification remains VERIFIED" in out.component_summaries["BUSINESS_FUNDAMENTALS"][1]


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
    assert out.component_summaries["NEWS_EVENTS_CATALYSTS"][0]=="VERIFIED · EXCLUDED FROM SCORE"


def test_post_reconciliation_evidence_quality_uses_final_evidence_set():
    evidence=tuple(
        EvidenceItem(name,"TITAN",RUN_AT,f"ref:{name}",verified)
        for name,verified in (
            ("PRICE_STRUCTURE",True),
            ("PV_PVPO",True),
            ("SPECIFIC_CHART_PATTERN",True),
            ("NEWS_EVENTS_CATALYSTS",True),
            ("BUSINESS_FUNDAMENTALS",True),
            ("INSTITUTIONAL_BEHAVIOUR",False),
            ("RELATIVE_STRENGTH",True),
            ("VALUATION",False),
            ("EVENT_SHOCK",False),
        )
    )
    out=apply_independent_research_validation(
        interpretation(),governed(),evidence=evidence
    )
    # Reconciliation excludes the unsupported mandatory components first.
    # Evidence quality is then recomputed from the surviving governed set.
    assert out.completeness_score == 78.0
    assert out.evidence_quality_score == 100.0


def test_v2_system_research_requires_lifecycle_snapshot_and_system_web():
    p=payload()
    p["contract_version"]="EDGE_RESEARCH_BUNDLE_V2"
    p["research_authority"]="EDGE_SYSTEM"
    p["retrieval_providers"]=["SYSTEM_WEB"]
    p["lifecycle_id"]="EDGE-LC-2026-09-19-TITAN-PREOPEN"
    p["market_snapshot_id"]="EDGE-MKT-TITAN-20260919-085000-abcdef123456"
    for source in p["sources"]:
        source["provider"]="SYSTEM_WEB"
    p["claims"].extend([
        {"claim_id":"c3","evidence_category":"VALUATION","statement":"Valuation independently checked.","materiality":"MODERATE","direction":"NEGATIVE","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
        {"claim_id":"c4","evidence_category":"INSTITUTIONAL_BEHAVIOUR","statement":"Institutional behaviour independently checked.","materiality":"MODERATE","direction":"POSITIVE","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
        {"claim_id":"c5","evidence_category":"EVENT_SHOCK","statement":"No material event shock identified in bounded evidence.","materiality":"HIGH","direction":"NEUTRAL","source_ids":["s2"],"verification_status":"VERIFIED","independent_validation":True},
    ])
    gate=validate_research_bundle_payload(p,ticker="TITAN",run_at=RUN_AT)
    assert gate.ready is True
    del p["market_snapshot_id"]
    gate=validate_research_bundle_payload(p,ticker="TITAN",run_at=RUN_AT)
    assert gate.ready is False
    assert any("market_snapshot_id" in b for b in gate.blockers)


def _event_research(direction: str):
    p=payload()
    p["claims"].append({
        "claim_id":"event-g5",
        "evidence_category":"EVENT_SHOCK",
        "statement":"Independent governed Event-Shock assessment.",
        "materiality":"HIGH",
        "direction":direction,
        "source_ids":["s2"],
        "verification_status":"VERIFIED",
        "independent_validation":True,
    })
    return GovernedResearchBundle(
        bundle_id="EDGE-RESEARCH-TITAN-EVENT-G5",
        ticker="TITAN",
        research_fresh_at=datetime(2026,9,19,8,55,tzinfo=timezone.utc),
        payload=p,
        verified_components=frozenset({"EVENT_SHOCK"}),
        source_refs_by_component={"EVENT_SHOCK":("https://www.nseindia.com/example",)},
    )


def test_g5_uses_verified_neutral_event_research_after_provider_score_is_excluded():
    base=interpretation()
    rows=tuple(
        ComponentInput(row.component,-1 if row.component=="EVENT_SHOCK" else row.raw_score,row.verified)
        for row in base.component_scores
    )
    provider=replace(base,component_scores=rows)
    research=_event_research("NEUTRAL")
    reconciled=apply_independent_research_validation(provider,research)
    event=next(row for row in reconciled.component_scores if row.component=="EVENT_SHOCK")
    assert event.raw_score is None
    assert event.verified is False
    state,refs=independently_verified_event_shock_g5_state(research)
    assert state=="NO_MATERIAL_RISK"
    assert refs==("https://www.nseindia.com/example",)


def test_g5_maps_verified_negative_event_research_to_moderate_without_rewriting_edge_score():
    research=_event_research("NEGATIVE")
    state,refs=independently_verified_event_shock_g5_state(research)
    assert state=="MODERATE"
    assert refs==("https://www.nseindia.com/example",)


def test_g5_fails_closed_on_uncertain_independent_event_research():
    research=_event_research("BINARY_UNCERTAIN")
    try:
        independently_verified_event_shock_g5_state(research)
    except ValueError as exc:
        assert "directionally uncertain" in str(exc)
    else:
        raise AssertionError("uncertain Event-Shock research must fail closed")
