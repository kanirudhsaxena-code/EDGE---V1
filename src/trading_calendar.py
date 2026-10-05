"""Provider-verified NSE trading calendar for EDGE lifecycle checkpoints.

Authority hierarchy:
1. Exact Upstox exchange timing for dates outside the provider's current-year
   holiday snapshot or for same-day session proof.
2. Upstox current-year holiday snapshot for ordinary current-year date math.
3. Weekends are always closed.

SPECIAL_TIMING remains a trading session for D:D+4 date selection, but the
pre-open scheduler may separately reject it when the standard 09:15 opening
window does not apply.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

from src.market_providers import UpstoxReadOnlyStockProvider

IST=ZoneInfo("Asia/Kolkata")
STANDARD_NSE_OPEN=time(9,15)


@dataclass(frozen=True)
class NseCalendarEntries:
    trading_holidays: frozenset[date]
    special_timing_dates: frozenset[date]


@dataclass(frozen=True)
class NseExactSession:
    session_date: date
    state: str
    preopen_eligible: bool
    market_open_at: datetime | None
    market_close_at: datetime | None


def _nse_in_open_exchanges(row: Mapping) -> bool:
    opened=row.get("open_exchanges")
    if not isinstance(opened,list):
        return False
    for item in opened:
        if isinstance(item,Mapping) and str(item.get("exchange","")).upper()=="NSE":
            return True
        if isinstance(item,str) and item.upper()=="NSE":
            return True
    return False


def parse_nse_calendar_entries(payload: Mapping) -> NseCalendarEntries:
    if payload.get("status") != "success":
        raise ValueError("market holiday payload status is not success")
    rows=payload.get("data")
    if not isinstance(rows,list):
        raise ValueError("market holiday payload data must be a list")

    holidays:set[date]=set()
    special:set[date]=set()
    for row in rows:
        if not isinstance(row,Mapping):
            continue
        try:
            day=date.fromisoformat(str(row["date"]))
        except Exception as exc:
            raise ValueError("invalid holiday date in provider payload") from exc

        holiday_type=str(row.get("holiday_type","")).upper()
        closed=row.get("closed_exchanges")
        closed_set={str(x).upper() for x in closed} if isinstance(closed,list) else set()
        nse_open=_nse_in_open_exchanges(row)

        if holiday_type=="TRADING_HOLIDAY" and "NSE" in closed_set and not nse_open:
            holidays.add(day)
        elif holiday_type=="SPECIAL_TIMING" and ("NSE" not in closed_set or nse_open):
            special.add(day)

    return NseCalendarEntries(frozenset(holidays),frozenset(special))


def parse_nse_trading_holidays(payload: Mapping) -> set[date]:
    return set(parse_nse_calendar_entries(payload).trading_holidays)


def parse_nse_market_timing(payload: Mapping, day: date) -> tuple[datetime,datetime] | None:
    if payload.get("status") != "success":
        raise ValueError("market timing payload status is not success")
    rows=payload.get("data")
    if not isinstance(rows,list):
        raise ValueError("market timing payload data must be a list")

    matches=[]
    for row in rows:
        if not isinstance(row,Mapping) or str(row.get("exchange","")).upper()!="NSE":
            continue
        try:
            start_ms=int(row["start_time"])
            end_ms=int(row["end_time"])
        except Exception as exc:
            raise ValueError("NSE market timing row is invalid") from exc
        start=datetime.fromtimestamp(start_ms/1000,tz=timezone.utc).astimezone(IST)
        end=datetime.fromtimestamp(end_ms/1000,tz=timezone.utc).astimezone(IST)
        if start.date()!=day or end.date()!=day or end<=start:
            raise ValueError("NSE market timing row date/window mismatch")
        matches.append((start,end))
    if len(matches)>1:
        raise ValueError("multiple NSE market timing rows are ambiguous")
    return matches[0] if matches else None


def classify_exact_nse_session(
    day: date,
    holiday_payload: Mapping,
    timing_payload: Mapping | None,
) -> NseExactSession:
    entries=parse_nse_calendar_entries(holiday_payload)
    timing=parse_nse_market_timing(timing_payload,day) if timing_payload is not None else None

    if day in entries.trading_holidays and timing is not None:
        raise ValueError("provider conflict: NSE is both closed and timed open")

    if timing is not None:
        opened,closed=timing
        standard=opened.time().replace(tzinfo=None)==STANDARD_NSE_OPEN
        state="TRADING_DAY" if standard else "SPECIAL_TIMING"
        return NseExactSession(day,state,standard,opened,closed)

    if day in entries.trading_holidays:
        return NseExactSession(day,"TRADING_HOLIDAY",False,None,None)
    if day in entries.special_timing_dates:
        return NseExactSession(day,"SPECIAL_TIMING",False,None,None)
    if day.weekday()>=5:
        return NseExactSession(day,"WEEKEND",False,None,None)
    raise ValueError("weekday NSE session lacks exact market timing proof")


G5_CALENDAR_VERSION = "UPSTOX_NSE_CALENDAR_V2_EXACT_CROSS_YEAR"


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
    """Pure current-year helper used by tests and deterministic calendar math."""
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


def _provider_trading_dates(
    provider: UpstoxReadOnlyStockProvider,
    *,
    start_on: date,
    count: int,
    strict_after: bool,
) -> tuple[tuple[date,...],str,datetime]:
    env=provider.market_holidays()
    entries=parse_nse_calendar_entries(env.payload)
    snapshot_year=env.received_at.astimezone(IST).year
    refs=[env.source_ref]
    acquired=[env.received_at]
    out=[]
    day=start_on
    if strict_after:
        day+=timedelta(days=1)
    safety=0
    while len(out)<count:
        safety+=1
        if safety>50:
            raise RuntimeError("unable to resolve requested provider-verified NSE trading dates")
        if day.year==snapshot_year:
            if day in entries.trading_holidays:
                day+=timedelta(days=1)
                continue
            needs_exact=day.weekday()>=5 or day in entries.special_timing_dates
            if not needs_exact:
                out.append(day)
            else:
                timing_env=provider.market_timings(day)
                refs.append(timing_env.source_ref)
                acquired.append(timing_env.received_at)
                if parse_nse_market_timing(timing_env.payload,day) is not None:
                    out.append(day)
        else:
            timing_env=provider.market_timings(day)
            refs.append(timing_env.source_ref)
            acquired.append(timing_env.received_at)
            if parse_nse_market_timing(timing_env.payload,day) is not None:
                out.append(day)
        day+=timedelta(days=1)

    return tuple(out),"|".join(refs),max(acquired)


def fetch_g5_five_nse_trading_dates(
    provider: UpstoxReadOnlyStockProvider,
    *,
    start_on: date,
) -> G5TradingDates:
    rows,source_ref,acquired_at=_provider_trading_dates(
        provider,start_on=start_on,count=5,strict_after=False
    )
    return G5TradingDates(
        dates=(rows[0],rows[1],rows[2],rows[3],rows[4]),
        calendar_version=G5_CALENDAR_VERSION,
        source_ref=source_ref,
        acquired_at=acquired_at,
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
    rows,_,_=_provider_trading_dates(
        provider,start_on=start_after,count=5,strict_after=True
    )
    return (rows[0],rows[1],rows[2],rows[3],rows[4])


def is_nse_trading_day(
    provider: UpstoxReadOnlyStockProvider,
    day: date,
) -> bool:
    env=provider.market_holidays()
    entries=parse_nse_calendar_entries(env.payload)
    snapshot_year=env.received_at.astimezone(IST).year
    if day.year==snapshot_year:
        if day in entries.trading_holidays:
            return False
        if day.weekday()<5 and day not in entries.special_timing_dates:
            return True
    timing=provider.market_timings(day)
    return parse_nse_market_timing(timing.payload,day) is not None