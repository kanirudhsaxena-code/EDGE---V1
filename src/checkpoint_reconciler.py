"""Reconcile overdue EDGE outcome checkpoints from read-only Upstox daily candles."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from src.market_providers import UpstoxReadOnlyStockProvider
from src.canonical_governance import is_nse_day, next_nse_day

IST=ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class DueCheckpoint:
    checkpoint_id: int
    recommendation_id: str
    ticker: str
    checkpoint_type: str
    due_date: date


@dataclass(frozen=True)
class CheckpointObservation:
    checkpoint_id: int
    actual_price: float
    period_high: float
    period_low: float
    observed_at: datetime
    source_ref: str


def overdue_due_checkpoints(connection: Any, ticker: str, run_at: datetime) -> tuple[DueCheckpoint,...]:
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")
    local=run_at.astimezone(IST)
    after_close=local.time() >= time(15,35)
    d=local.date()
    cur=connection.cursor()
    try:
        cur.execute(
            """
            select oc.checkpoint_id,oc.recommendation_id,r.ticker,oc.checkpoint_type,oc.due_date
            from outcome_checkpoints oc
            join recommendations r using(recommendation_id)
            join recommendation_lifecycle l using(recommendation_id)
            where r.ticker=%s
              and l.include_in_master_metrics
              and l.status='OPEN'
              and oc.status='DUE'
              and (oc.due_date < %s or (oc.due_date=%s and %s))
            order by oc.due_date,oc.checkpoint_id
            """,
            (ticker.strip().upper(),d,d,after_close),
        )
        return tuple(
            DueCheckpoint(int(x[0]),str(x[1]),str(x[2]),str(x[3]),x[4])
            for x in cur.fetchall()
        )
    finally:
        cur.close()


def _candle_for_date(payload: dict, due_date: date) -> tuple[float,float,float]:
    data=payload.get("data")
    rows=data.get("candles") if isinstance(data,dict) else None
    if not isinstance(rows,list):
        raise RuntimeError("daily candle payload is malformed")
    for row in rows:
        if not isinstance(row,list) or len(row)<5:
            continue
        stamp=str(row[0])
        if not stamp.startswith(due_date.isoformat()):
            continue
        high=float(row[2]); low=float(row[3]); close=float(row[4])
        if high < low or close <= 0:
            raise RuntimeError("invalid daily candle values")
        return close,high,low
    raise RuntimeError(f"no verified daily candle found for {due_date.isoformat()}")


def reconcile_overdue_checkpoints(
    connection: Any,
    provider: UpstoxReadOnlyStockProvider,
    ticker: str,
    run_at: datetime,
) -> tuple[CheckpointObservation,...]:
    due=overdue_due_checkpoints(connection,ticker,run_at)
    if not due:
        return ()

    instrument_key,_=provider.resolve_nse_equity(ticker)
    observations=[]
    for cp in due:
        # Legacy checkpoints can contain calendar dates that were not NSE sessions.
        # Preserve the immutable checkpoint row, but observe it on the next actual
        # NSE trading session. Real trading-day candle gaps still fail closed.
        observation_date = cp.due_date if is_nse_day(cp.due_date) else next_nse_day(cp.due_date)
        window_start = observation_date - timedelta(days=7)
        env=provider.daily(instrument_key,window_start,observation_date)
        try:
            close,high,low=_candle_for_date(dict(env.payload),observation_date)
        except RuntimeError as exc:
            if "no verified daily candle found" not in str(exc):
                raise
            legacy = provider.daily_legacy(instrument_key,observation_date,observation_date)
            close,high,low=_candle_for_date(dict(legacy.payload),observation_date)
            env = legacy
        source_ref=env.source_ref
        if observation_date != cp.due_date:
            source_ref += f"|calendar_rollforward:{cp.due_date.isoformat()}->{observation_date.isoformat()}"
        observations.append(
            CheckpointObservation(
                checkpoint_id=cp.checkpoint_id,
                actual_price=close,
                period_high=high,
                period_low=low,
                observed_at=run_at,
                source_ref=source_ref,
            )
        )

    cur=connection.cursor()
    try:
        for obs in observations:
            cur.execute(
                """
                update outcome_checkpoints
                set status='CAPTURED',
                    observed_at=%s,
                    actual_price=%s,
                    period_high=%s,
                    period_low=%s,
                    source_ref=%s,
                    notes=coalesce(notes,'') || %s
                where checkpoint_id=%s and status='DUE'
                """,
                (
                    obs.observed_at,obs.actual_price,obs.period_high,obs.period_low,
                    obs.source_ref,
                    " | Autonomous verified daily-close reconciliation.",
                    obs.checkpoint_id,
                ),
            )
            if getattr(cur,"rowcount",1) != 1:
                raise RuntimeError("checkpoint state changed during reconciliation")
        connection.commit()
        return tuple(observations)
    except Exception:
        connection.rollback()
        raise
    finally:
        cur.close()
