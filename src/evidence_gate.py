"""Fail-closed fresh-evidence gate for autonomous EDGE Stocks runs.

This module validates evidence packets before scoring/recommendation generation.
It does not calculate EDGE component scores, probabilities, or recommendations.

The gate enforces:
- provenance/source traceability
- ticker consistency
- retrieval/capture freshness
- required category coverage
- option-chain freshness when an options decision is requested
- no silent substitution of stale/missing evidence

Freshness here applies to when evidence was retrieved/captured for the run.
The underlying source may legitimately describe an older period (for example
the latest quarterly result), but it must be freshly retrieved and identified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

REQUIRED_CORE_CATEGORIES = (
    "PRICE_STRUCTURE",
    "PV_PVPO",
    "SPECIFIC_CHART_PATTERN",
    "NEWS_EVENTS_CATALYSTS",
    "BUSINESS_FUNDAMENTALS",
    "RELATIVE_STRENGTH",
    "EVENT_SHOCK",
)

OPTION_CATEGORY = "DERIVATIVES_OPTIONS"

OPTIONAL_CATEGORIES = (
    "INSTITUTIONAL_BEHAVIOUR",
    "VALUATION",
)

ALLOWED_CATEGORIES = set(REQUIRED_CORE_CATEGORIES) | {OPTION_CATEGORY} | set(OPTIONAL_CATEGORIES)

# Maximum age from evidence capture/retrieval to run time.
# Market-sensitive evidence must be near-live; web/fundamental evidence must be
# freshly retrieved for each run even when the underlying reported period is older.
MAX_AGE_MINUTES = {
    "PRICE_STRUCTURE": 30,
    "PV_PVPO": 30,
    "SPECIFIC_CHART_PATTERN": 30,
    "DERIVATIVES_OPTIONS": 30,
    "NEWS_EVENTS_CATALYSTS": 24 * 60,
    "BUSINESS_FUNDAMENTALS": 24 * 60,
    "INSTITUTIONAL_BEHAVIOUR": 24 * 60,
    "RELATIVE_STRENGTH": 30,
    "VALUATION": 24 * 60,
    "EVENT_SHOCK": 24 * 60,
}


@dataclass(frozen=True)
class EvidenceItem:
    category: str
    ticker: str
    captured_at: datetime
    source_ref: str
    verified: bool
    payload_ref: Optional[str] = None


@dataclass(frozen=True)
class EvidenceGateResult:
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    covered_categories: tuple[str, ...]


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("captured_at and run_at must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _age_minutes(run_at: datetime, captured_at: datetime) -> float:
    return (_utc(run_at) - _utc(captured_at)).total_seconds() / 60.0


def validate_fresh_evidence(
    ticker: str,
    evidence: Iterable[EvidenceItem],
    run_at: datetime,
    *,
    options_decision_requested: bool = False,
) -> EvidenceGateResult:
    """Validate a candidate evidence packet for an autonomous EDGE run.

    Fail-closed rules:
    - all required categories must have at least one valid fresh item
    - options decisions additionally require fresh DERIVATIVES_OPTIONS evidence
    - unverified items never satisfy coverage
    - blank source_ref never satisfies coverage
    - future-dated evidence is invalid
    - ticker mismatch is invalid
    - stale evidence is invalid

    Optional categories may be absent; frozen EDGE missing-evidence rules can
    exclude/renormalize those downstream. This gate does not perform that scoring.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        return EvidenceGateResult(False, ("ticker is required",), (), ())

    try:
        run_time = _utc(run_at)
    except ValueError as exc:
        return EvidenceGateResult(False, (str(exc),), (), ())

    items = list(evidence)
    blockers: list[str] = []
    warnings: list[str] = []
    valid_categories: set[str] = set()

    if not items:
        return EvidenceGateResult(False, ("no evidence supplied",), (), ())

    for idx, item in enumerate(items, start=1):
        category = item.category.strip().upper()
        item_ticker = item.ticker.strip().upper()
        prefix = f"item {idx} ({category or 'UNKNOWN'})"

        if category not in ALLOWED_CATEGORIES:
            blockers.append(f"{prefix}: unknown evidence category")
            continue
        if item_ticker != symbol:
            blockers.append(f"{prefix}: ticker mismatch ({item_ticker or 'blank'} != {symbol})")
            continue
        if not item.verified:
            blockers.append(f"{prefix}: source is not verified")
            continue
        if not item.source_ref or not item.source_ref.strip():
            blockers.append(f"{prefix}: source_ref is required")
            continue

        try:
            age = _age_minutes(run_time, item.captured_at)
        except ValueError as exc:
            blockers.append(f"{prefix}: {exc}")
            continue

        if age < -1:
            blockers.append(f"{prefix}: captured_at is in the future")
            continue

        max_age = MAX_AGE_MINUTES[category]
        if age > max_age:
            blockers.append(
                f"{prefix}: stale evidence ({age:.1f} min > {max_age} min allowed)"
            )
            continue

        valid_categories.add(category)

    required = set(REQUIRED_CORE_CATEGORIES)
    if options_decision_requested:
        required.add(OPTION_CATEGORY)

    missing = sorted(required - valid_categories)
    if missing:
        blockers.append("missing required fresh categories: " + ", ".join(missing))

    absent_optional = sorted(set(OPTIONAL_CATEGORIES) - valid_categories)
    if absent_optional:
        warnings.append(
            "optional categories unavailable and must be handled by downstream "
            "missing-evidence rules: " + ", ".join(absent_optional)
        )

    return EvidenceGateResult(
        ready=not blockers,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        covered_categories=tuple(sorted(valid_categories)),
    )
