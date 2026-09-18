from src.zone_engine import derive_structure_context, expected_price_zone


def synthetic():
    rows=[]
    vals=[100,101,102,103,104,103,102,101,100,99,100,101,102,103,104,105,104,103,102,101,
          100,101,102,103,104,105,106,105,104,103,102,101,100,99,98,99,100,101,102,103,
          104,105,106,107,106,105,104,103,102,101,100,101,102,103,104,105,104,103,102,103]
    for i,c in enumerate(vals):
        o=c-0.2
        rows.append([f"2026-01-{(i%28)+1:02d}",o,c+0.8,c-0.8,c,1000+i,0])
    return rows


def test_base_zone_uses_nearest_structural_levels_and_is_compact():
    ctx=derive_structure_context(synthetic(),pattern_name="RANGE")
    z=expected_price_zone(ctx,"BASE_RANGE")
    assert z.low < ctx.close < z.high
    assert z.width_pct < 12
    assert z.basis == "NEAREST_SUPPORT_RESISTANCE"


def test_bullish_zone_uses_resistance_objectives():
    ctx=derive_structure_context(synthetic(),pattern_name="TREND_CONTINUATION")
    z=expected_price_zone(ctx,"BULLISH")
    assert z.low >= ctx.close
    assert z.high > z.low
    assert z.resistance_used is not None


def test_bearish_zone_uses_support_objectives():
    ctx=derive_structure_context(synthetic(),pattern_name="TREND_CONTINUATION")
    z=expected_price_zone(ctx,"BEARISH")
    assert z.high <= ctx.close
    assert z.low < z.high
    assert z.support_used is not None


def test_missing_two_sided_structure_blocks_base_zone():
    from src.zone_engine import MarketStructureContext
    ctx=MarketStructureContext(100.0,(95.0,),(),2.0,"RANGE")
    try:
        expected_price_zone(ctx,"BASE_RANGE")
    except ValueError as exc:
        assert "support and resistance" in str(exc)
    else:
        raise AssertionError("must fail closed")


def test_overly_broad_structure_blocks_release_candidate():
    from src.zone_engine import MarketStructureContext
    ctx=MarketStructureContext(100.0,(80.0,),(120.0,),2.0,"RANGE")
    try:
        expected_price_zone(ctx,"BASE_RANGE")
    except ValueError as exc:
        assert "too broad" in str(exc)
    else:
        raise AssertionError("broad zone must fail closed")
