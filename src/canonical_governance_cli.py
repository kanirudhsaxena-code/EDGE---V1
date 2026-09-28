"""Finalize EDGE Stocks canonical selections after the hard 09:00 IST boundary."""
from __future__ import annotations

import json
import os

import psycopg

from src.canonical_governance import finalize_stock_canonicals


def main()->int:
    db_url=(os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        raise SystemExit("DATABASE_URL is required")
    conn=psycopg.connect(db_url)
    try:
        finalized=finalize_stock_canonicals(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT canonical_key,ticker,target_trading_date,forecast_horizon,
                       selection_status,canonical_type,selected_recommendation_id,selected_at
                  FROM edge_canonical_selections
                 WHERE target_trading_date=(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
                 ORDER BY ticker,forecast_horizon
            """)
            today=[{
                "canonical_key":r[0],
                "ticker":r[1],
                "target_trading_date":str(r[2]),
                "forecast_horizon":r[3],
                "selection_status":r[4],
                "canonical_type":r[5],
                "selected_recommendation_id":str(r[6]) if r[6] is not None else None,
                "selected_at":r[7].isoformat() if r[7] is not None else None,
            } for r in cur.fetchall()]
        print(json.dumps({
            "status":"EDGE_CANONICAL_SELECTION_COMPLETE",
            "finalized":finalized,
            "trading_enabled":False,
            "methodology_changed":False,
            "today_selections":today,
        },sort_keys=True))
    finally:
        conn.close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
