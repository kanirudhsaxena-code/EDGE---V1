from datetime import datetime, timezone

from src.production_orchestrator import HoldingState, _event_level, _recommendation_text


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
