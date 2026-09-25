"""Fail-closed validator for the 2C-02 EDGE truth baseline.

Research/read-only tooling only. This module does not calibrate forecasts, infer missing
values, or alter production recommendation semantics.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Sequence

HORIZONS = ("D", "D+1", "D+2", "D+3", "D+4")
TOP_LEVEL_REQUIRED = (
    "baseline_contract_version", "baseline_id", "baseline_hash", "generated_at",
    "source_systems", "observation_count", "distinct_ticker_count",
    "distinct_session_count", "coverage_by_ticker_horizon",
    "missing_unverified_counts", "session_sequences", "observations",
)
OBSERVATION_REQUIRED = (
    "ticker", "instrument_id", "issuance_asof", "trading_calendar_version",
    "horizon", "target_session", "spot", "atr14", "atr14_source_window",
    "realised_volatility", "realised_volatility_window", "liquidity_ratio",
    "gap_risk", "event_risk", "stock_regime", "sector_regime", "source_refs",
    "target_ohlc", "outcome_source_ref",
)
PROHIBITED_PRODUCTION_KEYS = {
    "recommendation", "trade_action", "market_trust", "canonical_selection",
    "probability_decay", "zone_width_multiplier", "expected_centre_formula",
}


class BaselineValidationError(ValueError):
    """Raised when a baseline cannot safely be used as G5 calibration evidence."""


def _missing(mapping: Mapping[str, Any], required: Sequence[str]) -> list[str]:
    return [key for key in required if key not in mapping]


def _parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise BaselineValidationError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineValidationError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise BaselineValidationError(f"{label} must include timezone")
    return parsed


def compute_baseline_hash(payload: Mapping[str, Any]) -> str:
    """Return deterministic SHA-256 over the complete artifact excluding baseline_hash."""
    frozen = {key: value for key, value in payload.items() if key != "baseline_hash"}
    encoded = json.dumps(
        frozen, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_session_sequences(payload: Mapping[str, Any], grouped: Mapping[str, Mapping[str, Any]]) -> None:
    declared = payload["session_sequences"]
    if not isinstance(declared, Mapping):
        raise BaselineValidationError("session_sequences must be an object")
    if set(declared) != set(grouped):
        raise BaselineValidationError("session_sequences keys do not match ticker/issuance groups")

    for key, horizon_rows in grouped.items():
        if set(horizon_rows) != set(HORIZONS):
            raise BaselineValidationError(f"{key} must contain exactly D:D+4 horizons")
        proof = declared[key]
        if not isinstance(proof, Mapping):
            raise BaselineValidationError(f"session_sequences[{key}] must be an object")
        required = ("trading_calendar_version", "calendar_source_ref", "sessions")
        missing = _missing(proof, required)
        if missing:
            raise BaselineValidationError(f"session_sequences[{key}] missing fields: {', '.join(missing)}")
        source_ref = proof["calendar_source_ref"]
        if not isinstance(source_ref, Mapping) or not source_ref.get("source") or not source_ref.get("hash"):
            raise BaselineValidationError(f"session_sequences[{key}].calendar_source_ref requires source and hash")
        sessions = proof["sessions"]
        if not isinstance(sessions, list) or len(sessions) != len(HORIZONS):
            raise BaselineValidationError(f"session_sequences[{key}].sessions must contain five ordered sessions")
        if len(set(sessions)) != len(HORIZONS) or sessions != sorted(sessions):
            raise BaselineValidationError(f"session_sequences[{key}].sessions must be unique and increasing")
        expected_sessions = [str(horizon_rows[h]["target_session"]) for h in HORIZONS]
        if sessions != expected_sessions:
            raise BaselineValidationError(f"session_sequences[{key}] does not match D:D+4 target_session rows")
        versions = {str(horizon_rows[h]["trading_calendar_version"]) for h in HORIZONS}
        if versions != {str(proof["trading_calendar_version"])}:
            raise BaselineValidationError(f"session_sequences[{key}] calendar version mismatch")


def validate_edge_truth_baseline(payload: Mapping[str, Any]) -> None:
    """Validate frozen evidence-contract structure/provenance; never infer or impute."""
    if not isinstance(payload, Mapping):
        raise BaselineValidationError("baseline must be an object")

    missing = _missing(payload, TOP_LEVEL_REQUIRED)
    if missing:
        raise BaselineValidationError(f"missing top-level fields: {', '.join(missing)}")

    generated_at = _parse_timestamp(payload["generated_at"], "generated_at")
    observations = payload["observations"]
    if not isinstance(observations, list) or not observations:
        raise BaselineValidationError("observations must be a non-empty list")
    if payload["observation_count"] != len(observations):
        raise BaselineValidationError("observation_count does not match observations")

    tickers: set[str] = set()
    sessions: set[str] = set()
    coverage: Counter[tuple[str, str]] = Counter()
    grouped: dict[str, dict[str, Any]] = defaultdict(dict)

    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping):
            raise BaselineValidationError(f"observation[{index}] must be an object")
        missing = _missing(observation, OBSERVATION_REQUIRED)
        if missing:
            raise BaselineValidationError(f"observation[{index}] missing fields: {', '.join(missing)}")
        prohibited = PROHIBITED_PRODUCTION_KEYS.intersection(observation)
        if prohibited:
            raise BaselineValidationError(
                f"observation[{index}] contains prohibited production/calibration fields: "
                + ", ".join(sorted(prohibited))
            )
        horizon = observation["horizon"]
        if horizon not in HORIZONS:
            raise BaselineValidationError(f"observation[{index}] invalid horizon: {horizon}")
        if not observation["source_refs"]:
            raise BaselineValidationError(f"observation[{index}] requires source_refs")
        if not observation["outcome_source_ref"]:
            raise BaselineValidationError(f"observation[{index}] requires outcome_source_ref")

        issuance = _parse_timestamp(observation["issuance_asof"], f"observation[{index}].issuance_asof")
        if issuance > generated_at:
            raise BaselineValidationError(f"observation[{index}] issuance_asof is after generated_at")
        for ref_index, source_ref in enumerate(observation["source_refs"]):
            if not isinstance(source_ref, Mapping) or not source_ref.get("hash") or not source_ref.get("asof"):
                raise BaselineValidationError(f"observation[{index}].source_refs[{ref_index}] requires asof and hash")
            source_asof = _parse_timestamp(source_ref["asof"], f"observation[{index}].source_refs[{ref_index}].asof")
            if source_asof > issuance:
                raise BaselineValidationError(f"observation[{index}] source provenance is after issuance_asof")

        ticker = str(observation["ticker"])
        issuance_key = str(observation["issuance_asof"])
        group_key = f"{ticker}|{issuance_key}"
        if horizon in grouped[group_key]:
            raise BaselineValidationError(f"duplicate horizon {horizon} for {group_key}")
        grouped[group_key][str(horizon)] = observation
        tickers.add(ticker)
        sessions.add(issuance_key)
        coverage[(ticker, str(horizon))] += 1

    _validate_session_sequences(payload, grouped)

    if payload["distinct_ticker_count"] != len(tickers):
        raise BaselineValidationError("distinct_ticker_count does not match observations")
    if payload["distinct_session_count"] != len(sessions):
        raise BaselineValidationError("distinct_session_count does not match observations")

    declared = payload["coverage_by_ticker_horizon"]
    if not isinstance(declared, Mapping):
        raise BaselineValidationError("coverage_by_ticker_horizon must be an object")
    expected = {f"{ticker}|{horizon}": count for (ticker, horizon), count in coverage.items()}
    if dict(declared) != expected:
        raise BaselineValidationError("coverage_by_ticker_horizon does not match observations")

    expected_hash = compute_baseline_hash(payload)
    if payload["baseline_hash"] != expected_hash:
        raise BaselineValidationError("baseline_hash does not match deterministic artifact hash")
