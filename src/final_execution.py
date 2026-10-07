"""Final Phase 8 execution and BOT reconciliation for EDGE V1.

This module converts the frozen forecast + visible market structure into an
execution candidate, finalizes Execution Quality, recalculates BOT once, and
then applies the frozen Decision Ladder / definitive-action policy.

It is fail-closed:
- directional actionable calls require visible stop + T1 + T2 structure;
- <1.2R is normally downgraded;
- options remain gated unless an exact verified contract is supplied;
- no broker trading action is performed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from src.decision_execution import (
    DecisionExecutionResult,
    OptionsSuitabilityInput,
    decide_action,
)
from src.frozen_engine import BotInputs, BotResult, bot_hunter
from src.persistence import ExecutionPlanWrite
from src.shadow_pipeline import ShadowComputation
from src.zone_engine import MarketStructureContext


@dataclass(frozen=True)
class FinalExecutionDecision:
    decision: DecisionExecutionResult
    bot: BotResult
    execution_plan: ExecutionPlanWrite
    rr_primary: Optional[float]


def _long_equity_plan(ctx: MarketStructureContext) -> tuple[ExecutionPlanWrite, Optional[float], float]:
    entry=ctx.close
    supports=[x for x in ctx.supports if x < entry]
    resistances=[x for x in ctx.resistances if x > entry]

    if not supports or len(resistances) < 2:
        return (
            ExecutionPlanWrite(
                instrument="NONE",
                invalidation_text="Insufficient verified support/resistance for actionable long execution.",
                risk_unit_category="0",
                execution_quality_score=0,
                execution_quality_level="UNACCEPTABLE",
                option_suitability_status="NO OPTION TRADE",
            ),
            None,
            0.0,
        )

    stop=supports[0]
    t1=resistances[0]
    t2=resistances[1]
    risk=entry-stop
    if risk <= 0:
        raise ValueError("invalid long execution risk")
    reward1=t1-entry
    reward2=t2-entry
    rr1=reward1/risk if reward1 > 0 else 0.0
    rr2=reward2/risk if reward2 > 0 else 0.0

    if rr1 >= 2.0:
        q,level=90.0,"EXCELLENT"
    elif rr1 >= 1.5:
        q,level=80.0,"GOOD"
    elif rr1 >= 1.2:
        q,level=65.0,"ADEQUATE"
    elif rr1 > 0:
        q,level=45.0,"WEAK"
    else:
        q,level=0.0,"UNACCEPTABLE"

    return (
        ExecutionPlanWrite(
            instrument="EQUITY",
            entry_low=entry,
            entry_high=entry,
            stop_price=stop,
            invalidation_text=f"Close/acceptance below verified structural support {stop:.2f}.",
            target1=t1,
            target2=t2,
            risk_per_unit=risk,
            reward_to_t1=max(0.0,reward1),
            reward_to_t2=max(0.0,reward2),
            rr_t1=rr1,
            rr_t2=rr2,
            risk_unit_category=None,
            time_exit="Frozen forecast horizon",
            execution_quality_score=q,
            execution_quality_level=level,
            option_suitability_status="NO OPTION TRADE",
            notes="Current-market equity entry derived from authenticated structure.",
        ),
        rr1,
        q,
    )


def _bearish_holder_plan(ctx: MarketStructureContext) -> tuple[ExecutionPlanWrite, Optional[float], float]:
    """Exit/defensive plan for an existing equity holding, not a short-equity plan."""
    entry=ctx.close
    supports=[x for x in ctx.supports if x < entry]
    resistances=[x for x in ctx.resistances if x > entry]

    if not supports:
        return (
            ExecutionPlanWrite(
                instrument="EQUITY_EXIT",
                entry_low=entry,
                entry_high=entry,
                invalidation_text="Immediate defensive exit/reduction; downside objective unavailable.",
                risk_unit_category="0",
                execution_quality_score=45,
                execution_quality_level="WEAK",
                option_suitability_status="NO OPTION TRADE",
            ),
            None,
            45.0,
        )

    t1=supports[0]
    t2=supports[1] if len(supports)>1 else None
    invalidation=resistances[0] if resistances else None
    rr1=None
    rr2=None
    risk=None
    if invalidation is not None and invalidation > entry:
        risk=invalidation-entry
        reward1=entry-t1
        rr1=reward1/risk if reward1>0 else 0.0
        if t2 is not None:
            rr2=(entry-t2)/risk if entry>t2 else 0.0

    if rr1 is None:
        q,level=60.0,"ADEQUATE"
    elif rr1 >= 2.0:
        q,level=90.0,"EXCELLENT"
    elif rr1 >= 1.5:
        q,level=80.0,"GOOD"
    elif rr1 >= 1.2:
        q,level=65.0,"ADEQUATE"
    else:
        q,level=45.0,"WEAK"

    return (
        ExecutionPlanWrite(
            instrument="EQUITY_EXIT",
            entry_low=entry,
            entry_high=entry,
            stop_price=invalidation,
            invalidation_text=(
                f"Bearish thesis invalidates above verified resistance {invalidation:.2f}."
                if invalidation is not None
                else "No verified upside invalidation level."
            ),
            target1=t1,
            target2=t2,
            risk_per_unit=risk,
            reward_to_t1=(entry-t1),
            reward_to_t2=((entry-t2) if t2 is not None else None),
            rr_t1=rr1,
            rr_t2=rr2,
            risk_unit_category=None,
            time_exit="Frozen forecast horizon",
            execution_quality_score=q,
            execution_quality_level=level,
            option_suitability_status="NO OPTION TRADE",
            notes="Defensive existing-holding exit/reduction plan; not a short-equity recommendation.",
        ),
        rr1,
        q,
    )


def reconcile_final_execution(
    shadow: ShadowComputation,
    *,
    holding_status_known: bool,
    holding_exists: bool = False,
    options_data: Optional[OptionsSuitabilityInput] = None,
) -> FinalExecutionDecision:
    ctx=shadow.recommendation
    # Structure context is needed only for directional execution candidates.
    structure=getattr(shadow, "zone_context", None)
    # ShadowComputation intentionally does not currently persist zone_context.
    # Recovering execution from only zone bounds would fabricate structure, so
    # callers must attach a MarketStructureContext through this private attr or
    # use reconcile_with_structure below.
    raise RuntimeError("use reconcile_with_structure with verified market structure")


def reconcile_with_structure(
    shadow: ShadowComputation,
    structure: MarketStructureContext,
    *,
    holding_status_known: bool,
    holding_exists: bool = False,
    options_data: Optional[OptionsSuitabilityInput] = None,
) -> FinalExecutionDecision:
    forecast=shadow.definitive_forecast

    if forecast=="BULLISH":
        plan,rr,exec_q=_long_equity_plan(structure)
    elif forecast=="BEARISH" and holding_status_known and holding_exists:
        plan,rr,exec_q=_bearish_holder_plan(structure)
    else:
        plan=ExecutionPlanWrite(
            instrument="NONE",
            risk_unit_category="0",
            time_exit="Frozen forecast horizon",
            execution_quality_score=0,
            execution_quality_level="NOT_EXECUTABLE",
            option_suitability_status="NO OPTION TRADE",
            notes="No directional candidate execution exists for this forecast/holding state.",
        )
        rr=None
        exec_q=0.0

    leading=max(shadow.bull_probability,shadow.base_probability,shadow.bear_probability)
    final_bot=bot_hunter(BotInputs(
        leading_probability=leading,
        market_trust=shadow.market_trust,
        structure_pattern_quality=shadow.structure_pattern_quality,
        pv_pvpo_confirmation=shadow.pv_pvpo_confirmation,
        catalyst_asymmetry=shadow.catalyst_asymmetry,
        execution_quality=exec_q,
    ))

    decision=decide_action(
        forecast=forecast,
        bot_grade=final_bot.grade,
        market_trust=shadow.market_trust,
        execution_quality_score=exec_q,
        holding_status_known=holding_status_known,
        holding_exists=holding_exists,
        override=shadow.event_override,
        rr=rr,
        options_data=options_data,
    )

    plan=ExecutionPlanWrite(
        **{
            **plan.__dict__,
            "risk_unit_category": decision.risk_unit_category,
            "option_suitability_status": decision.options_suitability_status,
        }
    )

    # A non-actionable decision must not masquerade as a live order, but the
    # candidate assessment must remain auditable and visible. Keep candidate
    # levels/invalidation/R:R and change only the final instrument/action state.
    if decision.definitive_recommendation in {"HOLD","AVOID","NO TRADE"}:
        candidate_instrument=plan.instrument
        directional=forecast in {"BULLISH","BEARISH"}
        structure_available=(
            candidate_instrument!="NONE"
            and (
                candidate_instrument=="EQUITY_EXIT"
                or (
                    plan.entry_low is not None
                    and plan.stop_price is not None
                    and plan.target1 is not None
                    and plan.target2 is not None
                )
            )
        )
        gates=[
            {
                "gate":"DIRECTIONAL_EDGE",
                "status":"PASS" if directional else "FAIL",
                "observed":forecast,
                "threshold":"BULLISH or BEARISH",
                "reason":None if directional else "base/range has no directional edge",
            },
            {
                "gate":"STRUCTURE",
                "status":"PASS" if structure_available else "FAIL",
                "observed":candidate_instrument,
                "threshold":"verified candidate entry/invalidation/target structure",
                "reason":None if structure_available else (
                    plan.invalidation_text
                    or "verified candidate execution structure is unavailable"
                ),
            },
            {
                "gate":"R_R",
                "status":(
                    "N/A" if not directional or rr is None
                    else ("PASS" if rr>=1.2 else "FAIL")
                ),
                "observed":rr,
                "threshold":">=1.2R",
                "reason":(
                    "R:R unavailable because no complete directional candidate exists"
                    if directional and rr is None
                    else ("R:R below 1.2" if rr is not None and rr<1.2 else None)
                ),
            },
            {
                "gate":"EXECUTION_QUALITY",
                "status":"PASS" if exec_q>=40 else "FAIL",
                "observed":exec_q,
                "threshold":">=40 minimum action gate",
                "reason":None if exec_q>=40 else "execution quality unacceptable",
            },
            {
                "gate":"EVENT_OVERRIDE",
                "status":"PASS" if shadow.event_override not in {"O2","O3"} else "FAIL",
                "observed":shadow.event_override or "CLEAR",
                "threshold":"no blocking O2/O3 override",
                "reason":(
                    f"{shadow.event_override} event override blocks this action"
                    if shadow.event_override in {"O2","O3"} else None
                ),
            },
            {
                "gate":"OPTIONS",
                "status":"PASS" if decision.options_suitability_status=="SUITABLE" else "FAIL",
                "observed":decision.options_suitability_status,
                "threshold":"SUITABLE for an options expression",
                "reason":(
                    None if decision.options_suitability_status=="SUITABLE"
                    else "options suitability/contract gate did not pass"
                ),
            },
        ]
        diagnostics={
            "candidate_instrument":candidate_instrument,
            "final_instrument":"NONE",
            "dominant_rejection_reason":decision.downgrade_reason or plan.invalidation_text or plan.notes or "non-actionable decision",
            "gate_results":gates,
        }
        plan=ExecutionPlanWrite(
            **{
                **plan.__dict__,
                "instrument":"NONE",
                "risk_unit_category":"0",
                "time_exit":plan.time_exit or "Frozen forecast horizon",
                "option_suitability_status":decision.options_suitability_status,
                "notes":json.dumps(diagnostics,sort_keys=True),
            }
        )

    return FinalExecutionDecision(
        decision=decision,
        bot=final_bot,
        execution_plan=plan,
        rr_primary=rr,
    )
