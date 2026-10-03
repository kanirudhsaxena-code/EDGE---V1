from datetime import datetime, timezone

from src.production_orchestrator import (
    HoldingState,
    _event_level,
    _recommendation_text,
    _live_reference_price,
    _preopen_iep_reference_price,
    _is_governed_preopen_time,
)


def test_holding_state_is_explicit_not_inferred():
    assert HoldingState.UNKNOWN.value=="UNKNOWN"
    assert HoldingState.HOLDS.value=="HOLDS"
    assert HoldingState.NO_HOLDING.value=="NO_HOLDING"


def test_holder_hold_text_is_declarative():
    assert _recommendation_text("HOLD","NO OPTION TRADE")=="HOLD existing delivery; NO OPTION TRADE."


def test_no_trade_text_is_declarative():
    assert _recommendation_text("NO TRADE","NO OPTION TRADE")=="NO TRADE; NO OPTION TRADE."


def test_event_levels_are_conservative():
    assert _event_level(None)=="LOW"
    assert _event_level("O1")=="HIGH"
    assert _event_level("O2")=="HIGH"
    assert _event_level("O3")=="EXTREME"


def _quote_payload(row):
    return {
        "https://api.upstox.com/v3/market-quote/quotes?instrument_key=NSE_EQ%7CTEST": {
            "data": {"NSE_EQ:TEST": row}
        }
    }


def test_normal_reference_price_uses_ltp_and_ignores_iep():
    payloads=_quote_payload({"last_price":101.5,"indicative_equilibrium_price":104.25})
    assert _live_reference_price(payloads)==101.5


def test_preopen_reference_price_requires_and_prefers_iep():
    payloads=_quote_payload({"last_price":101.5,"indicative_equilibrium_price":104.25})
    assert _preopen_iep_reference_price(payloads)==104.25
    assert _live_reference_price(payloads,preopen_iep_required=True)==104.25


def test_preopen_reference_price_never_falls_back_to_stale_ltp():
    payloads=_quote_payload({"last_price":101.5})
    assert _preopen_iep_reference_price(payloads) is None
    assert _live_reference_price(payloads,preopen_iep_required=True) is None


def test_preopen_reference_price_accepts_nested_feed_iep_shape():
    payloads=_quote_payload({"last_price":101.5,"ltpc":{"iep":103.75}})
    assert _preopen_iep_reference_price(payloads)==103.75


def test_governed_preopen_time_is_exact_and_weekday_only():
    assert _is_governed_preopen_time(datetime(2026,10,5,3,40,0,tzinfo=timezone.utc))
    assert _is_governed_preopen_time(datetime(2026,10,5,3,44,59,tzinfo=timezone.utc))
    assert not _is_governed_preopen_time(datetime(2026,10,5,3,45,0,tzinfo=timezone.utc))
    assert not _is_governed_preopen_time(datetime(2026,10,3,3,40,0,tzinfo=timezone.utc))
