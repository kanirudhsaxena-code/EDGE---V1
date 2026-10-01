from datetime import date, datetime, timezone

import pytest

from src.horizon_path_shadow import (
    G5_STOCK_DD4_METHODOLOGY_VERSION,
    build_g5_stock_dd4_forecast_path,
    build_shadow_forecast_path,
)


def _slots():
    dates = ["2026-09-24", "2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30"]
    labels = ["D", "D+1", "D+2", "D+3", "D+4"]
    return [
        {
            "horizon_label": label,
            "target_trading_date": target,
            "direction": "BULL",
            "probabilities": {"BULL": 55.0, "BASE": 30.0, "BEAR": 15.0},
            "expected_centre": 250.0 + i,
            "outer_expected_zone": {"low": 245.0 - i, "high": 255.0 + i},
            "evidence_basis": "stock ATR/liquidity/regime evidence",
            "regime_context": "TREND",
            "verification_state": "VERIFIED",
            "lineage": {"evidence_hash": f"hash-{i}"},
        }
        for i, (label, target) in enumerate(zip(labels, dates))
    ]


def test_builds_five_ordered_shadow_rows_with_lineage():
    path = build_shadow_forecast_path(
        recommendation_id="rec-1",
        source_run_id="run-1",
        issued_at=datetime(2026, 9, 24, 8, 40, tzinfo=timezone.utc),
        horizon_slots=_slots(),
        producer_version="EDGE_STOCK_HORIZON_SHADOW_V1",
    )
    assert [r.horizon_label for r in path.rows] == ["D", "D+1", "D+2", "D+3", "D+4"]
    assert all(r.lineage["mode"] == "SHADOW" for r in path.rows)
    assert all(r.lineage["producer_version"] == "EDGE_STOCK_HORIZON_SHADOW_V1" for r in path.rows)


def test_probability_vector_must_be_complete():
    slots = _slots()
    slots[2]["probabilities"] = {"BULL": 60.0, "BASE": 40.0}
    with pytest.raises(ValueError, match="exactly BULL, BASE and BEAR"):
        build_shadow_forecast_path(
            recommendation_id="rec-2", source_run_id="run-2",
            issued_at=datetime.now(timezone.utc), horizon_slots=slots,
            producer_version="EDGE_STOCK_HORIZON_SHADOW_V1",
        )


def test_stock_centre_must_be_inside_its_own_zone():
    slots = _slots()
    slots[1]["expected_centre"] = 999.0
    with pytest.raises(ValueError, match="inside the stock-specific zone"):
        build_shadow_forecast_path(
            recommendation_id="rec-3", source_run_id="run-3",
            issued_at=datetime.now(timezone.utc), horizon_slots=slots,
            producer_version="EDGE_STOCK_HORIZON_SHADOW_V1",
        )


def test_contract_is_independent_of_trade_action():
    # No trade/recommendation action is an input to the shadow path builder.
    # This proves NO TRADE cannot suppress construction of a valid issuance path.
    path = build_shadow_forecast_path(
        recommendation_id="no-trade-rec", source_run_id="run-4",
        issued_at=datetime.now(timezone.utc), horizon_slots=_slots(),
        producer_version="EDGE_STOCK_HORIZON_SHADOW_V1",
    )
    assert len(path.rows) == 5



def _g5_lineage():
    keys = ["p0","atr14","stock_regime","sector_regime","liquidity","event_gap_risk","calendar"]
    return (
        {k: f"id:{k}" for k in keys},
        {k: "2026-10-01T09:10:00+05:30" for k in keys},
        {k: f"sha256:{k}" for k in keys},
    )


def _g5_path(**overrides):
    source_ids, source_timestamps, source_hashes = _g5_lineage()
    values = dict(
        recommendation_id="rec-g5",
        source_run_id="run-g5",
        issued_at=datetime(2026, 10, 1, 9, 12, tzinfo=timezone.utc),
        p0=268.0,
        atr14=6.7,
        stock_regime="BULLISH",
        sector_regime="NEUTRAL",
        liquidity_state="NORMAL",
        event_gap_risk_state="NO_MATERIAL_RISK",
        target_trading_dates=(
            date(2026,10,1), date(2026,10,5), date(2026,10,6), date(2026,10,7), date(2026,10,8)
        ),
        calendar_version="NSE_CAL_V1",
        source_ids=source_ids,
        source_timestamps=source_timestamps,
        source_hashes=source_hashes,
        canonical_p0_verified=True,
        atr_history_sufficient=True,
        freshness_verified=True,
    )
    values.update(overrides)
    return build_g5_stock_dd4_forecast_path(**values)


def test_g5_v1_builds_exact_five_rows_and_probability_invariants():
    path = _g5_path()
    assert [r.horizon_label for r in path.rows] == ["D","D+1","D+2","D+3","D+4"]
    assert [r.target_trading_date.isoformat() for r in path.rows] == [
        "2026-10-01","2026-10-05","2026-10-06","2026-10-07","2026-10-08"
    ]
    for row in path.rows:
        assert abs(row.bull_probability + row.base_probability + row.bear_probability - 100.0) < 1e-9
        leader = max(
            (("BULL", row.bull_probability), ("BASE", row.base_probability), ("BEAR", row.bear_probability)),
            key=lambda pair: pair[1],
        )[0]
        assert row.direction == leader
        assert row.lineage["producer_version"] == G5_STOCK_DD4_METHODOLOGY_VERSION
        assert row.lineage["methodology_version"] == G5_STOCK_DD4_METHODOLOGY_VERSION


def test_g5_v1_matches_approved_d_horizon_math():
    path = _g5_path()
    row = path.rows[0]
    # Rs=+1, Rsec=0 -> B=.8; Q=1; h=1 -> U=1, Z=.8.
    # Base=.20+.35*(1-.8)+.10*(1-1)=.27
    # Bull=.73*.9=.657; Bear=.073
    assert row.bull_probability == pytest.approx(65.7)
    assert row.base_probability == pytest.approx(27.0)
    assert row.bear_probability == pytest.approx(7.3)
    net_dir = .657 - .073
    expected_centre = 268.0 * (1.0 + net_dir * (6.7 / 268.0))
    assert row.expected_centre == pytest.approx(expected_centre)
    assert row.outer_expected_zone_low == pytest.approx(expected_centre - 6.7)
    assert row.outer_expected_zone_high == pytest.approx(expected_centre + 6.7)


def test_g5_v1_all_horizons_anchor_to_same_frozen_p0():
    path = _g5_path()
    for h, row in enumerate(path.rows, start=1):
        b = 0.8
        q = 1.0
        u = q / (h ** 0.5)
        z = max(-0.8, min(0.8, b * u))
        base = max(0.20, min(0.55, 0.20 + 0.35 * (1 - abs(b)) + 0.10 * (1 - u)))
        bull = (1 - base) * (1 + z) / 2
        bear = (1 - base) * (1 - z) / 2
        expected = 268.0 * (1 + (bull - bear) * (6.7 / 268.0) * h)
        assert row.expected_centre == pytest.approx(expected)


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"canonical_p0_verified": False}, "P0 must be canonical"),
        ({"atr_history_sufficient": False}, "ATR14 requires sufficient"),
        ({"freshness_verified": False}, "freshness/lineage"),
        ({"liquidity_state": "FAIL"}, "liquidity FAIL"),
        ({"stock_regime": "UNKNOWN"}, "stock/sector regime"),
        ({"event_gap_risk_state": "UNVERIFIED"}, "event/gap-risk state"),
    ],
)
def test_g5_v1_fails_closed_on_unapproved_or_unverified_inputs(overrides, match):
    with pytest.raises(ValueError, match=match):
        _g5_path(**overrides)


def test_g5_v1_requires_complete_lineage():
    source_ids, source_timestamps, source_hashes = _g5_lineage()
    source_hashes = dict(source_hashes)
    source_hashes.pop("atr14")
    with pytest.raises(ValueError, match="source_hashes missing required lineage: atr14"):
        _g5_path(source_ids=source_ids, source_timestamps=source_timestamps, source_hashes=source_hashes)


def test_g5_v1_is_deterministic_for_same_frozen_inputs():
    first = _g5_path()
    second = _g5_path()
    first_rows = [
        (
            r.horizon_label, r.target_trading_date, r.direction,
            r.bull_probability, r.base_probability, r.bear_probability,
            r.expected_centre, r.outer_expected_zone_low, r.outer_expected_zone_high,
            dict(r.lineage),
        )
        for r in first.rows
    ]
    second_rows = [
        (
            r.horizon_label, r.target_trading_date, r.direction,
            r.bull_probability, r.base_probability, r.bear_probability,
            r.expected_centre, r.outer_expected_zone_low, r.outer_expected_zone_high,
            dict(r.lineage),
        )
        for r in second.rows
    ]
    assert first_rows == second_rows
