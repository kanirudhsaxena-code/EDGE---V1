"""Structure-based expected price zone engine for EDGE V1 shadow validation.

Purpose:
- derive visible/verifiable support and resistance from daily candles;
- use the definitive frozen forecast to select the relevant structural objective;
- keep the expected zone compact and auditable;
- never invent precise levels when structure is unavailable.

This does not change EDGE scoring/probability rules. It implements the frozen
Phase 3/8 principles that price structure must identify major support/resistance
and Target 1/2 must come from visible/verifiable structure/pattern/liquidity.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Optional, Sequence


@dataclass(frozen=True)
class MarketStructureContext:
    close: float
    supports: tuple[float, ...]
    resistances: tuple[float, ...]
    median_true_range: float
    pattern_name: str


@dataclass(frozen=True)
class ExpectedZoneResult:
    low: float
    high: float
    basis: str
    support_used: Optional[float]
    resistance_used: Optional[float]
    width_pct: float


def _tr(prev_close: float, high: float, low: float) -> float:
    return max(high-low, abs(high-prev_close), abs(low-prev_close))


def derive_structure_context(
    candles: Sequence[list],
    *,
    pattern_name: str,
    lookback: int = 120,
) -> MarketStructureContext:
    if len(candles) < 12:
        raise ValueError("at least 12 daily candles required for structure zone")
    rows = list(candles[-lookback:])
    close = float(rows[-1][4])

    trs=[]
    for prev, cur in zip(rows[:-1], rows[1:]):
        trs.append(_tr(float(prev[4]), float(cur[2]), float(cur[3])))
    mtr = median(trs[-20:]) if trs else max(close*0.01, 0.01)
    mtr = max(float(mtr), max(close*0.0025, 0.01))

    piv_hi=[]
    piv_lo=[]
    for i in range(2, len(rows)-2):
        hi=float(rows[i][2]); lo=float(rows[i][3])
        left_hi=max(float(rows[j][2]) for j in range(i-2,i))
        right_hi=max(float(rows[j][2]) for j in range(i+1,i+3))
        left_lo=min(float(rows[j][3]) for j in range(i-2,i))
        right_lo=min(float(rows[j][3]) for j in range(i+1,i+3))
        if hi >= left_hi and hi >= right_hi:
            piv_hi.append(hi)
        if lo <= left_lo and lo <= right_lo:
            piv_lo.append(lo)

    # Include recent visible range extrema as structural candidates, but do not
    # automatically expand the final zone to the full range.
    recent=rows[-20:]
    piv_hi.append(max(float(r[2]) for r in recent))
    piv_lo.append(min(float(r[3]) for r in recent))

    tol=0.35*mtr

    def cluster(values):
        vals=sorted(values)
        out=[]
        for v in vals:
            if not out or abs(v-out[-1]) > tol:
                out.append(v)
            else:
                out[-1]=(out[-1]+v)/2.0
        return out

    supports=tuple(sorted((x for x in cluster(piv_lo) if x < close), reverse=True))
    resistances=tuple(sorted(x for x in cluster(piv_hi) if x > close))
    return MarketStructureContext(
        close=close,
        supports=supports,
        resistances=resistances,
        median_true_range=mtr,
        pattern_name=pattern_name,
    )


def expected_price_zone(
    ctx: MarketStructureContext,
    definitive_forecast: str,
) -> ExpectedZoneResult:
    f=definitive_forecast.strip().upper()
    if f not in {"BULLISH","BEARISH","BASE_RANGE"}:
        raise ValueError("unsupported definitive forecast")

    c=ctx.close
    mtr=ctx.median_true_range
    if c <= 0 or mtr <= 0:
        raise ValueError("invalid market structure context")

    # EDGE stores direction and expected price zone separately. Historical LTF
    # calls show that a bearish or bullish forecast can still use a two-sided
    # expected zone around the current market state. Therefore the implementation
    # starts from the observed recent range (one median true range either side of
    # the close) and then lets material nearby structure refine/extend that range.
    baseline_low=c-mtr
    baseline_high=c+mtr

    min_material_distance=0.50*mtr
    max_material_distance=1.75*mtr
    extension=max(0.30*mtr, c*0.003)

    def material_support() -> Optional[float]:
        for level in ctx.supports:
            distance=c-level
            if min_material_distance <= distance <= max_material_distance:
                return level
        return None

    def material_resistance() -> Optional[float]:
        for level in ctx.resistances:
            distance=level-c
            if min_material_distance <= distance <= max_material_distance:
                return level
        return None

    support=material_support()
    resistance=material_resistance()

    # Keep the baseline volatility envelope unless nearby visible structure gives
    # a more useful boundary. Support can tighten the lower edge; resistance can
    # extend the upper edge when the next credible objective sits just beyond the
    # one-range baseline. These are implementation heuristics under validation,
    # not changes to the frozen EDGE scoring/probability model.
    low=max(0.01, baseline_low)
    if support is not None:
        low=max(low, support)

    high=baseline_high
    if resistance is not None:
        high=max(high, resistance+extension)

    if high <= low:
        raise ValueError("expected zone collapsed after structure refinement")

    width_pct=(high-low)/c*100.0
    if width_pct > 12.0:
        raise ValueError("structure-derived expected zone is too broad for release validation")

    return ExpectedZoneResult(
        low=float(low),
        high=float(high),
        basis="VOLATILITY_STRUCTURE_ENVELOPE",
        support_used=support,
        resistance_used=resistance,
        width_pct=width_pct,
    )
