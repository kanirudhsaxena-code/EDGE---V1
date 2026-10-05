"""CLI for the governed PREOPEN AUCTION DATA stage."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.market_providers import AcquisitionError, safe_diagnostic
from src.market_snapshot import capture_auction_snapshot


def main()->int:
    ticker=os.getenv("EDGE_TICKER","").strip().upper()
    lifecycle_id=os.getenv("EDGE_LIFECYCLE_ID","").strip()
    token=os.getenv("UPSTOX_ANALYTICS_TOKEN","").strip()
    db_url=os.getenv("DATABASE_URL","").strip()
    if not ticker or not lifecycle_id or not token or not db_url:
        print(json.dumps({
            "status":"AUCTION_BLOCKED",
            "diagnostic_code":"AUCTION_STAGE_CONFIGURATION_MISSING",
            "ticker":ticker or None,
            "lifecycle_id":lifecycle_id or None,
            "trading_enabled":False,
        },sort_keys=True))
        return 2

    import psycopg
    conn=psycopg.connect(db_url)
    now=datetime.now(timezone.utc)
    try:
        try:
            snapshot=capture_auction_snapshot(
                conn,ticker=ticker,lifecycle_id=lifecycle_id,
                run_at=now,upstox_token=token,
            )
        except AcquisitionError as exc:
            print(json.dumps({
                "status":"AUCTION_BLOCKED",
                "diagnostic_code":safe_diagnostic(exc),
                "ticker":ticker,"lifecycle_id":lifecycle_id,
                "trading_enabled":False,
            },sort_keys=True))
            return 3
        except Exception as exc:
            print(json.dumps({
                "status":"AUCTION_BLOCKED",
                "diagnostic_code":"AUCTION_STAGE_FAILED",
                "detail":str(exc)[:500],
                "ticker":ticker,"lifecycle_id":lifecycle_id,
                "trading_enabled":False,
            },sort_keys=True))
            return 3
        print(json.dumps({
            "status":"AUCTION_READY",
            "ticker":ticker,
            "lifecycle_id":lifecycle_id,
            "auction_snapshot_id":snapshot.auction_snapshot_id,
            "captured_at":snapshot.captured_at.isoformat(),
            "indicative_equilibrium_price":snapshot.indicative_equilibrium_price,
            "trading_enabled":False,
        },sort_keys=True))
        return 0
    finally:
        conn.close()


if __name__=="__main__":
    raise SystemExit(main())
