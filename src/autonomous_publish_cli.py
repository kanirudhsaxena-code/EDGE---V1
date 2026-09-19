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

    if not research_bundle_id:
        print(json.dumps({
            "status":"BLOCKED_RESEARCH_BUNDLE",
            "diagnostic_code":"CHATGPT_RESEARCH_BUNDLE_REQUIRED",
            "ticker":ticker,
            "run_mode":run_mode,
            "publishing_enabled":False,
            "trading_enabled":False,
        },sort_keys=True))
        return 0 if run_mode=="SCHEDULED" else 3

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
        if run_mode == "SCHEDULED" and not is_nse_trading_day(provider,india_date):
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
        if existing and run_mode == "SCHEDULED":
            print(json.dumps({
                "status":"ALREADY_PUBLISHED_TODAY",
                "ticker":ticker,
                "recommendation_id":existing[0],
                "publishing_enabled":True,
                "trading_enabled":False,
            },sort_keys=True))
            return 0

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
            release_approval=ReleaseApproval(
                shadow_validation_accepted=True,
                zone_method_validated=True,
                autonomous_publishing_approved=True,
            ),
        )
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
