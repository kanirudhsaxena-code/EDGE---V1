"""EDGE Efficacy Engine V2 helpers.

The production database is Neon/PostgreSQL.  This module holds deterministic
calculation and lifecycle helpers so business rules can be unit-tested without
market or database access.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional

D5_CHECKPOINTS = ("D+1", "D+2", "D+3", "D+4", "D+5")
VALID_CLOSE_REASONS = {"TARGET", "STOP", "D+5", "MANUAL_EXIT", "NOT_SCORABLE"}
VALID_FORECASTS = {"BULLISH", "BEARISH", "BASE_RANGE", "BASE/RANGE", "BASE", "RANGE"}


def validate_horizon_days(days: int) -> int:
    if not isinstance(days, int) or not 1 <= days <= 5:
        raise ValueError("EDGE recommendation horizon must be 1-5 trading days")
    return days


def percent_return(entry: float, exit_price: float, direction: str = "LONG") -> float:
    if entry <= 0:
        raise ValueError("entry must be > 0")
    raw = (exit_price - entry) / entry * 100.0
    if direction.upper() in {"BEARISH", "SHORT_AVOID"}:
        raw = -raw
    elif direction.upper() not in {"LONG", "BULLISH"}:
        raise ValueError("direction must be LONG/BULLISH or BEARISH/SHORT_AVOID")
    return raw


def mfe_mae(entry: float, period_high: float, period_low: float, direction: str = "LONG") -> tuple[float, float]:
    if min(entry, period_high, period_low) <= 0:
        raise ValueError("prices must be > 0")
    if period_low > period_high:
        raise ValueError("period_low cannot exceed period_high")
    d = direction.upper()
    if d in {"LONG", "BULLISH"}:
        mfe = (period_high - entry) / entry * 100.0
        mae = (period_low - entry) / entry * 100.0
    elif d in {"BEARISH", "SHORT_AVOID"}:
        mfe = (entry - period_low) / entry * 100.0
        mae = (entry - period_high) / entry * 100.0
    else:
        raise ValueError("invalid direction")
    return mfe, mae


def model_pnl_units(model_return_pct: float, standard_capital: float = 100.0) -> float:
    if standard_capital <= 0:
        raise ValueError("standard_capital must be > 0")
    return standard_capital * model_return_pct / 100.0


@dataclass(frozen=True)
class ClosedResult:
    verdict: str
    model_return_pct: float


@dataclass(frozen=True)
class CheckpointDiagnostic:
    checkpoint_type: str
    forecast_result: str
    zone_result: str


def summarize_hit_rate(results: Iterable[ClosedResult]) -> Optional[float]:
    scored = [r for r in results if r.verdict in {"WIN", "LOSS", "FLAT"}]
    if not scored:
        return None
    wins = sum(r.verdict == "WIN" for r in scored)
    return wins / len(scored) * 100.0


def provisional_forecast_result(
    forecast: str,
    reference_price: Optional[float],
    actual_price: Optional[float],
    zone_low: Optional[float] = None,
    zone_high: Optional[float] = None,
) -> str:
    """Score an OPEN recommendation checkpoint without mutating final efficacy.

    Returns HIT/MISS/NEUTRAL_AMBIGUOUS/NOT_SCORABLE. BASE/RANGE forecasts are
    assessed by zone containment; directional forecasts are assessed against
    the immutable reference price. This is diagnostic only and must never be
    written into final direction_hit/outcome_verdict fields while OPEN.
    """
    if actual_price is None:
        return "NOT_SCORABLE"
    f = forecast.upper()
    if f not in VALID_FORECASTS:
        return "NOT_SCORABLE"
    if f in {"BASE_RANGE", "BASE/RANGE", "BASE", "RANGE"}:
        if zone_low is None or zone_high is None or zone_low > zone_high:
            return "NOT_SCORABLE"
        return "HIT" if zone_low <= actual_price <= zone_high else "MISS"
    if reference_price is None or reference_price <= 0:
        return "NOT_SCORABLE"
    if f == "BULLISH":
        if actual_price > reference_price:
            return "HIT"
        if actual_price < reference_price:
            return "MISS"
        return "NEUTRAL_AMBIGUOUS"
    if f == "BEARISH":
        if actual_price < reference_price:
            return "HIT"
        if actual_price > reference_price:
            return "MISS"
        return "NEUTRAL_AMBIGUOUS"
    return "NOT_SCORABLE"


def provisional_zone_result(
    actual_price: Optional[float], zone_low: Optional[float], zone_high: Optional[float]
) -> str:
    if actual_price is None or zone_low is None or zone_high is None or zone_low > zone_high:
        return "NOT_SCORABLE"
    return "FULL_HIT" if zone_low <= actual_price <= zone_high else "MISS"


def summarize_checkpoint_accuracy(results: Iterable[CheckpointDiagnostic]) -> dict[str, Optional[float] | int]:
    rows = list(results)
    forecast_scorable = [r for r in rows if r.forecast_result in {"HIT", "MISS"}]
    zone_scorable = [r for r in rows if r.zone_result in {"FULL_HIT", "MISS"}]
    forecast_hits = sum(r.forecast_result == "HIT" for r in forecast_scorable)
    zone_hits = sum(r.zone_result == "FULL_HIT" for r in zone_scorable)
    return {
        "captured_checkpoints": len(rows),
        "forecast_scorable": len(forecast_scorable),
        "forecast_hits": forecast_hits,
        "forecast_misses": len(forecast_scorable) - forecast_hits,
        "forecast_accuracy_pct": None if not forecast_scorable else forecast_hits / len(forecast_scorable) * 100.0,
        "zone_scorable": len(zone_scorable),
        "zone_hits": zone_hits,
        "zone_misses": len(zone_scorable) - zone_hits,
        "zone_accuracy_pct": None if not zone_scorable else zone_hits / len(zone_scorable) * 100.0,
    }
