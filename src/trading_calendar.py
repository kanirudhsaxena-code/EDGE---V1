"""Holiday-aware NSE trading calendar for EDGE lifecycle checkpoints.

Uses Upstox Market Holidays as a read-only exchange calendar source and excludes:
- Saturdays/Sundays
- TRADING_HOLIDAY entries where NSE is closed

SPECIAL_TIMING days remain trading days. Settlement-only holidays do not block
NSE trading checkpoints.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Mapping, Sequence

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


def next_nse_trading_dates(
    start_after: date,
    holidays: Iterable[date],
    *,
    count: int = 5,
) -> tuple[date, ...]:
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


def fetch_next_five_nse_trading_dates(
    provider: UpstoxReadOnlyStockProvider,
    *,
    start_after: date,
) -> tuple[date,date,date,date,date]:
    env=provider.market_holidays()
    holidays=parse_nse_trading_holidays(env.payload)
    rows=next_nse_trading_dates(start_after,holidays,count=5)
    return (rows[0],rows[1],rows[2],rows[3],rows[4])
