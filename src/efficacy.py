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


def summarize_hit_rate(results: Iterable[ClosedResult]) -> Optional[float]:
    scored = [r for r in results if r.verdict in {"WIN", "LOSS", "FLAT"}]
    if not scored:
        return None
    wins = sum(r.verdict == "WIN" for r in scored)
    return wins / len(scored) * 100.0
