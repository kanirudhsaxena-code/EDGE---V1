"""Phase 2.0 G5 governed EDGE Stocks D through D+4 forecast-path persistence.

Additive only: this module validates and persists an already-produced forecast
path. It deliberately does not calculate probabilities, zones, scores, Market
Trust, recommendations, canonical selection, efficacy, or execution decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from typing import Any, Callable, Mapping, Optional

PATH_VERSION = "EDGE_STOCK_FORECAST_PATH_V1"
LABELS = ("D", "D+1", "D+2", "D+3", "D+4")
DIRECTIONS = ("BULL", "BASE", "BEAR")


@dataclass(frozen=True)
class ForecastPathRow:
    horizon_label: str
    target_trading_date: date
    direction: str
    bull_probability: float
    base_probability: float
    bear_probability: float
    outer_expected_zone_low: float
    outer_expected_zone_high: float
    evidence_basis: str
    regime_context: str
    verification_state: str
    lineage: Mapping[str, Any]
    expected_centre: Optional[float] = None


@dataclass(frozen=True)
class ForecastPathWrite:
    recommendation_id: str
    source_run_id: str
    issued_at: datetime
    rows: tuple[ForecastPathRow, ForecastPathRow, ForecastPathRow, ForecastPathRow, ForecastPathRow]
    version: str = PATH_VERSION


def validate_forecast_path(path: ForecastPathWrite) -> None:
    if path.version != PATH_VERSION:
        raise ValueError(f"forecast path version must be {PATH_VERSION}")
    if not path.recommendation_id.strip() or not path.source_run_id.strip():
        raise ValueError("forecast path recommendation_id and source_run_id are required")
    if path.issued_at.tzinfo is None:
        raise ValueError("forecast path issued_at must be timezone-aware")
    if len(path.rows) != 5:
        raise ValueError("forecast path must contain exactly five D through D+4 rows")
    if tuple(row.horizon_label for row in path.rows) != LABELS:
        raise ValueError("forecast path labels must be exactly D,D+1,D+2,D+3,D+4")
    dates = tuple(row.target_trading_date for row in path.rows)
    if dates != tuple(sorted(dates)) or len(set(dates)) != 5:
        raise ValueError("forecast path target trading dates must be unique and strictly increasing")
    for row in path.rows:
        probs = (row.bull_probability, row.base_probability, row.bear_probability)
        if any(value < 0 or value > 100 for value in probs):
            raise ValueError(f"{row.horizon_label} probabilities must be between 0 and 100")
        if abs(sum(probs) - 100.0) > 0.01:
            raise ValueError(f"{row.horizon_label} probabilities must sum to 100 within 0.01")
        leader = DIRECTIONS[max(range(3), key=lambda index: probs[index])]
        if row.direction != leader:
            raise ValueError(f"{row.horizon_label} direction must equal the highest-probability scenario")
        if row.outer_expected_zone_low > row.outer_expected_zone_high:
            raise ValueError(f"{row.horizon_label} outer expected zone low cannot exceed high")
        if not row.evidence_basis.strip() or not row.regime_context.strip() or not row.verification_state.strip():
            raise ValueError(f"{row.horizon_label} basis, regime context and verification state are required")
        if not row.lineage:
            raise ValueError(f"{row.horizon_label} issuance lineage is required")


def _payload(path: ForecastPathWrite) -> dict[str, Any]:
    return {
        "version": path.version,
        "recommendation_id": path.recommendation_id,
        "source_run_id": path.source_run_id,
        "issued_at": path.issued_at.isoformat(),
        "rows": [
            {
                "horizon_label": row.horizon_label,
                "target_trading_date": row.target_trading_date.isoformat(),
                "direction": row.direction,
                "probabilities": {
                    "bull": row.bull_probability,
                    "base": row.base_probability,
                    "bear": row.bear_probability,
                },
                "expected_centre": row.expected_centre,
                "outer_expected_zone": [row.outer_expected_zone_low, row.outer_expected_zone_high],
                "evidence_basis": row.evidence_basis,
                "regime_context": row.regime_context,
                "verification_state": row.verification_state,
                "lineage": dict(row.lineage),
            }
            for row in path.rows
        ],
    }


def forecast_path_hash(path: ForecastPathWrite) -> str:
    validate_forecast_path(path)
    raw = json.dumps(_payload(path), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def persist_forecast_path_with_cursor(cur: Any, path: ForecastPathWrite) -> str:
    """Append a validated path using the caller's open transaction.

    This is the G5 atomic-binding primitive: callers that are already persisting
    the parent recommendation can insert the SHADOW path before their single
    commit. It never commits or rolls back on its own.
    """
    validate_forecast_path(path)
    payload_hash = forecast_path_hash(path)
    cur.execute(
        "select payload_hash from edge_stock_forecast_paths where recommendation_id=%s limit 1",
        (path.recommendation_id,),
    )
    existing = cur.fetchone()
    if existing:
        if str(existing[0]) != payload_hash:
            raise RuntimeError("recommendation already has different immutable forecast-path content")
        return payload_hash
    cur.execute(
        """insert into edge_stock_forecast_paths
           (recommendation_id,path_version,source_run_id,issued_at,payload_hash)
           values (%s,%s,%s,%s,%s)""",
        (path.recommendation_id, path.version, path.source_run_id, path.issued_at, payload_hash),
    )
    for index, row in enumerate(path.rows):
        cur.execute(
            """insert into edge_stock_forecast_path_rows
               (recommendation_id,horizon_index,horizon_label,target_trading_date,direction,
                bull_probability,base_probability,bear_probability,expected_centre,
                outer_expected_zone_low,outer_expected_zone_high,evidence_basis,regime_context,
                verification_state,lineage)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                path.recommendation_id,index,row.horizon_label,row.target_trading_date,row.direction,
                row.bull_probability,row.base_probability,row.bear_probability,row.expected_centre,
                row.outer_expected_zone_low,row.outer_expected_zone_high,row.evidence_basis,
                row.regime_context,row.verification_state,json.dumps(dict(row.lineage),sort_keys=True),
            ),
        )
    return payload_hash


class ForecastPathPersistenceAdapter:
    """Append one immutable, already-governed five-row issuance path."""

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def persist(self, path: ForecastPathWrite) -> str:
        conn = self._connection_factory()
        cur = conn.cursor()
        try:
            payload_hash = persist_forecast_path_with_cursor(cur, path)
            conn.commit()
            return payload_hash
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
