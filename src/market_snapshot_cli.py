"""CLI for the DATA stage of a governed EDGE stock lifecycle."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.market_providers import AcquisitionError, safe_diagnostic
from src.market_snapshot import capture_market_snapshot, mark_data_blocked


def main()->int:
    ticker=os.getenv("EDGE_TICKER","").strip().upper()
    lifecycle_id=os.getenv("EDGE_LIFECYCLE_ID","").strip()
    trigger_type=os.getenv("EDGE_TRIGGER_TYPE","USER").strip().upper()
    target_session=os.getenv("EDGE_TARGET_SESSION","").strip() or None
    canonical_raw=os.getenv("EDGE_CANONICAL_REQUESTED_AT","").strip()
    token=os.getenv("UPSTOX_ANALYTICS_TOKEN","").strip()
    db_url=os.getenv("DATABASE_URL","").strip()

    if not ticker or not lifecycle_id or not token or not db_url:
        print(json.dumps({
            "status":"DATA_BLOCKED",
            "diagnostic_code":"DATA_STAGE_CONFIGURATION_MISSING",
            "ticker":ticker or None,
            "lifecycle_id":lifecycle_id or None,
            "trading_enabled":False,
        },sort_keys=True))
        return 2

    canonical=None
    if canonical_raw:
        try:
            canonical=datetime.fromisoformat(canonical_raw.replace("Z","+00:00"))
        except ValueError:
            print(json.dumps({"status":"DATA_BLOCKED","diagnostic_code":"INVALID_CANONICAL_REQUESTED_AT","ticker":ticker,"lifecycle_id":lifecycle_id,"trading_enabled":False},sort_keys=True))
            return 2
        if canonical.tzinfo is None:
            print(json.dumps({"status":"DATA_BLOCKED","diagnostic_code":"CANONICAL_REQUESTED_AT_MUST_BE_AWARE","ticker":ticker,"lifecycle_id":lifecycle_id,"trading_enabled":False},sort_keys=True))
            return 2

    import psycopg
    conn=psycopg.connect(db_url)
    now=datetime.now(timezone.utc)
    try:
        try:
            snapshot=capture_market_snapshot(
                conn,ticker=ticker,lifecycle_id=lifecycle_id,run_at=now,
                upstox_token=token,trigger_type=trigger_type,
                target_session=target_session,canonical_requested_at=canonical,
            )
        except AcquisitionError as exc:
            code=safe_diagnostic(exc)
            mark_data_blocked(conn,lifecycle_id,code)
            print(json.dumps({"status":"DATA_BLOCKED","diagnostic_code":code,"ticker":ticker,"lifecycle_id":lifecycle_id,"trading_enabled":False},sort_keys=True))
            return 3
        except Exception as exc:
            mark_data_blocked(conn,lifecycle_id,str(exc))
            print(json.dumps({"status":"DATA_BLOCKED","diagnostic_code":"DATA_STAGE_FAILED","detail":str(exc)[:500],"ticker":ticker,"lifecycle_id":lifecycle_id,"trading_enabled":False},sort_keys=True))
            return 3

        print(json.dumps({
            "status":"DATA_READY",
            "ticker":ticker,
            "lifecycle_id":snapshot.lifecycle_id,
            "market_snapshot_id":snapshot.snapshot_id,
            "captured_at":snapshot.captured_at.isoformat(),
            "research_started":False,
            "computation_started":False,
            "trading_enabled":False,
        },sort_keys=True))
        return 0
    finally:
        conn.close()


if __name__=="__main__":
    raise SystemExit(main())
