from datetime import date

from src.trading_calendar import (
    next_nse_trading_dates,
    parse_nse_trading_holidays,
)


def test_parse_only_nse_trading_holidays():
    payload={
        "status":"success",
        "data":[
            {"date":"2026-10-02","holiday_type":"TRADING_HOLIDAY","closed_exchanges":["NSE","BSE"]},
            {"date":"2026-10-05","holiday_type":"SETTLEMENT_HOLIDAY","closed_exchanges":["NSE"]},
            {"date":"2026-10-06","holiday_type":"TRADING_HOLIDAY","closed_exchanges":["MCX"]},
            {"date":"2026-10-07","holiday_type":"SPECIAL_TIMING","closed_exchanges":[]},
        ],
    }
    result=parse_nse_trading_holidays(payload)
    assert result=={date(2026,10,2)}


def test_next_five_dates_skip_weekends_and_holiday():
    result=next_nse_trading_dates(
        date(2026,10,1),
        {date(2026,10,2)},
        count=5,
    )
    assert result==(
        date(2026,10,5),
        date(2026,10,6),
        date(2026,10,7),
        date(2026,10,8),
        date(2026,10,9),
    )


def test_special_timing_is_not_removed_by_parser():
    payload={
        "status":"success",
        "data":[
            {"date":"2026-11-12","holiday_type":"SPECIAL_TIMING","closed_exchanges":[]}
        ],
    }
    assert parse_nse_trading_holidays(payload)==set()


def test_invalid_payload_fails_closed():
    try:
        parse_nse_trading_holidays({"status":"success","data":{}})
    except ValueError as exc:
        assert "list" in str(exc)
    else:
        raise AssertionError("invalid provider payload must fail")
