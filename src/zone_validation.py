"""Historical LTF zone-validation harness.

Replays only the structure-based expected-zone implementation against immutable
manual EDGE LTF zones already recorded for 15/16/17 Sep 2026. It uses only
candles available up to each replay date and does not alter any historical
recommendation, score or probability.

The output is diagnostic: overlap, centre error and relative width. No
methodology threshold is introduced here.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta

from src.autonomous_interpreter import _candles
from src.market_providers import UpstoxReadOnlyStockProvider
from src.zone_engine import derive_structure_context, expected_price_zone


CASES = (
    {
        "date": date(2026,9,15),
        "forecast": "BEARISH",
        "manual_zone": (288.0,304.0),
    },
    {
        "date": date(2026,9,16),
        "forecast": "BASE_RANGE",
        "manual_zone": (288.0,304.0),
    },
    {
        "date": date(2026,9,17),
        "forecast": "BASE_RANGE",
        "manual_zone": (298.0,315.0),
    },
)


def _metrics(proposed, manual):
    pl,ph=proposed
    ml,mh=manual
    inter=max(0.0,min(ph,mh)-max(pl,ml))
    mwidth=max(0.0001,mh-ml)
    pwidth=max(0.0001,ph-pl)
    pmid=(pl+ph)/2.0
    mmid=(ml+mh)/2.0
    return {
        "manual_overlap_pct": round(inter/mwidth*100.0,3),
        "centre_error_points": round(abs(pmid-mmid),3),
        "proposed_width": round(pwidth,3),
        "manual_width": round(mwidth,3),
        "width_ratio": round(pwidth/mwidth,3),
    }


def run(token: str) -> dict:
    provider=UpstoxReadOnlyStockProvider(token)
    key,_=provider.resolve_nse_equity("LTF")
    results=[]
    for case in CASES:
        end=case["date"]
        env=provider.daily(key,end-timedelta(days=120),end)
        candles=_candles(env.payload)
        ctx=derive_structure_context(candles,pattern_name="HISTORICAL_REPLAY")
        zone=expected_price_zone(ctx,case["forecast"])
        proposed=(zone.low,zone.high)
        results.append({
            "date":end.isoformat(),
            "forecast":case["forecast"],
            "manual_zone":list(case["manual_zone"]),
            "proposed_zone":[round(zone.low,3),round(zone.high,3)],
            "basis":zone.basis,
            "width_pct":round(zone.width_pct,3),
            **_metrics(proposed,case["manual_zone"]),
        })
    return {
        "ticker":"LTF",
        "validation_type":"STRUCTURE_ZONE_HISTORICAL_REPLAY",
        "cases":results,
        "publishing_enabled":False,
        "historical_records_modified":False,
    }


if __name__=="__main__":
    token=os.getenv("UPSTOX_ANALYTICS_TOKEN","")
    print(json.dumps(run(token),sort_keys=True))
