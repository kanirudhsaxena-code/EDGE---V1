"""G5 stock-specific horizon calibration evidence contract.

This is the governed boundary between existing verified EDGE Stocks evidence and
future D:D+4 SHADOW calibration. It deliberately defines/validates inputs only;
it does not invent horizon probability decay, zone-width multipliers, or alter
production recommendation logic.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional


@dataclass(frozen=True)
class StockHorizonCalibrationEvidence:
    symbol: str
    spot: float
    atr14: float
    realized_volatility_pct: float
    liquidity_ratio: float
    gap_risk_pct: float
    event_risk: str
    stock_regime: str
    sector_regime: str
    evidence_refs: Mapping[str, str]
    sector_relative_strength_pct: Optional[float] = None


def validate_stock_horizon_calibration_evidence(e: StockHorizonCalibrationEvidence) -> None:
    if not isinstance(e.symbol, str) or not e.symbol.strip():
        raise ValueError("symbol is required")
    numeric_fields = {
        "spot": e.spot,
        "atr14": e.atr14,
        "realized_volatility_pct": e.realized_volatility_pct,
        "liquidity_ratio": e.liquidity_ratio,
        "gap_risk_pct": e.gap_risk_pct,
    }
    if e.sector_relative_strength_pct is not None:
        numeric_fields["sector_relative_strength_pct"] = e.sector_relative_strength_pct
    for field, value in numeric_fields.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{field} must be a finite number")
    if e.spot <= 0:
        raise ValueError("spot must be positive")
    if e.atr14 <= 0:
        raise ValueError("atr14 must be positive and evidence-derived")
    if e.realized_volatility_pct < 0:
        raise ValueError("realized_volatility_pct cannot be negative")
    if e.liquidity_ratio <= 0:
        raise ValueError("liquidity_ratio must be positive")
    if e.gap_risk_pct < 0:
        raise ValueError("gap_risk_pct cannot be negative")
    if not isinstance(e.event_risk, str) or e.event_risk not in {"NONE", "LOW", "MODERATE", "HIGH", "UNVERIFIED"}:
        raise ValueError("event_risk must use the governed stock evidence vocabulary")
    if (
        not isinstance(e.stock_regime, str)
        or not e.stock_regime.strip()
        or not isinstance(e.sector_regime, str)
        or not e.sector_regime.strip()
    ):
        raise ValueError("stock_regime and sector_regime are required")
    if not isinstance(e.evidence_refs, Mapping):
        raise ValueError("evidence_refs must be a mapping")
    required_refs = {"price_history", "volatility", "liquidity", "regime"}
    invalid_refs = sorted(
        key
        for key in required_refs
        if not isinstance(e.evidence_refs.get(key), str) or not e.evidence_refs.get(key, "").strip()
    )
    if invalid_refs:
        raise ValueError(f"missing or invalid calibration evidence refs: {','.join(invalid_refs)}")


def calibration_evidence_payload(e: StockHorizonCalibrationEvidence) -> dict:
    """Return an auditable SHADOW input payload after strict validation.

    No horizon probabilities or zones are calculated here. Those must be supplied
    by the separately governed empirical calibration step rather than guessed.
    """
    validate_stock_horizon_calibration_evidence(e)
    return {
        "symbol": e.symbol.strip().upper(),
        "spot": float(e.spot),
        "atr14": float(e.atr14),
        "realized_volatility_pct": float(e.realized_volatility_pct),
        "liquidity_ratio": float(e.liquidity_ratio),
        "gap_risk_pct": float(e.gap_risk_pct),
        "event_risk": e.event_risk,
        "stock_regime": e.stock_regime,
        "sector_regime": e.sector_regime,
        "sector_relative_strength_pct": e.sector_relative_strength_pct,
        "evidence_refs": dict(e.evidence_refs),
        "mode": "SHADOW",
    }
