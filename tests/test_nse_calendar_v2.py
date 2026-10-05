from datetime import date, datetime, timezone

import pytest

from src.trading_calendar import (
    classify_exact_nse_session,
    fetch_g5_five_nse_trading_dates,
    parse_nse_calendar_entries,
    parse_nse_market_timing,
)

def ms(iso):
    return int(datetime.fromisoformat(iso).timestamp()*1000)

def holidays(rows):
    return {"status":"success","data":rows}

def timings(rows):
    return {"status":"success","data":rows}

def test_calendar_entries_keep_closed_and_special_separate():
    e=parse_nse_calendar_entries(holidays([
        {"date":"2026-10-20","holiday_type":"TRADING_HOLIDAY","closed_exchanges":["NSE"],"open_exchanges":[]},
        {"date":"2026-11-12","holiday_type":"SPECIAL_TIMING","closed_exchanges":[],"open_exchanges":[{"exchange":"NSE"}]},
    ]))
    assert e.trading_holidays==frozenset({date(2026,10,20)})
    assert e.special_timing_dates==frozenset({date(2026,11,12)})

def test_exact_standard_session_is_preopen_eligible():
    d=date(2026,10,6)
    p=timings([{"exchange":"NSE","start_time":ms("2026-10-06T09:15:00+05:30"),"end_time":ms("2026-10-06T15:30:00+05:30")}])
    s=classify_exact_nse_session(d,holidays([]),p)
    assert s.state=="TRADING_DAY"
    assert s.preopen_eligible is True

def test_weekend_standard_live_session_can_be_preopen_eligible():
    d=date(2026,2,1)
    h=holidays([{"date":"2026-02-01","holiday_type":"SPECIAL_TIMING","closed_exchanges":[],"open_exchanges":[{"exchange":"NSE"}]}])
    p=timings([{"exchange":"NSE","start_time":ms("2026-02-01T09:15:00+05:30"),"end_time":ms("2026-02-01T15:30:00+05:30")}])
    s=classify_exact_nse_session(d,h,p)
    assert s.state=="TRADING_DAY"
    assert s.preopen_eligible is True

def test_special_timing_session_is_not_standard_preopen_eligible():
    d=date(2026,11,12)
    h=holidays([{"date":"2026-11-12","holiday_type":"SPECIAL_TIMING","closed_exchanges":[],"open_exchanges":[{"exchange":"NSE"}]}])
    p=timings([{"exchange":"NSE","start_time":ms("2026-11-12T18:00:00+05:30"),"end_time":ms("2026-11-12T19:00:00+05:30")}])
    s=classify_exact_nse_session(d,h,p)
    assert s.state=="SPECIAL_TIMING"
    assert s.preopen_eligible is False

def test_provider_conflict_fails_closed():
    d=date(2026,10,20)
    h=holidays([{"date":"2026-10-20","holiday_type":"TRADING_HOLIDAY","closed_exchanges":["NSE"],"open_exchanges":[]}])
    p=timings([{"exchange":"NSE","start_time":ms("2026-10-20T09:15:00+05:30"),"end_time":ms("2026-10-20T15:30:00+05:30")}])
    with pytest.raises(ValueError,match="both closed and timed open"):
        classify_exact_nse_session(d,h,p)

class Env:
    def __init__(self,payload,received_at=None,source_ref="ref"):
        self.payload=payload
        self.received_at=received_at or datetime(2026,12,30,tzinfo=timezone.utc)
        self.source_ref=source_ref

class CrossYearProvider:
    def market_holidays(self):
        return Env(holidays([]),datetime(2026,12,30,tzinfo=timezone.utc),"holiday-ref")
    def market_timings(self,day):
        # Jan 1 is closed (no NSE timing); Jan 2 and Jan 4/5 are open.
        rows=[] if day==date(2027,1,1) or day.weekday()>=5 else [{"exchange":"NSE","start_time":ms(f"{day.isoformat()}T09:15:00+05:30"),"end_time":ms(f"{day.isoformat()}T15:30:00+05:30")}]
        return Env(timings(rows),datetime(2026,12,30,tzinfo=timezone.utc),f"timing-{day}")

def test_g5_cross_year_dates_use_exact_future_year_timings():
    out=fetch_g5_five_nse_trading_dates(CrossYearProvider(),start_on=date(2026,12,30))
    assert out.dates==(
        date(2026,12,30),
        date(2026,12,31),
        date(2027,1,4),
        date(2027,1,5),
        date(2027,1,6),
    )
    assert "timing-2027-01-01" in out.source_ref