"""Read-only provider adapters for autonomous EDGE Stocks evidence acquisition.

Execution-layer only:
- GET requests only
- explicit Upstox endpoint allowlist
- no order/trade/account endpoints
- no credentials in diagnostics
- bounded response sizes and retry budget

The adapter produces provider observations plus bounded raw payload envelopes for
an injected governed EDGE engine. It does not score or forecast.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
import time
from typing import Any, Mapping, Optional, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

UPSTOX_BASE = "https://api.upstox.com"
NIFTY_50 = "NSE_INDEX|Nifty 50"


class AcquisitionError(RuntimeError):
    pass


def safe_diagnostic(error: Exception) -> str:
    known = {
        "UPSTOX_TOKEN_MISSING": "TOKEN_MISSING",
        "AUTH_REJECTED": "AUTH_REJECTED",
        "NETWORK_FAILED": "NETWORK_FAILED",
        "INVALID_JSON": "INVALID_JSON",
        "RESPONSE_SCHEMA_INVALID": "RESPONSE_SCHEMA_INVALID",
        "INSTRUMENT_NOT_FOUND": "INSTRUMENT_NOT_FOUND",
        "AMBIGUOUS_INSTRUMENT": "AMBIGUOUS_INSTRUMENT",
        "EMPTY_CANDLES": "EMPTY_CANDLES",
        "OPTION_CHAIN_UNAVAILABLE": "OPTION_CHAIN_UNAVAILABLE",
    }
    if isinstance(error, AcquisitionError):
        raw = str(error)
        if raw in known:
            return known[raw]
        if raw.startswith(("HTTP_", "NETWORK_", "SCHEMA_", "JSON_")):
            return raw
        return "ACQUISITION_FAILED"
    return "ACQUISITION_FAILED"


def _upstox_error_code(exc: HTTPError) -> str:
    try:
        raw = exc.read(65536)
        payload = json.loads(raw)
        candidates = []
        if isinstance(payload, dict):
            candidates.extend([
                payload.get("errorCode"),
                payload.get("error_code"),
                payload.get("code"),
            ])
            errors = payload.get("errors")
            if isinstance(errors, list):
                for item in errors:
                    if isinstance(item, dict):
                        candidates.extend([
                            item.get("errorCode"),
                            item.get("error_code"),
                            item.get("code"),
                        ])
        for value in candidates:
            if value:
                cleaned = re.sub(r"[^A-Za-z0-9_-]", "", str(value))[:64]
                if cleaned:
                    return cleaned
    except Exception:
        pass
    return "NO_CODE"


def _stage_label(path: str) -> str:
    if path == "/v2/instruments/search":
        return "INSTRUMENT_SEARCH"
    if path == "/v2/market-quote/quotes":
        return "MARKET_QUOTE"
    if path == "/v2/option/contract":
        return "OPTION_CONTRACT"
    if path == "/v2/option/chain":
        return "OPTION_CHAIN"
    if path.startswith("/v3/historical-candle/intraday/"):
        return "INTRADAY_CANDLE"
    if path.startswith("/v3/historical-candle/"):
        return "HISTORICAL_CANDLE"
    if path.startswith("/v2/fundamentals/"):
        return "FUNDAMENTALS"
    if path == "/v2/news":
        return "NEWS"
    return "UPSTOX"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class ProviderEnvelope:
    source_ref: str
    received_at: datetime
    path: str
    parameters: Mapping[str, str]
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ProviderObservation:
    category: str
    ticker: str
    captured_at: datetime
    source_ref: str
    verified: bool
    provider: str
    evidence_type: str
    payload_ref: Optional[str] = None
    detail: Optional[str] = None


@dataclass(frozen=True)
class MarketAcquisition:
    observations: tuple[ProviderObservation, ...]
    payloads: Mapping[str, Mapping[str, Any]]
    instrument_key: str


@dataclass(frozen=True)
class ResearchAcquisition:
    observations: tuple[ProviderObservation, ...]
    payloads: Mapping[str, Mapping[str, Any]]


class ResearchProvider(Protocol):
    def collect(self, ticker: str, run_at: datetime) -> ResearchAcquisition: ...


class UpstoxReadOnlyStockProvider:
    """Hardened read-only stock market-data provider."""

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
            "/v2/market-quote/quotes",
            "/v2/option/contract",
            "/v2/option/chain",
        }
        allowed_prefixes = (
            "/v3/historical-candle/intraday/",
            "/v3/historical-candle/",
        )
        if path not in allowed_exact and not any(path.startswith(p) for p in allowed_prefixes):
            raise AcquisitionError("ENDPOINT_NOT_PERMITTED")

        url = UPSTOX_BASE + path + ("?" + urlencode(params) if params else "")
        last_error: Optional[Exception] = None
        for attempt in range(3):
            self._sleep(1)
            req = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self._token,
                    "User-Agent": "EDGE-Stocks-Readonly/1.0",
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
                received = datetime.now(timezone.utc)
                digest = hashlib.sha256(raw).hexdigest()
                return ProviderEnvelope(
                    source_ref=f"upstox:{path}" + (f"?{urlencode(sorted(params.items()))}" if params else "") + f"#sha256={digest}",
                    received_at=received,
                    path=path,
                    parameters=params,
                    payload=payload,
                )
            except HTTPError as exc:
                if exc.code in (401, 403):
                    raise AcquisitionError(f"HTTP_{_stage_label(path)}_{exc.code}_{_upstox_error_code(exc)}") from None
                last_error = exc
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise AcquisitionError(f"HTTP_{_stage_label(path)}_{exc.code}") from None
                self._sleep(2 ** (attempt + 1))
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt == 2:
                    raise AcquisitionError(f"NETWORK_{_stage_label(path)}") from None
                self._sleep(2 ** (attempt + 1))
            except (ValueError, UnicodeError):
                raise AcquisitionError(f"JSON_{_stage_label(path)}") from None
        raise AcquisitionError(f"NETWORK_{_stage_label(path)}") from last_error

    def resolve_nse_equity(self, ticker: str) -> tuple[str, str]:
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
        ]
        if not exact:
            raise AcquisitionError("INSTRUMENT_NOT_FOUND")
        keys = {str(r.get("instrument_key", "")) for r in exact if r.get("instrument_key")}
        if len(keys) != 1:
            raise AcquisitionError("AMBIGUOUS_INSTRUMENT")
        row = exact[0]
        return next(iter(keys)), str(row.get("name") or symbol)

    def quote(self, instrument_key: str) -> ProviderEnvelope:
        return self._get("/v2/market-quote/quotes", {"instrument_key": instrument_key})

    def intraday(self, instrument_key: str) -> ProviderEnvelope:
        key = quote(instrument_key, safe="")
        return self._get(f"/v3/historical-candle/intraday/{key}/minutes/1")

    def daily(self, instrument_key: str, start: date, end: date) -> ProviderEnvelope:
        if start > end or (end - start).days > 366:
            raise AcquisitionError("INVALID_HISTORY_RANGE")
        key = quote(instrument_key, safe="")
        return self._get(
            f"/v3/historical-candle/{key}/days/1/{end.isoformat()}/{start.isoformat()}"
        )

    def option_contracts(self, instrument_key: str) -> ProviderEnvelope:
        return self._get("/v2/option/contract", {"instrument_key": instrument_key})

    def option_chain(self, instrument_key: str, expiry: date) -> ProviderEnvelope:
        return self._get(
            "/v2/option/chain",
            {"instrument_key": instrument_key, "expiry_date": expiry.isoformat()},
        )

    @staticmethod
    def _require_candles(env: ProviderEnvelope) -> None:
        data = env.payload.get("data")
        candles = data.get("candles") if isinstance(data, dict) else None
        if not isinstance(candles, list) or not candles:
            raise AcquisitionError("EMPTY_CANDLES")

    def acquire_market(
        self,
        ticker: str,
        run_at: datetime,
        *,
        options_decision_requested: bool = False,
    ) -> MarketAcquisition:
        if run_at.tzinfo is None:
            raise ValueError("run_at must be timezone-aware")
        symbol = ticker.strip().upper()
        instrument_key, _company_name = self.resolve_nse_equity(symbol)

        stock_quote = self.quote(instrument_key)
        stock_intraday = self.intraday(instrument_key)
        stock_daily = self.daily(
            instrument_key,
            run_at.date() - timedelta(days=180),
            run_at.date(),
        )
        benchmark_quote = self.quote(NIFTY_50)
        benchmark_intraday = self.intraday(NIFTY_50)
        benchmark_daily = self.daily(
            NIFTY_50,
            run_at.date() - timedelta(days=180),
            run_at.date(),
        )
        self._require_candles(stock_intraday)
        self._require_candles(stock_daily)
        self._require_candles(benchmark_intraday)
        self._require_candles(benchmark_daily)

        payloads: dict[str, Mapping[str, Any]] = {}
        for env in (stock_quote, stock_intraday, stock_daily, benchmark_quote, benchmark_intraday, benchmark_daily):
            payloads[env.source_ref] = env.payload

        market_ref = "|".join(
            [stock_quote.source_ref, stock_intraday.source_ref, stock_daily.source_ref]
        )
        rs_ref = "|".join([stock_quote.source_ref, benchmark_quote.source_ref, benchmark_intraday.source_ref, benchmark_daily.source_ref])

        observations: list[ProviderObservation] = [
            ProviderObservation(
                "PRICE_STRUCTURE", symbol, run_at, market_ref, True, "UPSTOX",
                "QUOTE_INTRADAY_DAILY", detail="Authenticated stock quote + intraday + daily candles",
            ),
            ProviderObservation(
                "SPECIFIC_CHART_PATTERN", symbol, run_at, market_ref, True, "UPSTOX",
                "INTRADAY_DAILY_CANDLES", detail="Raw candles available for governed pattern analysis",
            ),
            ProviderObservation(
                "RELATIVE_STRENGTH", symbol, run_at, rs_ref, True, "UPSTOX",
                "STOCK_VS_NIFTY50", detail="Stock and Nifty 50 authenticated market observations",
            ),
        ]

        chain_env: Optional[ProviderEnvelope] = None
        try:
            contracts = self.option_contracts(instrument_key)
            rows = contracts.payload.get("data")
            expiries = sorted(
                {
                    date.fromisoformat(str(r["expiry"]))
                    for r in rows
                    if isinstance(r, dict)
                    and r.get("underlying_key") == instrument_key
                    and r.get("expiry")
                    and date.fromisoformat(str(r["expiry"])) >= run_at.date()
                }
            ) if isinstance(rows, list) else []
            if expiries:
                chain_env = self.option_chain(instrument_key, expiries[0])
                chain_rows = chain_env.payload.get("data")
                if not isinstance(chain_rows, list) or not chain_rows:
                    chain_env = None
                else:
                    payloads[contracts.source_ref] = contracts.payload
                    payloads[chain_env.source_ref] = chain_env.payload
        except (AcquisitionError, ValueError, KeyError):
            chain_env = None

        pv_ref = market_ref
        pv_detail = "Price-volume evidence from authenticated quote/candles"
        if chain_env is not None:
            pv_ref += "|" + chain_env.source_ref
            pv_detail += " plus nearest-expiry option-chain OI"
            observations.append(
                ProviderObservation(
                    "DERIVATIVES_OPTIONS", symbol, run_at, chain_env.source_ref, True,
                    "UPSTOX", "OPTION_CHAIN", detail="Nearest active stock option-chain snapshot",
                )
            )
        elif options_decision_requested:
            # Do not synthesize derivatives evidence. The downstream evidence gate
            # will block an options decision because DERIVATIVES_OPTIONS is absent.
            pass

        observations.append(
            ProviderObservation(
                "PV_PVPO", symbol, run_at, pv_ref, True, "UPSTOX",
                "PRICE_VOLUME_OI", detail=pv_detail,
            )
        )

        return MarketAcquisition(tuple(observations), payloads, instrument_key)
