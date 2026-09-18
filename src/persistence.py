"""Atomic persistence adapter for canonical EDGE V1 Neon/PostgreSQL schema.

This module does not fetch market evidence and does not calculate EDGE scores.
It persists an already-governed recommendation bundle into the existing schema
inside one database transaction.

The adapter is intentionally DB-API compatible so production can inject a
psycopg connection factory without coupling core EDGE logic to a driver.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class ComponentScoreWrite:
    component: str
    original_weight: float
    raw_score: Optional[int]
    normalized_direction: Optional[float]
    evidence_quality: str
    availability_status: str
    normalized_weight: Optional[float]
    weighted_contribution: Optional[float]
    conflict_flag: bool = False
    gate_override_flag: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class MarketTrustWrite:
    evidence_quality_score: float
    freshness_score: float
    completeness_score: float
    directional_agreement_score: float
    market_confirmation_score: float
    market_trust_score: float
    market_trust_band: str


@dataclass(frozen=True)
class BotScoreWrite:
    forecast_edge: float
    market_trust: float
    structure_pattern_quality: float
    pv_pvpo_confirmation: float
    catalyst_asymmetry: float
    execution_quality: float
    bot_score: float
    bot_grade: str
    decision_ladder: str


@dataclass(frozen=True)
class ExecutionPlanWrite:
    instrument: str
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    stop_price: Optional[float] = None
    invalidation_text: Optional[str] = None
    target1: Optional[float] = None
    target2: Optional[float] = None
    risk_per_unit: Optional[float] = None
    reward_to_t1: Optional[float] = None
    reward_to_t2: Optional[float] = None
    rr_t1: Optional[float] = None
    rr_t2: Optional[float] = None
    risk_unit_category: Optional[str] = None
    time_exit: Optional[str] = None
    option_strike: Optional[float] = None
    option_expiry: Optional[date] = None
    observed_premium: Optional[float] = None
    execution_quality_score: Optional[float] = None
    execution_quality_level: Optional[str] = None
    option_suitability_status: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class CanonicalRecommendationWrite:
    recommendation_id: str
    parent_recommendation_id: Optional[str]
    ticker: str
    company_name: Optional[str]
    run_timestamp: datetime
    forecast_horizon: str
    bull_probability: float
    base_probability: float
    bear_probability: float
    definitive_forecast: str
    expected_price_zone_low: Optional[float]
    expected_price_zone_high: Optional[float]
    des: float
    market_trust_score: float
    market_trust_band: str
    bot_score: float
    bot_grade: str
    decision_ladder: str
    definitive_recommendation: str
    holding_status_known: bool
    event_shock_level: str
    active_override: Optional[str]
    evidence_gate_status: str
    rationale: Optional[str]
    tracking_policy: str
    horizon_days: int
    expiry_trading_date: date
    reference_price: float
    evidence_source_refs: tuple[str, ...]
    component_scores: tuple[ComponentScoreWrite, ...]
    market_trust: MarketTrustWrite
    bot: BotScoreWrite
    execution_plan: ExecutionPlanWrite
    checkpoint_dates: tuple[date, date, date, date, date]
    model_version: str = "EDGE_V1"
    command_type: str = "EDGE"


def _canonical_hash(bundle: CanonicalRecommendationWrite) -> str:
    payload = {
        "recommendation_id": bundle.recommendation_id,
        "parent_recommendation_id": bundle.parent_recommendation_id,
        "ticker": bundle.ticker,
        "run_timestamp": bundle.run_timestamp.isoformat(),
        "forecast_horizon": bundle.forecast_horizon,
        "probabilities": [
            bundle.bull_probability,
            bundle.base_probability,
            bundle.bear_probability,
        ],
        "definitive_forecast": bundle.definitive_forecast,
        "zone": [bundle.expected_price_zone_low, bundle.expected_price_zone_high],
        "des": bundle.des,
        "market_trust_score": bundle.market_trust_score,
        "bot_score": bundle.bot_score,
        "definitive_recommendation": bundle.definitive_recommendation,
        "evidence_source_refs": sorted(bundle.evidence_source_refs),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_bundle(bundle: CanonicalRecommendationWrite) -> None:
    if not bundle.recommendation_id.strip():
        raise ValueError("recommendation_id is required")
    if not bundle.ticker.strip():
        raise ValueError("ticker is required")
    if bundle.model_version != "EDGE_V1":
        raise ValueError("model_version must be EDGE_V1")
    if bundle.command_type != "EDGE":
        raise ValueError("new autonomous recommendation command_type must be EDGE")
    if not 1 <= bundle.horizon_days <= 5:
        raise ValueError("horizon_days must be 1-5")
    if len(bundle.checkpoint_dates) != 5:
        raise ValueError("exactly five D+1...D+5 checkpoint dates are required")
    if tuple(sorted(bundle.checkpoint_dates)) != bundle.checkpoint_dates:
        raise ValueError("checkpoint dates must be increasing")
    if bundle.checkpoint_dates[-1] != bundle.expiry_trading_date:
        raise ValueError("D+5 checkpoint must equal expiry_trading_date")
    if abs(
        bundle.bull_probability + bundle.base_probability + bundle.bear_probability - 100.0
    ) > 0.01:
        raise ValueError("probabilities must sum to 100")
    if bundle.expected_price_zone_low is not None and bundle.expected_price_zone_high is not None:
        if bundle.expected_price_zone_low > bundle.expected_price_zone_high:
            raise ValueError("expected price zone low cannot exceed high")
    if bundle.reference_price <= 0:
        raise ValueError("reference_price must be > 0")
    refs = [r.strip() for r in bundle.evidence_source_refs if r.strip()]
    if not refs:
        raise ValueError("at least one evidence_source_ref is required")
    if len(set(refs)) != len(refs):
        raise ValueError("evidence_source_refs must be unique")
    if not bundle.component_scores:
        raise ValueError("component_scores are required")


class AtomicNeonPersistenceAdapter:
    """Persist one governed EDGE recommendation atomically.

    connection_factory must return a DB-API connection supporting cursor(),
    commit(), and rollback(). The cursor must support execute() and fetchone().
    """

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def persist(self, bundle: CanonicalRecommendationWrite) -> str:
        _validate_bundle(bundle)
        conn = self._connection_factory()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                insert into edge_runs
                  (command_type,ticker,run_timestamp,model_version,status,notes)
                values (%s,%s,%s,%s,'STARTED',%s)
                returning run_id
                """,
                (
                    bundle.command_type,
                    bundle.ticker.upper(),
                    bundle.run_timestamp,
                    bundle.model_version,
                    "Autonomous governed EDGE run.",
                ),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("edge_runs insert did not return run_id")
            run_id = row[0]

            record_hash = _canonical_hash(bundle)
            cur.execute(
                """
                insert into recommendations (
                  recommendation_id,parent_recommendation_id,run_id,model_version,ticker,
                  company_name,run_timestamp,forecast_horizon,bull_probability,base_probability,
                  bear_probability,definitive_forecast,expected_price_zone_low,
                  expected_price_zone_high,des,market_trust_score,market_trust_band,bot_score,
                  bot_grade,decision_ladder,definitive_recommendation,holding_status_known,
                  event_shock_level,active_override,evidence_gate_status,rationale,
                  committed_at,record_hash
                ) values (
                  %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                  %s,%s,%s,%s,%s,%s,%s,%s
                )
                """,
                (
                    bundle.recommendation_id,
                    bundle.parent_recommendation_id,
                    run_id,
                    bundle.model_version,
                    bundle.ticker.upper(),
                    bundle.company_name,
                    bundle.run_timestamp,
                    bundle.forecast_horizon,
                    bundle.bull_probability,
                    bundle.base_probability,
                    bundle.bear_probability,
                    bundle.definitive_forecast,
                    bundle.expected_price_zone_low,
                    bundle.expected_price_zone_high,
                    bundle.des,
                    bundle.market_trust_score,
                    bundle.market_trust_band,
                    bundle.bot_score,
                    bundle.bot_grade,
                    bundle.decision_ladder,
                    bundle.definitive_recommendation,
                    bundle.holding_status_known,
                    bundle.event_shock_level,
                    bundle.active_override,
                    bundle.evidence_gate_status,
                    bundle.rationale,
                    bundle.run_timestamp,
                    record_hash,
                ),
            )

            cur.execute(
                """
                insert into recommendation_lifecycle (
                  recommendation_id,tracking_policy,include_in_master_metrics,horizon_days,
                  expiry_trading_date,status,standard_model_capital,actual_user_executed
                ) values (%s,%s,true,%s,%s,'OPEN',100,false)
                """,
                (
                    bundle.recommendation_id,
                    bundle.tracking_policy,
                    bundle.horizon_days,
                    bundle.expiry_trading_date,
                ),
            )

            cur.execute(
                """
                insert into recommendation_performance (
                  recommendation_id,reference_price,current_price,current_return_pct,
                  outcome_verdict,last_assessed_at,notes
                ) values (%s,%s,%s,0,'OPEN',%s,%s)
                """,
                (
                    bundle.recommendation_id,
                    bundle.reference_price,
                    bundle.reference_price,
                    bundle.run_timestamp,
                    "D0 autonomous reference; final efficacy remains horizon-governed.",
                ),
            )

            refs = tuple(r.strip() for r in bundle.evidence_source_refs if r.strip())
            cur.execute(
                """
                select evidence_id,source_ref
                from evidence_items
                where ticker=%s
                  and verification_status='VERIFIED'
                  and source_ref = any(%s)
                """,
                (bundle.ticker.upper(), list(refs)),
            )
            found = cur.fetchall()
            found_by_ref = {source_ref: evidence_id for evidence_id, source_ref in found}
            missing = [ref for ref in refs if ref not in found_by_ref]
            if missing:
                raise RuntimeError(
                    "verified canonical evidence not found for source_ref(s): " + ", ".join(missing)
                )
            for ref in refs:
                cur.execute(
                    """
                    insert into recommendation_evidence
                      (recommendation_id,evidence_id,use_role)
                    values (%s,%s,'ANALYTICAL_EVIDENCE')
                    """,
                    (bundle.recommendation_id, found_by_ref[ref]),
                )

            for row in bundle.component_scores:
                cur.execute(
                    """
                    insert into component_scores (
                      recommendation_id,component,original_weight,raw_score,
                      normalized_direction,evidence_quality,availability_status,
                      normalized_weight,weighted_contribution,conflict_flag,
                      gate_override_flag,notes
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        bundle.recommendation_id,row.component,row.original_weight,row.raw_score,
                        row.normalized_direction,row.evidence_quality,row.availability_status,
                        row.normalized_weight,row.weighted_contribution,row.conflict_flag,
                        row.gate_override_flag,row.notes,
                    ),
                )

            mt = bundle.market_trust
            cur.execute(
                """
                insert into market_trust (
                  recommendation_id,evidence_quality_score,freshness_score,completeness_score,
                  directional_agreement_score,market_confirmation_score,market_trust_score,
                  market_trust_band
                ) values (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    bundle.recommendation_id,mt.evidence_quality_score,mt.freshness_score,
                    mt.completeness_score,mt.directional_agreement_score,
                    mt.market_confirmation_score,mt.market_trust_score,mt.market_trust_band,
                ),
            )

            bot = bundle.bot
            cur.execute(
                """
                insert into bot_scores (
                  recommendation_id,forecast_edge,market_trust,structure_pattern_quality,
                  pv_pvpo_confirmation,catalyst_asymmetry,execution_quality,bot_score,
                  bot_grade,decision_ladder
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    bundle.recommendation_id,bot.forecast_edge,bot.market_trust,
                    bot.structure_pattern_quality,bot.pv_pvpo_confirmation,
                    bot.catalyst_asymmetry,bot.execution_quality,bot.bot_score,
                    bot.bot_grade,bot.decision_ladder,
                ),
            )

            ep = bundle.execution_plan
            cur.execute(
                """
                insert into execution_plans (
                  recommendation_id,instrument,entry_low,entry_high,stop_price,invalidation_text,
                  target1,target2,risk_per_unit,reward_to_t1,reward_to_t2,rr_t1,rr_t2,
                  risk_unit_category,time_exit,option_strike,option_expiry,observed_premium,
                  execution_quality_score,execution_quality_level,option_suitability_status,notes
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    bundle.recommendation_id,ep.instrument,ep.entry_low,ep.entry_high,
                    ep.stop_price,ep.invalidation_text,ep.target1,ep.target2,ep.risk_per_unit,
                    ep.reward_to_t1,ep.reward_to_t2,ep.rr_t1,ep.rr_t2,ep.risk_unit_category,
                    ep.time_exit,ep.option_strike,ep.option_expiry,ep.observed_premium,
                    ep.execution_quality_score,ep.execution_quality_level,
                    ep.option_suitability_status,ep.notes,
                ),
            )

            for idx, due_date in enumerate(bundle.checkpoint_dates, start=1):
                cur.execute(
                    """
                    insert into outcome_checkpoints (
                      recommendation_id,checkpoint_type,due_date,status,notes
                    ) values (%s,%s,%s,'DUE',%s)
                    """,
                    (
                        bundle.recommendation_id,
                        f"D+{idx}",
                        due_date,
                        "V2 final checkpoint." if idx == 5 else "V2 checkpoint.",
                    ),
                )

            cur.execute(
                "update edge_runs set status='COMMITTED' where run_id=%s",
                (run_id,),
            )
            conn.commit()
            return bundle.recommendation_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
