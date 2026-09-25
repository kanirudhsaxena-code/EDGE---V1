"""Deterministic builder for populated 2C-02 EDGE truth-baseline artifacts.

This is research/read-only tooling. It accepts already-attributable observations and
calendar proofs; it never fetches, imputes, calibrates, or changes production semantics.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from src.edge_truth_baseline import HORIZONS, compute_baseline_hash, validate_edge_truth_baseline


def _count_missing_unverified(observations: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in observations:
        for key, value in row.items():
            if value is None or value == "" or (isinstance(value, str) and value.upper() in {"UNKNOWN", "UNVERIFIED"}):
                counts[key] += 1
    return dict(sorted(counts.items()))


def build_edge_truth_baseline(
    *,
    baseline_id: str,
    observations: Sequence[Mapping[str, Any]],
    session_sequences: Mapping[str, Mapping[str, Any]],
    source_systems: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
    contract_version: str = "2C-02-v1",
) -> dict[str, Any]:
    """Freeze supplied attributable evidence into the governed deterministic artifact.

    The builder deliberately derives metadata only. Observation values and session proofs
    are copied exactly; missing evidence is never reconstructed or inferred.
    """
    if not baseline_id or not isinstance(baseline_id, str):
        raise ValueError("baseline_id is required")
    if not observations:
        raise ValueError("observations must be non-empty")
    if not source_systems:
        raise ValueError("source_systems must be non-empty")

    rows = [dict(row) for row in observations]
    # Stable order makes independent freezes byte/hash reproducible without altering values.
    rows.sort(key=lambda row: (str(row.get("ticker", "")), str(row.get("issuance_asof", "")), HORIZONS.index(str(row.get("horizon"))) if row.get("horizon") in HORIZONS else 99))
    tickers = {str(row.get("ticker")) for row in rows}
    issuance_sessions = {str(row.get("issuance_asof")) for row in rows}
    coverage: Counter[tuple[str, str]] = Counter((str(row.get("ticker")), str(row.get("horizon"))) for row in rows)

    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    payload: dict[str, Any] = {
        "baseline_contract_version": contract_version,
        "baseline_id": baseline_id,
        "baseline_hash": "",
        "generated_at": generated_at,
        "source_systems": [dict(source) for source in source_systems],
        "observation_count": len(rows),
        "distinct_ticker_count": len(tickers),
        "distinct_session_count": len(issuance_sessions),
        "coverage_by_ticker_horizon": {
            f"{ticker}|{horizon}": count
            for (ticker, horizon), count in sorted(coverage.items())
        },
        "missing_unverified_counts": _count_missing_unverified(rows),
        "session_sequences": {key: dict(value) for key, value in sorted(session_sequences.items())},
        "observations": rows,
    }
    payload["baseline_hash"] = compute_baseline_hash(payload)
    validate_edge_truth_baseline(payload)
    return payload
