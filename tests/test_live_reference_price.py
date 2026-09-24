from src.production_orchestrator import _live_reference_price, _rebase_structure_context
from src.zone_engine import MarketStructureContext


def test_live_reference_price_uses_authenticated_upstox_quote():
    payloads={
        "upstox:/v3/market-quote/quotes?instrument_key=NSE_EQ%7CINE498L01015#sha256=abc": {
            "status":"success",
            "data":{
                "NSE_EQ:INE498L01015":{
                    "last_price":312.70,
                    "ohlc":{"close":310.00},
                }
            },
        },
        "upstox:/v3/historical-candle/NSE_EQ%7CINE498L01015/days/1/2026-09-24/2026-03-28#sha256=def": {
            "status":"success",
            "data":{"candles":[["2026-09-23T00:00:00+05:30",307.85,312.65,307.85,310.00,1000,0]]},
        },
    }
    assert _live_reference_price(payloads) == 312.70


def test_rebase_structure_context_reclassifies_levels_around_live_price():
    ctx=MarketStructureContext(
        close=310.00,
        supports=(308.00,303.00),
        resistances=(312.00,318.00),
        median_true_range=5.00,
        pattern_name="RANGE",
    )
    rebased=_rebase_structure_context(ctx,312.70)
    assert rebased.close == 312.70
    assert rebased.supports == (312.00,308.00,303.00)
    assert rebased.resistances == (318.00,)
