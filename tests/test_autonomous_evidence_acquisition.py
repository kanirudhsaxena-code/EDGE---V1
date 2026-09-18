import json
from datetime import datetime, timezone
from io import BytesIO

from src.autonomous_evidence_acquisition import AutonomousEvidenceAcquirer
from src.market_providers import ProviderObservation, ResearchAcquisition, UpstoxReadOnlyStockProvider


RUN_AT = datetime(2026, 9, 18, 4, 0, tzinfo=timezone.utc)


class Response:
    def __init__(self, url, payload):
        self._url = url
        self._raw = json.dumps(payload).encode()

    def read(self, n):
        return self._raw

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeOpener:
    def __init__(self, ticker="LTF", include_chain=True):
        self.ticker = ticker
        self.include_chain = include_chain

    def open(self, request, timeout=20):
        url = request.full_url
        if "/v2/instruments/search" in url:
            payload = {
                "status": "success",
                "data": [{
                    "name": "L&T FINANCE LTD",
                    "segment": "NSE_EQ",
                    "exchange": "NSE",
                    "instrument_key": "NSE_EQ|INE498L01015",
                    "trading_symbol": self.ticker,
                    "instrument_type": "EQ",
                }],
            }
        elif "/v2/market-quote/quotes" in url or "/v3/market-quote/quotes" in url:
            payload = {"status":"success","data":{"quote":{"last_price":302.3}}}
        elif "/v3/historical-candle/" in url:
            payload = {
                "status":"success",
                "data":{"candles":[["2026-09-18T09:15:00+05:30",300,303,299,302,100000,5000]]},
            }
        elif "/v2/option/contract" in url:
            payload = {
                "status":"success",
                "data": ([{
                    "expiry":"2026-09-24",
                    "underlying_key":"NSE_EQ|INE498L01015",
                }] if self.include_chain else []),
            }
        elif "/v2/option/chain" in url:
            payload = {"status":"success","data":[{"strike_price":300}]}
        else:
            raise AssertionError(url)
        return Response(url, payload)


class Research:
    def collect(self, ticker, run_at):
        rows = (
            ProviderObservation("NEWS_EVENTS_CATALYSTS",ticker,run_at,"web:news",True,"WEB","NEWS"),
            ProviderObservation("BUSINESS_FUNDAMENTALS",ticker,run_at,"web:fund",True,"WEB","FUND"),
            ProviderObservation("EVENT_SHOCK",ticker,run_at,"web:event",True,"WEB","EVENT"),
        )
        return ResearchAcquisition(rows, {"web:news":{"ok":True},"web:fund":{"ok":True},"web:event":{"ok":True}})


def provider(include_chain=True):
    return UpstoxReadOnlyStockProvider(
        "token",
        opener=FakeOpener(include_chain=include_chain),
        sleep=lambda _: None,
    )


def test_market_plus_research_satisfies_core_gate():
    acquirer = AutonomousEvidenceAcquirer(provider(), [Research()])
    bundle = acquirer.acquire("LTF", RUN_AT)
    assert bundle.gate.ready is True
    cats = {e.category for e in bundle.evidence}
    assert {"PRICE_STRUCTURE","PV_PVPO","SPECIFIC_CHART_PATTERN","RELATIVE_STRENGTH"} <= cats
    assert {"NEWS_EVENTS_CATALYSTS","BUSINESS_FUNDAMENTALS","EVENT_SHOCK"} <= cats


def test_missing_research_fails_closed():
    bundle = AutonomousEvidenceAcquirer(provider()).acquire("LTF", RUN_AT)
    assert bundle.gate.ready is False
    text = " ".join(bundle.gate.blockers)
    assert "NEWS_EVENTS_CATALYSTS" in text
    assert "BUSINESS_FUNDAMENTALS" in text
    assert "EVENT_SHOCK" in text


def test_options_decision_requires_actual_chain():
    bundle = AutonomousEvidenceAcquirer(
        provider(include_chain=False), [Research()]
    ).acquire("LTF", RUN_AT, options_decision_requested=True)
    assert bundle.gate.ready is False
    assert any("DERIVATIVES_OPTIONS" in b for b in bundle.gate.blockers)


def test_market_provider_never_needs_trading_endpoint():
    p = provider()
    market = p.acquire_market("LTF", RUN_AT)
    assert market.instrument_key.startswith("NSE_EQ|")
    assert all("order" not in ref.lower() for ref in market.payloads)


def test_exact_symbol_resolution_rejects_ambiguous_or_missing_symbol():
    p = UpstoxReadOnlyStockProvider(
        "token", opener=FakeOpener(ticker="OTHER"), sleep=lambda _: None
    )
    try:
        p.resolve_nse_equity("LTF")
    except Exception as exc:
        assert "INSTRUMENT_NOT_FOUND" in str(exc)
    else:
        raise AssertionError("must reject non-exact instrument search result")
