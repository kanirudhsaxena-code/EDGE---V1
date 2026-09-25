import copy

import pytest

from src.edge_truth_baseline import BaselineValidationError, validate_edge_truth_baseline


def _observation(horizon="D"):
    return {
        "ticker": "TEST",
        "instrument_id": "NSE:TEST",
        "issuance_asof": "2026-09-01T15:30:00+05:30",
        "trading_calendar_version": "NSE:test",
        "horizon": horizon,
        "target_session": "2026-09-01",
        "spot": 100.0,
        "atr14": 2.0,
        "atr14_source_window": "14 trading sessions",
        "realised_volatility": 0.2,
        "realised_volatility_window": "20 trading sessions",
        "liquidity_ratio": 1.1,
        "gap_risk": "LOW",
        "event_risk": "UNVERIFIED",
        "stock_regime": "RANGE",
        "sector_regime": "RANGE",
        "source_refs": [{"source": "fixture", "asof": "2026-09-01T15:30:00+05:30", "hash": "abc"}],
        "target_ohlc": {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0},
        "outcome_source_ref": {"source": "fixture", "hash": "def"},
    }


def _baseline():
    observations = [_observation(horizon) for horizon in ("D", "D+1", "D+2", "D+3", "D+4")]
    return {
        "baseline_contract_version": "2C-02-v1",
        "baseline_id": "fixture",
        "baseline_hash": "fixture-hash",
        "generated_at": "2026-09-10T00:00:00Z",
        "source_systems": [{"name": "fixture", "version": "1"}],
        "observation_count": 5,
        "distinct_ticker_count": 1,
        "distinct_session_count": 1,
        "coverage_by_ticker_horizon": {f"TEST|{h}": 1 for h in ("D", "D+1", "D+2", "D+3", "D+4")},
        "missing_unverified_counts": {"event_risk": 5},
        "observations": observations,
    }


def test_valid_complete_baseline_contract_passes():
    validate_edge_truth_baseline(_baseline())


@pytest.mark.parametrize("field", ["atr14", "realised_volatility", "source_refs", "target_ohlc"])
def test_missing_required_observation_field_fails_closed(field):
    payload = _baseline()
    del payload["observations"][0][field]
    with pytest.raises(BaselineValidationError):
        validate_edge_truth_baseline(payload)


def test_empty_baseline_is_not_calibration_evidence():
    payload = _baseline()
    payload["observations"] = []
    payload["observation_count"] = 0
    with pytest.raises(BaselineValidationError, match="non-empty"):
        validate_edge_truth_baseline(payload)


def test_production_or_calibration_semantics_are_rejected():
    payload = _baseline()
    payload["observations"][0]["zone_width_multiplier"] = 1.25
    with pytest.raises(BaselineValidationError, match="prohibited"):
        validate_edge_truth_baseline(payload)


def test_declared_coverage_must_equal_frozen_observations():
    payload = _baseline()
    payload["coverage_by_ticker_horizon"]["TEST|D+4"] = 2
    with pytest.raises(BaselineValidationError, match="coverage"):
        validate_edge_truth_baseline(payload)


def test_no_imputation_of_missing_provenance():
    payload = copy.deepcopy(_baseline())
    payload["observations"][2]["source_refs"] = []
    with pytest.raises(BaselineValidationError, match="source_refs"):
        validate_edge_truth_baseline(payload)
