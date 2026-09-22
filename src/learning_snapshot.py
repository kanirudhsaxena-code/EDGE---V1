"""EDGE Stocks VNext Learning Lab immutable snapshot helpers.

Pure transformation only. No scoring, recommendation, execution or production
configuration mutation is possible from this module.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

RUN_ROLES={"CANONICAL","DIAGNOSTIC","MANUAL","SHADOW"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)


def content_hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_outcome_observation(row: Mapping[str,Any]) -> dict[str,Any] | None:
    verdict=str(row.get("outcome_verdict") or "")
    if verdict in {"","OPEN"}:
        return None
    role=str(row.get("run_role") or "")
    if role not in RUN_ROLES:
        raise ValueError("run_role must be CANONICAL, DIAGNOSTIC, MANUAL or SHADOW")
    eligible=bool(row.get("official_efficacy_eligible"))
    exclusion=row.get("exclusion_reason")
    if not eligible and not exclusion:
        exclusion="NON_CANONICAL"
    target=str(row.get("target_trading_date") or "")
    if not target:
        raise ValueError("target_trading_date is mandatory")
    identity={
        "recommendation_id":row.get("recommendation_id"),
        "target_trading_date":target,
        "outcome_verdict":verdict,
        "observed_at":row.get("observed_at"),
    }
    return {
        "observation_id":"llobs-edge-"+content_hash(identity)[:20],
        "engine":"EDGE_STOCKS",
        "source_run_id":str(row.get("run_id") or row.get("recommendation_id") or ""),
        "recommendation_id":row.get("recommendation_id"),
        "ticker":row.get("ticker"),
        "run_role":role,
        "official_efficacy_eligible":eligible,
        "target_trading_date":target,
        "horizon":"TRADE",
        "dimension":"RECOMMENDATION_OUTCOME",
        "observation_type":"SUCCESS" if verdict=="WIN" else ("ERROR" if verdict=="LOSS" else "NEUTRAL"),
        "outcome_classification":verdict,
        "metrics":{
            "model_return_pct":row.get("model_return_pct"),
            "direction_hit":row.get("direction_hit"),
            "zone_result":row.get("zone_result"),
            "mfe_pct":row.get("mfe_pct"),
            "mae_pct":row.get("mae_pct"),
        },
        "evidence":{"source_ref":row.get("source_ref")},
        "exclusion_reason":exclusion,
        "observed_at":str(row.get("observed_at") or ""),
        "source_ref":str(row.get("source_ref") or f"recommendation:{row.get('recommendation_id')}"),
        "production_change_allowed":False,
    }


def _day_normalized_success(observations: Sequence[Mapping[str,Any]]) -> float | None:
    by_date:dict[str,list[float]]=defaultdict(list)
    for row in observations:
        date=str(row.get("target_trading_date") or "")
        if date:
            by_date[date].append(1.0 if row.get("observation_type")=="SUCCESS" else 0.0)
    daily=[sum(values)/len(values) for values in by_date.values() if values]
    return None if not daily else sum(daily)/len(daily)


def build_daily_snapshot(
    *,
    cycle_id:str,
    as_of:str,
    runs:Sequence[Mapping[str,Any]],
    observations:Sequence[Mapping[str,Any]],
    matured_outcomes:Sequence[Mapping[str,Any]],
    hypotheses:Sequence[Mapping[str,Any]]=(),
    challengers:Sequence[Mapping[str,Any]]=(),
    data_quality_state:str="PASS",
    source_lineage:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    roles=Counter(str(row.get("run_role") or "") for row in runs)
    unknown=set(roles)-RUN_ROLES
    if unknown:
        raise ValueError(f"unknown run roles: {sorted(unknown)}")
    scorable=sum(1 for row in matured_outcomes if row.get("scorable") is True)
    gaps=sum(1 for row in matured_outcomes if row.get("data_gap") is True)
    if scorable+gaps>len(matured_outcomes):
        raise ValueError("outcome populations overlap or exceed matured outcomes")
    active_hypotheses=sum(1 for row in hypotheses if row.get("status") not in {"REJECTED","DEFERRED"})
    active_challengers=sum(1 for row in challengers if row.get("status") in {"CANDIDATE","VALIDATING","PENDING_USER_APPROVAL"})
    approvals=sum(1 for row in challengers if row.get("status")=="PENDING_USER_APPROVAL")
    tickers=sorted({str(row.get("ticker")) for row in runs if row.get("ticker")})
    target_dates=sorted({str(row.get("target_trading_date")) for row in runs if row.get("target_trading_date")})
    content={
        "tickers":tickers,
        "ticker_count":len(tickers),
        "independent_target_date_count":len(target_dates),
        "independent_target_dates":target_dates,
        "day_normalized_success_rate":_day_normalized_success(observations),
        "official_efficacy_population":"SELECTED_CANONICAL_ONLY",
        "learning_population":"ALL_ELIGIBLE_RUN_ROLES_DAY_NORMALIZED",
        "production_change_allowed":False,
    }
    counts={
        "runs_analyzed":len(runs),
        "canonical_runs":roles["CANONICAL"],
        "diagnostic_runs":roles["DIAGNOSTIC"],
        "manual_runs":roles["MANUAL"],
        "shadow_runs":roles["SHADOW"],
        "matured_outcomes":len(matured_outcomes),
        "scorable_outcomes":scorable,
        "data_gap_outcomes":gaps,
        "new_observations":len(observations),
        "active_hypotheses":active_hypotheses,
        "active_challengers":active_challengers,
        "approval_required":approvals,
    }
    payload={
        "engine":"EDGE_STOCKS","cycle_id":cycle_id,"as_of":as_of,
        "snapshot_status":"PARTIAL" if gaps else "COMPLETE",
        "counts":counts,"data_quality_state":data_quality_state,
        "methodology_versions":{"EDGE":"EDGE_V1"},
        "source_lineage":dict(source_lineage or {}),
        "snapshot":content,
    }
    digest=content_hash(payload)
    return {"snapshot_id":"llsnap-edge-"+digest[:24],**payload,"content_hash":digest}
