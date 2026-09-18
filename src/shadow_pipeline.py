"""Governed non-publishing EDGE shadow pipeline.

This is the boundary between evidence interpretation and frozen computation.
The injected analyst may interpret evidence (component raw scores, trust
subscores, execution-quality inputs, price zone, and declarative action), but
it is NOT allowed to choose DES, Market Trust, probabilities, BOT score/grade,
or the definitive forecast. Those are recomputed by the frozen EDGE core.

The pipeline is shadow-only: it never persists.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping, Optional, Sequence

from src.autonomous_evidence_acquisition import AcquiredEvidenceBundle
from src.autonomous_runner import RecommendationEnvelope
from src.evidence_gate import EvidenceItem
from src.frozen_engine import (
    BotInputs,
    ComponentInput,
    TrustInputs,
    bot_hunter,
    compute_des,
    market_trust,
    probabilities,
)


@dataclass(frozen=True)
class AnalystInterpretation:
    component_scores: tuple[ComponentInput, ...]
    evidence_quality_score: float
    freshness_score: float
    completeness_score: float
    market_confirmation_score: float
    structure_pattern_quality: float
    pv_pvpo_confirmation: float
    catalyst_asymmetry: float
    execution_quality: float
    expected_price_zone_low: Optional[float]
    expected_price_zone_high: Optional[float]
    horizon_trading_days: int
    definitive_recommendation: str
    event_override: Optional[str] = None


@dataclass(frozen=True)
class ShadowComputation:
    ticker: str
    run_timestamp: datetime
    des: float
    directional_agreement: float
    market_trust: float
    market_trust_band: str
    bull_probability: float
    base_probability: float
    bear_probability: float
    definitive_forecast: str
    bot_score: float
    bot_grade: str
    component_scores: tuple[ComponentInput, ...]
    evidence_quality_score: float
    freshness_score: float
    completeness_score: float
    market_confirmation_score: float
    structure_pattern_quality: float
    pv_pvpo_confirmation: float
    catalyst_asymmetry: float
    execution_quality: float
    event_override: Optional[str]
    recommendation: RecommendationEnvelope


EvidenceAnalyst = Callable[
    [str, Sequence[EvidenceItem], Mapping[str, Mapping], datetime],
    AnalystInterpretation,
]


def compute_shadow_recommendation(
    bundle: AcquiredEvidenceBundle,
    run_at: datetime,
    analyst: EvidenceAnalyst,
) -> ShadowComputation:
    """Interpret fresh evidence, then recompute all frozen quantitative outputs."""
    if not bundle.gate.ready:
        raise ValueError("fresh evidence gate is not ready")

    interpreted = analyst(
        bundle.ticker,
        bundle.evidence,
        bundle.payloads,
        run_at,
    )

    if not 1 <= interpreted.horizon_trading_days <= 5:
        raise ValueError("horizon_trading_days must be 1-5")
    if not interpreted.definitive_recommendation.strip():
        raise ValueError("definitive_recommendation is required")

    low = interpreted.expected_price_zone_low
    high = interpreted.expected_price_zone_high
    if (low is None) != (high is None):
        raise ValueError("expected price zone must provide both low and high or neither")
    if low is not None and high is not None and low > high:
        raise ValueError("expected price zone low cannot exceed high")

    des_result = compute_des(interpreted.component_scores)
    trust_result = market_trust(
        TrustInputs(
            evidence_quality=interpreted.evidence_quality_score,
            freshness=interpreted.freshness_score,
            completeness=interpreted.completeness_score,
            directional_agreement=des_result.directional_agreement,
            market_confirmation=interpreted.market_confirmation_score,
        )
    )
    prob = probabilities(
        des_result.des,
        trust_result.score,
        override=interpreted.event_override,
    )
    leading = max(prob.bull, prob.base, prob.bear)
    bot = bot_hunter(
        BotInputs(
            leading_probability=leading,
            market_trust=trust_result.score,
            structure_pattern_quality=interpreted.structure_pattern_quality,
            pv_pvpo_confirmation=interpreted.pv_pvpo_confirmation,
            catalyst_asymmetry=interpreted.catalyst_asymmetry,
            execution_quality=interpreted.execution_quality,
        )
    )

    recommendation = RecommendationEnvelope(
        ticker=bundle.ticker,
        run_timestamp=run_at,
        framework_version="EDGE_V1",
        definitive_forecast=prob.definitive_forecast,
        definitive_recommendation=interpreted.definitive_recommendation,
        bull_probability=prob.bull,
        base_probability=prob.base,
        bear_probability=prob.bear,
        horizon_trading_days=interpreted.horizon_trading_days,
        expected_price_zone_low=low,
        expected_price_zone_high=high,
        evidence_refs=tuple(e.source_ref for e in bundle.evidence),
    )

    return ShadowComputation(
        ticker=bundle.ticker,
        run_timestamp=run_at,
        des=des_result.des,
        directional_agreement=des_result.directional_agreement,
        market_trust=trust_result.score,
        market_trust_band=trust_result.band,
        bull_probability=prob.bull,
        base_probability=prob.base,
        bear_probability=prob.bear,
        definitive_forecast=prob.definitive_forecast,
        bot_score=bot.score,
        bot_grade=bot.grade,
        component_scores=interpreted.component_scores,
        evidence_quality_score=interpreted.evidence_quality_score,
        freshness_score=interpreted.freshness_score,
        completeness_score=interpreted.completeness_score,
        market_confirmation_score=interpreted.market_confirmation_score,
        structure_pattern_quality=interpreted.structure_pattern_quality,
        pv_pvpo_confirmation=interpreted.pv_pvpo_confirmation,
        catalyst_asymmetry=interpreted.catalyst_asymmetry,
        execution_quality=interpreted.execution_quality,
        event_override=interpreted.event_override,
        recommendation=recommendation,
    )
