"""EDGE V1 user-facing report renderer.

The approved Efficacy V2 amendment supersedes the earlier two-table-only
operating display for a standard EDGE <STOCK> run. Mandatory user-facing order:

1. EDGE MASTER ASSESSMENT
2. ACTIVE CALLS
3. CURRENT STOCK OUTCOME
4. DRILL-DOWN

Detailed scoring mathematics and evidence records remain in the audit layer.
"""
from __future__ import annotations

from typing import Mapping, Optional

from src.assessment_context import AssessmentContext
from src.persistence import CanonicalRecommendationWrite


def _fmt(value, digits=2):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _pct(value):
    return "N/A" if value is None else f"{float(value):.1f}%"


def _escape(value) -> str:
    return _fmt(value).replace("|", "\\|").replace("\n", " ")


def render_standard_edge_report(
    recommendation: CanonicalRecommendationWrite,
    assessment: AssessmentContext,
    *,
    component_summaries: Optional[Mapping[str, tuple[str,str]]] = None,
) -> str:
    """Render the mandatory Efficacy V2 four-table output and no extra narrative."""
    m=assessment.master
    s=assessment.stock

    table1=[
        "| EDGE MASTER ASSESSMENT | Value | Status / Detail |",
        "|---|---:|---|",
        f"| Tracked Recommendations | {m.recommendations} | {m.open_recommendations} OPEN / {m.closed_recommendations} CLOSED |",
        f"| Tracked Stocks | {m.unique_stocks} | System-wide |",
        f"| Official Scorable Sample | {m.official_scorable_recommendations} | CLOSED/scorable only |",
        f"| Recommendation Hit Rate | {_pct(m.recommendation_hit_rate_pct)} | Official; N/A until scorable closures exist |",
        f"| Directional Hit Rate | {_pct(m.direction_hit_rate_pct)} | Official; CLOSED/scorable only |",
        f"| Target Hit Rate | {_pct(m.target_hit_rate_pct)} | Official; CLOSED/scorable only |",
        f"| Average Gain / Loss | {_pct(m.avg_gain_pct)} / {_pct(m.avg_loss_pct)} | Standardized model results |",
        f"| Average MFE / MAE | {_pct(m.avg_mfe_pct)} / {_pct(m.avg_mae_pct)} | Opportunity efficacy |",
        f"| Cumulative Model P/L | {_fmt(m.cumulative_model_pnl_units)} | Model P/L, not inferred user P/L |",
        f"| Provisional Forecast Accuracy | {_pct(m.provisional_forecast_accuracy_pct)} | {m.provisional_forecast_hits} hit / {m.provisional_forecast_misses} miss; {m.provisional_forecast_scorable} scorable checkpoints |",
        f"| Provisional Zone Accuracy | {_pct(m.provisional_zone_accuracy_pct)} | {m.provisional_zone_hits} hit / {m.provisional_zone_misses} miss; {m.provisional_zone_scorable} scorable checkpoints |",
        f"| Checkpoint State | {m.provisional_captured_checkpoints} captured / {m.provisional_due_checkpoints} due | Provisional diagnostics; not official closed-call efficacy |",
        f"| {s.ticker} Stock Assessment | {_pct(s.provisional_forecast_accuracy_pct)} forecast / {_pct(s.provisional_zone_accuracy_pct)} zone | {s.provisional_captured_checkpoints} captured; latest observation {_escape(s.latest_checkpoint_observed_at or 'N/A')} |",
    ]

    table2=[
        "| ACTIVE CALLS | Latest Active Recommendation | Current State | Efficacy / Horizon |",
        "|---|---|---|---|",
    ]
    if not assessment.active_calls:
        table2.append("| None | N/A | No active calls | N/A |")
    else:
        for call in assessment.active_calls:
            probs=(
                f"Bull {_fmt(call.bull_probability,1)}% / "
                f"Base {_fmt(call.base_probability,1)}% / "
                f"Bear {_fmt(call.bear_probability,1)}%"
            )
            zone=(
                f"{_fmt(call.zone_low)}–{_fmt(call.zone_high)}"
                if call.zone_low is not None and call.zone_high is not None else "N/A"
            )
            state=(
                f"{_escape(call.outcome_verdict or 'OPEN')}; "
                f"Px {_fmt(call.current_price)}; Return {_pct(call.current_return_pct)}"
            )
            table2.append(
                f"| {_escape(call.ticker)} | {_escape(call.recommendation_id)} — "
                f"{_escape(call.definitive_forecast)}; {_escape(call.definitive_recommendation)} | "
                f"{_escape(state)} | {_escape(probs)}; Zone {_escape(zone)}; Expiry {_escape(call.expiry_trading_date or 'N/A')} |"
            )

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

    table3=[
        "| CURRENT STOCK OUTCOME | EDGE Output | Execution / Level | Interpretation |",
        "|---|---|---|---|",
        f"| Recommendation ID | {_escape(recommendation.recommendation_id)} | Parent {_escape(recommendation.parent_recommendation_id or 'None')} | New immutable assessment |",
        f"| Forecast | {_escape(recommendation.definitive_forecast)} | {_escape(p)} | Highest-probability scenario |",
        f"| Expected Move | {_escape(zone)} | {_escape(recommendation.forecast_horizon)} | Frozen forecast objective |",
        f"| Market Trust | {_fmt(recommendation.market_trust_score,1)} / {_escape(recommendation.market_trust_band)} | DES {_fmt(recommendation.des,1)} | Evidence confidence + directional balance |",
        f"| BOT Hunter | {_fmt(recommendation.bot_score,1)} / {_escape(recommendation.bot_grade)} | {_escape(recommendation.decision_ladder)} | Opportunity quality / commitment state |",
        f"| Definitive Recommendation | {_escape(recommendation.definitive_recommendation)} | {_escape(ep.instrument)} | Final EDGE decision |",
        f"| Entry | {_escape(entry)} | {_escape(ep.invalidation_text or 'N/A')} | Direct recommended execution |",
        f"| Risk Control | Stop {_fmt(ep.stop_price)} | {_escape(ep.risk_unit_category or 'N/A')} | Maximum defined thesis risk |",
        f"| Targets | {_escape(targets)} | R:R T1 {_fmt(ep.rr_t1)} / T2 {_fmt(ep.rr_t2)} | Reward path |",
        f"| Options Contract | {_escape(contract)} | {_escape(ep.option_suitability_status or 'N/A')} | N/A when options branch is gated |",
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
    table4=[
        "| DRILL-DOWN | Score / Level | Key Outcome | Interpretation |",
        "|---|---|---|---|",
    ]
    for label in order:
        key=aliases.get(label)
        if key:
            row=component_by_name.get(key)
            score="Not Verified"
            availability="Not Verified"
            if row is not None:
                availability=row.availability_status
                if row.raw_score is not None:
                    score=str(row.raw_score)
            outcome,interpretation=summaries.get(
                label,(availability,"Component evidence retained in immutable audit record")
            )
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
        table4.append(
            f"| {_escape(label)} | {_escape(score)} | {_escape(outcome)} | {_escape(interpretation)} |"
        )

    return "\n".join(table1)+"\n\n"+"\n".join(table2)+"\n\n"+"\n".join(table3)+"\n\n"+"\n".join(table4)
