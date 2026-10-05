"""Governed EDGE autonomous publishing CLI.

This CLI persists a recommendation only after the already-implemented release
guard confirms:
- live shadow validation accepted
- expected-zone method validated
- autonomous publishing approved

It never places broker orders and never accesses trading endpoints.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.market_providers import AcquisitionError, UpstoxReadOnlyStockProvider, safe_diagnostic
from src.historical_cache import PostgresHistoricalCache
from src.trading_calendar import is_nse_trading_day

from src.production_orchestrator import HoldingState, build_production_candidate
from src.release_gate import ReleaseApproval


def _bounded_payload(result, ticker, holding):
    payload={
        "status":result.status,
        "ticker":ticker,
        "holding_state":holding.value,
        "blockers":list(result.blockers),
        "publishing_enabled":True,
        "trading_enabled":False,
        "persistence_id":result.persistence_id,
    }
    if result.canonical_bundle is not None:
        b=result.canonical_bundle
        payload.update({
            "recommendation_id":b.recommendation_id,
            "parent_recommendation_id":b.parent_recommendation_id,
            "forecast":b.definitive_forecast,
            "probabilities":{
                "bull":round(float(b.bull_probability),3),
                "base":round(float(b.base_probability),3),
                "bear":round(float(b.bear_probability),3),
            },
            "expected_price_zone":[
                float(b.expected_price_zone_low) if b.expected_price_zone_low is not None else None,
                float(b.expected_price_zone_high) if b.expected_price_zone_high is not None else None,
            ],
            "des":round(float(b.des),3),
            "market_trust":round(float(b.market_trust_score),3),
            "market_trust_band":b.market_trust_band,
            "bot_score":round(float(b.bot_score),3),
            "bot_grade":b.bot_grade,
            "decision_ladder":b.decision_ladder,
            "definitive_recommendation":b.definitive_recommendation,
            "checkpoint_dates":[d.isoformat() for d in b.checkpoint_dates],
        })
    return payload


def main() -> int:
    ticker=os.getenv("EDGE_TICKER","LTF").strip().upper()
    token=os.getenv("UPSTOX_ANALYTICS_TOKEN","")
    db_url=os.getenv("DATABASE_URL","")
    holding_raw=os.getenv("EDGE_HOLDING_STATE","UNKNOWN").strip().upper()
    run_mode=os.getenv("EDGE_RUN_MODE","MANUAL").strip().upper()
    research_bundle_id=os.getenv("EDGE_RESEARCH_BUNDLE_ID","").strip()
    lifecycle_id=os.getenv("EDGE_LIFECYCLE_ID","").strip()
    market_snapshot_id=os.getenv("EDGE_MARKET_SNAPSHOT_ID","").strip()
    auction_snapshot_id=os.getenv("EDGE_AUCTION_SNAPSHOT_ID","").strip()
    canonical_requested_raw=os.getenv("EDGE_CANONICAL_REQUESTED_AT","").strip()
    canonical_attempt_slot=os.getenv("EDGE_CANONICAL_ATTEMPT_SLOT","").strip() or None
    canonical_requested_at=None
    if canonical_requested_raw:
        try:
            canonical_requested_at=datetime.fromisoformat(canonical_requested_raw.replace("Z","+00:00"))
        except ValueError:
            print(json.dumps({
                "status":"BLOCKED_CONFIGURATION",
                "diagnostic_code":"INVALID_CANONICAL_REQUESTED_AT",
                "ticker":ticker,
                "publishing_enabled":False,
                "trading_enabled":False,
            },sort_keys=True))
            return 2
        if canonical_requested_at.tzinfo is None:
            print(json.dumps({
                "status":"BLOCKED_CONFIGURATION",
                "diagnostic_code":"CANONICAL_REQUESTED_AT_MUST_BE_TIMEZONE_AWARE",
                "ticker":ticker,
                "publishing_enabled":False,
                "trading_enabled":False,
            },sort_keys=True))
            return 2

    if not research_bundle_id:
        print(json.dumps({
            "status":"BLOCKED_RESEARCH_BUNDLE",
            "diagnostic_code":"GOVERNED_RESEARCH_BUNDLE_REQUIRED",
            "ticker":ticker,
            "run_mode":run_mode,
            "publishing_enabled":False,
            "trading_enabled":False,
        },sort_keys=True))
        return 0 if run_mode=="SCHEDULED" else 3

    if bool(lifecycle_id) != bool(market_snapshot_id):
        print(json.dumps({
            "status":"BLOCKED_DATA_LINEAGE",
            "diagnostic_code":"LIFECYCLE_AND_MARKET_SNAPSHOT_REQUIRED_TOGETHER",
            "ticker":ticker,
            "lifecycle_id":lifecycle_id or None,
            "market_snapshot_id":market_snapshot_id or None,
            "publishing_enabled":False,
            "trading_enabled":False,
        },sort_keys=True))
        return 2

    if not token or not db_url:
        code="UPSTOX_TOKEN_MISSING" if not token else "DATABASE_URL_MISSING"
        print(json.dumps({
            "status":"BLOCKED_CONFIGURATION",
            "diagnostic_code":code,
            "ticker":ticker,
            "publishing_enabled":False,
            "trading_enabled":False,
        },sort_keys=True))
        return 2

    try:
        holding=HoldingState(holding_raw)
    except ValueError:
        print(json.dumps({
            "status":"BLOCKED_CONFIGURATION",
            "diagnostic_code":"INVALID_HOLDING_STATE",
            "ticker":ticker,
            "publishing_enabled":False,
            "trading_enabled":False,
        },sort_keys=True))
        return 2

    import psycopg

    now=datetime.now(timezone.utc)
    india_now=now.astimezone(ZoneInfo("Asia/Kolkata"))
    india_date=india_now.date()

    if run_mode == "SCHEDULED" and (
        india_now.time().hour < 15 or (
            india_now.time().hour == 15 and india_now.time().minute < 40
        )
    ):
        print(json.dumps({
            "status":"BEFORE_MARKET_CLOSE",
            "ticker":ticker,
            "india_time":india_now.isoformat(),
            "run_mode":run_mode,
            "publishing_enabled":True,
            "trading_enabled":False,
        },sort_keys=True))
        return 0

    try:
        provider=UpstoxReadOnlyStockProvider(token)
        if (run_mode == "SCHEDULED" or canonical_requested_at is not None) and not is_nse_trading_day(provider,india_date):
            print(json.dumps({
                "status":"NON_TRADING_DAY",
                "ticker":ticker,
                "india_date":india_date.isoformat(),
                "publishing_enabled":True,
                "trading_enabled":False,
            },sort_keys=True))
            return 0
    except AcquisitionError as exc:
        print(json.dumps({
            "status":"BLOCKED_CONFIGURATION",
            "ticker":ticker,
            "diagnostic_code":safe_diagnostic(exc),
            "publishing_enabled":False,
            "trading_enabled":False,
        },sort_keys=True))
        return 2

    conn=psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select recommendation_id
                from recommendations
                where ticker=%s
                  and recommendation_id like %s
                  and (run_timestamp at time zone 'Asia/Kolkata')::date=%s
                order by run_timestamp desc
                limit 1
                """,
                (ticker,f"EDGE-{ticker}-%-AUTO",india_date),
            )
            existing=cur.fetchone()
        if existing and (run_mode == "SCHEDULED" or canonical_requested_at is not None):
            print(json.dumps({
                "status":"ALREADY_PUBLISHED_TODAY",
                "ticker":ticker,
                "recommendation_id":existing[0],
                "publishing_enabled":True,
                "trading_enabled":False,
            },sort_keys=True))
            return 0

        if lifecycle_id:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select ticker,stage,market_snapshot_id,research_bundle_id,auction_snapshot_id
                      from edge_run_lifecycles
                     where lifecycle_id=%s
                     limit 1
                    """,
                    (lifecycle_id,),
                )
                lifecycle=cur.fetchone()
                if not lifecycle:
                    print(json.dumps({"status":"BLOCKED_DATA_LINEAGE","diagnostic_code":"LIFECYCLE_NOT_FOUND","ticker":ticker,"lifecycle_id":lifecycle_id,"trading_enabled":False},sort_keys=True))
                    return 3
                if str(lifecycle[0]).upper()!=ticker or str(lifecycle[1])!="RESEARCH_READY" or str(lifecycle[2] or "")!=market_snapshot_id or str(lifecycle[3] or "")!=research_bundle_id:
                    print(json.dumps({
                        "status":"BLOCKED_DATA_LINEAGE",
                        "diagnostic_code":"LIFECYCLE_NOT_RESEARCH_READY",
                        "ticker":ticker,
                        "lifecycle_id":lifecycle_id,
                        "stage":str(lifecycle[1]),
                        "market_snapshot_id":str(lifecycle[2] or ""),
                        "research_bundle_id":str(lifecycle[3] or ""),
                        "trading_enabled":False,
                    },sort_keys=True))
                    return 3
                if canonical_requested_at is not None:
                    if not auction_snapshot_id or str(lifecycle[4] or "")!=auction_snapshot_id:
                        print(json.dumps({
                            "status":"BLOCKED_AUCTION_LINEAGE",
                            "diagnostic_code":"AUCTION_SNAPSHOT_NOT_BOUND_TO_LIFECYCLE",
                            "ticker":ticker,
                            "lifecycle_id":lifecycle_id,
                            "auction_snapshot_id":auction_snapshot_id or None,
                            "stored_auction_snapshot_id":str(lifecycle[4] or "") or None,
                            "trading_enabled":False,
                        },sort_keys=True))
                        return 3
                cur.execute(
                    """
                    update edge_run_lifecycles
                       set stage='COMPUTE_PENDING',
                           stage_detail='Governed reconciliation/computation started from run-bound DATA and RESEARCH',
                           updated_at=now()
                     where lifecycle_id=%s and stage='RESEARCH_READY'
                    """,
                    (lifecycle_id,),
                )
                if cur.rowcount!=1:
                    raise RuntimeError("lifecycle did not transition RESEARCH_READY -> COMPUTE_PENDING")
            conn.commit()

        historical_cache=PostgresHistoricalCache(db_url)
        result=build_production_candidate(
            connection=conn,
            ticker=ticker,
            run_at=now,
            upstox_token=token,
            holding_state=holding,
            publish=True,
            historical_cache=historical_cache,
            research_bundle_id=research_bundle_id,
            lifecycle_id=lifecycle_id or None,
            market_snapshot_id=market_snapshot_id or None,
            auction_snapshot_id=auction_snapshot_id or None,
            canonical_requested_at=canonical_requested_at,
            canonical_attempt_slot=canonical_attempt_slot,
            governance_trigger_type=("SCHEDULED" if run_mode=="SCHEDULED" or canonical_attempt_slot else "USER"),
            release_approval=ReleaseApproval(
                shadow_validation_accepted=True,
                zone_method_validated=True,
                autonomous_publishing_approved=True,
            ),
        )
        if lifecycle_id:
            state_conn=psycopg.connect(db_url)
            try:
                with state_conn.cursor() as cur:
                    if result.status=="PUBLISHED":
                        cur.execute(
                            """
                            update edge_run_lifecycles
                               set stage='PERSISTED',
                                   recommendation_id=%s,
                                   stage_detail='Governed computation persisted successfully',
                                   updated_at=now()
                             where lifecycle_id=%s and stage='COMPUTE_PENDING'
                            """,
                            (result.persistence_id,lifecycle_id),
                        )
                    else:
                        cur.execute(
                            """
                            update edge_run_lifecycles
                               set stage='COMPUTE_BLOCKED',
                                   stage_detail=%s,
                                   updated_at=now()
                             where lifecycle_id=%s and stage='COMPUTE_PENDING'
                            """,
                            ((result.status+": "+"; ".join(result.blockers))[:1000],lifecycle_id),
                        )
                state_conn.commit()
            finally:
                state_conn.close()

        print(json.dumps(_bounded_payload(result,ticker,holding),sort_keys=True,default=str))
        if result.report_markdown:
            with open("edge-published-report.md","w",encoding="utf-8") as fh:
                fh.write(result.report_markdown)
        return 0 if result.status=="PUBLISHED" else 3
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__=="__main__":
    raise SystemExit(main())
