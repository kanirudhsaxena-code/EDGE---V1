"""Autonomous read-only Upstox research evidence provider for EDGE Stocks.

Uses only Upstox GET endpoints for instrument search, news, company fundamentals,
and non-trading market indicators. It never accesses positions, holdings, orders,
funds, or trading actions.

The provider returns raw payload envelopes plus evidence observations. Analytical
interpretation remains inside the governed EDGE engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.market_providers import (
    AcquisitionError,
    ProviderEnvelope,
    ProviderObservation,
    ResearchAcquisition,
    UPSTOX_BASE,
    _stage_label,
)

INDIA_VIX = "NSE_INDEX|India VIX"
BRENT = "GLOBAL_INDICATOR|BZUSD"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UpstoxReadOnlyResearchProvider:
    def __init__(self, token: str, opener=None, sleep=time.sleep):
        if not token or not token.strip():
            raise AcquisitionError("UPSTOX_TOKEN_MISSING")
        self._token = token.strip()
        self._opener = opener or build_opener(_NoRedirect())
        self._sleep = sleep

    def _get(self, path: str, params: Optional[Mapping[str, str]] = None) -> ProviderEnvelope:
        params = dict(params or {})
        allowed_exact = {
            "/v2/instruments/search",
            "/v2/news",
            "/v2/market-quote/quotes",
        }
        allowed_prefixes = ("/v2/fundamentals/",)
        if path not in allowed_exact and not any(path.startswith(p) for p in allowed_prefixes):
            raise AcquisitionError("ENDPOINT_NOT_PERMITTED")

        url = UPSTOX_BASE + path + ("?" + urlencode(params) if params else "")
        for attempt in range(3):
            self._sleep(1)
            req = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self._token,
                    "User-Agent": "EDGE-Stocks-Readonly-Research/1.0",
                },
                method="GET",
            )
            try:
                with self._opener.open(req, timeout=20) as response:
                    raw = response.read(8_000_001)
                    final_url = response.geturl()
                if final_url != url or len(raw) > 8_000_000 or not raw:
                    raise AcquisitionError(f"SCHEMA_{_stage_label(path)}")
                payload = json.loads(raw)
                if not isinstance(payload, dict) or payload.get("status") != "success":
                    raise AcquisitionError(f"SCHEMA_{_stage_label(path)}")
                digest = hashlib.sha256(raw).hexdigest()
                return ProviderEnvelope(
                    source_ref=f"upstox:{path}" + (f"?{urlencode(sorted(params.items()))}" if params else "") + f"#sha256={digest}",
                    received_at=datetime.now(timezone.utc),
                    path=path,
                    parameters=params,
                    payload=payload,
                )
            except HTTPError as exc:
                if exc.code in (401, 403):
                    raise AcquisitionError(f"HTTP_{_stage_label(path)}_{exc.code}") from None
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise AcquisitionError(f"HTTP_{_stage_label(path)}_{exc.code}") from None
                self._sleep(2 ** (attempt + 1))
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise AcquisitionError(f"NETWORK_{_stage_label(path)}") from None
                self._sleep(2 ** (attempt + 1))
            except (ValueError, UnicodeError):
                raise AcquisitionError(f"JSON_{_stage_label(path)}") from None
        raise AcquisitionError(f"NETWORK_{_stage_label(path)}")

    def _resolve(self, ticker: str) -> tuple[str, str]:
        symbol = ticker.strip().upper()
        env = self._get(
            "/v2/instruments/search",
            {
                "query": symbol,
                "exchanges": "NSE",
                "segments": "EQ",
                "page_number": "1",
                "records": "30",
            },
        )
        rows = env.payload.get("data")
        if not isinstance(rows, list):
            raise AcquisitionError("RESPONSE_SCHEMA_INVALID")
        exact = [
            r for r in rows
            if isinstance(r, dict)
            and str(r.get("trading_symbol", "")).upper() == symbol
            and r.get("segment") == "NSE_EQ"
            and r.get("instrument_type") == "EQ"
            and r.get("instrument_key")
            and r.get("isin")
        ]
        if len(exact) != 1:
            raise AcquisitionError("INSTRUMENT_NOT_FOUND" if not exact else "AMBIGUOUS_INSTRUMENT")
        return str(exact[0]["instrument_key"]), str(exact[0]["isin"])

    def collect(self, ticker: str, run_at: datetime) -> ResearchAcquisition:
        if run_at.tzinfo is None:
            raise ValueError("run_at must be timezone-aware")
        symbol = ticker.strip().upper()
        instrument_key, isin = self._resolve(symbol)

        news = self._get(
            "/v2/news",
            {
                "category": "instrument_keys",
                "instrument_keys": instrument_key,
                "page_number": "1",
                "page_size": "100",
            },
        )
        profile = self._get(f"/v2/fundamentals/{isin}/profile")
        income = self._get(
            f"/v2/fundamentals/{isin}/income-statement",
            {"type": "consolidated", "time_period": "quarterly"},
        )
        balance = self._get(
            f"/v2/fundamentals/{isin}/balance-sheet",
            {"type": "consolidated"},
        )
        cashflow = self._get(
            f"/v2/fundamentals/{isin}/cash-flow",
            {"type": "consolidated"},
        )
        holdings = self._get(f"/v2/fundamentals/{isin}/share-holdings")
        ratios = self._get(f"/v2/fundamentals/{isin}/key-ratios")
        actions = self._get(f"/v2/fundamentals/{isin}/corporate-actions")
        vix = self._get("/v2/market-quote/quotes", {"instrument_key": INDIA_VIX})
        brent = self._get("/v2/market-quote/quotes", {"instrument_key": BRENT})

        payloads = {
            env.source_ref: env.payload
            for env in (news, profile, income, balance, cashflow, holdings, ratios, actions, vix, brent)
        }

        news_ref = news.source_ref
        fundamental_ref = "|".join([profile.source_ref, income.source_ref, balance.source_ref, cashflow.source_ref])
        event_ref = "|".join([news.source_ref, actions.source_ref, vix.source_ref, brent.source_ref])

        observations = (
            ProviderObservation(
                "NEWS_EVENTS_CATALYSTS", symbol, run_at, news_ref, True, "UPSTOX",
                "INSTRUMENT_NEWS_7D",
                detail="Instrument-specific news feed; raw headlines/summaries retained for governed analysis",
            ),
            ProviderObservation(
                "BUSINESS_FUNDAMENTALS", symbol, run_at, fundamental_ref, True, "UPSTOX",
                "PROFILE_INCOME_BALANCE_CASHFLOW",
                detail="Company profile plus consolidated quarterly income, balance-sheet and cash-flow evidence",
            ),
            ProviderObservation(
                "INSTITUTIONAL_BEHAVIOUR", symbol, run_at, holdings.source_ref, True, "UPSTOX",
                "SHAREHOLDING_PATTERN",
                detail="Quarterly promoter/FII/DII/public shareholding pattern",
            ),
            ProviderObservation(
                "VALUATION", symbol, run_at, ratios.source_ref, True, "UPSTOX",
                "KEY_RATIOS",
                detail="Company vs sector P/E, P/B, ROA, ROE, ROCE and EV/EBITDA",
            ),
            ProviderObservation(
                "EVENT_SHOCK", symbol, run_at, event_ref, True, "UPSTOX",
                "NEWS_CORPORATE_ACTIONS_VIX_BRENT",
                detail="Recent company news/corporate actions plus India VIX and Brent snapshots",
            ),
        )
        return ResearchAcquisition(observations, payloads)
