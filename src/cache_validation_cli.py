"""Validation-only production gate for EDGE durable historical cache.

Seeds daily EDGE_STOCK and NIFTY50 series through authenticated Upstox if absent,
then proves a second read succeeds from Neon with the network boundary disabled.
No recommendation, scoring, learning, checkpoint, or trading writes occur.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from src.historical_cache import PostgresHistoricalCache
from src.market_providers import NIFTY_50, UpstoxReadOnlyStockProvider


class NetworkForbidden:
    def open(self, *args, **kwargs):
        raise AssertionError("provider network call occurred after cache was seeded")


def _candle_dates(envelope):
    data=envelope.payload.get("data") if isinstance(envelope.payload,dict) else None
    candles=data.get("candles") if isinstance(data,dict) else None
    if not isinstance(candles,list) or not candles:
        raise RuntimeError("validation candles missing")
    dates=[]
    for row in candles:
        if not isinstance(row,list) or not row:
            continue
        stamp=datetime.fromisoformat(str(row[0]).replace("Z","+00:00"))
        if stamp.tzinfo is None:
            raise RuntimeError("validation candle timestamp naive")
        dates.append(stamp.date())
    if not dates:
        raise RuntimeError("validation candle dates missing")
    return min(dates),max(dates),len(candles)


def _validate_series(provider, cache, instrument_key, start, end):
    first=provider.daily(instrument_key,start,end)
    first_start,first_end,count=_candle_dates(first)

    direct_cached=cache.read_daily(instrument_key,first_start,first_end)
    if direct_cached is None:
        raise RuntimeError("direct cache readback returned MISS")

    cached_provider=UpstoxReadOnlyStockProvider(
        "validation-placeholder-token",
        opener=NetworkForbidden(),
        sleep=lambda _:None,
        historical_cache=cache,
    )
    second=cached_provider.daily(instrument_key,first_start,first_end)
    if not second.source_ref.startswith("upstox:cache:EDGE_STOCK:PRICE_CANDLES:"):
        raise RuntimeError("cache readback did not use durable EDGE cache")
    second_start,second_end,second_count=_candle_dates(second)
    if (second_start,second_end,second_count)!=(first_start,first_end,count):
        raise RuntimeError("cache readback coverage mismatch")
    return {
        "instrument_key":instrument_key,
        "first_source":"CACHE" if first.source_ref.startswith("upstox:cache:") else "UPSTOX_WRITE_THROUGH",
        "readback_source":"CACHE",
        "start":first_start.isoformat(),
        "end":first_end.isoformat(),
        "candle_count":count,
    }


def main():
    token=os.getenv("UPSTOX_ANALYTICS_TOKEN","").strip()
    db_url=os.getenv("DATABASE_URL","").strip()
    ticker=os.getenv("EDGE_CACHE_VALIDATION_TICKER","LTF").strip().upper()
    if not token or not db_url:
        print(json.dumps({"status":"BLOCKED_CONFIGURATION"}))
        return 2

    cache=PostgresHistoricalCache(db_url)
    provider=UpstoxReadOnlyStockProvider(
        token,
        historical_cache=cache,
    )
    instrument_key,_=provider.resolve_nse_equity(ticker)
    end=datetime.now(timezone.utc).date()
    start=end-timedelta(days=45)

    stock=_validate_series(provider,cache,instrument_key,start,end)
    benchmark=_validate_series(provider,cache,NIFTY_50,start,end)

    print(json.dumps({
        "schema":"edge-shared-cache-production-gate-v1",
        "status":"PASS",
        "ticker":ticker,
        "stock":stock,
        "benchmark":benchmark,
        "recommendation_write":False,
        "checkpoint_write":False,
        "learning_write":False,
        "trading_enabled":False,
        "methodology_changed":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
