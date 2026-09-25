import pytest

from src.horizon_calibration_inputs import (
    StockHorizonCalibrationEvidence,
    calibration_evidence_payload,
    validate_stock_horizon_calibration_evidence,
)


def evidence(**overrides):
    values = dict(
        symbol="LTF",
        spot=268.0,
        atr14=7.25,
        realized_volatility_pct=31.4,
        liquidity_ratio=1.35,
        gap_risk_pct=2.1,
        event_risk="MODERATE",
        stock_regime="TREND",
        sector_regime="RANGE",
        sector_relative_strength_pct=1.8,
        evidence_refs={
            "price_history": "run:stock-daily",
            "volatility": "derived:atr14-rv",
            "liquidity": "derived:volume-ratio",
            "gap_event_risk": "run:stock-gap-event-context",
            "regime": "run:stock-sector-context",
        },
    )
    values.update(overrides)
    return StockHorizonCalibrationEvidence(**values)


def test_valid_stock_specific_calibration_evidence_is_shadow_only():
    payload = calibration_evidence_payload(evidence())
    assert payload["mode"] == "SHADOW"
    assert payload["atr14"] == 7.25
    assert payload["stock_regime"] == "TREND"
    assert payload["evidence_refs"]["gap_event_risk"] == "run:stock-gap-event-context"
    assert "probabilities" not in payload
    assert "zone" not in payload


def test_missing_lineage_reference_fails_closed():
    with pytest.raises(ValueError, match="missing or invalid calibration evidence refs: liquidity"):
        validate_stock_horizon_calibration_evidence(
            evidence(evidence_refs={
                "price_history": "p",
                "volatility": "v",
                "gap_event_risk": "g",
                "regime": "r",
            })
        )


def test_missing_gap_event_risk_lineage_fails_closed():
    with pytest.raises(ValueError, match="missing or invalid calibration evidence refs: gap_event_risk"):
        validate_stock_horizon_calibration_evidence(
            evidence(evidence_refs={
                "price_history": "p",
                "volatility": "v",
                "liquidity": "l",
                "regime": "r",
            })
        )


@pytest.mark.parametrize("evidence_refs", [None, [], "not-a-mapping"])
def test_malformed_evidence_refs_fail_closed(evidence_refs):
    with pytest.raises(ValueError, match="evidence_refs must be a mapping"):
        validate_stock_horizon_calibration_evidence(evidence(evidence_refs=evidence_refs))


@pytest.mark.parametrize("bad_value", [None, 0, False, [], {}, object()])
def test_non_string_required_evidence_reference_values_fail_closed(bad_value):
    refs = {
        "price_history": "p",
        "volatility": "v",
        "liquidity": "l",
        "gap_event_risk": "g",
        "regime": "r",
    }
    refs["volatility"] = bad_value
    with pytest.raises(ValueError, match="missing or invalid calibration evidence refs: volatility"):
        validate_stock_horizon_calibration_evidence(evidence(evidence_refs=refs))


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("symbol", None, "symbol is required"),
        ("event_risk", None, "event_risk"),
        ("stock_regime", None, "stock_regime and sector_regime"),
        ("sector_regime", None, "stock_regime and sector_regime"),
    ],
)
def test_non_string_identity_and_regime_evidence_fails_closed(field, value, match):
    with pytest.raises(ValueError, match=match):
        validate_stock_horizon_calibration_evidence(evidence(**{field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("spot", 0),
        ("atr14", 0),
        ("realized_volatility_pct", -1),
        ("liquidity_ratio", 0),
        ("gap_risk_pct", -0.1),
    ],
)
def test_invalid_numeric_evidence_fails_closed(field, value):
    with pytest.raises(ValueError):
        validate_stock_horizon_calibration_evidence(evidence(**{field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("spot", float("nan")),
        ("atr14", float("inf")),
        ("realized_volatility_pct", float("-inf")),
        ("liquidity_ratio", float("nan")),
        ("gap_risk_pct", float("inf")),
        ("sector_relative_strength_pct", float("nan")),
    ],
)
def test_non_finite_numeric_evidence_fails_closed(field, value):
    with pytest.raises(ValueError, match="finite number"):
        validate_stock_horizon_calibration_evidence(evidence(**{field: value}))


def test_boolean_numeric_evidence_fails_closed():
    with pytest.raises(ValueError, match="spot must be a finite number"):
        validate_stock_horizon_calibration_evidence(evidence(spot=True))


def test_unverified_event_risk_is_explicit_not_fabricated():
    payload = calibration_evidence_payload(evidence(event_risk="UNVERIFIED"))
    assert payload["event_risk"] == "UNVERIFIED"


def test_unknown_event_risk_is_rejected():
    with pytest.raises(ValueError, match="event_risk"):
        validate_stock_horizon_calibration_evidence(evidence(event_risk="GUESS"))
