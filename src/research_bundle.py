"""Governed EDGE Research Bundle V1 reader and independent-validation gate.

This module does not change frozen EDGE weights, probability formulas, BOT, or
recommendation semantics. It validates the ChatGPT research artifact and decides
whether supporting provider-derived research components are eligible to remain
VERIFIED for the frozen computation core.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from typing import Any, Mapping, Optional, Sequence

from src.frozen_engine import ComponentInput
from src.shadow_pipeline import AnalystInterpretation

CONTRACT_VERSION="EDGE_RESEARCH_BUNDLE_V1"
RESEARCH_AUTHORITY="CHATGPT"
MANDATORY_RETRIEVAL_PROVIDER="CHATGPT_WEB"
RESEARCH_SENSITIVE_COMPONENTS={
    "BUSINESS_FUNDAMENTALS",
    "VALUATION",
    "INSTITUTIONAL_BEHAVIOUR",
    "NEWS_EVENTS_CATALYSTS",
    "EVENT_SHOCK",
}
CLAIM_TO_COMPONENT={
    "BUSINESS_FUNDAMENTALS":"BUSINESS_FUNDAMENTALS",
    "VALUATION":"VALUATION",
    "INSTITUTIONAL_BEHAVIOUR":"INSTITUTIONAL_BEHAVIOUR",
    "NEWS_EVENTS_CATALYSTS":"NEWS_EVENTS_CATALYSTS",
    "EVENT_SHOCK":"EVENT_SHOCK",
}


@dataclass(frozen=True)
class GovernedResearchBundle:
    bundle_id:str
    ticker:str
    research_fresh_at:datetime
    payload:Mapping[str,Any]
    verified_components:frozenset[str]
    source_refs_by_component:Mapping[str,tuple[str,...]]


@dataclass(frozen=True)
class ResearchBundleGate:
    ready:bool
    blockers:tuple[str,...]
    warnings:tuple[str,...]


def _aware(value:Any)->Optional[datetime]:
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except Exception:
        return None
    return dt if dt.tzinfo is not None else None


def _payload(row_value:Any)->Mapping[str,Any]:
    if isinstance(row_value,Mapping):
        return row_value
    if isinstance(row_value,str):
        parsed=json.loads(row_value)
        if isinstance(parsed,Mapping):
            return parsed
    raise ValueError("research bundle payload must be a JSON object")


def validate_research_bundle_payload(
    payload:Mapping[str,Any],
    *,
    ticker:str,
    run_at:datetime,
)->ResearchBundleGate:
    blockers:list[str]=[]
    warnings:list[str]=[]
    symbol=ticker.strip().upper()

    if payload.get("contract_version")!=CONTRACT_VERSION:
        blockers.append("research contract version mismatch")
    if str(payload.get("research_authority","")).upper()!=RESEARCH_AUTHORITY:
        blockers.append("research_authority must be CHATGPT")
    if str(payload.get("ticker","")).upper()!=symbol:
        blockers.append("research bundle ticker mismatch")

    providers={str(x).upper() for x in payload.get("retrieval_providers",[]) if x}
    if MANDATORY_RETRIEVAL_PROVIDER not in providers:
        blockers.append("CHATGPT_WEB research is mandatory")
    for p in providers:
        if p not in {"CHATGPT_WEB","EXA","UPSTOX"}:
            blockers.append(f"unknown retrieval provider {p}")

    fresh=_aware(payload.get("research_fresh_at"))
    if fresh is None:
        blockers.append("research_fresh_at is invalid")
    else:
        age=(run_at.astimezone(timezone.utc)-fresh.astimezone(timezone.utc)).total_seconds()/60.0
        if age < -2:
            blockers.append("research bundle is future-dated")
        elif age > 24*60:
            blockers.append("research bundle is stale (>24h)")

    sources=payload.get("sources")
    if not isinstance(sources,list) or not sources:
        blockers.append("research sources are required")
        sources=[]
    source_by_id={}
    for i,raw in enumerate(sources):
        if not isinstance(raw,Mapping):
            blockers.append(f"source {i+1} is invalid")
            continue
        sid=str(raw.get("source_id","")).strip()
        url=str(raw.get("url","")).strip()
        provider=str(raw.get("provider","")).upper()
        if not sid or sid in source_by_id:
            blockers.append(f"source {i+1} id is blank or duplicated")
            continue
        if not url.startswith(("http://","https://")):
            blockers.append(f"source {sid} URL is invalid")
        if provider not in {"CHATGPT_WEB","EXA","UPSTOX"}:
            blockers.append(f"source {sid} provider is invalid")
        source_by_id[sid]=raw

    claims=payload.get("claims")
    if not isinstance(claims,list) or not claims:
        blockers.append("research claims are required")
        claims=[]

    verified_components:set[str]=set()
    for i,raw in enumerate(claims):
        if not isinstance(raw,Mapping):
            blockers.append(f"claim {i+1} is invalid")
            continue
        category=str(raw.get("evidence_category","")).upper()
        status=str(raw.get("verification_status","")).upper()
        materiality=str(raw.get("materiality","")).upper()
        ids=raw.get("source_ids")
        if not isinstance(ids,list) or not ids:
            blockers.append(f"claim {i+1} has no source_ids")
            continue
        used=[source_by_id.get(str(sid)) for sid in ids]
        if any(x is None for x in used):
            blockers.append(f"claim {i+1} references an unknown source")
            continue
        providers_used={str(x.get("provider","")).upper() for x in used if isinstance(x,Mapping)}
        independent=bool(providers_used & {"CHATGPT_WEB","EXA"})
        if materiality in {"HIGH","CRITICAL"} and status=="VERIFIED":
            if raw.get("independent_validation") is not True or not independent:
                blockers.append(f"claim {i+1} material VERIFIED claim lacks independent web validation")
        if status=="CONFLICTED" and materiality in {"HIGH","CRITICAL"}:
            blockers.append(f"claim {i+1} has unresolved material conflict")
        component=CLAIM_TO_COMPONENT.get(category)
        if component and status=="VERIFIED" and independent:
            verified_components.add(component)

    missing=sorted(RESEARCH_SENSITIVE_COMPONENTS-verified_components)
    if missing:
        warnings.append("research-sensitive components without independent VERIFIED support: "+", ".join(missing))

    return ResearchBundleGate(not blockers,tuple(blockers),tuple(warnings))


def load_governed_research_bundle(
    connection:Any,
    bundle_id:str,
    *,
    ticker:str,
    run_at:datetime,
)->GovernedResearchBundle:
    if not bundle_id or not bundle_id.strip():
        raise ValueError("research_bundle_id is required")
    with connection.cursor() as cur:
        cur.execute(
            """
            select bundle_id,ticker,research_fresh_at,payload,status
              from edge_research_bundles
             where bundle_id=%s
             limit 1
            """,
            (bundle_id.strip(),),
        )
        row=cur.fetchone()
    if not row:
        raise ValueError("research bundle not found")
    stored_id,stored_ticker,stored_fresh,payload_raw,status=row
    if str(status)!="READY":
        raise ValueError("research bundle is not READY")
    payload=_payload(payload_raw)
    gate=validate_research_bundle_payload(payload,ticker=ticker,run_at=run_at)
    if not gate.ready:
        raise ValueError("research bundle blocked: "+"; ".join(gate.blockers))

    source_by_id={str(x["source_id"]):x for x in payload.get("sources",[]) if isinstance(x,Mapping) and x.get("source_id")}
    refs:dict[str,list[str]]={}
    verified:set[str]=set()
    for claim in payload.get("claims",[]):
        if not isinstance(claim,Mapping) or str(claim.get("verification_status","")).upper()!="VERIFIED":
            continue
        component=CLAIM_TO_COMPONENT.get(str(claim.get("evidence_category","")).upper())
        if not component:
            continue
        urls=[]
        for sid in claim.get("source_ids",[]):
            source=source_by_id.get(str(sid))
            if source and str(source.get("provider","")).upper() in {"CHATGPT_WEB","EXA"}:
                url=str(source.get("url","")).strip()
                if url:
                    urls.append(url)
        if urls:
            verified.add(component)
            refs.setdefault(component,[]).extend(urls)
    return GovernedResearchBundle(
        bundle_id=str(stored_id),
        ticker=str(stored_ticker).upper(),
        research_fresh_at=stored_fresh if isinstance(stored_fresh,datetime) else _aware(stored_fresh) or run_at,
        payload=payload,
        verified_components=frozenset(verified),
        source_refs_by_component={k:tuple(dict.fromkeys(v)) for k,v in refs.items()},
    )


def apply_independent_research_validation(
    interpretation:AnalystInterpretation,
    research:GovernedResearchBundle,
)->AnalystInterpretation:
    rows=[]
    summaries=dict(interpretation.component_summaries or {})
    for row in interpretation.component_scores:
        name=row.component.strip().upper()
        if name not in RESEARCH_SENSITIVE_COMPONENTS:
            rows.append(row)
            continue
        if name not in research.verified_components:
            rows.append(ComponentInput(name,None,verified=False))
            summaries[name]=(
                "NOT VERIFIED",
                "Supporting provider evidence was excluded because fresh independent ChatGPT web validation was unavailable."
            )
            continue
        rows.append(row)
        prior=summaries.get(name,("VERIFIED",""))
        count=len(research.source_refs_by_component.get(name,()))
        suffix=f" Independent ChatGPT web research validated this component using {count} source(s) in {research.bundle_id}."
        summaries[name]=(prior[0],(prior[1]+suffix).strip())
    return replace(
        interpretation,
        component_scores=tuple(rows),
        component_summaries=summaries,
    )
