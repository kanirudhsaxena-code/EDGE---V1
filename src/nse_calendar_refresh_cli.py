"""Refresh and persist the governed NSE calendar/session cache."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.market_providers import AcquisitionError, UpstoxReadOnlyStockProvider, safe_diagnostic
from src.trading_calendar import (
    classify_exact_nse_session,
    parse_nse_calendar_entries,
    should_fetch_exact_nse_timing,
)

IST=ZoneInfo("Asia/Kolkata")


def _stable_hash(value)->str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def main()->int:
    token=os.getenv("UPSTOX_ANALYTICS_TOKEN","").strip()
    db_url=os.getenv("DATABASE_URL","").strip()
    target_raw=os.getenv("EDGE_SESSION_DATE","").strip()
    if not token or not db_url:
        print(json.dumps({
            "status":"BLOCKED_CONFIGURATION",
            "diagnostic_code":"UPSTOX_TOKEN_MISSING" if not token else "DATABASE_URL_MISSING",
            "trading_enabled":False,
        },sort_keys=True))
        return 2

    try:
        target=date.fromisoformat(target_raw) if target_raw else datetime.now(IST).date()
    except ValueError:
        print(json.dumps({"status":"BLOCKED_CONFIGURATION","diagnostic_code":"INVALID_SESSION_DATE","trading_enabled":False},sort_keys=True))
        return 2

    try:
        provider=UpstoxReadOnlyStockProvider(token)
        holiday_env=provider.market_holidays()
        entries=parse_nse_calendar_entries(holiday_env.payload)
        snapshot_year=holiday_env.received_at.astimezone(IST).year
        if snapshot_year!=target.year:
            # The annual endpoint is documented as current-year only. For a
            # non-current target, exact timing remains authoritative but we do
            # not persist a falsely-labelled annual snapshot.
            annual_payload=None
        else:
            annual_payload={
                "calendar_year":snapshot_year,
                "trading_holidays":sorted(d.isoformat() for d in entries.trading_holidays),
                "special_timing_dates":sorted(d.isoformat() for d in entries.special_timing_dates),
                "provider":"UPSTOX",
                "source_ref":holiday_env.source_ref,
                "acquired_at":holiday_env.received_at.isoformat(),
            }

        timing_env=None
        timing_payload=None
        # A verified trading-holiday row is already sufficient closed-session
        # authority. Do not make a needless timings request that could turn an
        # expected market closure into provider-error noise.
        if should_fetch_exact_nse_timing(target,entries):
            timing_env=provider.market_timings(target)
            timing_payload=timing_env.payload
        exact=classify_exact_nse_session(target,holiday_env.payload,timing_payload)

    except (AcquisitionError,ValueError) as exc:
        print(json.dumps({
            "status":"BLOCKED_PROVIDER_CALENDAR",
            "target_date":target.isoformat(),
            "diagnostic_code":safe_diagnostic(exc) if isinstance(exc,AcquisitionError) else "CALENDAR_VALIDATION_FAILED",
            "detail":str(exc)[:300],
            "trading_enabled":False,
        },sort_keys=True))
        return 3

    import psycopg
    conn=psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            if annual_payload is not None:
                annual_hash=_stable_hash(annual_payload)
                cur.execute(
                    """
                    INSERT INTO nse_calendar_year_snapshots(
                      calendar_year,provider,status,trading_holidays,special_timing_dates,
                      source_ref,acquired_at,payload_hash
                    ) VALUES (%s,'UPSTOX','VERIFIED',%s::jsonb,%s::jsonb,%s,%s,%s)
                    ON CONFLICT (calendar_year,payload_hash) DO NOTHING
                    """,
                    (
                        annual_payload["calendar_year"],
                        json.dumps(annual_payload["trading_holidays"]),
                        json.dumps(annual_payload["special_timing_dates"]),
                        annual_payload["source_ref"],
                        holiday_env.received_at,
                        annual_hash,
                    ),
                )

            acquired=max(
                [holiday_env.received_at]+([timing_env.received_at] if timing_env else [])
            )
            proof_payload={
                "session_date":target.isoformat(),
                "session_state":exact.state,
                "preopen_eligible":exact.preopen_eligible,
                "market_open_at":exact.market_open_at.isoformat() if exact.market_open_at else None,
                "market_close_at":exact.market_close_at.isoformat() if exact.market_close_at else None,
                "calendar_source_ref":holiday_env.source_ref,
                "timing_source_ref":timing_env.source_ref if timing_env else None,
                "acquired_at":acquired.isoformat(),
            }
            proof_hash=_stable_hash(proof_payload)
            cur.execute(
                """
                INSERT INTO nse_session_proofs(
                  session_date,session_state,preopen_eligible,market_open_at,market_close_at,
                  provider,timing_source_ref,calendar_source_ref,acquired_at,payload,payload_hash,status
                ) VALUES (%s,%s,%s,%s,%s,'UPSTOX',%s,%s,%s,%s::jsonb,%s,'VERIFIED')
                ON CONFLICT (session_date,payload_hash) DO NOTHING
                """,
                (
                    target,
                    exact.state,
                    exact.preopen_eligible,
                    exact.market_open_at,
                    exact.market_close_at,
                    timing_env.source_ref if timing_env else None,
                    holiday_env.source_ref,
                    acquired,
                    json.dumps(proof_payload,sort_keys=True),
                    proof_hash,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    print(json.dumps({
        "status":"NSE_CALENDAR_REFRESHED",
        "target_date":target.isoformat(),
        "session_state":exact.state,
        "preopen_eligible":exact.preopen_eligible,
        "market_open_at":exact.market_open_at.isoformat() if exact.market_open_at else None,
        "market_close_at":exact.market_close_at.isoformat() if exact.market_close_at else None,
        "calendar_year_cached":annual_payload["calendar_year"] if annual_payload else None,
        "provider":"UPSTOX",
        "trading_enabled":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())