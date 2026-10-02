"""Holiday-aware NSE trading calendar for EDGE lifecycle checkpoints.

Uses Upstox Market Holidays as a read-only exchange calendar source and excludes:
- Saturdays/Sundays
- TRADING_HOLIDAY entries where NSE is closed

SPECIAL_TIMING days remain trading days. Settlement-only holidays do not block
NSE trading checkpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
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



G5_CALENDAR_VERSION = "UPSTOX_NSE_HOLIDAYS_V1"


@dataclass(frozen=True)
class G5TradingDates:
    dates: tuple[date, date, date, date, date]
    calendar_version: str
    source_ref: str
    acquired_at: datetime


def g5_nse_trading_dates(
    start_on: date,
    holidays: Iterable[date],
    *,
    count: int = 5,
) -> tuple[date, ...]:
    """Return D:D+4 with D equal to the first valid session on/after start_on."""
    if count <= 0:
        raise ValueError("count must be positive")
    closed = set(holidays)
    out = []
    day = start_on
    safety = 0
    while len(out) < count:
        safety += 1
        if safety > 40:
            raise RuntimeError("unable to resolve requested G5 trading dates")
        if day.weekday() < 5 and day not in closed:
            out.append(day)
        day += timedelta(days=1)
    return tuple(out)


def fetch_g5_five_nse_trading_dates(
    provider: UpstoxReadOnlyStockProvider,
    *,
    start_on: date,
) -> G5TradingDates:
    env = provider.market_holidays()
    holidays = parse_nse_trading_holidays(env.payload)
    rows = g5_nse_trading_dates(start_on, holidays, count=5)
    return G5TradingDates(
        dates=(rows[0], rows[1], rows[2], rows[3], rows[4]),
        calendar_version=G5_CALENDAR_VERSION,
        source_ref=env.source_ref,
        acquired_at=env.received_at,
    )

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


def is_nse_trading_day(
    provider: UpstoxReadOnlyStockProvider,
    day: date,
) -> bool:
    if day.weekday() >= 5:
        return False
    env=provider.market_holidays()
    holidays=parse_nse_trading_holidays(env.payload)
    return day not in holidays
