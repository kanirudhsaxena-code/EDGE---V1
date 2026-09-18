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

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo
from typing import Any, Optional

from src.autonomous_evidence_acquisition import AutonomousEvidenceAcquirer
from src.autonomous_interpreter import ConservativeAutonomousInterpreter
from src.checkpoint_reconciler import reconcile_overdue_checkpoints
from src.evidence_persistence import canonical_evidence_records
from src.final_execution import reconcile_with_structure
from src.market_providers import UpstoxReadOnlyStockProvider
from src.persistence import AtomicNeonPersistenceAdapter, CanonicalRecommendationWrite
from src.pre_run_gate import evaluate_pre_run_gate
from src.production_bundle import ProductionMetadata, build_canonical_bundle
from src.release_gate import ReleaseApproval, evaluate_release_gate
from src.report import render_standard_edge_report
from src.shadow_pipeline import compute_shadow_recommendation
from src.state_recovery import recover_pre_run_state
from src.trading_calendar import fetch_next_five_nse_trading_dates
from src.upstox_research import UpstoxReadOnlyResearchProvider


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
) -> ProductionCandidateResult:
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")

    market=UpstoxReadOnlyStockProvider(upstox_token)
    research=UpstoxReadOnlyResearchProvider(upstox_token)

    # Canonical efficacy is assessed first. Only overdue checkpoints are captured;
    # today's incomplete session is never substituted for a daily close.
    reconcile_overdue_checkpoints(connection,market,ticker,run_at)
    state=recover_pre_run_state(connection,ticker,run_at)
    pre=evaluate_pre_run_gate(state.open_recommendations,state.efficacy_snapshot)
    if not pre.ready:
        return ProductionCandidateResult(
            "BLOCKED_PRE_RUN_EFFICACY",pre.blockers,None,None,None
        )

    acquirer=AutonomousEvidenceAcquirer(market,[research])
    acquired=acquirer.acquire(ticker,run_at,options_decision_requested=False)
    if not acquired.gate.ready:
        return ProductionCandidateResult(
            "BLOCKED_EVIDENCE",acquired.gate.blockers,None,None,None
        )

    analyst=ConservativeAutonomousInterpreter()
    interpretation=analyst(acquired.ticker,acquired.evidence,acquired.payloads,run_at)
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
        reference_price=interpretation.zone_context.close,
        checkpoint_dates=checkpoint_dates,
        execution_plan=final.execution_plan,
        active_override=shadow.event_override,
        rationale="Autonomous governed EDGE V1 production candidate.",
    )
    canonical=build_canonical_bundle(shadow,metadata)
    report=render_standard_edge_report(canonical)

    if not publish:
        return ProductionCandidateResult(
            "PRODUCTION_CANDIDATE_READY",(),canonical,report,None
        )

    approval=release_approval or ReleaseApproval()
    release=evaluate_release_gate(
        approval,recommendation_text=canonical.definitive_recommendation
    )
    if not release.ready:
        return ProductionCandidateResult(
            "BLOCKED_RELEASE_GOVERNANCE",release.blockers,canonical,report,None
        )

    evidence_rows=canonical_evidence_records(acquired.evidence)
    adapter=AtomicNeonPersistenceAdapter(
        lambda: connection,evidence_records=evidence_rows
    )
    persistence_id=adapter.persist(canonical)
    return ProductionCandidateResult(
        "PUBLISHED",(),canonical,report,persistence_id
    )
