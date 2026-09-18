"""Deterministic EDGE V1 frozen computation core.

Implements only formulas that are explicitly frozen in the canonical EDGE V1
Master Specification:
- Phase 5 component weights / raw-score normalization / missing-data rescaling / DES
- Phase 6 Market Trust weighted average / directional agreement / probability engine
- Phase 7 BOT Hunter weighted score + frozen grade bands

It deliberately does NOT infer component raw scores from market/news payloads,
select chart patterns, derive expected price zones, or choose a final action.
Those require governed evidence interpretation and execution analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

COMPONENT_WEIGHTS = {
    "PRICE_STRUCTURE": 18.0,
    "PV_PVPO": 18.0,
    "SPECIFIC_CHART_PATTERN": 12.0,
    "NEWS_EVENTS_CATALYSTS": 12.0,
    "BUSINESS_FUNDAMENTALS": 10.0,
    "INSTITUTIONAL_BEHAVIOUR": 10.0,
    "RELATIVE_STRENGTH": 8.0,
    "VALUATION": 7.0,
    "EVENT_SHOCK": 5.0,
}

TRUST_WEIGHTS = {
    "EVIDENCE_QUALITY": 30.0,
    "FRESHNESS": 20.0,
    "COMPLETENESS": 15.0,
    "DIRECTIONAL_AGREEMENT": 20.0,
    "MARKET_CONFIRMATION": 15.0,
}

BOT_WEIGHTS = {
    "FORECAST_EDGE": 25.0,
    "MARKET_TRUST": 20.0,
    "STRUCTURE_PATTERN": 20.0,
    "PV_PVPO_CONFIRMATION": 15.0,
    "CATALYST_ASYMMETRY": 10.0,
    "EXECUTION_QUALITY": 10.0,
}

RAW_TO_DIRECTION = {-2: -1.0, -1: -0.5, 0: 0.0, 1: 0.5, 2: 1.0}


@dataclass(frozen=True)
class ComponentInput:
    component: str
    raw_score: Optional[int]
    verified: bool = True


@dataclass(frozen=True)
class ComponentResult:
    component: str
    original_weight: float
    raw_score: Optional[int]
    normalized_direction: Optional[float]
    normalized_weight: Optional[float]
    weighted_contribution: Optional[float]
    availability_status: str


@dataclass(frozen=True)
class DesResult:
    des: float
    positive_contribution: float
    negative_contribution_abs: float
    directional_agreement: float
    components: tuple[ComponentResult, ...]


@dataclass(frozen=True)
class TrustInputs:
    evidence_quality: float
    freshness: float
    completeness: float
    directional_agreement: float
    market_confirmation: float


@dataclass(frozen=True)
class MarketTrustResult:
    score: float
    band: str


@dataclass(frozen=True)
class ProbabilityResult:
    bull: float
    base: float
    bear: float
    directional_strength: float
    trust: float
    effective_conviction: float
    definitive_forecast: str
    cap_applied: Optional[str]


@dataclass(frozen=True)
class BotInputs:
    leading_probability: float
    market_trust: float
    structure_pattern_quality: float
    pv_pvpo_confirmation: float
    catalyst_asymmetry: float
    execution_quality: float


@dataclass(frozen=True)
class BotResult:
    forecast_edge: float
    score: float
    grade: str


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _pct(value: float, name: str) -> float:
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return float(value)


def compute_des(components: Iterable[ComponentInput]) -> DesResult:
    """Apply frozen Phase 5 missing-data normalization and compute DES."""
    supplied = list(components)
    seen: set[str] = set()
    for item in supplied:
        name = item.component.strip().upper()
        if name not in COMPONENT_WEIGHTS:
            raise ValueError(f"unknown EDGE component: {name}")
        if name in seen:
            raise ValueError(f"duplicate EDGE component: {name}")
        seen.add(name)
        if item.verified and item.raw_score not in RAW_TO_DIRECTION:
            raise ValueError(f"{name} raw_score must be one of -2,-1,0,1,2")
        if not item.verified and item.raw_score is not None:
            raise ValueError(f"{name} cannot carry raw_score when not verified")

    by_name = {item.component.strip().upper(): item for item in supplied}
    eligible = [
        name for name, item in by_name.items()
        if item.verified and item.raw_score is not None
    ]
    total_eligible_weight = sum(COMPONENT_WEIGHTS[name] for name in eligible)
    if total_eligible_weight <= 0:
        raise ValueError("at least one verified scored component is required")

    results: list[ComponentResult] = []
    positive = 0.0
    negative_abs = 0.0
    for name, original_weight in COMPONENT_WEIGHTS.items():
        item = by_name.get(name)
        if item is None or not item.verified or item.raw_score is None:
            results.append(
                ComponentResult(
                    component=name,
                    original_weight=original_weight,
                    raw_score=None,
                    normalized_direction=None,
                    normalized_weight=None,
                    weighted_contribution=None,
                    availability_status="NOT_VERIFIED",
                )
            )
            continue

        direction = RAW_TO_DIRECTION[item.raw_score]
        normalized_weight = original_weight / total_eligible_weight * 100.0
        contribution = normalized_weight * direction
        if contribution > 0:
            positive += contribution
        elif contribution < 0:
            negative_abs += abs(contribution)
        results.append(
            ComponentResult(
                component=name,
                original_weight=original_weight,
                raw_score=item.raw_score,
                normalized_direction=direction,
                normalized_weight=normalized_weight,
                weighted_contribution=contribution,
                availability_status="AVAILABLE",
            )
        )

    des = positive - negative_abs
    agreement = (
        100.0 * abs(positive - negative_abs) / (positive + negative_abs)
        if positive + negative_abs > 0
        else 50.0
    )
    return DesResult(
        des=des,
        positive_contribution=positive,
        negative_contribution_abs=negative_abs,
        directional_agreement=agreement,
        components=tuple(results),
    )


def market_trust(inputs: TrustInputs) -> MarketTrustResult:
    values = {
        "EVIDENCE_QUALITY": _pct(inputs.evidence_quality, "evidence_quality"),
        "FRESHNESS": _pct(inputs.freshness, "freshness"),
        "COMPLETENESS": _pct(inputs.completeness, "completeness"),
        "DIRECTIONAL_AGREEMENT": _pct(inputs.directional_agreement, "directional_agreement"),
        "MARKET_CONFIRMATION": _pct(inputs.market_confirmation, "market_confirmation"),
    }
    score = sum(values[k] * TRUST_WEIGHTS[k] / 100.0 for k in TRUST_WEIGHTS)
    if score >= 85:
        band = "VERY HIGH"
    elif score >= 70:
        band = "HIGH"
    elif score >= 55:
        band = "MODERATE"
    elif score >= 40:
        band = "LOW"
    else:
        band = "VERY LOW"
    return MarketTrustResult(score=score, band=band)


def probabilities(des: float, mt: float, *, override: Optional[str] = None) -> ProbabilityResult:
    """Compute frozen Phase 6 Bull/Base/Bear probabilities.

    The canonical formula fully defines the uncapped distribution. Caps only
    matter if the leading directional probability exceeds a threshold.

    Because the Master Specification defines cap thresholds but does not specify
    a distinct redistribution formula for excess probability, the implementation
    moves any capped excess into Base. This preserves exactly 100% while reducing
    directional conviction, which is consistent with the frozen design principle
    that Base expands as conviction/trust falls. This behavior is explicitly
    surfaced through cap_applied for auditability.
    """
    if des < -100 or des > 100:
        raise ValueError("DES must be between -100 and 100")
    mt = _pct(mt, "market_trust")
    ov = (override or "").strip().upper() or None
    if ov not in (None, "O1", "O2", "O3"):
        raise ValueError("override must be None/O1/O2/O3")
    if ov == "O3":
        raise ValueError("O3 supersedes the normal probability engine")

    d = min(abs(des) / 100.0, 1.0)
    t = mt / 100.0
    c = d * t
    base = _clamp(20.0 + 55.0 * (1.0 - c), 20.0, 75.0)
    pool = 100.0 - base
    leading_directional = pool * (0.50 + 0.50 * t)
    opposite = pool - leading_directional

    if des >= 0:
        bull, bear = leading_directional, opposite
        leading_name = "BULL"
    else:
        bear, bull = leading_directional, opposite
        leading_name = "BEAR"

    cap = 90.0
    cap_reason = None
    if mt < 40:
        cap = min(cap, 55.0)
        cap_reason = "MT_BELOW_40"
    elif mt < 55:
        cap = min(cap, 60.0)
        cap_reason = "MT_BELOW_55"
    if ov == "O1":
        cap = min(cap, 70.0)
        cap_reason = "O1" if cap == 70.0 else cap_reason

    current_leading = bull if leading_name == "BULL" else bear
    if current_leading > cap:
        excess = current_leading - cap
        base += excess
        if leading_name == "BULL":
            bull = cap
        else:
            bear = cap
        cap_applied = cap_reason or "V1_90_CAP"
    else:
        cap_applied = None

    total = bull + base + bear
    bull = bull / total * 100.0
    base = base / total * 100.0
    bear = bear / total * 100.0

    if max(bull, base, bear) == bull:
        forecast = "BULLISH"
    elif max(bull, base, bear) == bear:
        forecast = "BEARISH"
    else:
        forecast = "BASE_RANGE"

    return ProbabilityResult(
        bull=bull,
        base=base,
        bear=bear,
        directional_strength=d,
        trust=t,
        effective_conviction=c,
        definitive_forecast=forecast,
        cap_applied=cap_applied,
    )


def bot_hunter(inputs: BotInputs) -> BotResult:
    lead = _pct(inputs.leading_probability, "leading_probability")
    mt = _pct(inputs.market_trust, "market_trust")
    structure = _pct(inputs.structure_pattern_quality, "structure_pattern_quality")
    pv = _pct(inputs.pv_pvpo_confirmation, "pv_pvpo_confirmation")
    catalyst = _pct(inputs.catalyst_asymmetry, "catalyst_asymmetry")
    execution = _pct(inputs.execution_quality, "execution_quality")

    forecast_edge = _clamp((lead - 33.3) / 56.7 * 100.0, 0.0, 100.0)
    score = (
        forecast_edge * 0.25
        + mt * 0.20
        + structure * 0.20
        + pv * 0.15
        + catalyst * 0.10
        + execution * 0.10
    )
    if score >= 90:
        grade = "A++"
    elif score >= 80:
        grade = "A+"
    elif score >= 70:
        grade = "A"
    elif score >= 60:
        grade = "B"
    else:
        grade = "C"
    return BotResult(forecast_edge=forecast_edge, score=score, grade=grade)
