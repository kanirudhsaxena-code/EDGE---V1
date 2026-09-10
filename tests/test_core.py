from src.ledger import recommendation_id, D5_CHECKPOINT_TYPES
from src.scoring import validate_probabilities
from src.efficacy import (
    ClosedResult,
    mfe_mae,
    model_pnl_units,
    percent_return,
    summarize_hit_rate,
    validate_horizon_days,
)


def test_recommendation_id():
    assert recommendation_id("ltf", "20260909", 1) == "EDGE-LTF-20260909-01"


def test_probabilities():
    validate_probabilities(60, 25, 15)


def test_d5_checkpoints():
    assert D5_CHECKPOINT_TYPES == ("D+1", "D+2", "D+3", "D+4", "D+5")


def test_horizon_guard():
    assert validate_horizon_days(5) == 5
    try:
        validate_horizon_days(6)
    except ValueError:
        pass
    else:
        raise AssertionError("6-day horizon must be rejected")


def test_long_return_and_excursions():
    assert round(percent_return(100, 108, "LONG"), 2) == 8.00
    mfe, mae = mfe_mae(100, 110, 97, "LONG")
    assert round(mfe, 2) == 10.00
    assert round(mae, 2) == -3.00


def test_bearish_return_and_excursions():
    assert round(percent_return(200, 190, "BEARISH"), 2) == 5.00
    mfe, mae = mfe_mae(200, 207, 188, "BEARISH")
    assert round(mfe, 2) == 6.00
    assert round(mae, 2) == -3.50


def test_model_pnl_and_hit_rate():
    assert model_pnl_units(8, 100) == 8
    rate = summarize_hit_rate([ClosedResult("WIN", 8), ClosedResult("LOSS", -3)])
    assert rate == 50.0
