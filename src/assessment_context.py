"""Master-spec assessment retrieval for EDGE V1 Efficacy V2.

This module implements the approved Efficacy V2 user-facing assessment inputs:
1. EDGE MASTER ASSESSMENT
2. ACTIVE CALLS
plus stock-level diagnostics used to make provisional vs official efficacy explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class MasterAssessment:
    recommendations: int
    unique_stocks: int
    open_recommendations: int
    closed_recommendations: int
    recommendation_hit_rate_pct: Optional[float]
    direction_hit_rate_pct: Optional[float]
    target_hit_rate_pct: Optional[float]
    avg_gain_pct: Optional[float]
    avg_loss_pct: Optional[float]
    avg_mfe_pct: Optional[float]
    avg_mae_pct: Optional[float]
    cumulative_model_pnl_units: Optional[float]
    official_scorable_recommendations: int
    provisional_captured_checkpoints: int
    provisional_due_checkpoints: int
    provisional_forecast_scorable: int
    provisional_forecast_hits: int
    provisional_forecast_misses: int
    provisional_forecast_accuracy_pct: Optional[float]
    provisional_zone_scorable: int
    provisional_zone_hits: int
    provisional_zone_misses: int
    provisional_zone_accuracy_pct: Optional[float]


@dataclass(frozen=True)
class ActiveCall:
    ticker: str
    recommendation_id: str
    definitive_forecast: str
    definitive_recommendation: str
    zone_low: Optional[float]
    zone_high: Optional[float]
    expiry_trading_date: Optional[str]
    current_price: Optional[float]
    current_return_pct: Optional[float]
    outcome_verdict: Optional[str]
    open_recommendations: int
    bull_probability: Optional[float]
    base_probability: Optional[float]
    bear_probability: Optional[float]


@dataclass(frozen=True)
class StockAssessment:
    ticker: str
    recommendations: int
    open_recommendations: int
    closed_recommendations: int
    recommendation_hit_rate_pct: Optional[float]
    direction_hit_rate_pct: Optional[float]
    target_hit_rate_pct: Optional[float]
    official_scorable_recommendations: int
    provisional_captured_checkpoints: int
    provisional_due_checkpoints: int
    provisional_forecast_scorable: int
    provisional_forecast_hits: int
    provisional_forecast_misses: int
    provisional_forecast_accuracy_pct: Optional[float]
    provisional_zone_scorable: int
    provisional_zone_hits: int
    provisional_zone_misses: int
    provisional_zone_accuracy_pct: Optional[float]
    latest_checkpoint_observed_at: Optional[str]


@dataclass(frozen=True)
class AssessmentContext:
    master: MasterAssessment
    active_calls: tuple[ActiveCall, ...]
    stock: StockAssessment


def _f(x):
    return float(x) if x is not None else None


def load_assessment_context(connection: Any, ticker: str) -> AssessmentContext:
    symbol=ticker.strip().upper()
    cur=connection.cursor()
    try:
        cur.execute("""
            select
              recommendations,unique_stocks,open_recommendations,closed_recommendations,
              recommendation_hit_rate_pct,direction_hit_rate_pct,target_hit_rate_pct,
              avg_gain_pct,avg_loss_pct,avg_mfe_pct,avg_mae_pct,cumulative_model_pnl_units,
              official_scorable_recommendations,
              provisional_captured_checkpoints,provisional_due_checkpoints,
              provisional_forecast_scorable,provisional_forecast_hits,
              provisional_forecast_misses,provisional_forecast_accuracy_pct,
              provisional_zone_scorable,provisional_zone_hits,provisional_zone_misses,
              provisional_zone_accuracy_pct
            from v_edge_master_report
        """)
        m=cur.fetchone()
        if m is None:
            raise RuntimeError("EDGE master assessment view returned no row")
        master=MasterAssessment(
            int(m[0] or 0),int(m[1] or 0),int(m[2] or 0),int(m[3] or 0),
            _f(m[4]),_f(m[5]),_f(m[6]),_f(m[7]),_f(m[8]),_f(m[9]),_f(m[10]),_f(m[11]),
            int(m[12] or 0),int(m[13] or 0),int(m[14] or 0),int(m[15] or 0),
            int(m[16] or 0),int(m[17] or 0),_f(m[18]),int(m[19] or 0),
            int(m[20] or 0),int(m[21] or 0),_f(m[22]),
        )

        cur.execute("""
            select ticker,recommendation_id,definitive_forecast,definitive_recommendation,
                   expected_price_zone_low,expected_price_zone_high,expiry_trading_date,
                   current_price,current_return_pct,outcome_verdict,open_recommendations,
                   bull_probability,base_probability,bear_probability
            from v_edge_active_calls
            order by ticker
        """)
        active=tuple(
            ActiveCall(
                str(r[0]),str(r[1]),str(r[2]),str(r[3]),_f(r[4]),_f(r[5]),
                (r[6].isoformat() if r[6] is not None and hasattr(r[6],"isoformat") else (str(r[6]) if r[6] is not None else None)),
                _f(r[7]),_f(r[8]),str(r[9]) if r[9] is not None else None,
                int(r[10] or 0),_f(r[11]),_f(r[12]),_f(r[13]),
            )
            for r in cur.fetchall()
        )

        cur.execute("""
            select
              ticker,recommendations,open_recommendations,closed_recommendations,
              recommendation_hit_rate_pct,direction_hit_rate_pct,target_hit_rate_pct,
              official_scorable_recommendations,
              provisional_captured_checkpoints,provisional_due_checkpoints,
              provisional_forecast_scorable,provisional_forecast_hits,
              provisional_forecast_misses,provisional_forecast_accuracy_pct,
              provisional_zone_scorable,provisional_zone_hits,provisional_zone_misses,
              provisional_zone_accuracy_pct,latest_checkpoint_observed_at
            from v_edge_stock_report
            where ticker=%s
        """,(symbol,))
        s=cur.fetchone()
        if s is None:
            stock=StockAssessment(
                symbol,0,0,0,None,None,None,0,0,0,0,0,0,None,0,0,0,None,None
            )
        else:
            stock=StockAssessment(
                str(s[0]),int(s[1] or 0),int(s[2] or 0),int(s[3] or 0),
                _f(s[4]),_f(s[5]),_f(s[6]),int(s[7] or 0),int(s[8] or 0),
                int(s[9] or 0),int(s[10] or 0),int(s[11] or 0),int(s[12] or 0),
                _f(s[13]),int(s[14] or 0),int(s[15] or 0),int(s[16] or 0),
                _f(s[17]),(s[18].isoformat() if s[18] is not None and hasattr(s[18],"isoformat") else (str(s[18]) if s[18] is not None else None)),
            )
        return AssessmentContext(master=master,active_calls=active,stock=stock)
    finally:
        cur.close()
