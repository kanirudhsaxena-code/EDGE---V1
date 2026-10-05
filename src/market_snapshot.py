"""Immutable run-bound stock data snapshot for EDGE.

This module owns the DATA stage only. It acquires authenticated Upstox market
and provider-research evidence before any independent web research is allowed.
It does not score, reconcile, forecast, recommend, or trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from src.market_providers import MarketAcquisition, ProviderObservation, ResearchAcquisition, UpstoxReadOnlyStockProvider
from src.upstox_research import UpstoxReadOnlyResearchProvider

SCHEMA_VERSION="EDGE_MARKET_SNAPSHOT_V1"


@dataclass(frozen=True)
class StoredMarketSnapshot:
    snapshot_id:str
    lifecycle_id:str
    ticker:str
    captured_at:datetime
    market:MarketAcquisition
    provider_research:ResearchAcquisition


def _aware(value:Any)->datetime:
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if dt.tzinfo is None:
        raise ValueError("snapshot timestamp must be timezone-aware")
    return dt


def _observation_payload(row:ProviderObservation)->dict[str,Any]:
    return {
        "category":row.category,
        "ticker":row.ticker,
        "captured_at":row.captured_at.isoformat(),
        "source_ref":row.source_ref,
        "verified":bool(row.verified),
        "provider":row.provider,
        "evidence_type":row.evidence_type,
        "payload_ref":row.payload_ref,
        "detail":row.detail,
    }


def _observation_from_payload(raw:Mapping[str,Any])->ProviderObservation:
    return ProviderObservation(
        category=str(raw["category"]),
        ticker=str(raw["ticker"]),
        captured_at=_aware(raw["captured_at"]),
        source_ref=str(raw["source_ref"]),
        verified=bool(raw["verified"]),
        provider=str(raw["provider"]),
        evidence_type=str(raw["evidence_type"]),
        payload_ref=None if raw.get("payload_ref") is None else str(raw.get("payload_ref")),
        detail=None if raw.get("detail") is None else str(raw.get("detail")),
    )


def _stable_json(value:Any)->str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)


def capture_market_snapshot(
    connection:Any,
    *,
    ticker:str,
    lifecycle_id:str,
    run_at:datetime,
    upstox_token:str,
    trigger_type:str,
    target_session:str|None=None,
    canonical_requested_at:datetime|None=None,
)->StoredMarketSnapshot:
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")
    symbol=ticker.strip().upper()
    lifecycle=lifecycle_id.strip()
    if not lifecycle:
        raise ValueError("lifecycle_id is required")
    trigger=trigger_type.strip().upper()
    if trigger not in {"USER","SCHEDULED"}:
        raise ValueError("trigger_type must be USER or SCHEDULED")

    with connection.cursor() as cur:
        cur.execute(
            """
            insert into edge_run_lifecycles(
              lifecycle_id,ticker,trigger_type,target_session,canonical_requested_at,stage,stage_detail
            ) values (%s,%s,%s,%s,%s,'DATA_PENDING','Authenticated stock data acquisition started')
            on conflict (lifecycle_id) do update
            set updated_at=now(),
                stage=case
                  when edge_run_lifecycles.stage in ('RUN_CREATED','DATA_PENDING','DATA_BLOCKED')
                  then 'DATA_PENDING'
                  else edge_run_lifecycles.stage
                end,
                stage_detail=case
                  when edge_run_lifecycles.stage in ('RUN_CREATED','DATA_PENDING','DATA_BLOCKED')
                  then 'Authenticated stock data acquisition started'
                  else edge_run_lifecycles.stage_detail
                end
            """,
            (lifecycle,symbol,trigger,target_session,canonical_requested_at),
        )
        cur.execute(
            "select ticker,stage,market_snapshot_id from edge_run_lifecycles where lifecycle_id=%s",
            (lifecycle,),
        )
        row=cur.fetchone()
    connection.commit()
    if not row or str(row[0]).upper()!=symbol:
        raise ValueError("lifecycle ticker mismatch")
    if row[2]:
        return load_market_snapshot(connection,str(row[2]),ticker=symbol,lifecycle_id=lifecycle)

    market_provider=UpstoxReadOnlyStockProvider(upstox_token)
    provider_research=UpstoxReadOnlyResearchProvider(upstox_token)
    market=market_provider.acquire_market(symbol,run_at,options_decision_requested=False)
    supporting=provider_research.collect(symbol,run_at)

    payload={
        "schema_version":SCHEMA_VERSION,
        "lifecycle_id":lifecycle,
        "ticker":symbol,
        "captured_at":run_at.astimezone(timezone.utc).isoformat(),
        "market":{
            "instrument_key":market.instrument_key,
            "observations":[_observation_payload(x) for x in market.observations],
            "payloads":dict(market.payloads),
        },
        "provider_research":{
            "observations":[_observation_payload(x) for x in supporting.observations],
            "payloads":dict(supporting.payloads),
        },
    }
    raw=_stable_json(payload)
    digest=hashlib.sha256(raw.encode("utf-8")).hexdigest()
    stamp=run_at.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    snapshot_id=f"EDGE-MKT-{symbol}-{stamp}-{digest[:12]}"

    with connection.cursor() as cur:
        cur.execute(
            """
            insert into edge_market_snapshots(
              snapshot_id,lifecycle_id,ticker,captured_at,provider,payload,payload_hash,status
            ) values (%s,%s,%s,%s,'UPSTOX',%s::jsonb,%s,'DATA_READY')
            """,
            (snapshot_id,lifecycle,symbol,run_at,_stable_json(payload),digest),
        )
        cur.execute(
            """
            update edge_run_lifecycles
               set stage='DATA_READY',
                   market_snapshot_id=%s,
                   stage_detail='Immutable authenticated Upstox data snapshot ready',
                   updated_at=now()
             where lifecycle_id=%s
               and stage='DATA_PENDING'
            """,
            (snapshot_id,lifecycle),
        )
        if cur.rowcount!=1:
            raise RuntimeError("lifecycle did not transition DATA_PENDING -> DATA_READY")
    connection.commit()
    return StoredMarketSnapshot(snapshot_id,lifecycle,symbol,run_at,market,supporting)


def mark_data_blocked(connection:Any,lifecycle_id:str,detail:str)->None:
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                update edge_run_lifecycles
                   set stage='DATA_BLOCKED',stage_detail=%s,updated_at=now()
                 where lifecycle_id=%s
                   and stage in ('RUN_CREATED','DATA_PENDING','DATA_BLOCKED')
                """,
                (str(detail)[:1000],lifecycle_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()


def load_market_snapshot(
    connection:Any,
    snapshot_id:str,
    *,
    ticker:str,
    lifecycle_id:str,
)->StoredMarketSnapshot:
    with connection.cursor() as cur:
        cur.execute(
            """
            select snapshot_id,lifecycle_id,ticker,captured_at,payload,status
              from edge_market_snapshots
             where snapshot_id=%s
             limit 1
            """,
            (snapshot_id.strip(),),
        )
        row=cur.fetchone()
    if not row:
        raise ValueError("market snapshot not found")
    stored_id,stored_lifecycle,stored_ticker,captured_at,payload_raw,status=row
    if str(status)!="DATA_READY":
        raise ValueError("market snapshot is not DATA_READY")
    if str(stored_ticker).upper()!=ticker.strip().upper():
        raise ValueError("market snapshot ticker mismatch")
    if str(stored_lifecycle)!=lifecycle_id.strip():
        raise ValueError("market snapshot lifecycle mismatch")
    payload=payload_raw if isinstance(payload_raw,Mapping) else json.loads(str(payload_raw))
    if payload.get("schema_version")!=SCHEMA_VERSION:
        raise ValueError("market snapshot schema mismatch")
    market_raw=payload.get("market")
    research_raw=payload.get("provider_research")
    if not isinstance(market_raw,Mapping) or not isinstance(research_raw,Mapping):
        raise ValueError("market snapshot payload is incomplete")
    market=MarketAcquisition(
        observations=tuple(_observation_from_payload(x) for x in market_raw.get("observations",[]) if isinstance(x,Mapping)),
        payloads=dict(market_raw.get("payloads",{})),
        instrument_key=str(market_raw.get("instrument_key","")),
    )
    supporting=ResearchAcquisition(
        observations=tuple(_observation_from_payload(x) for x in research_raw.get("observations",[]) if isinstance(x,Mapping)),
        payloads=dict(research_raw.get("payloads",{})),
    )
    if not market.instrument_key or not market.observations or not supporting.observations:
        raise ValueError("market snapshot evidence is incomplete")
    return StoredMarketSnapshot(
        snapshot_id=str(stored_id),
        lifecycle_id=str(stored_lifecycle),
        ticker=str(stored_ticker).upper(),
        captured_at=captured_at if isinstance(captured_at,datetime) else _aware(captured_at),
        market=market,
        provider_research=supporting,
    )


@dataclass(frozen=True)
class StoredAuctionSnapshot:
    auction_snapshot_id:str
    lifecycle_id:str
    ticker:str
    captured_at:datetime
    source_ref:str
    indicative_equilibrium_price:float
    payload:Mapping[str,Any]


def _auction_iep(payload:Mapping[str,Any])->float|None:
    data=payload.get("data")
    rows=[]
    if isinstance(data,Mapping):
        rows.append(data)
        rows.extend(value for value in data.values() if isinstance(value,Mapping))
    for row in rows:
        candidates=[row.get("indicative_equilibrium_price")]
        ltpc=row.get("ltpc")
        if isinstance(ltpc,Mapping):
            candidates.append(ltpc.get("iep"))
        for value in candidates:
            try:
                iep=float(value)
            except (TypeError,ValueError):
                continue
            if iep>0:
                return iep
    return None


def capture_auction_snapshot(
    connection:Any,
    *,
    ticker:str,
    lifecycle_id:str,
    run_at:datetime,
    upstox_token:str,
)->StoredAuctionSnapshot:
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")
    local=run_at.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata"))
    clock=local.timetz().replace(tzinfo=None)
    from datetime import time
    if local.weekday()>=5 or not (time(9,10)<=clock<time(9,15)):
        raise ValueError("auction snapshot is outside governed 09:10-09:15 IST window")

    symbol=ticker.strip().upper()
    lifecycle=lifecycle_id.strip()
    with connection.cursor() as cur:
        cur.execute(
            """
            select ticker,stage,market_snapshot_id,research_bundle_id,auction_snapshot_id
              from edge_run_lifecycles
             where lifecycle_id=%s
             limit 1
            """,
            (lifecycle,),
        )
        row=cur.fetchone()
    if not row:
        raise ValueError("lifecycle not found")
    if str(row[0]).upper()!=symbol:
        raise ValueError("lifecycle ticker mismatch")
    if str(row[1]) not in {"AUCTION_PENDING","AUCTION_READY"}:
        raise ValueError("auction requires AUCTION_PENDING lifecycle")
    if not row[2] or not row[3]:
        raise ValueError("auction lifecycle DATA/RESEARCH lineage is incomplete")
    if row[4]:
        return load_auction_snapshot(connection,str(row[4]),ticker=symbol,lifecycle_id=lifecycle)

    provider=UpstoxReadOnlyStockProvider(upstox_token)
    instrument_key,_=provider.resolve_nse_equity(symbol)
    quote=provider.quote(instrument_key)
    iep=_auction_iep(quote.payload)
    if iep is None:
        raise ValueError("pre-open indicative equilibrium price is unavailable from Upstox quote")

    payload={
        "schema_version":"EDGE_AUCTION_SNAPSHOT_V1",
        "lifecycle_id":lifecycle,
        "ticker":symbol,
        "captured_at":run_at.astimezone(timezone.utc).isoformat(),
        "instrument_key":instrument_key,
        "source_ref":quote.source_ref,
        "quote":quote.payload,
        "indicative_equilibrium_price":iep,
    }
    raw=_stable_json(payload)
    digest=hashlib.sha256(raw.encode("utf-8")).hexdigest()
    stamp=run_at.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    auction_id=f"EDGE-AUCT-{symbol}-{stamp}-{digest[:12]}"

    with connection.cursor() as cur:
        cur.execute(
            """
            insert into edge_auction_snapshots(
              auction_snapshot_id,lifecycle_id,ticker,captured_at,provider,source_ref,
              indicative_equilibrium_price,payload,payload_hash,status
            ) values (%s,%s,%s,%s,'UPSTOX',%s,%s,%s::jsonb,%s,'AUCTION_READY')
            """,
            (auction_id,lifecycle,symbol,run_at,quote.source_ref,iep,raw,digest),
        )
        cur.execute(
            """
            update edge_run_lifecycles
               set auction_snapshot_id=%s,
                   stage='AUCTION_READY',
                   stage_detail='Frozen pre-open AUCTION snapshot ready for governed computation',
                   updated_at=now()
             where lifecycle_id=%s
               and stage='AUCTION_PENDING'
            """,
            (auction_id,lifecycle),
        )
        if cur.rowcount!=1:
            raise RuntimeError("lifecycle did not transition AUCTION_PENDING -> AUCTION_READY")
    connection.commit()
    return StoredAuctionSnapshot(
        auction_snapshot_id=auction_id,
        lifecycle_id=lifecycle,
        ticker=symbol,
        captured_at=run_at,
        source_ref=quote.source_ref,
        indicative_equilibrium_price=iep,
        payload=payload,
    )


def load_auction_snapshot(
    connection:Any,
    auction_snapshot_id:str,
    *,
    ticker:str,
    lifecycle_id:str,
)->StoredAuctionSnapshot:
    with connection.cursor() as cur:
        cur.execute(
            """
            select auction_snapshot_id,lifecycle_id,ticker,captured_at,source_ref,
                   indicative_equilibrium_price,payload,status
              from edge_auction_snapshots
             where auction_snapshot_id=%s
             limit 1
            """,
            (auction_snapshot_id.strip(),),
        )
        row=cur.fetchone()
    if not row:
        raise ValueError("auction snapshot not found")
    if str(row[7])!="AUCTION_READY":
        raise ValueError("auction snapshot is not AUCTION_READY")
    if str(row[2]).upper()!=ticker.strip().upper():
        raise ValueError("auction snapshot ticker mismatch")
    if str(row[1])!=lifecycle_id.strip():
        raise ValueError("auction snapshot lifecycle mismatch")
    payload=row[6] if isinstance(row[6],Mapping) else json.loads(str(row[6]))
    return StoredAuctionSnapshot(
        auction_snapshot_id=str(row[0]),
        lifecycle_id=str(row[1]),
        ticker=str(row[2]).upper(),
        captured_at=row[3] if isinstance(row[3],datetime) else _aware(row[3]),
        source_ref=str(row[4]),
        indicative_equilibrium_price=float(row[5]),
        payload=payload,
    )
