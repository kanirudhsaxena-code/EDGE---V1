"""Live non-publishing EDGE production-candidate CLI.

Safe output only: no database URL, Upstox token, provider raw payloads, or
credentials are printed. Publish mode is permanently false in this CLI.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.production_orchestrator import (
    HoldingState,
    build_production_candidate,
)


def main() -> int:
    ticker=os.getenv("EDGE_TICKER","LTF").strip().upper()
    token=os.getenv("UPSTOX_ANALYTICS_TOKEN","")
    db_url=os.getenv("DATABASE_URL","")
    holding_raw=os.getenv("EDGE_HOLDING_STATE","UNKNOWN").strip().upper()

    if not token:
        print(json.dumps({
            "status":"BLOCKED_CONFIGURATION",
            "diagnostic_code":"UPSTOX_TOKEN_MISSING",
            "ticker":ticker,
        },sort_keys=True))
        return 2
    if not db_url:
        print(json.dumps({
            "status":"BLOCKED_CONFIGURATION",
            "diagnostic_code":"DATABASE_URL_MISSING",
            "ticker":ticker,
        },sort_keys=True))
        return 2
    try:
        holding=HoldingState(holding_raw)
    except ValueError:
        print(json.dumps({
            "status":"BLOCKED_CONFIGURATION",
            "diagnostic_code":"INVALID_HOLDING_STATE",
            "ticker":ticker,
        },sort_keys=True))
        return 2

    import psycopg

    conn=psycopg.connect(db_url)
    try:
        result=build_production_candidate(
            connection=conn,
            ticker=ticker,
            run_at=datetime.now(timezone.utc),
            upstox_token=token,
            holding_state=holding,
            publish=False,
        )
        payload={
            "status":result.status,
            "ticker":ticker,
            "holding_state":holding.value,
            "blockers":list(result.blockers),
            "publishing_enabled":False,
            "trading_enabled":False,
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
                "execution":{
                    "instrument":b.execution_plan.instrument,
                    "entry_low":b.execution_plan.entry_low,
                    "entry_high":b.execution_plan.entry_high,
                    "stop":b.execution_plan.stop_price,
                    "target1":b.execution_plan.target1,
                    "target2":b.execution_plan.target2,
                    "rr_t1":b.execution_plan.rr_t1,
                    "rr_t2":b.execution_plan.rr_t2,
                    "execution_quality_score":b.execution_plan.execution_quality_score,
                    "execution_quality_level":b.execution_plan.execution_quality_level,
                    "option_suitability_status":b.execution_plan.option_suitability_status,
                },
            })
        print(json.dumps(payload,sort_keys=True,default=str))
        if result.report_markdown:
            with open("edge-production-candidate-report.md","w",encoding="utf-8") as fh:
                fh.write(result.report_markdown)
        return 0 if result.status=="PRODUCTION_CANDIDATE_READY" else 3
    finally:
        conn.close()


if __name__=="__main__":
    raise SystemExit(main())
