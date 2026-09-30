from datetime import datetime, timezone

import pytest

from src.horizon_path_shadow import build_shadow_forecast_path


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
