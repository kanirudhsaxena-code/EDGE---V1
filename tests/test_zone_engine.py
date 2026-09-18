from src.zone_engine import MarketStructureContext, derive_structure_context, expected_price_zone


def synthetic():
    rows=[]
    vals=[100,101,102,103,104,103,102,101,100,99,100,101,102,103,104,105,104,103,102,101,
          100,101,102,103,104,105,106,105,104,103,102,101,100,99,98,99,100,101,102,103,
          104,105,106,107,106,105,104,103,102,101,100,101,102,103,104,105,104,103,102,103]
    for i,c in enumerate(vals):
        o=c-0.2
        rows.append([f"2026-01-{(i%28)+1:02d}",o,c+0.8,c-0.8,c,1000+i,0])
    return rows


def test_expected_zone_is_two_sided_for_all_forecasts():
    ctx=derive_structure_context(synthetic(),pattern_name="RANGE")
    zones=[expected_price_zone(ctx,f) for f in ("BASE_RANGE","BULLISH","BEARISH")]
    for z in zones:
        assert z.low < ctx.close < z.high
        assert z.width_pct < 12
        assert z.basis == "VOLATILITY_STRUCTURE_ENVELOPE"


def test_nearby_material_support_can_tighten_lower_boundary():
    ctx=MarketStructureContext(
        close=100.0,
        supports=(96.0,90.0),
        resistances=(110.0,),
        median_true_range=5.0,
        pattern_name="RANGE",
    )
    z=expected_price_zone(ctx,"BASE_RANGE")
    # baseline low is 95; support at 96 is material and tightens the lower edge.
    assert abs(z.low-96.0) < 1e-9
    assert z.support_used == 96.0


def test_nearby_material_resistance_can_extend_upper_boundary():
    ctx=MarketStructureContext(
        close=100.0,
        supports=(90.0,),
        resistances=(106.0,120.0),
        median_true_range=5.0,
        pattern_name="RANGE",
    )
    z=expected_price_zone(ctx,"BASE_RANGE")
    # baseline high is 105; 106 resistance is material and receives a small
    # observed-volatility tolerance, extending the envelope.
    assert z.high > 106.0
    assert z.resistance_used == 106.0


def test_micro_levels_do_not_collapse_zone():
    ctx=MarketStructureContext(
        close=100.0,
        supports=(99.5,),
        resistances=(100.5,),
        median_true_range=5.0,
        pattern_name="RANGE",
    )
    z=expected_price_zone(ctx,"BASE_RANGE")
    assert abs(z.low-95.0) < 1e-9
    assert abs(z.high-105.0) < 1e-9
    assert z.support_used is None
    assert z.resistance_used is None


def test_invalid_context_fails_closed():
    ctx=MarketStructureContext(100.0,(),(),0.0,"RANGE")
    try:
        expected_price_zone(ctx,"BASE_RANGE")
    except ValueError as exc:
        assert "invalid market structure" in str(exc)
    else:
        raise AssertionError("invalid structure context must fail closed")
