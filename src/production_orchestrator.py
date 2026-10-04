"""End-to-end non-publishing EDGE production-candidate orchestrator.

Sequence:
1. Reconcile overdue canonical checkpoints.
2. Recover canonical prior-call efficacy state.
3. Fail closed through pre-run gate.
4. Acquire fresh read-only evidence.
5. Interpret evidence and compute frozen EDGE forecast.
6. Finalize Phase 8 execution quality and reconcile BOT/Decision Ladder.
7. Resolve D+1..D+5 using the exchange holiday calendar.
8. Build a canonical recommendation bundle and exact Phase 9 report.
9. Persist only when the caller explicitly enables publish and passes release governance.

No broker order/trading action exists here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo
from typing import Any, Callable, Mapping, Optional

from src.assessment_context import load_assessment_context
from src.autonomous_evidence_acquisition import AutonomousEvidenceAcquirer
from src.autonomous_interpreter import ConservativeAutonomousInterpreter
from src.checkpoint_reconciler import reconcile_overdue_checkpoints
from src.evidence_persistence import canonical_evidence_records
from src.final_execution import reconcile_with_structure
from src.forecast_path import ForecastPathWrite
from src.g5_issuance_inputs import (
    G5InputError,
    G5IssuanceInputs,
    G5_SECTOR_REGISTRY_VERSION,
    candles_from_payload,
    combined_lineage,
    compute_atr14,
    event_gap_risk_state,
    extract_profile_sector,
    latest_candle_as_of,
    lineage_from_source,
    liquidity_state_from_candles,
    producer_lineage_maps,
    regime_from_candles,
    regime_from_price_structure,
    sector_benchmark_name,
    stock_daily_payload,
)
from src.horizon_path_shadow import build_g5_stock_dd4_forecast_path
from src.market_providers import AcquisitionError, UpstoxReadOnlyStockProvider
from src.persistence import AtomicNeonPersistenceAdapter, CanonicalRecommendationWrite
from src.pre_run_gate import evaluate_pre_run_gate
from src.production_bundle import ProductionMetadata, build_canonical_bundle
from src.release_gate import ReleaseApproval, evaluate_release_gate
from src.report import render_standard_edge_report
from src.shadow_pipeline import compute_shadow_recommendation
from src.state_recovery import recover_pre_run_state
from src.trading_calendar import fetch_g5_five_nse_trading_dates, fetch_next_five_nse_trading_dates
from src.upstox_research import UpstoxReadOnlyResearchProvider
from src.zone_engine import MarketStructureContext
from src.research_bundle import (
    load_governed_research_bundle,
    augment_acquired_evidence_with_research,
    apply_independent_research_validation,
    ResearchReconciliationError,
)


class HoldingState(str, Enum):
    UNKNOWN="UNKNOWN"
    HOLDS="HOLDS"
    NO_HOLDING="NO_HOLDING"


@dataclass(frozen=True)
class ProductionCandidateResult:
    status: str
    blockers: tuple[str,...]
    canonical_bundle: Optional[CanonicalRecommendationWrite]
    report_markdown: Optional[str]
    persistence_id: Optional[str]
    forecast_path: Optional[ForecastPathWrite] = None


def _event_level(override: Optional[str]) -> str:
    if override=="O3":
        return "EXTREME"
    if override in {"O1","O2"}:
        return "HIGH"
    return "LOW"


def _recommendation_text(action: str, option_status: str) -> str:
    if action=="HOLD":
        return "HOLD existing delivery; NO OPTION TRADE."
    if action in {"NO TRADE","AVOID"}:
        return f"{action}; NO OPTION TRADE."
    suffix="" if option_status=="SUITABLE" else "; NO OPTION TRADE"
    return action + suffix + "."


def _quote_rows(payloads: Mapping[str, Mapping[str, Any]]):
    for source_ref,payload in payloads.items():
        if "/v3/market-quote/quotes" not in source_ref:
            continue
        data=payload.get("data") if isinstance(payload,Mapping) else None
        if not isinstance(data,Mapping):
            continue
        yield data
        for value in data.values():
            if isinstance(value,Mapping):
                yield value


def _preopen_iep_reference_price(payloads: Mapping[str, Mapping[str, Any]]) -> Optional[float]:
    """Extract only an auction-derived IEP for a governed pre-open canonical.

    Full Market Quote V3 may expose indicative_equilibrium_price directly.  A
    nested ltpc.iep form is also accepted for schema compatibility with the V3
    market-data feed shape.  There is intentionally no LTP fallback here:
    yesterday's/stale last trade must never masquerade as the pre-open auction
    reference price.
    """
    for row in _quote_rows(payloads):
        candidates=(row.get("indicative_equilibrium_price"),)
        ltpc=row.get("ltpc")
        if isinstance(ltpc,Mapping):
            candidates=(*candidates,ltpc.get("iep"))
        for value in candidates:
            try:
                price=float(value)
            except (TypeError,ValueError):
                continue
            if price>0:
                return price
    return None


def _live_reference_price(
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    preopen_iep_required: bool=False,
) -> Optional[float]:
    """Extract the authenticated reference price for this production run.

    Normal runs use exchange LTP. A governed pre-open canonical requires IEP and
    deliberately refuses to substitute an older last trade.
    """
    if preopen_iep_required:
        return _preopen_iep_reference_price(payloads)
    for row in _quote_rows(payloads):
        for key in ("last_price","ltp","last_traded_price"):
            value=row.get(key)
            try:
                price=float(value)
            except (TypeError,ValueError):
                continue
            if price>0:
                return price
    return None


def _is_governed_preopen_time(value: datetime) -> bool:
    if value.tzinfo is None or value.utcoffset() is None:
        return False
    local=value.astimezone(ZoneInfo("Asia/Kolkata"))
    clock=local.timetz().replace(tzinfo=None)
    return local.weekday()<5 and time(9,10)<=clock<time(9,15)


def _same_ist_date(left: datetime, right: datetime) -> bool:
    ist=ZoneInfo("Asia/Kolkata")
    return left.astimezone(ist).date()==right.astimezone(ist).date()


def _rebase_structure_context(
    ctx: MarketStructureContext,
    reference_price: float,
) -> MarketStructureContext:
    """Re-anchor daily-derived structure around the fresh authenticated LTP."""
    if reference_price<=0:
        raise ValueError("reference_price must be positive")
    levels=tuple(dict.fromkeys((*ctx.supports,*ctx.resistances)))
    supports=tuple(sorted((x for x in levels if x<reference_price),reverse=True))
    resistances=tuple(sorted(x for x in levels if x>reference_price))
    return replace(
        ctx,
        close=float(reference_price),
        supports=supports,
        resistances=resistances,
    )



def _verified_component_raw_score(interpretation, component: str) -> Optional[int]:
    target = component.strip().upper()
    for row in interpretation.component_scores:
        if row.component.strip().upper() != target:
            continue
        if not row.verified or row.raw_score is None:
            return None
        return int(row.raw_score)
    return None


def _stock_quote_source_ref(
    payloads: Mapping[str, Mapping[str, Any]],
    instrument_key: str,
) -> str:
    encoded = instrument_key.replace("|", "%7C")
    matches = [
        source_ref
        for source_ref in payloads
        if "/v3/market-quote/quotes" in source_ref
        and (instrument_key in source_ref or encoded in source_ref)
    ]
    if len(matches) != 1:
        raise G5InputError("G5 requires exactly one attributable stock quote source")
    return matches[0]


def _build_g5_issuance_inputs(
    *,
    acquired,
    interpretation,
    shadow,
    market: UpstoxReadOnlyStockProvider,
    governed_research,
    run_at: datetime,
    p0: float,
) -> G5IssuanceInputs:
    local_day = run_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
    stock_candles, stock_daily_ref = stock_daily_payload(
        acquired.payloads,
        instrument_key=acquired.instrument_key,
    )
    atr14 = compute_atr14(stock_candles)
    liquidity_state = liquidity_state_from_candles(stock_candles)

    stock_score = _verified_component_raw_score(interpretation, "PRICE_STRUCTURE")
    if stock_score is None:
        raise G5InputError("G5 stock Price Structure is not verified")
    stock_regime = regime_from_price_structure(stock_score)

    sector_name, profile_ref = extract_profile_sector(acquired.payloads)
    sector_benchmark = sector_benchmark_name(sector_name)
    sector_key, resolved_sector_name = market.resolve_nse_index(sector_benchmark)
    if resolved_sector_name.casefold() != sector_benchmark.casefold():
        raise G5InputError("G5 resolved sector benchmark identity changed unexpectedly")
    sector_env = market.daily(
        sector_key,
        local_day - timedelta(days=180),
        local_day,
    )
    sector_candles = candles_from_payload(sector_env.payload)
    sector_regime = regime_from_candles(sector_candles)

    event_score = _verified_component_raw_score(interpretation, "EVENT_SHOCK")
    event_state = event_gap_risk_state(
        event_shock_raw_score=event_score,
        active_override=shadow.event_override,
    )

    g5_calendar = fetch_g5_five_nse_trading_dates(
        market,
        start_on=local_day,
    )
    quote_ref = _stock_quote_source_ref(acquired.payloads, acquired.instrument_key)
    stock_as_of = latest_candle_as_of(stock_candles)
    sector_as_of = latest_candle_as_of(sector_candles)
    event_refs = tuple(
        dict.fromkeys(
            evidence.source_ref
            for evidence in acquired.evidence
            if evidence.category == "EVENT_SHOCK"
            and evidence.verified
            and evidence.source_ref.strip()
        )
    )
    if not event_refs:
        raise G5InputError("G5 Event-Shock lineage is unavailable")

    lineage = {
        "p0": lineage_from_source(
            source_ref=quote_ref,
            provider="UPSTOX",
            as_of=run_at.isoformat(),
            acquired_at=run_at,
        ),
        "atr14": lineage_from_source(
            source_ref=stock_daily_ref,
            provider="UPSTOX",
            as_of=stock_as_of,
            acquired_at=run_at,
        ),
        "stock_regime": lineage_from_source(
            source_ref=stock_daily_ref,
            provider="UPSTOX",
            as_of=stock_as_of,
            acquired_at=run_at,
        ),
        "sector_regime": combined_lineage(
            source_refs=(profile_ref, sector_env.source_ref),
            provider="UPSTOX",
            as_of=sector_as_of,
            acquired_at=sector_env.received_at,
            derivation_version=G5_SECTOR_REGISTRY_VERSION,
        ),
        "liquidity": lineage_from_source(
            source_ref=stock_daily_ref,
            provider="UPSTOX",
            as_of=stock_as_of,
            acquired_at=run_at,
        ),
        "event_gap_risk": combined_lineage(
            source_refs=event_refs,
            provider="GOVERNED_EDGE_EVIDENCE",
            as_of=governed_research.research_fresh_at.isoformat(),
            acquired_at=run_at,
        ),
        "calendar": lineage_from_source(
            source_ref=g5_calendar.source_ref,
            provider="UPSTOX",
            as_of=local_day.isoformat(),
            acquired_at=g5_calendar.acquired_at,
            derivation_version=g5_calendar.calendar_version,
        ),
    }
    return G5IssuanceInputs(
        p0=float(p0),
        atr14=atr14,
        stock_regime=stock_regime,
        sector_regime=sector_regime,
        liquidity_state=liquidity_state,
        event_gap_risk_state=event_state,
        target_trading_dates=g5_calendar.dates,
        calendar_version=g5_calendar.calendar_version,
        lineage=lineage,
        sector_name=sector_name,
        sector_benchmark=sector_benchmark,
    )

def build_production_candidate(
    *,
    connection: Any,
    ticker: str,
    run_at: datetime,
    upstox_token: str,
    holding_state: HoldingState=HoldingState.UNKNOWN,
    company_name: Optional[str]=None,
    publish: bool=False,
    release_approval: Optional[ReleaseApproval]=None,
    historical_cache: Any=None,
    research_bundle_id: Optional[str]=None,
    canonical_requested_at: Optional[datetime]=None,
    canonical_attempt_slot: Optional[str]=None,
    governance_trigger_type: str="USER",
    runtime_clock: Optional[Callable[[], datetime]]=None,
) -> ProductionCandidateResult:
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")

    preopen_canonical=canonical_requested_at is not None
    if preopen_canonical:
        if (
            canonical_requested_at is None
            or not _is_governed_preopen_time(canonical_requested_at)
            or not _is_governed_preopen_time(run_at)
            or not _same_ist_date(canonical_requested_at,run_at)
        ):
            return ProductionCandidateResult(
                "BLOCKED_PREOPEN_DEADLINE",
                ("pre-open canonical execution is outside the governed 09:10-09:15 IST window",),
                None,None,None,
            )

    market=UpstoxReadOnlyStockProvider(upstox_token,historical_cache=historical_cache)
    research=UpstoxReadOnlyResearchProvider(upstox_token)

    # Canonical efficacy is assessed first. Only overdue checkpoints are captured;
    # today's incomplete session is never substituted for a daily close.
    reconcile_overdue_checkpoints(connection,market,ticker,run_at)
    state=recover_pre_run_state(connection,ticker,run_at)
    assessment=load_assessment_context(connection,ticker)
    pre=evaluate_pre_run_gate(state.open_recommendations,state.efficacy_snapshot)
    if not pre.ready:
        return ProductionCandidateResult(
            "BLOCKED_PRE_RUN_EFFICACY",pre.blockers,None,None,None
        )

    if not research_bundle_id:
        return ProductionCandidateResult(
            "BLOCKED_RESEARCH_BUNDLE",("fresh ChatGPT research bundle is required",),None,None,None
        )
    try:
        with connection.cursor() as cur:
            cur.execute(
                "select recommendation_id from recommendation_research_bundle where bundle_id=%s limit 1",
                (research_bundle_id,),
            )
            prior_link=cur.fetchone()
        if prior_link:
            return ProductionCandidateResult(
                "BLOCKED_RESEARCH_BUNDLE",
                ("research bundle has already been consumed by a prior recommendation; a distinct new run requires new research",),
                None,None,None,
            )
        governed_research=load_governed_research_bundle(
            connection,research_bundle_id,ticker=ticker,run_at=run_at
        )
    except (ValueError,TypeError,KeyError) as exc:
        return ProductionCandidateResult(
            "BLOCKED_RESEARCH_BUNDLE",(str(exc),),None,None,None
        )

    acquirer=AutonomousEvidenceAcquirer(market,[research])
    acquired=acquirer.acquire(ticker,run_at,options_decision_requested=False)
    acquired=augment_acquired_evidence_with_research(
        acquired,governed_research,run_at=run_at,options_decision_requested=False
    )
    if not acquired.gate.ready:
        return ProductionCandidateResult(
            "BLOCKED_EVIDENCE",acquired.gate.blockers,None,None,None
        )

    analyst=ConservativeAutonomousInterpreter()
    interpretation=analyst(acquired.ticker,acquired.evidence,acquired.payloads,run_at)

    # Trend/pattern scoring intentionally uses completed daily candles. Production
    # reference price, expected zone and any execution geometry must instead use
    # the fresh authenticated quote acquired for this run.
    live_reference_price=_live_reference_price(acquired.payloads,preopen_iep_required=preopen_canonical)
    if live_reference_price is None:
        return ProductionCandidateResult(
            "BLOCKED_EVIDENCE",(
                "pre-open indicative equilibrium price is unavailable from governed Upstox quote evidence"
                if preopen_canonical
                else "fresh authenticated Upstox market quote is unavailable",
            ),None,None,None
        )
    if interpretation.zone_context is None:
        return ProductionCandidateResult(
            "BLOCKED_EXECUTION",("verified market structure context is unavailable",),None,None,None
        )
    interpretation=replace(
        interpretation,
        zone_context=_rebase_structure_context(
            interpretation.zone_context,
            live_reference_price,
        ),
    )

    try:
        interpretation=apply_independent_research_validation(
            interpretation,governed_research,evidence=acquired.evidence
        )
    except ResearchReconciliationError as exc:
        return ProductionCandidateResult(
            "BLOCKED_RESEARCH_RECONCILIATION",exc.blockers,None,None,None
        )
    shadow=compute_shadow_recommendation(
        acquired,run_at,lambda *_: interpretation
    )
    if interpretation.zone_context is None:
        return ProductionCandidateResult(
            "BLOCKED_EXECUTION",("verified market structure context is unavailable",),None,None,None
        )

    known=holding_state!=HoldingState.UNKNOWN
    holds=holding_state==HoldingState.HOLDS
    final=reconcile_with_structure(
        shadow,interpretation.zone_context,
        holding_status_known=known,holding_exists=holds,
        options_data=None,
    )

    checkpoint_dates=fetch_next_five_nse_trading_dates(
        market,start_after=run_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
    )
    parent_id=(
        state.open_recommendations[-1].recommendation_id
        if state.open_recommendations else None
    )
    stamp=run_at.strftime("%Y%m%d-%H%M%S")
    rid=f"EDGE-{ticker.strip().upper()}-{stamp}-AUTO"
    final_text=_recommendation_text(
        final.decision.definitive_recommendation,
        final.decision.options_suitability_status,
    )

    metadata=ProductionMetadata(
        recommendation_id=rid,
        parent_recommendation_id=parent_id,
        company_name=company_name,
        decision_ladder=final.decision.decision_ladder,
        definitive_recommendation=final_text,
        holding_status_known=known,
        event_shock_level=_event_level(shadow.event_override),
        reference_price=live_reference_price,
        checkpoint_dates=checkpoint_dates,
        execution_plan=final.execution_plan,
        active_override=shadow.event_override,
        rationale="Autonomous governed EDGE V1 production candidate with mandatory ChatGPT research validation and fresh authenticated Upstox reference price.",
        research_bundle_id=governed_research.bundle_id,
        canonical_requested_at=canonical_requested_at,
        canonical_attempt_slot=canonical_attempt_slot,
        governance_trigger_type=governance_trigger_type,
        research_fresh_at=governed_research.research_fresh_at,
    )
    canonical=build_canonical_bundle(shadow,metadata)

    try:
        g5_inputs=_build_g5_issuance_inputs(
            acquired=acquired,
            interpretation=interpretation,
            shadow=shadow,
            market=market,
            governed_research=governed_research,
            run_at=run_at,
            p0=live_reference_price,
        )
        source_ids,source_timestamps,source_hashes=producer_lineage_maps(g5_inputs)
        forecast_path=build_g5_stock_dd4_forecast_path(
            recommendation_id=canonical.recommendation_id,
            source_run_id=canonical.recommendation_id,
            issued_at=run_at,
            p0=g5_inputs.p0,
            atr14=g5_inputs.atr14,
            stock_regime=g5_inputs.stock_regime,
            sector_regime=g5_inputs.sector_regime,
            liquidity_state=g5_inputs.liquidity_state,
            event_gap_risk_state=g5_inputs.event_gap_risk_state,
            target_trading_dates=g5_inputs.target_trading_dates,
            calendar_version=g5_inputs.calendar_version,
            source_ids=source_ids,
            source_timestamps=source_timestamps,
            source_hashes=source_hashes,
            canonical_p0_verified=True,
            atr_history_sufficient=True,
            freshness_verified=True,
        )
        report=render_standard_edge_report(
            canonical,
            assessment,
            component_summaries=shadow.component_summaries,
            forecast_path=forecast_path,
        )
    except (G5InputError,AcquisitionError,ValueError) as exc:
        return ProductionCandidateResult(
            "BLOCKED_G5_INPUTS",(str(exc),),canonical,None,None,None
        )

    if not publish:
        return ProductionCandidateResult(
            "PRODUCTION_CANDIDATE_READY",(),canonical,report,None,forecast_path
        )

    approval=release_approval or ReleaseApproval()
    release=evaluate_release_gate(
        approval,recommendation_text=canonical.definitive_recommendation
    )
    if not release.ready:
        return ProductionCandidateResult(
            "BLOCKED_RELEASE_GOVERNANCE",release.blockers,canonical,report,None,forecast_path
        )

    if preopen_canonical:
        publication_now=(runtime_clock or (lambda: datetime.now(timezone.utc)))()
        if (
            publication_now.tzinfo is None
            or publication_now.utcoffset() is None
            or not _is_governed_preopen_time(publication_now)
            or not _same_ist_date(canonical_requested_at,publication_now)
        ):
            return ProductionCandidateResult(
                "BLOCKED_PREOPEN_DEADLINE",
                ("pre-open canonical publication crossed the 09:15 IST hard boundary",),
                canonical,report,None,forecast_path,
            )

    evidence_rows=canonical_evidence_records(acquired.evidence)
    adapter=AtomicNeonPersistenceAdapter(
        lambda: connection,evidence_records=evidence_rows,forecast_path=forecast_path
    )
    persistence_id=adapter.persist(canonical)
    return ProductionCandidateResult(
        "PUBLISHED",(),canonical,report,persistence_id,forecast_path
    )