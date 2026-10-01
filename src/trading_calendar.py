"""Holiday-aware NSE trading calendar for EDGE lifecycle checkpoints.

Uses Upstox Market Holidays as a read-only exchange calendar source and excludes:
- Saturdays/Sundays
- TRADING_HOLIDAY entries where NSE is closed

SPECIAL_TIMING days remain trading days. Settlement-only holidays do not block
NSE trading checkpoints.

G5 production horizon invariant:
- the forecast path is exactly five ordered trading sessions: D, D+1, D+2, D+3, D+4;
- D is included when it is itself an NSE trading day;
- D+5 is never part of a new current EDGE Stocks forecast path.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Mapping

from src.market_providers import UpstoxReadOnlyStockProvider


def parse_nse_trading_holidays(payload: Mapping) -> set[date]:
    if payload.get("status") != "success":
        raise ValueError("market holiday payload status is not success")
    rows=payload.get("data")
    if not isinstance(rows,list):
        raise ValueError("market holiday payload data must be a list")

    holidays:set[date]=set()
    for row in rows:
        if not isinstance(row,Mapping):
            continue
        if str(row.get("holiday_type","")).upper() != "TRADING_HOLIDAY":
            continue
        closed=row.get("closed_exchanges")
        if not isinstance(closed,list) or "NSE" not in {str(x).upper() for x in closed}:
            continue
        try:
            holidays.add(date.fromisoformat(str(row["date"])))
        except Exception as exc:
            raise ValueError("invalid holiday date in provider payload") from exc
    return holidays


def is_nse_trading_date(day: date, holidays: Iterable[date]) -> bool:
    """Return whether *day* is an NSE trading session using governed holiday data."""
    return day.weekday() < 5 and day not in set(holidays)


def next_nse_trading_dates(
    start_after: date,
    holidays: Iterable[date],
    *,
    count: int = 5,
) -> tuple[date, ...]:
    """Return future NSE sessions strictly after *start_after*.

    Kept for lifecycle/outcome uses that explicitly need future sessions. New EDGE
    Stocks forecast-path construction must use ``nse_forecast_dates_d_through_d4``.
    """
    if count <= 0:
        raise ValueError("count must be positive")
    closed=set(holidays)
    out=[]
    day=start_after
    safety=0
    while len(out)<count:
        day += timedelta(days=1)
        safety += 1
        if safety > 40:
            raise RuntimeError("unable to resolve requested trading dates")
        if day.weekday() >= 5:
            continue
        if day in closed:
            continue
        out.append(day)
    return tuple(out)


def nse_forecast_dates_d_through_d4(
    d: date,
    holidays: Iterable[date],
) -> tuple[date,date,date,date,date]:
    """Resolve the canonical five-session EDGE Stocks forecast path.

    The first row is D itself, therefore D must be a valid NSE trading day. The
    remaining four rows are the next four valid NSE trading sessions. This
    function deliberately cannot emit a sixth D+5 row.
    """
    closed=set(holidays)
    if not is_nse_trading_date(d, closed):
        raise ValueError("forecast D must be an NSE trading day")
    future=next_nse_trading_dates(d, closed, count=4)
    return (d, future[0], future[1], future[2], future[3])


def fetch_nse_forecast_dates_d_through_d4(
    provider: UpstoxReadOnlyStockProvider,
    *,
    d: date,
) -> tuple[date,date,date,date,date]:
    env=provider.market_holidays()
    holidays=parse_nse_trading_holidays(env.payload)
    return nse_forecast_dates_d_through_d4(d, holidays)


def fetch_next_five_nse_trading_dates(
    provider: UpstoxReadOnlyStockProvider,
    *,
    start_after: date,
) -> tuple[date,date,date,date,date]:
    """Legacy/future-checkpoint helper.

    This remains available for lifecycle code that genuinely needs five future
    sessions. It must not be used to build a new EDGE Stocks current forecast.
    """
    env=provider.market_holidays()
    holidays=parse_nse_trading_holidays(env.payload)
    rows=next_nse_trading_dates(start_after,holidays,count=5)
    return (rows[0],rows[1],rows[2],rows[3],rows[4])


def is_nse_trading_day(
    provider: UpstoxReadOnlyStockProvider,
    day: date,
) -> bool:
    env=provider.market_holidays()
    holidays=parse_nse_trading_holidays(env.payload)
    return is_nse_trading_date(day, holidays)
