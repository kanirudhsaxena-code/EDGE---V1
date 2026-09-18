"""Canonical Neon state recovery for the EDGE pre-run efficacy gate."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from typing import Any

from src.pre_run_gate import EfficacySnapshot, OpenRecommendationState

IST=ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class RecoveredPreRunState:
    open_recommendations: tuple[OpenRecommendationState, ...]
    efficacy_snapshot: EfficacySnapshot


def _checkpoint_cutoff(run_at: datetime) -> tuple[object, bool]:
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")
    local=run_at.astimezone(IST)
    # Small post-close buffer avoids treating an in-progress trading session as
    # an overdue daily checkpoint.
    return local.date(), local.time() >= time(15,35)


def recover_pre_run_state(connection: Any, ticker: str, run_at: datetime) -> RecoveredPreRunState:
    symbol=ticker.strip().upper()
    if not symbol:
        raise ValueError("ticker is required")
    local_date,after_close=_checkpoint_cutoff(run_at)

    cur=connection.cursor()
    try:
        cur.execute(
            """
            select
              official_scorable_recommendations,
              recommendation_hit_rate_pct,
              direction_hit_rate_pct,
              provisional_captured_checkpoints,
              provisional_forecast_scorable,
              provisional_forecast_hits,
              provisional_forecast_misses,
              provisional_zone_scorable,
              provisional_zone_hits,
              provisional_zone_misses
            from v_edge_stock_report
            where ticker=%s
            """,
            (symbol,),
        )
        row=cur.fetchone()
        if row is None:
            snapshot=EfficacySnapshot(
                official_sample_size=0,
                recommendation_hit_rate_pct=None,
                directional_accuracy_pct=None,
                forecast_accuracy_pct=None,
                provisional_captured_checkpoints=0,
                provisional_forecast_scorable=0,
                provisional_forecast_hits=0,
                provisional_forecast_misses=0,
                provisional_zone_scorable=0,
                provisional_zone_hits=0,
                provisional_zone_misses=0,
            )
        else:
            snapshot=EfficacySnapshot(
                official_sample_size=int(row[0] or 0),
                recommendation_hit_rate_pct=float(row[1]) if row[1] is not None else None,
                directional_accuracy_pct=float(row[2]) if row[2] is not None else None,
                # Current canonical read model does not expose an independent
                # closed-only forecast-accuracy metric.
                forecast_accuracy_pct=None,
                provisional_captured_checkpoints=int(row[3] or 0),
                provisional_forecast_scorable=int(row[4] or 0),
                provisional_forecast_hits=int(row[5] or 0),
                provisional_forecast_misses=int(row[6] or 0),
                provisional_zone_scorable=int(row[7] or 0),
                provisional_zone_hits=int(row[8] or 0),
                provisional_zone_misses=int(row[9] or 0),
            )

        cur.execute(
            """
            select
              r.recommendation_id,
              r.ticker,
              l.status,
              l.expiry_trading_date,
              count(oc.checkpoint_id) as scheduled_checkpoints,
              count(oc.checkpoint_id) filter (where oc.status='CAPTURED') as captured_checkpoints,
              max(oc.observed_at) filter (where oc.status='CAPTURED') as latest_observed_at,
              count(oc.checkpoint_id) filter (
                where oc.status='DUE'
                  and (
                    oc.due_date < %s
                    or (oc.due_date = %s and %s)
                  )
              ) as overdue_due_checkpoints
            from recommendations r
            join recommendation_lifecycle l using(recommendation_id)
            left join outcome_checkpoints oc using(recommendation_id)
            where r.ticker=%s
              and l.include_in_master_metrics
              and l.status='OPEN'
            group by r.recommendation_id,r.ticker,l.status,l.expiry_trading_date
            order by r.run_timestamp
            """,
            (local_date,local_date,after_close,symbol),
        )
        rows=cur.fetchall()
        open_rows=tuple(
            OpenRecommendationState(
                recommendation_id=str(r[0]),
                ticker=str(r[1]),
                lifecycle_status=str(r[2]),
                expiry_trading_date=(r[3].isoformat() if r[3] is not None else ""),
                due_checkpoint_count=int(r[4] or 0),
                captured_checkpoint_count=int(r[5] or 0),
                latest_checkpoint_observed_at=(r[6].isoformat() if r[6] is not None else None),
                overdue_checkpoint_count=int(r[7] or 0),
            )
            for r in rows
        )
        return RecoveredPreRunState(open_rows,snapshot)
    finally:
        cur.close()
