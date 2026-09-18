"""Frozen EDGE V1 decision/execution policy.

Implements only rules explicitly present in the canonical EDGE V1 Master
Specification for:
- Decision Ladder classification
- definitive equity action mapping
- execution-quality interpretation from R:R
- relative risk-unit category
- fail-closed options suitability gate

This module does not place trades and does not invent contract details.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OptionsSuitabilityInput:
    fresh_chain: bool
    directional_actionable: bool
    expiry_covers_horizon: bool
    strike_responsive: bool
    liquidity_adequate: bool
    premium_risk_defined: bool
    event_theta_acceptable: bool
    contract_symbol: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None
    observed_premium: Optional[float] = None


@dataclass(frozen=True)
class DecisionExecutionResult:
    decision_ladder: str
    risk_unit_category: str
    definitive_recommendation: str
    options_direction_candidate: Optional[str]
    options_suitability_status: str
    execution_quality_level: str
    actionable: bool
    downgrade_reason: Optional[str]


def execution_quality_from_rr(rr: Optional[float]) -> tuple[str, int]:
    if rr is None:
        return ("UNVERIFIED", 0)
    if rr < 0:
        raise ValueError("R:R cannot be negative")
    if rr >= 2.0:
        return ("STRONG", 90)
    if rr >= 1.5:
        return ("ACCEPTABLE", 80)
    if rr >= 1.2:
        return ("MARGINAL", 65)
    return ("POOR", 45)


def _ladder(bot_grade: str, mt: float, execution_quality_score: float) -> str:
    grade = bot_grade.strip().upper()
    if grade not in {"C","B","A","A+","A++"}:
        raise ValueError("invalid BOT grade")
    if not 0 <= mt <= 100:
        raise ValueError("Market Trust must be 0-100")
    if not 0 <= execution_quality_score <= 100:
        raise ValueError("execution_quality_score must be 0-100")

    if grade == "C":
        return "WATCHLIST" if mt >= 40 else "OBSERVE"

    if grade == "B":
        if mt < 40:
            return "WATCHLIST"
        if mt < 55:
            return "WATCHLIST"
        if execution_quality_score >= 60:
            return "PILOT"
        return "INVESTIGATION"

    if grade == "A":
        if mt >= 70 and execution_quality_score >= 60:
            return "PARTIAL"
        if mt >= 55 and execution_quality_score >= 60:
            return "PILOT"
        return "INVESTIGATION"

    if grade == "A+":
        if mt >= 70 and execution_quality_score >= 75:
            return "FULL"
        if mt >= 70:
            return "PARTIAL"
        if mt >= 55 and execution_quality_score >= 60:
            return "PILOT"
        return "INVESTIGATION"

    # A++
    if mt >= 85 and execution_quality_score >= 75:
        return "FULL"
    if mt >= 70 and execution_quality_score >= 60:
        return "PARTIAL"
    if mt >= 55 and execution_quality_score >= 60:
        return "PILOT"
    return "INVESTIGATION"


def risk_unit_for_ladder(ladder: str) -> str:
    mapping = {
        "OBSERVE":"0",
        "WATCHLIST":"0",
        "INVESTIGATION":"0",
        "PILOT":"0.25R",
        "PARTIAL":"0.50R",
        "FULL":"1.00R",
    }
    try:
        return mapping[ladder]
    except KeyError as exc:
        raise ValueError("invalid Decision Ladder") from exc


def options_suitability(
    direction: Optional[str],
    data: Optional[OptionsSuitabilityInput],
) -> tuple[str, Optional[str]]:
    if direction not in {None,"BUY CALL","BUY PUT"}:
        raise ValueError("invalid options direction candidate")
    if direction is None:
        return ("NO OPTION TRADE", None)
    if data is None:
        return ("NO OPTION TRADE", "options evidence/contract suitability unavailable")

    required = (
        data.fresh_chain,
        data.directional_actionable,
        data.expiry_covers_horizon,
        data.strike_responsive,
        data.liquidity_adequate,
        data.premium_risk_defined,
        data.event_theta_acceptable,
    )
    if not all(required):
        return ("NO OPTION TRADE", "options suitability gate failed")

    if not data.contract_symbol or data.strike is None or not data.expiry or data.observed_premium is None:
        return ("NO OPTION TRADE", "exact option contract is not fully verified")

    return ("SUITABLE", None)


def decide_action(
    *,
    forecast: str,
    bot_grade: str,
    market_trust: float,
    execution_quality_score: float,
    holding_status_known: bool,
    holding_exists: bool = False,
    override: Optional[str] = None,
    hard_gate: bool = False,
    rr: Optional[float] = None,
    options_data: Optional[OptionsSuitabilityInput] = None,
) -> DecisionExecutionResult:
    f=forecast.strip().upper()
    if f not in {"BULLISH","BASE_RANGE","BEARISH"}:
        raise ValueError("invalid definitive forecast")

    ov=(override or "").strip().upper() or None
    if ov not in {None,"O1","O2","O3"}:
        raise ValueError("invalid override")

    rr_level,_=execution_quality_from_rr(rr)
    ladder=_ladder(bot_grade,market_trust,execution_quality_score)
    risk=risk_unit_for_ladder(ladder)

    # Hard gates dominate the action branch.
    if hard_gate:
        return DecisionExecutionResult(
            ladder,risk,"NO TRADE",None,"NO OPTION TRADE",
            rr_level,False,"hard evidence gate"
        )

    # Critical/severe event overrides are fail-closed.
    if ov=="O3":
        action="REDUCE" if holding_status_known and holding_exists and f=="BEARISH" else (
            "HOLD" if holding_status_known and holding_exists else "AVOID"
        )
        return DecisionExecutionResult(
            ladder,risk,action,None,"NO OPTION TRADE",
            rr_level,False,"O3 critical override"
        )
    if ov=="O2" and f=="BULLISH":
        action="HOLD" if holding_status_known and holding_exists else "AVOID"
        return DecisionExecutionResult(
            ladder,risk,action,None,"NO OPTION TRADE",
            rr_level,False,"O2 severe override"
        )

    # Base/range is not a directional new-entry call under the frozen map.
    if f=="BASE_RANGE":
        action="HOLD" if holding_status_known and holding_exists else "NO TRADE"
        return DecisionExecutionResult(
            ladder,risk,action,None,"NO OPTION TRADE",
            rr_level,False,"base/range has no directional edge"
        )

    grade=bot_grade.strip().upper()

    # Poor execution (<1.2R where R:R is known) normally downgrades to no trade.
    if rr is not None and rr < 1.2:
        action="HOLD" if holding_status_known and holding_exists else "NO TRADE"
        return DecisionExecutionResult(
            ladder,risk,action,None,"NO OPTION TRADE",
            rr_level,False,"R:R below 1.2"
        )

    if execution_quality_score < 40:
        action="HOLD" if holding_status_known and holding_exists else "NO TRADE"
        return DecisionExecutionResult(
            ladder,risk,action,None,"NO OPTION TRADE",
            rr_level,False,"execution quality unacceptable"
        )

    if f=="BULLISH":
        if grade in {"A++","A+"} and market_trust >= 70 and execution_quality_score >= 75:
            action="STRONG BUY" if grade=="A++" or market_trust>=85 else "BUY"
            option_candidate="BUY CALL"
        elif grade=="A" and market_trust >= 55 and execution_quality_score >= 60:
            action="BUY"
            option_candidate="BUY CALL"
        elif grade=="B":
            action="HOLD" if holding_status_known and holding_exists else "ACCUMULATE"
            option_candidate=None
        else:
            action="HOLD" if holding_status_known and holding_exists else "NO TRADE"
            option_candidate=None

    else:  # BEARISH
        if grade in {"A","A+","A++"} and market_trust >= 55 and execution_quality_score >= 60:
            if holding_status_known and holding_exists:
                action="SELL" if grade in {"A+","A++"} and market_trust >= 70 else "REDUCE"
            else:
                action="AVOID"
            option_candidate="BUY PUT"
        elif grade=="B":
            action="REDUCE" if holding_status_known and holding_exists else "NO TRADE"
            option_candidate=None
        else:
            action="NO TRADE" if not (holding_status_known and holding_exists) else "HOLD"
            option_candidate=None

    opt_status,opt_reason=options_suitability(option_candidate,options_data)
    if option_candidate and opt_status!="SUITABLE":
        # Frozen rules allow the equity action to stand while options branch is
        # gated. We do not fabricate BUY CALL/PUT.
        option_candidate=None

    actionable=action in {"STRONG BUY","BUY","ACCUMULATE","SELL","REDUCE"}
    return DecisionExecutionResult(
        decision_ladder=ladder,
        risk_unit_category=risk,
        definitive_recommendation=action,
        options_direction_candidate=option_candidate,
        options_suitability_status=opt_status,
        execution_quality_level=rr_level,
        actionable=actionable,
        downgrade_reason=opt_reason,
    )
