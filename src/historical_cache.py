"""Durable provider-neutral historical cache for EDGE Stocks.

Execution-layer only. This module mirrors the MDOS market-cache-document-v1
integrity contract used by 5DR while keeping EDGE_STOCK consumer namespacing.
It never changes EDGE scoring, probabilities, zones, DES, Market Trust,
recommendation semantics, learning semantics, or trading behavior.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Optional

from src.market_providers import ProviderEnvelope


CACHE_SCHEMA = "market-cache-document-v1"
PROVIDER_ID = "UPSTOX"
SOURCE_SEMANTIC = "UPSTOX_AUTHENTICATED"


def _json_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("historical cache timestamp invalid")
    if result.tzinfo is None:
        raise ValueError("historical cache timestamp must be timezone-aware")
    return result.astimezone(timezone.utc)


def _record_from_candle(candle: list[Any]) -> dict[str, Any]:
    if not isinstance(candle, list) or len(candle) < 6:
        raise ValueError("historical cache candle invalid")
    stamp = _timestamp(candle[0]).isoformat()
    normalized = [stamp] + list(candle[1:])
    return {"timestamp": stamp, "candle": normalized}


def _series_id(instrument_key: str) -> str:
    key = instrument_key.strip()
    if not key:
        raise ValueError("instrument_key is required")
    return f"EDGE_STOCK:PRICE_CANDLES:{key}:1d"


def _build_document(series_id: str, records: list[dict[str, Any]], audit_events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(records, key=lambda row: row["timestamp"])
    dataset_sha = _json_sha(ordered)
    latest = ordered[-1]["timestamp"] if ordered else None
    core = {
        "schema": CACHE_SCHEMA,
        "series_id": series_id,
        "provider_id": PROVIDER_ID,
        "source_semantic": SOURCE_SEMANTIC,
        "dataset_sha256": dataset_sha,
        "latest_timestamp": latest,
        "record_count": len(ordered),
        "records": ordered,
        "audit_events": audit_events[-100:],
    }
    document_sha = _json_sha(core)
    return {**core, "document_sha256": document_sha}


class PostgresHistoricalCache:
    """Separate DB connection boundary for cache reads/writes.

    A dedicated connection is opened per operation so cache persistence cannot
    accidentally commit or roll back canonical EDGE recommendation state.
    """

    def __init__(self, dsn: str, connect=None):
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("historical cache DATABASE_URL missing")
        if connect is None:
            import psycopg
            connect = psycopg.connect
        if not callable(connect):
            raise ValueError("historical cache connect factory invalid")
        self._dsn = dsn.strip()
        self._connect = connect

    def _read_document(self, series_id: str) -> Optional[dict[str, Any]]:
        with closing(self._connect(self._dsn)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select provider_id, source_semantic, document_sha256::text,
                           dataset_sha256::text, latest_timestamp, record_count, document
                      from market_data_cache.market_cache_documents
                     where series_id=%s
                    """,
                    (series_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        provider_id, source_semantic, document_sha, dataset_sha, latest, count, document = row
        if not isinstance(document, Mapping):
            raise ValueError("historical cache document invalid")
        doc = dict(document)
        if (
            doc.get("schema") != CACHE_SCHEMA
            or doc.get("series_id") != series_id
            or str(doc.get("document_sha256")) != str(document_sha)
            or str(doc.get("dataset_sha256")) != str(dataset_sha)
            or provider_id != PROVIDER_ID
            or source_semantic != SOURCE_SEMANTIC
            or int(count) != len(doc.get("records") or [])
        ):
            raise ValueError("historical cache integrity mismatch")
        core = {k: v for k, v in doc.items() if k != "document_sha256"}
        if _json_sha(core) != str(document_sha):
            raise ValueError("historical cache document hash mismatch")
        if _json_sha(doc.get("records") or []) != str(dataset_sha):
            raise ValueError("historical cache dataset hash mismatch")
        return doc

    def read_daily(self, instrument_key: str, start: date, end: date) -> Optional[ProviderEnvelope]:
        if start > end:
            raise ValueError("historical cache window invalid")
        sid = _series_id(instrument_key)
        doc = self._read_document(sid)
        if doc is None:
            return None
        records = doc.get("records") or []
        selected = [
            row for row in records
            if start <= _timestamp(row["timestamp"]).date() <= end
        ]
        if not selected:
            return None
        earliest = min(_timestamp(row["timestamp"]).date() for row in records)
        latest = max(_timestamp(row["timestamp"]).date() for row in records)
        if earliest > start or latest < end:
            return None
        return ProviderEnvelope(
            source_ref=f"upstox:cache:{sid}#sha256={doc['document_sha256']}",
            received_at=datetime.now(timezone.utc),
            path=f"cache://{sid}",
            parameters={"start": start.isoformat(), "end": end.isoformat()},
            payload={
                "status": "success",
                "data": {"candles": [list(row["candle"]) for row in selected]},
                "cache": {
                    "series_id": sid,
                    "document_sha256": doc["document_sha256"],
                    "dataset_sha256": doc["dataset_sha256"],
                    "provider_id": PROVIDER_ID,
                    "source_semantic": SOURCE_SEMANTIC,
                },
            },
        )

    def write_daily(
        self,
        instrument_key: str,
        envelope: ProviderEnvelope,
        *,
        requested_start: date,
        requested_end: date,
    ) -> str:
        data = envelope.payload.get("data") if isinstance(envelope.payload, Mapping) else None
        candles = data.get("candles") if isinstance(data, Mapping) else None
        if not isinstance(candles, list) or not candles:
            raise ValueError("historical cache cannot persist empty candles")

        sid = _series_id(instrument_key)
        existing = self._read_document(sid)
        merged: dict[str, dict[str, Any]] = {}
        audit = []
        if existing:
            for row in existing.get("records") or []:
                merged[str(row["timestamp"])] = dict(row)
            audit = list(existing.get("audit_events") or [])

        for candle in candles:
            record = _record_from_candle(candle)
            merged[record["timestamp"]] = record

        audit.append({
            "event": "WRITE_THROUGH",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "requested_start": requested_start.isoformat(),
            "requested_end": requested_end.isoformat(),
            "provider_source_ref": envelope.source_ref,
        })
        document = _build_document(sid, list(merged.values()), audit)

        with closing(self._connect(self._dsn)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into market_data_cache.market_cache_documents
                    (series_id,provider_id,source_semantic,document_sha256,dataset_sha256,
                     latest_timestamp,record_count,document,updated_at)
                    values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,now())
                    on conflict(series_id) do update set
                      provider_id=excluded.provider_id,
                      source_semantic=excluded.source_semantic,
                      document_sha256=excluded.document_sha256,
                      dataset_sha256=excluded.dataset_sha256,
                      latest_timestamp=excluded.latest_timestamp,
                      record_count=excluded.record_count,
                      document=excluded.document,
                      updated_at=now()
                    """,
                    (
                        sid,
                        PROVIDER_ID,
                        SOURCE_SEMANTIC,
                        document["document_sha256"],
                        document["dataset_sha256"],
                        document["latest_timestamp"],
                        document["record_count"],
                        json.dumps(document, sort_keys=True, separators=(",", ":")),
                    ),
                )
            conn.commit()
        return document["document_sha256"]
