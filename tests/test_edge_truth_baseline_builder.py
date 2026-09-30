import copy

import pytest

from src.edge_truth_baseline import validate_edge_truth_baseline
from src.edge_truth_baseline_builder import build_edge_truth_baseline

HORIZONS = ("D", "D+1", "D+2", "D+3", "D+4")
SESSIONS = ("2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07")
ISSUANCE = "2026-09-01T15:30:00+05:30"


def _rows():
    rows = []
    for horizon, session in zip(HORIZONS, SESSIONS):
        rows.append({
            "ticker": "TEST", "instrument_id": "NSE:TEST", "issuance_asof": ISSUANCE,
            "trading_calendar_version": "NSE:test", "horizon": horizon,
            "target_session": session, "spot": 100.0, "atr14": 2.0,
            "atr14_source_window": "14 trading sessions", "realised_volatility": 0.2,
            "realised_volatility_window": "20 trading sessions", "liquidity_ratio": 1.1,
            "gap_risk": "LOW", "event_risk": "UNVERIFIED", "stock_regime": "RANGE",
            "sector_regime": "RANGE",
            "source_refs": [{"source": "fixture", "asof": ISSUANCE, "hash": "abc"}],
            "target_ohlc": {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0},
            "outcome_source_ref": {"source": "fixture", "hash": "def"},
        })
    return rows


def _sequences():
    return {f"TEST|{ISSUANCE}": {
        "trading_calendar_version": "NSE:test",
        "calendar_source_ref": {"source": "fixture-calendar", "hash": "calendar-sha256"},
        "sessions": list(SESSIONS),
    }}


def _build(rows=None):
    return build_edge_truth_baseline(
        baseline_id="bounded-fixture", observations=rows or _rows(),
        session_sequences=_sequences(), source_systems=[{"name": "fixture", "version": "1"}],
        generated_at="2026-09-10T00:00:00Z",
    )


def test_builder_freezes_valid_populated_artifact():
    artifact = _build()
    validate_edge_truth_baseline(artifact)
    assert artifact["observation_count"] == 5
    assert artifact["coverage_by_ticker_horizon"] == {f"TEST|{h}": 1 for h in HORIZONS}
    assert artifact["missing_unverified_counts"] == {"event_risk": 5}
    assert artifact["baseline_hash"].startswith("sha256:")


def test_builder_is_deterministic_for_same_evidence_and_freeze_time():
    rows = list(reversed(_rows()))
    first = _build(rows)
    second = _build(copy.deepcopy(rows))
    assert first == second
    assert [row["horizon"] for row in first["observations"]] == list(HORIZONS)


def test_builder_does_not_impute_missing_evidence():
    rows = _rows(); rows[0]["atr14"] = None
    artifact = _build(rows)
    assert artifact["observations"][0]["atr14"] is None
    assert artifact["missing_unverified_counts"]["atr14"] == 1


def test_builder_fails_closed_on_incomplete_horizon_group():
    with pytest.raises(Exception, match="exactly D:D\\+4"):
        _build(_rows()[:-1])


def test_builder_preserves_unverified_evidence_explicitly():
    artifact = _build()
    assert all(row["event_risk"] == "UNVERIFIED" for row in artifact["observations"])
    assert artifact["missing_unverified_counts"]["event_risk"] == 5


def test_builder_deep_freezes_nested_input_evidence_after_hashing():
    rows = _rows()
    sequences = _sequences()
    source_systems = [{"name": "fixture", "version": "1", "provenance": {"hash": "source-hash"}}]
    artifact = build_edge_truth_baseline(
        baseline_id="immutable-fixture", observations=rows,
        session_sequences=sequences, source_systems=source_systems,
        generated_at="2026-09-10T00:00:00Z",
    )
    frozen_hash = artifact["baseline_hash"]

    rows[0]["source_refs"][0]["hash"] = "mutated"
    rows[0]["target_ohlc"]["close"] = 999.0
    sequences[f"TEST|{ISSUANCE}"]["calendar_source_ref"]["hash"] = "mutated-calendar"
    sequences[f"TEST|{ISSUANCE}"]["sessions"][0] = "2099-01-01"
    source_systems[0]["provenance"]["hash"] = "mutated-source"

    assert artifact["observations"][0]["source_refs"][0]["hash"] == "abc"
    assert artifact["observations"][0]["target_ohlc"]["close"] == 101.0
    assert artifact["session_sequences"][f"TEST|{ISSUANCE}"]["calendar_source_ref"]["hash"] == "calendar-sha256"
    assert artifact["session_sequences"][f"TEST|{ISSUANCE}"]["sessions"][0] == SESSIONS[0]
    assert artifact["source_systems"][0]["provenance"]["hash"] == "source-hash"
    assert artifact["baseline_hash"] == frozen_hash
    validate_edge_truth_baseline(artifact)
