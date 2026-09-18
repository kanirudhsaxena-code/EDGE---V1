"""Canonical production bundle builder for governed EDGE persistence.

Bridges validated shadow computation into the existing CanonicalRecommendationWrite
schema without altering frozen EDGE methodology.

The builder deliberately requires external, already-governed inputs for:
- final production recommendation text
- decision ladder
- execution plan
- verified D+1..D+5 trading dates
- reference price / company metadata
- lifecycle parent recommendation id

It fails closed rather than inventing calendar dates, actions, or execution levels.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.frozen_engine import BotInputs, compute_des, bot_hunter
from src.persistence import (
    BotScoreWrite,
    CanonicalRecommendationWrite,
    ComponentScoreWrite,
    ExecutionPlanWrite,
    MarketTrustWrite,
)
from src.shadow_pipeline import ShadowComputation


@dataclass(frozen=True)
class ProductionMetadata:
    recommendation_id: str
    parent_recommendation_id: Optional[str]
    company_name: Optional[str]
    decision_ladder: str
    definitive_recommendation: str
    holding_status_known: bool
    event_shock_level: str
    reference_price: float
    checkpoint_dates: tuple[date, date, date, date, date]
    execution_plan: ExecutionPlanWrite
    tracking_policy: str = "EDGE_D5_V2"
    active_override: Optional[str] = None
    rationale: Optional[str] = None


def build_canonical_bundle(
    shadow: ShadowComputation,
    metadata: ProductionMetadata,
) -> CanonicalRecommendationWrite:
    if metadata.definitive_recommendation.strip().upper().startswith("SHADOW ONLY"):
        raise ValueError("production recommendation cannot be shadow-only")
    if not metadata.recommendation_id.strip():
        raise ValueError("recommendation_id is required")
    if metadata.reference_price <= 0:
        raise ValueError("reference_price must be positive")
    if len(metadata.checkpoint_dates) != 5:
        raise ValueError("exactly five verified trading dates are required")
    if tuple(sorted(metadata.checkpoint_dates)) != metadata.checkpoint_dates:
        raise ValueError("checkpoint dates must be strictly ordered")
    if len(set(metadata.checkpoint_dates)) != 5:
        raise ValueError("checkpoint dates must be unique")
    if not metadata.decision_ladder.strip():
        raise ValueError("decision_ladder is required")

    des = compute_des(shadow.component_scores)
    component_rows = tuple(
        ComponentScoreWrite(
            component=row.component,
            original_weight=row.original_weight,
            raw_score=row.raw_score,
            normalized_direction=row.normalized_direction,
            evidence_quality="VERIFIED" if row.availability_status == "AVAILABLE" else "NOT_VERIFIED",
            availability_status=row.availability_status,
            normalized_weight=row.normalized_weight,
            weighted_contribution=row.weighted_contribution,
            conflict_flag=False,
            gate_override_flag=shadow.event_override,
            notes=None,
        )
        for row in des.components
    )

    final_execution_quality = metadata.execution_plan.execution_quality_score
    if final_execution_quality is None:
        raise ValueError("final execution quality score is required")
    leading=max(shadow.bull_probability,shadow.base_probability,shadow.bear_probability)
    bot=bot_hunter(BotInputs(
        leading_probability=leading,
        market_trust=shadow.market_trust,
        structure_pattern_quality=shadow.structure_pattern_quality,
        pv_pvpo_confirmation=shadow.pv_pvpo_confirmation,
        catalyst_asymmetry=shadow.catalyst_asymmetry,
        execution_quality=float(final_execution_quality),
    ))

    mt=MarketTrustWrite(
        evidence_quality_score=shadow.evidence_quality_score,
        freshness_score=shadow.freshness_score,
        completeness_score=shadow.completeness_score,
        directional_agreement_score=shadow.directional_agreement,
        market_confirmation_score=shadow.market_confirmation_score,
        market_trust_score=shadow.market_trust,
        market_trust_band=shadow.market_trust_band,
    )

    bot_row=BotScoreWrite(
        forecast_edge=bot.forecast_edge,
        market_trust=shadow.market_trust,
        structure_pattern_quality=shadow.structure_pattern_quality,
        pv_pvpo_confirmation=shadow.pv_pvpo_confirmation,
        catalyst_asymmetry=shadow.catalyst_asymmetry,
        execution_quality=float(final_execution_quality),
        bot_score=bot.score,
        bot_grade=bot.grade,
        decision_ladder=metadata.decision_ladder,
    )

    return CanonicalRecommendationWrite(
        recommendation_id=metadata.recommendation_id,
        parent_recommendation_id=metadata.parent_recommendation_id,
        ticker=shadow.ticker,
        company_name=metadata.company_name,
        run_timestamp=shadow.run_timestamp,
        forecast_horizon=f"D+{shadow.recommendation.horizon_trading_days}",
        bull_probability=shadow.bull_probability,
        base_probability=shadow.base_probability,
        bear_probability=shadow.bear_probability,
        definitive_forecast=shadow.definitive_forecast,
        expected_price_zone_low=shadow.recommendation.expected_price_zone_low,
        expected_price_zone_high=shadow.recommendation.expected_price_zone_high,
        des=shadow.des,
        market_trust_score=shadow.market_trust,
        market_trust_band=shadow.market_trust_band,
        bot_score=bot.score,
        bot_grade=bot.grade,
        decision_ladder=metadata.decision_ladder,
        definitive_recommendation=metadata.definitive_recommendation,
        holding_status_known=metadata.holding_status_known,
        event_shock_level=metadata.event_shock_level,
        active_override=metadata.active_override or shadow.event_override,
        evidence_gate_status="PASS",
        rationale=metadata.rationale,
        tracking_policy=metadata.tracking_policy,
        horizon_days=shadow.recommendation.horizon_trading_days,
        expiry_trading_date=metadata.checkpoint_dates[-1],
        reference_price=metadata.reference_price,
        evidence_source_refs=tuple(dict.fromkeys(shadow.recommendation.evidence_refs)),
        component_scores=component_rows,
        market_trust=mt,
        bot=bot_row,
        execution_plan=metadata.execution_plan,
        checkpoint_dates=metadata.checkpoint_dates,
    )
