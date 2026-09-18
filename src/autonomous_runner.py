"""Fail-closed orchestration shell for autonomous EDGE Stocks runs.

This module wires the already-approved pre-run efficacy gate and fresh-evidence
gate into a single runner contract. It intentionally does NOT reimplement the
frozen EDGE methodology. A governed EDGE engine callable must be injected; the
runner only invokes it after both gates pass and validates the returned
recommendation envelope before persistence.

Publication is separated from calculation so a future persistence adapter can
commit atomically to Neon only after all checks pass.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Mapping, Optional, Protocol, Sequence

from src.evidence_gate import EvidenceItem, EvidenceGateResult, validate_fresh_evidence
from src.pre_run_gate import (
    EfficacySnapshot,
    OpenRecommendationState,
    PreRunGateResult,
    evaluate_pre_run_gate,
)
from src.scoring import validate_probabilities


class PersistenceAdapter(Protocol):
    def persist(self, recommendation: "RecommendationEnvelope") -> str: ...


@dataclass(frozen=True)
class RecommendationEnvelope:
    ticker: str
    run_timestamp: datetime
    framework_version: str
    definitive_forecast: str
    definitive_recommendation: str
    bull_probability: float
    base_probability: float
    bear_probability: float
    horizon_trading_days: int
    expected_price_zone_low: Optional[float]
    expected_price_zone_high: Optional[float]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class RunnerResult:
    status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    pre_run_gate: PreRunGateResult
    evidence_gate: Optional[EvidenceGateResult]
    recommendation: Optional[RecommendationEnvelope]
    persistence_id: Optional[str]


GovernedEdgeEngine = Callable[
    [str, Sequence[EvidenceItem], datetime, bool],
    RecommendationEnvelope,
]


def _validate_recommendation_envelope(
    expected_ticker: str,
    run_at: datetime,
    recommendation: RecommendationEnvelope,
    supplied_evidence: Sequence[EvidenceItem],
) -> tuple[str, ...]:
    blockers: list[str] = []
    symbol = expected_ticker.strip().upper()

    if recommendation.ticker.strip().upper() != symbol:
        blockers.append("engine output ticker does not match requested ticker")
    if recommendation.framework_version != "EDGE_V1":
        blockers.append("engine output framework_version must be EDGE_V1")
    if recommendation.run_timestamp != run_at:
        blockers.append("engine output run_timestamp must equal governed run timestamp")
    if not 1 <= recommendation.horizon_trading_days <= 5:
        blockers.append("recommendation horizon must be 1-5 trading days")
    if not recommendation.definitive_forecast.strip():
        blockers.append("definitive_forecast is required")
    if not recommendation.definitive_recommendation.strip():
        blockers.append("definitive_recommendation is required")

    try:
        validate_probabilities(
            recommendation.bull_probability,
            recommendation.base_probability,
            recommendation.bear_probability,
        )
    except ValueError as exc:
        blockers.append(str(exc))

    low = recommendation.expected_price_zone_low
    high = recommendation.expected_price_zone_high
    if (low is None) != (high is None):
        blockers.append("expected price zone must provide both low and high or neither")
    if low is not None and high is not None and low > high:
        blockers.append("expected price zone low cannot exceed high")

    supplied_refs = {e.source_ref.strip() for e in supplied_evidence if e.source_ref.strip()}
    output_refs = {r.strip() for r in recommendation.evidence_refs if r.strip()}
    if not output_refs:
        blockers.append("recommendation must retain evidence_refs")
    if not output_refs.issubset(supplied_refs):
        blockers.append("recommendation contains evidence_refs not present in supplied evidence")

    return tuple(blockers)


def run_governed_edge(
    *,
    ticker: str,
    run_at: datetime,
    open_recommendations: Iterable[OpenRecommendationState],
    efficacy_snapshot: EfficacySnapshot,
    evidence: Iterable[EvidenceItem],
    engine: GovernedEdgeEngine,
    options_decision_requested: bool = False,
    persistence: Optional[PersistenceAdapter] = None,
    publish: bool = False,
) -> RunnerResult:
    """Execute the governed sequence and fail closed on any inconsistency.

    Sequence:
      1. Assess prior recommendation efficacy.
      2. Validate fresh evidence.
      3. Invoke the injected frozen EDGE engine.
      4. Validate the engine output envelope and evidence lineage.
      5. Persist only when publish=True and a persistence adapter is supplied.

    The runner never changes frozen EDGE weights/formulas and never derives a
    recommendation on its own.
    """
    pre = evaluate_pre_run_gate(open_recommendations, efficacy_snapshot)
    if not pre.ready:
        return RunnerResult(
            status="BLOCKED_PRE_RUN_EFFICACY",
            blockers=pre.blockers,
            warnings=(),
            pre_run_gate=pre,
            evidence_gate=None,
            recommendation=None,
            persistence_id=None,
        )

    evidence_rows = tuple(evidence)
    evidence_gate = validate_fresh_evidence(
        ticker,
        evidence_rows,
        run_at,
        options_decision_requested=options_decision_requested,
    )
    if not evidence_gate.ready:
        return RunnerResult(
            status="BLOCKED_EVIDENCE",
            blockers=evidence_gate.blockers,
            warnings=evidence_gate.warnings,
            pre_run_gate=pre,
            evidence_gate=evidence_gate,
            recommendation=None,
            persistence_id=None,
        )

    recommendation = engine(
        ticker.strip().upper(),
        evidence_rows,
        run_at,
        options_decision_requested,
    )
    output_blockers = _validate_recommendation_envelope(
        ticker, run_at, recommendation, evidence_rows
    )
    if output_blockers:
        return RunnerResult(
            status="BLOCKED_ENGINE_OUTPUT",
            blockers=output_blockers,
            warnings=evidence_gate.warnings,
            pre_run_gate=pre,
            evidence_gate=evidence_gate,
            recommendation=None,
            persistence_id=None,
        )

    if not publish:
        return RunnerResult(
            status="SHADOW_READY",
            blockers=(),
            warnings=evidence_gate.warnings,
            pre_run_gate=pre,
            evidence_gate=evidence_gate,
            recommendation=recommendation,
            persistence_id=None,
        )

    if persistence is None:
        return RunnerResult(
            status="BLOCKED_PERSISTENCE",
            blockers=("publish requested but persistence adapter is not configured",),
            warnings=evidence_gate.warnings,
            pre_run_gate=pre,
            evidence_gate=evidence_gate,
            recommendation=recommendation,
            persistence_id=None,
        )

    persistence_id = persistence.persist(recommendation)
    if not persistence_id or not str(persistence_id).strip():
        return RunnerResult(
            status="BLOCKED_PERSISTENCE",
            blockers=("persistence adapter did not return an immutable persistence id",),
            warnings=evidence_gate.warnings,
            pre_run_gate=pre,
            evidence_gate=evidence_gate,
            recommendation=recommendation,
            persistence_id=None,
        )

    return RunnerResult(
        status="PUBLISHED",
        blockers=(),
        warnings=evidence_gate.warnings,
        pre_run_gate=pre,
        evidence_gate=evidence_gate,
        recommendation=recommendation,
        persistence_id=str(persistence_id),
    )
