from datetime import date

import pytest

from src.trading_calendar import (
    next_nse_trading_dates,
    nse_forecast_dates_d_through_d4,
    parse_nse_trading_holidays,
)


def test_parse_nse_trading_holidays_filters_non_nse_and_non_trading_rows():
    payload={
        "status":"success",
        "data":[
            {"date":"2026-10-02","holiday_type":"TRADING_HOLIDAY","closed_exchanges":["NSE","BSE"]},
            {"date":"2026-10-03","holiday_type":"SETTLEMENT_HOLIDAY","closed_exchanges":["NSE"]},
            {"date":"2026-10-05","holiday_type":"TRADING_HOLIDAY","closed_exchanges":["BSE"]},
        ],
    }
    assert parse_nse_trading_holidays(payload)=={date(2026,10,2)}


def test_next_nse_trading_dates_remains_future_only_for_lifecycle_use():
    rows=next_nse_trading_dates(
        date(2026,9,30),
        {date(2026,10,2)},
        count=5,
    )
    assert rows==(date(2026,10,1),date(2026,10,5),date(2026,10,6),date(2026,10,7),date(2026,10,8))


def test_g5_forecast_path_is_exactly_d_through_d4_and_skips_holiday_weekend():
    rows=nse_forecast_dates_d_through_d4(
        date(2026,9,30),
        {date(2026,10,2)},
    )
    assert rows==(date(2026,9,30),date(2026,10,1),date(2026,10,5),date(2026,10,6),date(2026,10,7))
    assert len(rows)==5
    assert date(2026,10,8) not in rows  # D+5 must never enter a new current forecast path.


def test_g5_forecast_path_fails_closed_when_d_is_not_trading_day():
    with pytest.raises(ValueError,match="forecast D must be an NSE trading day"):
        nse_forecast_dates_d_through_d4(date(2026,10,2),{date(2026,10,2)})


def test_parse_requires_success_payload():
    with pytest.raises(ValueError):
        parse_nse_trading_holidays({"status":"error","data":[]})
