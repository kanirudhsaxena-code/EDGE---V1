"""G5 EDGE Stocks horizon-path SHADOW producer contract.

Adapts the governed 5DR multi-horizon design pattern without copying NIFTY
numeric parameters. The caller must supply five stock-specific, evidence-derived
horizon slots. This module normalizes/validates those slots into the immutable
EDGE Stocks ForecastPathWrite used by G5 persistence.

SHADOW ONLY: this module does not alter the frozen production recommendation,
Market Trust, canonical selection, efficacy population, or trading action.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Sequence

from .forecast_path import ForecastPathRow, ForecastPathWrite, LABELS, validate_forecast_path

SCENARIOS = ("BULL", "BASE", "BEAR")


def _number(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def build_shadow_forecast_path(
    *,
    recommendation_id: str,
    source_run_id: str,
    issued_at: datetime,
    horizon_slots: Sequence[Mapping[str, Any]],
    producer_version: str,
) -> ForecastPathWrite:
    """Validate genuine stock-specific D:D+4 slots and build a persistence write.

    Deliberately does not derive/decay/interpolate probabilities or zones. The
    horizon producer upstream must calculate them from approved stock evidence.
    """
    if len(horizon_slots) != 5:
        raise ValueError("G5 shadow producer requires exactly five D through D+4 slots")
    if not producer_version.strip():
        raise ValueError("G5 shadow producer version is required")

    rows = []
    for expected_label, slot in zip(LABELS, horizon_slots):
        label = str(slot.get("horizon_label") or "")
        if label != expected_label:
            raise ValueError(f"G5 horizon order must be {','.join(LABELS)}")
        target = slot.get("target_trading_date")
        if isinstance(target, str):
            target = date.fromisoformat(target)
        if not isinstance(target, date):
            raise ValueError(f"{label} target_trading_date is required")

        probs = slot.get("probabilities")
        if not isinstance(probs, Mapping) or set(probs) != set(SCENARIOS):
            raise ValueError(f"{label} probabilities must contain exactly BULL, BASE and BEAR")
        bull = _number(probs["BULL"], f"{label}.BULL")
        base = _number(probs["BASE"], f"{label}.BASE")
        bear = _number(probs["BEAR"], f"{label}.BEAR")

        zone = slot.get("outer_expected_zone")
        if not isinstance(zone, Mapping):
            raise ValueError(f"{label} stock-specific outer_expected_zone is required")
        low = _number(zone.get("low"), f"{label}.zone.low")
        high = _number(zone.get("high"), f"{label}.zone.high")
        centre_raw = slot.get("expected_centre")
        centre = None if centre_raw is None else _number(centre_raw, f"{label}.expected_centre")
        if centre is not None and not (low <= centre <= high):
            raise ValueError(f"{label} expected_centre must lie inside the stock-specific zone")

        lineage = slot.get("lineage")
        if not isinstance(lineage, Mapping) or not lineage:
            raise ValueError(f"{label} lineage is required")
        lineage = dict(lineage)
        lineage["producer_version"] = producer_version
        lineage["mode"] = "SHADOW"

        rows.append(ForecastPathRow(
            horizon_label=label,
            target_trading_date=target,
            direction=str(slot.get("direction") or ""),
            bull_probability=bull,
            base_probability=base,
            bear_probability=bear,
            expected_centre=centre,
            outer_expected_zone_low=low,
            outer_expected_zone_high=high,
            evidence_basis=str(slot.get("evidence_basis") or ""),
            regime_context=str(slot.get("regime_context") or ""),
            verification_state=str(slot.get("verification_state") or ""),
            lineage=lineage,
        ))

    path = ForecastPathWrite(
        recommendation_id=recommendation_id,
        source_run_id=source_run_id,
        issued_at=issued_at,
        rows=tuple(rows),  # type: ignore[arg-type]
    )
    validate_forecast_path(path)
    return path
