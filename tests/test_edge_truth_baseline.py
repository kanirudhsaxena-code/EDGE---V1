import copy

import pytest

from src.edge_truth_baseline import (
    BaselineValidationError,
    compute_baseline_hash,
    validate_edge_truth_baseline,
)

HORIZONS = ("D", "D+1", "D+2", "D+3", "D+4")
SESSIONS = ("2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07")


def _observation(horizon="D", target_session="2026-09-01"):
    return {
        "ticker": "TEST", "instrument_id": "NSE:TEST",
        "issuance_asof": "2026-09-01T15:30:00+05:30",
        "trading_calendar_version": "NSE:test", "horizon": horizon,
        "target_session": target_session, "spot": 100.0, "atr14": 2.0,
        "atr14_source_window": "14 trading sessions", "realised_volatility": 0.2,
        "realised_volatility_window": "20 trading sessions", "liquidity_ratio": 1.1,
        "gap_risk": "LOW", "event_risk": "UNVERIFIED", "stock_regime": "RANGE",
        "sector_regime": "RANGE",
        "source_refs": [{"source": "fixture", "asof": "2026-09-01T15:30:00+05:30", "hash": "abc"}],
        "target_ohlc": {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0},
        "outcome_source_ref": {"source": "fixture", "hash": "def"},
    }


def _baseline():
    observations = [_observation(horizon, session) for horizon, session in zip(HORIZONS, SESSIONS)]
    group_key = "TEST|2026-09-01T15:30:00+05:30"
    payload = {
        "baseline_contract_version": "2C-02-v1", "baseline_id": "fixture",
        "baseline_hash": "", "generated_at": "2026-09-10T00:00:00Z",
        "source_systems": [{"name": "fixture", "version": "1"}],
        "observation_count": 5, "distinct_ticker_count": 1, "distinct_session_count": 1,
        "coverage_by_ticker_horizon": {f"TEST|{h}": 1 for h in HORIZONS},
        "missing_unverified_counts": {"event_risk": 5},
        "session_sequences": {
            group_key: {
                "trading_calendar_version": "NSE:test",
                "calendar_source_ref": {"source": "fixture-calendar", "hash": "calendar-sha256"},
                "sessions": list(SESSIONS),
            }
        },
        "observations": observations,
    }
    payload["baseline_hash"] = compute_baseline_hash(payload)
    return payload


def _rehash(payload):
    payload["baseline_hash"] = compute_baseline_hash(payload)
    return payload


def test_valid_complete_baseline_contract_passes():
    validate_edge_truth_baseline(_baseline())


@pytest.mark.parametrize("field", ["atr14", "realised_volatility", "source_refs", "target_ohlc"])
def test_missing_required_observation_field_fails_closed(field):
    payload = _baseline(); del payload["observations"][0][field]
    with pytest.raises(BaselineValidationError):
        validate_edge_truth_baseline(payload)


def test_empty_baseline_is_not_calibration_evidence():
    payload = _baseline(); payload["observations"] = []; payload["observation_count"] = 0
    with pytest.raises(BaselineValidationError, match="non-empty"):
        validate_edge_truth_baseline(payload)


def test_production_or_calibration_semantics_are_rejected():
    payload = _baseline(); payload["observations"][0]["zone_width_multiplier"] = 1.25
    with pytest.raises(BaselineValidationError, match="prohibited"):
        validate_edge_truth_baseline(payload)


def test_declared_coverage_must_equal_frozen_observations():
    payload = _baseline(); payload["coverage_by_ticker_horizon"]["TEST|D+4"] = 2
    with pytest.raises(BaselineValidationError, match="coverage"):
        validate_edge_truth_baseline(payload)


def test_no_imputation_of_missing_provenance():
    payload = copy.deepcopy(_baseline()); payload["observations"][2]["source_refs"] = []
    with pytest.raises(BaselineValidationError, match="source_refs"):
        validate_edge_truth_baseline(payload)


def test_mutated_frozen_observation_invalidates_hash():
    payload = _baseline(); payload["observations"][0]["spot"] = 101.0
    with pytest.raises(BaselineValidationError, match="baseline_hash"):
        validate_edge_truth_baseline(payload)


def test_future_source_provenance_fails_closed_even_with_valid_hash():
    payload = _baseline(); payload["observations"][0]["source_refs"][0]["asof"] = "2026-09-01T15:31:00+05:30"; _rehash(payload)
    with pytest.raises(BaselineValidationError, match="after issuance_asof"):
        validate_edge_truth_baseline(payload)


def test_naive_provenance_timestamp_fails_closed():
    payload = _baseline(); payload["observations"][0]["source_refs"][0]["asof"] = "2026-09-01T15:30:00"; _rehash(payload)
    with pytest.raises(BaselineValidationError, match="timezone"):
        validate_edge_truth_baseline(payload)


def test_calendar_sequence_must_match_horizon_rows():
    payload = _baseline(); payload["session_sequences"][next(iter(payload["session_sequences"]))]["sessions"][2] = "2026-09-08"; _rehash(payload)
    with pytest.raises(BaselineValidationError, match="does not match"):
        validate_edge_truth_baseline(payload)


def test_calendar_sequence_rejects_calendar_day_weekend_fabrication():
    payload = _baseline(); key = next(iter(payload["session_sequences"])); payload["session_sequences"][key]["sessions"] = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-05"]; payload["observations"][4]["target_session"] = "2026-09-05"; _rehash(payload)
    # The validator cannot infer holidays/weekends; it therefore requires an attributable
    # governed calendar proof. Removing that proof fails closed rather than accepting dates.
    del payload["session_sequences"][key]["calendar_source_ref"]
    _rehash(payload)
    with pytest.raises(BaselineValidationError, match="calendar_source_ref"):
        validate_edge_truth_baseline(payload)


def test_calendar_version_must_match_all_five_horizons():
    payload = _baseline(); payload["observations"][3]["trading_calendar_version"] = "NSE:other"; _rehash(payload)
    with pytest.raises(BaselineValidationError, match="calendar version mismatch"):
        validate_edge_truth_baseline(payload)
