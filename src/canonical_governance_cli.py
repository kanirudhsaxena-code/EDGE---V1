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
        print(json.dumps({
            "status":"EDGE_CANONICAL_SELECTION_COMPLETE",
            "finalized":finalized,
            "trading_enabled":False,
            "methodology_changed":False,
        },sort_keys=True))
    finally:
        conn.close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
