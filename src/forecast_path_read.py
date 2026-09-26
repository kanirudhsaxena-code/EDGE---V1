"""G5 SHADOW-only exact recovery for persisted EDGE D:D+4 forecast paths.

Read-only by construction: no canonical selection, recommendation, efficacy,
Market Trust, Learning Lab production population, or trading behavior.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from src.forecast_path import (
    ForecastPathRow,
    ForecastPathWrite,
    forecast_path_hash,
    validate_forecast_path,
)


def recover_forecast_path_with_cursor(cur: Any, recommendation_id: str) -> ForecastPathWrite:
    if not isinstance(recommendation_id, str) or not recommendation_id.strip():
        raise ValueError("recommendation_id must be a non-blank string")
    cur.execute(
        """select path_version,source_run_id,issued_at,payload_hash
           from edge_stock_forecast_paths where recommendation_id=%s limit 1""",
        (recommendation_id,),
    )
    header = cur.fetchone()
    if not header:
        raise LookupError("SHADOW forecast path not found")
    version, source_run_id, issued_at, stored_hash = header
    cur.execute(
        """select horizon_index,horizon_label,target_trading_date,direction,
                  bull_probability,base_probability,bear_probability,expected_centre,
                  outer_expected_zone_low,outer_expected_zone_high,evidence_basis,
                  regime_context,verification_state,lineage
           from edge_stock_forecast_path_rows
           where recommendation_id=%s order by horizon_index asc""",
        (recommendation_id,),
    )
    raw_rows = list(cur.fetchall())
    if len(raw_rows) != 5 or tuple(r[0] for r in raw_rows) != (0, 1, 2, 3, 4):
        raise RuntimeError("stored SHADOW forecast path is incomplete or misordered")
    rows = []
    for r in raw_rows:
        lineage = r[13]
        if isinstance(lineage, str):
            lineage = json.loads(lineage)
        if not isinstance(lineage, dict):
            raise RuntimeError("stored SHADOW forecast lineage is malformed")
        rows.append(ForecastPathRow(
            horizon_label=r[1], target_trading_date=r[2], direction=r[3],
            bull_probability=float(r[4]), base_probability=float(r[5]), bear_probability=float(r[6]),
            expected_centre=None if r[7] is None else float(r[7]),
            outer_expected_zone_low=float(r[8]), outer_expected_zone_high=float(r[9]),
            evidence_basis=r[10], regime_context=r[11], verification_state=r[12], lineage=lineage,
        ))
    path = ForecastPathWrite(
        recommendation_id=recommendation_id,
        source_run_id=source_run_id,
        issued_at=issued_at if isinstance(issued_at, datetime) else datetime.fromisoformat(str(issued_at)),
        rows=tuple(rows),
        version=version,
    )
    validate_forecast_path(path)
    if forecast_path_hash(path) != str(stored_hash):
        raise RuntimeError("stored SHADOW forecast path failed immutable payload-hash verification")
    return path


class ForecastPathReadAdapter:
    """Read-only exact recovery adapter for the G5 SHADOW path."""

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def recover(self, recommendation_id: str) -> ForecastPathWrite:
        conn = self._connection_factory()
        cur = conn.cursor()
        try:
            return recover_forecast_path_with_cursor(cur, recommendation_id)
        finally:
            cur.close()
            conn.close()
