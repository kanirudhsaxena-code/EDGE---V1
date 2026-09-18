"""Phase 9 two-table EDGE V1 report renderer.

Standard EDGE/UPDATE output is exactly two user-facing tables:
1. Outcome/Decision
2. Institutional Drill-down

This renderer returns markdown only; no narrative is added before or after.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional

from src.persistence import CanonicalRecommendationWrite


def _fmt(value, digits=2):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _escape(value) -> str:
    return _fmt(value).replace("|", "\\|").replace("\n", " ")


def render_standard_edge_report(
    recommendation: CanonicalRecommendationWrite,
    *,
    component_summaries: Optional[Mapping[str, tuple[str,str]]] = None,
) -> str:
    """Render exactly two markdown tables and no surrounding narrative."""
    p=(
        f"Bull {_fmt(recommendation.bull_probability,1)}% / "
        f"Base {_fmt(recommendation.base_probability,1)}% / "
        f"Bear {_fmt(recommendation.bear_probability,1)}%"
    )
    zone=(
        f"{_fmt(recommendation.expected_price_zone_low)}–"
        f"{_fmt(recommendation.expected_price_zone_high)}"
        if recommendation.expected_price_zone_low is not None
        and recommendation.expected_price_zone_high is not None
        else "N/A"
    )
    ep=recommendation.execution_plan
    entry=(
        f"{_fmt(ep.entry_low)}–{_fmt(ep.entry_high)}"
        if ep.entry_low is not None and ep.entry_high is not None
        else _fmt(ep.entry_low if ep.entry_low is not None else ep.entry_high)
    )
    targets=f"T1 {_fmt(ep.target1)} / T2 {_fmt(ep.target2)}"
    contract="N/A"
    if ep.option_strike is not None or ep.option_expiry is not None:
        contract=(
            f"{_escape(ep.instrument)} | strike {_fmt(ep.option_strike)} | "
            f"expiry {_fmt(ep.option_expiry)} | premium {_fmt(ep.observed_premium)}"
        )

    table1=[
        "| Field | EDGE Output | Execution / Level | Interpretation |",
        "|---|---|---|---|",
        f"| Forecast | {_escape(recommendation.definitive_forecast)} | {_escape(p)} | Highest-probability scenario |",
        f"| Expected Move | {_escape(zone)} | {_escape(recommendation.forecast_horizon)} | Frozen forecast objective |",
        f"| Market Trust | {_fmt(recommendation.market_trust_score,1)} / {_escape(recommendation.market_trust_band)} | DES {_fmt(recommendation.des,1)} | Evidence confidence + directional balance |",
        f"| BOT Hunter | {_fmt(recommendation.bot_score,1)} / {_escape(recommendation.bot_grade)} | {_escape(recommendation.decision_ladder)} | Opportunity quality / commitment state |",
        f"| Definitive Recommendation | {_escape(recommendation.definitive_recommendation)} | {_escape(ep.instrument)} | Final EDGE decision |",
        f"| Entry | {_escape(entry)} | {_escape(ep.invalidation_text or 'N/A')} | Direct recommended execution |",
        f"| Risk Control | Stop {_fmt(ep.stop_price)} | {_escape(ep.risk_unit_category or 'N/A')} | Maximum defined thesis risk |",
        f"| Targets | {_escape(targets)} | R:R T1 {_fmt(ep.rr_t1)} / T2 {_fmt(ep.rr_t2)} | Reward path |",
        f"| Options Contract | {_escape(contract)} | {_escape(ep.option_suitability_status or 'N/A')} | N/A for equity-only calls |",
        f"| Event Risk | {_escape(recommendation.event_shock_level)} | {_escape(recommendation.active_override or 'Normal')} | Near-term shock constraint |",
    ]

    summaries=dict(component_summaries or {})
    component_by_name={x.component:x for x in recommendation.component_scores}
    order=(
        "Business & Fundamentals",
        "Valuation",
        "Price Structure",
        "Specific Chart Pattern",
        "PV/PVPO",
        "Relative Strength",
        "Institutional Behaviour",
        "News, Events & Catalysts (10–15D)",
        "Event-Shock Risk",
        "Market Trust",
        "BOT Hunter",
        "Decision Ladder",
        "Execution Quality",
    )

    aliases={
        "Business & Fundamentals":"BUSINESS_FUNDAMENTALS",
        "Valuation":"VALUATION",
        "Price Structure":"PRICE_STRUCTURE",
        "Specific Chart Pattern":"SPECIFIC_CHART_PATTERN",
        "PV/PVPO":"PV_PVPO",
        "Relative Strength":"RELATIVE_STRENGTH",
        "Institutional Behaviour":"INSTITUTIONAL_BEHAVIOUR",
        "News, Events & Catalysts (10–15D)":"NEWS_EVENTS_CATALYSTS",
        "Event-Shock Risk":"EVENT_SHOCK",
    }

    table2=[
        "| EDGE Component | Score / Level | Key Outcome | Interpretation |",
        "|---|---|---|---|",
    ]
    for label in order:
        key=aliases.get(label)
        if key:
            row=component_by_name.get(key)
            score="Not Verified"
            if row is not None and row.raw_score is not None:
                score=str(row.raw_score)
            outcome,interpretation=summaries.get(label,("Stored audit evidence","See immutable evidence record"))
        elif label=="Market Trust":
            score=f"{_fmt(recommendation.market_trust_score,1)} / {recommendation.market_trust_band}"
            outcome,interpretation=summaries.get(label,("Quality/freshness/completeness/agreement","Confidence in evidence"))
        elif label=="BOT Hunter":
            score=f"{_fmt(recommendation.bot_score,1)} / {recommendation.bot_grade}"
            outcome,interpretation=summaries.get(label,("Opportunity-quality summary","C / B / A / A+ / A++"))
        elif label=="Decision Ladder":
            score=recommendation.decision_ladder
            outcome,interpretation=summaries.get(label,("Capital-commitment classification","Observe/Watchlist/Investigation/Pilot/Partial/Full"))
        else:
            score=_fmt(ep.execution_quality_score,1)
            if ep.execution_quality_level:
                score+=f" / {ep.execution_quality_level}"
            outcome,interpretation=summaries.get(label,("Entry/stop/targets/R:R/instrument quality","Executable / downgrade / No Trade"))
        table2.append(
            f"| {_escape(label)} | {_escape(score)} | {_escape(outcome)} | {_escape(interpretation)} |"
        )

    return "\n".join(table1)+"\n\n"+"\n".join(table2)
