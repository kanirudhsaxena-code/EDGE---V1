"""Conservative autonomous evidence interpreter for EDGE V1 shadow runs.

This module converts authenticated structured evidence into the qualitative/raw
inputs required by the frozen EDGE computation core. It is deliberately
conservative:
- it only interprets payload fields it can parse deterministically;
- unsupported/malformed evidence is left unverified rather than guessed;
- severe O2/O3 event overrides are never inferred from keywords alone;
- outputs are intended for shadow validation before production publishing.

The frozen EDGE math remains in src.frozen_engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Iterable, Mapping, Optional, Sequence

from src.evidence_gate import EvidenceItem
from src.frozen_engine import ComponentInput, COMPONENT_WEIGHTS
from src.shadow_pipeline import AnalystInterpretation


def _payloads_matching(payloads: Mapping[str, Mapping], needle: str) -> list[Mapping]:
    return [v for k, v in payloads.items() if needle in k]


def _first_payload(payloads: Mapping[str, Mapping], needle: str) -> Optional[Mapping]:
    rows = _payloads_matching(payloads, needle)
    return rows[0] if rows else None


def _candles(payload: Optional[Mapping]) -> list[list]:
    if not payload:
        return []
    data = payload.get("data")
    rows = data.get("candles") if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        return []
    out = [r for r in rows if isinstance(r, list) and len(r) >= 6]
    try:
        return sorted(out, key=lambda x: str(x[0]))
    except Exception:
        return []


def _close(row: list) -> float:
    return float(row[4])


def _volume(row: list) -> float:
    try:
        return max(0.0, float(row[5]))
    except Exception:
        return 0.0


def _sma(values: Sequence[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def _pct_change(a: float, b: float) -> Optional[float]:
    if a == 0:
        return None
    return (b / a - 1.0) * 100.0


def _atr(candles: Sequence[list], n: int = 14) -> Optional[float]:
    if len(candles) < n + 1:
        return None
    trs: list[float] = []
    for prev, cur in zip(candles[-(n+1):-1], candles[-n:]):
        high, low, prev_close = float(cur[2]), float(cur[3]), float(prev[4])
        trs.append(max(high-low, abs(high-prev_close), abs(low-prev_close)))
    return sum(trs) / len(trs) if trs else None


def _technical_scores(stock_daily: list[list], benchmark_daily: list[list], option_chain: Optional[Mapping]):
    closes = [_close(r) for r in stock_daily]
    if len(closes) < 20:
        raise ValueError("at least 20 daily candles are required for autonomous technical interpretation")

    c = closes[-1]
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    r5 = _pct_change(closes[-6], c) if len(closes) >= 6 else 0.0
    r20 = _pct_change(closes[-21], c) if len(closes) >= 21 else 0.0

    if sma50 is not None and c > sma20 > sma50 and (r5 or 0) > 2:
        price_score = 2
    elif c > sma20 and (r20 or 0) >= 0:
        price_score = 1
    elif sma50 is not None and c < sma20 < sma50 and (r5 or 0) < -2:
        price_score = -2
    elif c < sma20 and (r20 or 0) <= 0:
        price_score = -1
    else:
        price_score = 0

    prior = stock_daily[-21:-1] if len(stock_daily) >= 21 else stock_daily[:-1]
    prior_high = max(float(r[2]) for r in prior)
    prior_low = min(float(r[3]) for r in prior)
    recent5 = stock_daily[-5:]
    recent_low = min(float(r[3]) for r in recent5)
    recent_high = max(float(r[2]) for r in recent5)

    if c > prior_high:
        pattern_score, pattern_name = 2, "RANGE_BREAKOUT"
    elif c < prior_low:
        pattern_score, pattern_name = -2, "SUPPORT_BREAKDOWN"
    elif recent_low < prior_low and c > prior_low:
        pattern_score, pattern_name = 1, "FAILED_BREAKDOWN"
    elif recent_high > prior_high and c < prior_high:
        pattern_score, pattern_name = -1, "FAILED_BREAKOUT"
    elif price_score > 0:
        pattern_score, pattern_name = 1, "TREND_CONTINUATION"
    elif price_score < 0:
        pattern_score, pattern_name = -1, "TREND_CONTINUATION"
    else:
        pattern_score, pattern_name = 0, "RANGE"

    vols = [_volume(r) for r in stock_daily]
    avg20v = sum(vols[-21:-1]) / max(1, len(vols[-21:-1]))
    vr = vols[-1] / avg20v if avg20v > 0 else 1.0
    day_ret = _pct_change(float(stock_daily[-1][1]), c) or 0.0
    if day_ret > 2 and vr >= 2.0:
        pv_score = 2
    elif day_ret > 0.5 and vr >= 1.2:
        pv_score = 1
    elif day_ret < -2 and vr >= 2.0:
        pv_score = -2
    elif day_ret < -0.5 and vr >= 1.2:
        pv_score = -1
    else:
        pv_score = 0

    # If current option-chain OI is available, use it as confirmation only.
    if option_chain:
        rows = option_chain.get("data")
        if isinstance(rows, list) and rows:
            call_oi = put_oi = 0.0
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                for side, acc in (("call_options","call"),("put_options","put")):
                    md = row.get(side, {}).get("market_data", {}) if isinstance(row.get(side), Mapping) else {}
                    oi = md.get("oi")
                    try:
                        oi = float(oi)
                    except Exception:
                        oi = 0.0
                    if acc == "call":
                        call_oi += max(0.0, oi)
                    else:
                        put_oi += max(0.0, oi)
            if call_oi > 0 and put_oi > 0:
                pcr = put_oi / call_oi
                if pcr >= 1.25 and pv_score >= 0:
                    pv_score = min(2, pv_score + 1)
                elif pcr <= 0.80 and pv_score <= 0:
                    pv_score = max(-2, pv_score - 1)

    bench_closes = [_close(r) for r in benchmark_daily]
    if len(bench_closes) >= 21 and len(closes) >= 21:
        s5 = _pct_change(closes[-6], c) or 0.0
        b5 = _pct_change(bench_closes[-6], bench_closes[-1]) or 0.0
        s20 = _pct_change(closes[-21], c) or 0.0
        b20 = _pct_change(bench_closes[-21], bench_closes[-1]) or 0.0
        rel5, rel20 = s5-b5, s20-b20
        if rel5 > 3 and rel20 > 3:
            rs_score = 2
        elif rel5 > 0 and rel20 > 0:
            rs_score = 1
        elif rel5 < -3 and rel20 < -3:
            rs_score = -2
        elif rel5 < 0 and rel20 < 0:
            rs_score = -1
        else:
            rs_score = 0
    else:
        rs_score = None

    atr = _atr(stock_daily) or max(0.01, c * 0.02)
    zone_low = max(0.01, min(prior_low, c - 1.5 * atr))
    zone_high = max(c + 1.5 * atr, prior_high)

    return {
        "PRICE_STRUCTURE": price_score,
        "SPECIFIC_CHART_PATTERN": pattern_score,
        "PV_PVPO": pv_score,
        "RELATIVE_STRENGTH": rs_score,
        "pattern_name": pattern_name,
        "zone_low": zone_low,
        "zone_high": zone_high,
    }


def _parse_pct(value) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace("%","").replace(",","")
    try:
        return float(s)
    except Exception:
        return None


def _fundamental_score(income_payload: Optional[Mapping]) -> Optional[int]:
    if not income_payload:
        return None
    data = income_payload.get("data")
    items = data.get("income_statement") if isinstance(data, Mapping) else None
    if not isinstance(items, list):
        return None
    changes = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        hist = item.get("history")
        if not isinstance(hist, list) or not hist:
            continue
        changes[str(item.get("category","")).lower()] = _parse_pct(hist[0].get("change"))
    rev = changes.get("revenue")
    net = changes.get("net_profit")
    if rev is None or net is None:
        return None
    if rev >= 10 and net >= 15:
        return 2
    if rev > 0 and net > 0:
        return 1
    if rev <= -15 and net <= -15:
        return -2
    if rev < 0 or net < 0:
        return -1
    return 0


def _valuation_score(ratios_payload: Optional[Mapping]) -> Optional[int]:
    if not ratios_payload:
        return None
    rows = ratios_payload.get("data")
    if not isinstance(rows, list):
        return None
    premiums = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("name") not in {"P/E","P/B","EV/EBITDA"}:
            continue
        c = _parse_pct(row.get("company_value"))
        s = _parse_pct(row.get("sector_value"))
        if c is None or s in (None, 0):
            continue
        premiums.append((c/s)-1.0)
    if not premiums:
        return None
    avg = sum(premiums)/len(premiums)
    if avg <= -0.30:
        return 2
    if avg <= -0.15:
        return 1
    if avg >= 0.30:
        return -2
    if avg >= 0.15:
        return -1
    return 0


def _institutional_score(holdings_payload: Optional[Mapping]) -> Optional[int]:
    if not holdings_payload:
        return None
    rows = holdings_payload.get("data")
    if not isinstance(rows, list):
        return None
    delta = 0.0
    found = 0
    for row in rows:
        if not isinstance(row, Mapping) or row.get("category") not in {"fii","mutual_funds","other_dii"}:
            continue
        hist = row.get("history")
        if not isinstance(hist, list) or len(hist) < 2:
            continue
        try:
            delta += float(hist[0]["value"]) - float(hist[1]["value"])
            found += 1
        except Exception:
            pass
    if found == 0:
        return None
    if delta >= 1.5:
        return 2
    if delta > 0.25:
        return 1
    if delta <= -1.5:
        return -2
    if delta < -0.25:
        return -1
    return 0


_POSITIVE = (
    "order win","wins order","record profit","profit rises","profit jumps","upgrade",
    "approval","launch","partnership","stake increase","buyback","dividend","debt reduction",
)
_NEGATIVE = (
    "downgrade","profit falls","profit drops","loss widens","default","fraud","investigation",
    "penalty","regulatory action","auditor resignation","pledge","lawsuit","warning",
)
_SEVERE = ("fraud","default","insolvency","auditor resignation","ban","prohibition","accounting manipulation")


def _news_texts(news_payload: Optional[Mapping]) -> list[str]:
    if not news_payload:
        return []
    data = news_payload.get("data")
    rows = []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, Mapping):
        for value in data.values():
            if isinstance(value, list):
                rows.extend(value)
    out=[]
    for row in rows:
        if isinstance(row, Mapping):
            out.append((str(row.get("heading",""))+" "+str(row.get("summary",""))).lower())
    return out


def _catalyst_scores(news_payload: Optional[Mapping]):
    texts = _news_texts(news_payload)
    pos = sum(any(k in t for k in _POSITIVE) for t in texts)
    neg = sum(any(k in t for k in _NEGATIVE) for t in texts)
    severe = sum(any(k in t for k in _SEVERE) for t in texts)
    if pos >= 2 and neg == 0:
        catalyst = 2
    elif pos > neg:
        catalyst = 1
    elif neg >= 2 and pos == 0:
        catalyst = -2
    elif neg > pos:
        catalyst = -1
    else:
        catalyst = 0

    # Keyword-only automation may flag caution, but never O2/O3.
    event = -1 if severe or neg >= 2 else 0
    override = "O1" if severe else None
    return catalyst, event, override


def _quality_score(evidence: Sequence[EvidenceItem]) -> float:
    if not evidence:
        return 0.0
    verified = sum(1 for e in evidence if e.verified and e.source_ref.strip())
    return verified / len(evidence) * 100.0


def _completeness(component_scores: Sequence[ComponentInput]) -> float:
    total=0.0
    for row in component_scores:
        if row.verified and row.raw_score is not None:
            total += COMPONENT_WEIGHTS[row.component]
    return total


def _market_confirmation(scores: Mapping[str, Optional[int]]) -> float:
    vals=[scores.get("PRICE_STRUCTURE"),scores.get("PV_PVPO"),scores.get("SPECIFIC_CHART_PATTERN")]
    vals=[v for v in vals if v is not None]
    if len(vals)<2:
        return 40.0
    signs=[0 if v==0 else (1 if v>0 else -1) for v in vals]
    nonzero=[s for s in signs if s]
    if len(nonzero)>=2 and len(set(nonzero))==1:
        return 100.0 if len(nonzero)==3 else 70.0
    if 1 in nonzero and -1 in nonzero:
        return 20.0
    return 40.0


class ConservativeAutonomousInterpreter:
    """Deterministic interpreter suitable for shadow validation.

    It intentionally produces a non-actionable shadow recommendation string.
    Final production action/execution logic remains gated until live shadow
    parity is demonstrated.
    """

    def __call__(
        self,
        ticker: str,
        evidence: Sequence[EvidenceItem],
        payloads: Mapping[str, Mapping],
        run_at: datetime,
    ) -> AnalystInterpretation:
        stock_daily_payload = None
        benchmark_daily_payload = None
        for key,payload in payloads.items():
            if "/historical-candle/" not in key or "/days/1/" not in key:
                continue
            if "NSE_EQ%7C" in key and stock_daily_payload is None:
                stock_daily_payload = payload
            elif "NSE_INDEX%7CNifty%2050" in key and benchmark_daily_payload is None:
                benchmark_daily_payload = payload

        stock_daily = _candles(stock_daily_payload)
        benchmark_daily = _candles(benchmark_daily_payload)
        option_chain = _first_payload(payloads, "/v2/option/chain")

        tech = _technical_scores(stock_daily, benchmark_daily, option_chain)
        income = _first_payload(payloads, "/income-statement")
        ratios = _first_payload(payloads, "/key-ratios")
        holdings = _first_payload(payloads, "/share-holdings")
        news = _first_payload(payloads, "/v2/news")

        fundamental = _fundamental_score(income)
        valuation = _valuation_score(ratios)
        institutional = _institutional_score(holdings)
        catalyst, event_shock, override = _catalyst_scores(news)

        scores = {
            "PRICE_STRUCTURE": tech["PRICE_STRUCTURE"],
            "PV_PVPO": tech["PV_PVPO"],
            "SPECIFIC_CHART_PATTERN": tech["SPECIFIC_CHART_PATTERN"],
            "NEWS_EVENTS_CATALYSTS": catalyst,
            "BUSINESS_FUNDAMENTALS": fundamental,
            "INSTITUTIONAL_BEHAVIOUR": institutional,
            "RELATIVE_STRENGTH": tech["RELATIVE_STRENGTH"],
            "VALUATION": valuation,
            "EVENT_SHOCK": event_shock,
        }
        rows=tuple(
            ComponentInput(name, score, verified=score is not None)
            for name,score in scores.items()
        )

        structure_quality = {2:90,1:75,0:60,-1:75,-2:90}[tech["SPECIFIC_CHART_PATTERN"]]
        pv_quality = {2:90,1:75,0:60,-1:75,-2:90}[tech["PV_PVPO"]]
        catalyst_asymmetry = max(0.0,min(100.0,50.0 + 20.0*catalyst))

        return AnalystInterpretation(
            component_scores=rows,
            evidence_quality_score=_quality_score(evidence),
            freshness_score=100.0,
            completeness_score=_completeness(rows),
            market_confirmation_score=_market_confirmation(scores),
            structure_pattern_quality=structure_quality,
            pv_pvpo_confirmation=pv_quality,
            catalyst_asymmetry=catalyst_asymmetry,
            execution_quality=60.0,
            expected_price_zone_low=tech["zone_low"],
            expected_price_zone_high=tech["zone_high"],
            horizon_trading_days=5,
            definitive_recommendation="SHADOW ONLY — production action not released.",
            event_override=override,
        )
