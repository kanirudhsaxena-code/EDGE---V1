from datetime import date, datetime, timedelta, timezone

import pytest

from src.g5_issuance_inputs import (
    G5InputError,
    G5IssuanceInputs,
    compute_atr14,
    candles_from_payload,
    event_gap_risk_state,
    extract_profile_sector,
    lineage_from_source,
    liquidity_state_from_ratio,
    liquidity_ratio,
    producer_lineage_maps,
    regime_from_candles,
    regime_from_price_structure,
    sector_benchmark_name,
    stock_daily_payload,
)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_liquidity_inputs_fail_closed(bad):
    with pytest.raises(G5InputError):
        liquidity_state_from_ratio(bad)
    rows = _trend_candles(25)
    rows[-1][5] = bad
    with pytest.raises(G5InputError):
        liquidity_ratio(rows)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_invalid_atr_ohlc_fails_closed(bad):
    rows = _trend_candles(15)
    rows[-1][2] = bad
    with pytest.raises(G5InputError):
        compute_atr14(rows)


def test_malformed_candle_is_rejected_instead_of_silently_dropped():
    rows = _trend_candles(30)
    rows.insert(10, ["2026-01-11"])
    with pytest.raises(G5InputError, match="malformed"):
        candles_from_payload({"data": {"candles": rows}})


def _trend_candles(n=60, start=100.0, step=1.0, volume=1000.0):
    rows = []
    day = date(2026, 1, 1)
    for i in range(n):
        close = start + i * step
        rows.append([
            (day + timedelta(days=i)).isoformat(),
            close - 0.5,
            close + 1.0,
            close - 1.0,
            close,
            volume,
        ])
    return rows


def test_atr14_uses_true_range_and_requires_fifteen_completed_bars():
    rows = [["2026-01-01", 99.0, 101.0, 98.0, 100.0, 1000.0]]
    prev_close = 100.0
    for i in range(1, 15):
        close = prev_close + 2.0
        rows.append([
            f"2026-01-{i+1:02d}",
            prev_close + 1.0,
            prev_close + 3.0,
            prev_close + 1.0,
            close,
            1000.0,
        ])
        prev_close = close
    assert compute_atr14(rows) == pytest.approx(3.0)
    with pytest.raises(G5InputError, match="15 completed"):
        compute_atr14(rows[-14:])


def test_rs_bridge_reuses_frozen_price_structure_classifier():
    assert regime_from_price_structure(2) == "BULLISH"
    assert regime_from_price_structure(0) == "NEUTRAL"
    assert regime_from_price_structure(-2) == "BEARISH"
    assert regime_from_candles(_trend_candles()) == "BULLISH"


@pytest.mark.parametrize(
    "ratio,expected",
    [
        (0.75, "NORMAL"),
        (1.20, "NORMAL"),
        (0.40, "CAUTION"),
        (0.7499, "CAUTION"),
        (0.3999, "WEAK"),
    ],
)
def test_liquidity_thresholds_are_exactly_the_approved_boundaries(ratio, expected):
    assert liquidity_state_from_ratio(ratio) == expected


def test_event_risk_bridge_is_fail_closed_and_preserves_override_severity():
    assert event_gap_risk_state(event_shock_raw_score=0, active_override=None) == "NO_MATERIAL_RISK"
    assert event_gap_risk_state(event_shock_raw_score=-1, active_override=None) == "MODERATE"
    assert event_gap_risk_state(event_shock_raw_score=0, active_override="O1") == "HIGH_RISK"
    assert event_gap_risk_state(event_shock_raw_score=-1, active_override="O3") == "HIGH_RISK"
    with pytest.raises(G5InputError, match="not verified"):
        event_gap_risk_state(event_shock_raw_score=None, active_override=None)


def test_sector_identity_comes_from_profile_and_registry_never_defaults_to_nifty50():
    payloads = {
        "upstox:/v2/fundamentals/INE498L01015/profile#sha256=" + "a" * 64:
            {"status": "success", "data": {"sector": "Finance - NBFC"}},
    }
    sector, source_ref = extract_profile_sector(payloads)
    assert sector == "Finance - NBFC"
    assert source_ref in payloads
    assert sector_benchmark_name(sector) == "Nifty Financial Services"
    assert sector_benchmark_name("Private Bank") == "Nifty Private Bank"
    assert sector_benchmark_name("Household Products") == "Nifty FMCG"
    with pytest.raises(G5InputError, match="unsupported"):
        sector_benchmark_name("Unmapped Specialist Sector")


def test_stock_daily_payload_requires_attributable_matching_instrument():
    source = (
        "upstox:/v3/historical-candle/NSE_EQ%7CINE498L01015/days/1/"
        "2026-10-01/2026-03-01#sha256=" + "b" * 64
    )
    payloads = {source: {"status": "success", "data": {"candles": _trend_candles(30)}}}
    rows, ref = stock_daily_payload(payloads, instrument_key="NSE_EQ|INE498L01015")
    assert len(rows) == 30
    assert ref == source


def test_lineage_is_exact_and_producer_maps_require_every_dimension():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    keys = ("p0", "atr14", "stock_regime", "sector_regime", "liquidity", "event_gap_risk", "calendar")
    lineage = {
        key: lineage_from_source(
            source_ref=f"upstox:{key}#sha256=" + "c" * 64,
            provider="UPSTOX",
            as_of="2026-10-01T15:30:00+05:30",
            acquired_at=now,
        )
        for key in keys
    }
    inputs = G5IssuanceInputs(
        p0=268.0,
        atr14=6.7,
        stock_regime="BULLISH",
        sector_regime="NEUTRAL",
        liquidity_state="NORMAL",
        event_gap_risk_state="NO_MATERIAL_RISK",
        target_trading_dates=(
            date(2026, 10, 5),
            date(2026, 10, 6),
            date(2026, 10, 7),
            date(2026, 10, 8),
            date(2026, 10, 9),
        ),
        calendar_version="UPSTOX_NSE_HOLIDAYS_V1",
        lineage=lineage,
        sector_name="Finance - NBFC",
        sector_benchmark="Nifty Financial Services",
    )
    ids, timestamps, hashes = producer_lineage_maps(inputs)
    assert tuple(ids) == keys
    assert set(timestamps) == set(keys)
    assert set(hashes) == set(keys)
    assert all(value == "c" * 64 for value in hashes.values())

    broken = dict(lineage)
    broken.pop("sector_regime")
    with pytest.raises(G5InputError, match="sector_regime"):
        producer_lineage_maps(
            G5IssuanceInputs(
                p0=inputs.p0,
                atr14=inputs.atr14,
                stock_regime=inputs.stock_regime,
                sector_regime=inputs.sector_regime,
                liquidity_state=inputs.liquidity_state,
                event_gap_risk_state=inputs.event_gap_risk_state,
                target_trading_dates=inputs.target_trading_dates,
                calendar_version=inputs.calendar_version,
                lineage=broken,
                sector_name=inputs.sector_name,
                sector_benchmark=inputs.sector_benchmark,
            )
        )
