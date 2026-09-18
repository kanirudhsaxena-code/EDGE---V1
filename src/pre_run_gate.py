"""Deterministic pre-run efficacy gate for EDGE V1.

This module does not generate recommendations. It verifies that the efficacy
state that must be assessed before a new EDGE run is internally coherent and
explicitly represented. The autonomous runner can call this gate before any
fresh-evidence scoring or recommendation publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

VALID_LIFECYCLE_STATUSES = {"OPEN", "CLOSED", "NOT_SCORABLE"}
VALID_CHECKPOINT_STATES = {"DUE", "CAPTURED", "MISSED", "NOT_SCORABLE"}


@dataclass(frozen=True)
class OpenRecommendationState:
    recommendation_id: str
    ticker: str
    lifecycle_status: str
    expiry_trading_date: str
    due_checkpoint_count: int
    captured_checkpoint_count: int
    latest_checkpoint_observed_at: Optional[str] = None
    overdue_checkpoint_count: int = 0


@dataclass(frozen=True)
class EfficacySnapshot:
    official_sample_size: int
    recommendation_hit_rate_pct: Optional[float]
    directional_accuracy_pct: Optional[float]
    forecast_accuracy_pct: Optional[float]
    provisional_captured_checkpoints: int
    provisional_forecast_scorable: int
    provisional_forecast_hits: int
    provisional_forecast_misses: int
    provisional_zone_scorable: int
    provisional_zone_hits: int
    provisional_zone_misses: int


@dataclass(frozen=True)
class PreRunGateResult:
    ready: bool
    blockers: tuple[str, ...]
    assessed_open_recommendations: int


def _valid_percentage(value: Optional[float]) -> bool:
    return value is None or 0.0 <= value <= 100.0


def validate_efficacy_snapshot(snapshot: EfficacySnapshot) -> tuple[str, ...]:
    blockers: list[str] = []
    if snapshot.official_sample_size < 0:
        blockers.append("official sample size cannot be negative")
    if snapshot.official_sample_size == 0:
        if any(
            value is not None
            for value in (
                snapshot.recommendation_hit_rate_pct,
                snapshot.directional_accuracy_pct,
                snapshot.forecast_accuracy_pct,
            )
        ):
            blockers.append("official efficacy must remain N/A when official sample size is zero")
    for name, value in (
        ("recommendation hit rate", snapshot.recommendation_hit_rate_pct),
        ("directional accuracy", snapshot.directional_accuracy_pct),
        ("forecast accuracy", snapshot.forecast_accuracy_pct),
    ):
        if not _valid_percentage(value):
            blockers.append(f"{name} must be between 0 and 100 when present")

    counters = {
        "provisional captured checkpoints": snapshot.provisional_captured_checkpoints,
        "provisional forecast scorable": snapshot.provisional_forecast_scorable,
        "provisional forecast hits": snapshot.provisional_forecast_hits,
        "provisional forecast misses": snapshot.provisional_forecast_misses,
        "provisional zone scorable": snapshot.provisional_zone_scorable,
        "provisional zone hits": snapshot.provisional_zone_hits,
        "provisional zone misses": snapshot.provisional_zone_misses,
    }
    for name, value in counters.items():
        if value < 0:
            blockers.append(f"{name} cannot be negative")

    if snapshot.provisional_forecast_hits + snapshot.provisional_forecast_misses != snapshot.provisional_forecast_scorable:
        blockers.append("provisional forecast hit/miss counts must equal provisional forecast scorable count")
    if snapshot.provisional_zone_hits + snapshot.provisional_zone_misses != snapshot.provisional_zone_scorable:
        blockers.append("provisional zone hit/miss counts must equal provisional zone scorable count")
    if snapshot.provisional_forecast_scorable > snapshot.provisional_captured_checkpoints:
        blockers.append("provisional forecast scorable count cannot exceed captured checkpoints")
    if snapshot.provisional_zone_scorable > snapshot.provisional_captured_checkpoints:
        blockers.append("provisional zone scorable count cannot exceed captured checkpoints")
    return tuple(blockers)


def evaluate_pre_run_gate(
    open_recommendations: Iterable[OpenRecommendationState],
    efficacy_snapshot: EfficacySnapshot,
) -> PreRunGateResult:
    """Fail closed unless prior recommendation efficacy state is assessable.

    The gate intentionally does not judge the market or create a forecast. It
    only protects the required sequence: assess existing recommendations first,
    then permit the evidence/analysis stage of a new run.
    """
    blockers = list(validate_efficacy_snapshot(efficacy_snapshot))
    rows = list(open_recommendations)

    seen_ids: set[str] = set()
    for row in rows:
        rid = row.recommendation_id.strip()
        if not rid:
            blockers.append("open recommendation is missing recommendation_id")
        elif rid in seen_ids:
            blockers.append(f"duplicate open recommendation_id: {rid}")
        seen_ids.add(rid)

        if not row.ticker.strip():
            blockers.append(f"{rid or 'unknown recommendation'} is missing ticker")
        if row.lifecycle_status not in VALID_LIFECYCLE_STATUSES:
            blockers.append(f"{rid or 'unknown recommendation'} has invalid lifecycle status")
        if row.lifecycle_status != "OPEN":
            blockers.append(f"{rid or 'unknown recommendation'} supplied to open-call gate is not OPEN")
        if not row.expiry_trading_date.strip():
            blockers.append(f"{rid or 'unknown recommendation'} is missing expiry_trading_date")
        if row.due_checkpoint_count < 0 or row.captured_checkpoint_count < 0:
            blockers.append(f"{rid or 'unknown recommendation'} has negative checkpoint counts")
        if row.captured_checkpoint_count > row.due_checkpoint_count:
            blockers.append(f"{rid or 'unknown recommendation'} captured checkpoints exceed scheduled checkpoints")
        if row.captured_checkpoint_count > 0 and not row.latest_checkpoint_observed_at:
            blockers.append(f"{rid or 'unknown recommendation'} has captured checkpoints but no observation timestamp")
        if row.overdue_checkpoint_count < 0:
            blockers.append(f"{rid or 'unknown recommendation'} has negative overdue checkpoint count")
        if row.overdue_checkpoint_count > 0:
            blockers.append(
                f"{rid or 'unknown recommendation'} has {row.overdue_checkpoint_count} overdue DUE checkpoint(s)"
            )

    return PreRunGateResult(
        ready=not blockers,
        blockers=tuple(blockers),
        assessed_open_recommendations=len(rows),
    )
