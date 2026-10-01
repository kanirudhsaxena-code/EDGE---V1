"""G5 EDGE Stocks horizon-path SHADOW producer contract.

Adapts the governed 5DR multi-horizon design pattern without copying NIFTY
numeric parameters. The caller must supply five stock-specific, evidence-derived
horizon slots. This module normalizes/validates those slots into the immutable
EDGE Stocks ForecastPathWrite used by G5 persistence.

SHADOW ONLY: this module does not alter the frozen production recommendation,
Market Trust, canonical selection, efficacy population, or trading action.
"""
from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any, Mapping, Sequence

from .forecast_path import ForecastPathRow, ForecastPathWrite, LABELS, validate_forecast_path

SCENARIOS = ("BULL", "BASE", "BEAR")


def _number(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def build_shadow_forecast_path(
    *,
    recommendation_id: str,
    source_run_id: str,
    issued_at: datetime,
    horizon_slots: Sequence[Mapping[str, Any]],
    producer_version: str,
) -> ForecastPathWrite:
    """Validate genuine stock-specific D:D+4 slots and build a persistence write.

    Deliberately does not derive/decay/interpolate probabilities or zones. The
    horizon producer upstream must calculate them from approved stock evidence.
    """
    if len(horizon_slots) != 5:
        raise ValueError("G5 shadow producer requires exactly five D through D+4 slots")
    if not producer_version.strip():
        raise ValueError("G5 shadow producer version is required")

    rows = []
    for expected_label, slot in zip(LABELS, horizon_slots):
        label = str(slot.get("horizon_label") or "")
        if label != expected_label:
            raise ValueError(f"G5 horizon order must be {','.join(LABELS)}")
        target = slot.get("target_trading_date")
        if isinstance(target, str):
            target = date.fromisoformat(target)
        if not isinstance(target, date):
            raise ValueError(f"{label} target_trading_date is required")

        probs = slot.get("probabilities")
        if not isinstance(probs, Mapping) or set(probs) != set(SCENARIOS):
            raise ValueError(f"{label} probabilities must contain exactly BULL, BASE and BEAR")
        bull = _number(probs["BULL"], f"{label}.BULL")
        base = _number(probs["BASE"], f"{label}.BASE")
        bear = _number(probs["BEAR"], f"{label}.BEAR")

        zone = slot.get("outer_expected_zone")
        if not isinstance(zone, Mapping):
            raise ValueError(f"{label} stock-specific outer_expected_zone is required")
        low = _number(zone.get("low"), f"{label}.zone.low")
        high = _number(zone.get("high"), f"{label}.zone.high")
        centre_raw = slot.get("expected_centre")
        centre = None if centre_raw is None else _number(centre_raw, f"{label}.expected_centre")
        if centre is not None and not (low <= centre <= high):
            raise ValueError(f"{label} expected_centre must lie inside the stock-specific zone")

        lineage = slot.get("lineage")
        if not isinstance(lineage, Mapping) or not lineage:
            raise ValueError(f"{label} lineage is required")
        lineage = dict(lineage)
        lineage["producer_version"] = producer_version
        lineage["mode"] = "SHADOW"

        rows.append(ForecastPathRow(
            horizon_label=label,
            target_trading_date=target,
            direction=str(slot.get("direction") or ""),
            bull_probability=bull,
            base_probability=base,
            bear_probability=bear,
            expected_centre=centre,
            outer_expected_zone_low=low,
            outer_expected_zone_high=high,
            evidence_basis=str(slot.get("evidence_basis") or ""),
            regime_context=str(slot.get("regime_context") or ""),
            verification_state=str(slot.get("verification_state") or ""),
            lineage=lineage,
        ))

    path = ForecastPathWrite(
        recommendation_id=recommendation_id,
        source_run_id=source_run_id,
        issued_at=issued_at,
        rows=tuple(rows),  # type: ignore[arg-type]
    )
    validate_forecast_path(path)
    return path


G5_STOCK_DD4_METHODOLOGY_VERSION = "G5_STOCK_DD4_V1.0"
_G5_REGIME = {"BULLISH": 1.0, "NEUTRAL": 0.0, "TRANSITION": 0.0, "BEARISH": -1.0}
_G5_LIQUIDITY = {"NORMAL": 1.00, "CAUTION": 0.85, "WEAK": 0.70}
_G5_EVENT_RISK = {"NO_MATERIAL_RISK": 1.00, "MODERATE": 0.85, "HIGH_RISK": 0.70}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_g5_stock_dd4_forecast_path(
    *,
    recommendation_id: str,
    source_run_id: str,
    issued_at: datetime,
    p0: float,
    atr14: float,
    stock_regime: str,
    sector_regime: str,
    liquidity_state: str,
    event_gap_risk_state: str,
    target_trading_dates: Sequence[date],
    calendar_version: str,
    source_ids: Mapping[str, str],
    source_timestamps: Mapping[str, str],
    source_hashes: Mapping[str, str],
    canonical_p0_verified: bool,
    atr_history_sufficient: bool,
    freshness_verified: bool,
) -> ForecastPathWrite:
    """Build the approved stock-specific G5 D:D+4 path.

    Implements G5_STOCK_DD4_V1.0 exactly. This producer is additive to the
    frozen EDGE_V1 aggregate decision engine and never changes recommendation,
    DES, Market Trust, BOT, canonical selection or efficacy rules.
    """
    if not canonical_p0_verified:
        raise ValueError("G5 P0 must be canonical and verified")
    if not atr_history_sufficient:
        raise ValueError("G5 ATR14 requires sufficient verified history")
    if not freshness_verified:
        raise ValueError("G5 source freshness/lineage verification failed")
    if isinstance(p0, bool) or not isinstance(p0, (int, float)) or not math.isfinite(float(p0)) or float(p0) <= 0:
        raise ValueError("G5 P0 must be a positive finite number")
    if isinstance(atr14, bool) or not isinstance(atr14, (int, float)) or not math.isfinite(float(atr14)) or float(atr14) <= 0:
        raise ValueError("G5 ATR14 must be a positive finite number")

    rs_key = str(stock_regime or "").strip().upper()
    rsec_key = str(sector_regime or "").strip().upper()
    liq_key = str(liquidity_state or "").strip().upper()
    event_key = str(event_gap_risk_state or "").strip().upper()
    if rs_key not in _G5_REGIME or rsec_key not in _G5_REGIME:
        raise ValueError("G5 stock/sector regime must be Bullish, Neutral, Transition or Bearish")
    if liq_key == "FAIL":
        raise ValueError("G5 liquidity FAIL is not forecastable")
    if liq_key not in _G5_LIQUIDITY:
        raise ValueError("G5 liquidity state must be NORMAL, CAUTION or WEAK")
    if event_key not in _G5_EVENT_RISK:
        raise ValueError("G5 event/gap-risk state must be NO_MATERIAL_RISK, MODERATE or HIGH_RISK")

    dates = tuple(target_trading_dates)
    if len(dates) != 5 or any(not isinstance(d, date) for d in dates):
        raise ValueError("G5 target trading dates must contain exactly five dates")
    if tuple(sorted(dates)) != dates or len(set(dates)) != 5:
        raise ValueError("G5 target trading dates must be unique and increasing")
    if not isinstance(calendar_version, str) or not calendar_version.strip():
        raise ValueError("G5 trading calendar version is required")

    required_lineage = {"p0", "atr14", "stock_regime", "sector_regime", "liquidity", "event_gap_risk", "calendar"}
    for name, mapping in (
        ("source_ids", source_ids),
        ("source_timestamps", source_timestamps),
        ("source_hashes", source_hashes),
    ):
        if not isinstance(mapping, Mapping):
            raise ValueError(f"G5 {name} must be a mapping")
        missing = sorted(k for k in required_lineage if not isinstance(mapping.get(k), str) or not mapping.get(k, "").strip())
        if missing:
            raise ValueError(f"G5 {name} missing required lineage: {','.join(missing)}")

    p0f = float(p0)
    atrf = float(atr14)
    rs = _G5_REGIME[rs_key]
    rsec = _G5_REGIME[rsec_key]
    l = _G5_LIQUIDITY[liq_key]
    e = _G5_EVENT_RISK[event_key]
    b = (0.80 * rs) + (0.20 * rsec)
    q = min(l, e)
    atr_pct = atrf / p0f

    slots = []
    for index, (label, target) in enumerate(zip(LABELS, dates), start=1):
        h = float(index)
        u = q / math.sqrt(h)
        z = _clamp(b * u, -0.80, 0.80)
        base = _clamp(0.20 + 0.35 * (1.0 - abs(b)) + 0.10 * (1.0 - u), 0.20, 0.55)
        bull = (1.0 - base) * (1.0 + z) / 2.0
        bear = 1.0 - base - bull
        probs = {"BULL": bull * 100.0, "BASE": base * 100.0, "BEAR": bear * 100.0}
        direction = max(("BULL", "BASE", "BEAR"), key=lambda key: probs[key])
        net_dir = bull - bear
        expected_centre = p0f * (1.0 + net_dir * atr_pct * h)
        base_width = p0f * atr_pct * math.sqrt(h)
        outer_width = base_width / q
        lineage = {
            "methodology_version": G5_STOCK_DD4_METHODOLOGY_VERSION,
            "p0": p0f,
            "atr14": atrf,
            "stock_regime": rs_key,
            "sector_regime": rsec_key,
            "liquidity_state": liq_key,
            "event_gap_risk_state": event_key,
            "B": b,
            "Q": q,
            "U": u,
            "Z": z,
            "calendar_version": calendar_version,
            "source_ids": dict(source_ids),
            "source_timestamps": dict(source_timestamps),
            "source_hashes": dict(source_hashes),
        }
        slots.append({
            "horizon_label": label,
            "target_trading_date": target,
            "direction": direction,
            "probabilities": probs,
            "expected_centre": expected_centre,
            "outer_expected_zone": {
                "low": expected_centre - outer_width,
                "high": expected_centre + outer_width,
            },
            "evidence_basis": "G5_STOCK_DD4_V1.0 verified stock-specific P0/ATR/regime/liquidity/event evidence",
            "regime_context": f"stock={rs_key};sector={rsec_key};liquidity={liq_key};event={event_key}",
            "verification_state": "VERIFIED",
            "lineage": lineage,
        })

    return build_shadow_forecast_path(
        recommendation_id=recommendation_id,
        source_run_id=source_run_id,
        issued_at=issued_at,
        horizon_slots=slots,
        producer_version=G5_STOCK_DD4_METHODOLOGY_VERSION,
    )
