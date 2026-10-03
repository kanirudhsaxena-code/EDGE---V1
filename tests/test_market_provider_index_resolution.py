from datetime import datetime, timezone

import pytest

from src.market_providers import AcquisitionError, ProviderEnvelope, UpstoxReadOnlyStockProvider


def _provider(rows_by_query):
    provider = UpstoxReadOnlyStockProvider("test-token", sleep=lambda _x: None)

    def fake_get(path, params=None):
        assert path == "/v2/instruments/search"
        query = str((params or {}).get("query", ""))
        rows = rows_by_query.get(query, [])
        return ProviderEnvelope(
            source_ref=f"upstox:{path}?query={query}",
            received_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
            path=path,
            parameters=dict(params or {}),
            payload={"status": "success", "data": rows},
        )

    provider._get = fake_get
    return provider


def _index(name, symbol, key=None):
    return {
        "name": name,
        "trading_symbol": symbol,
        "instrument_key": key or f"NSE_INDEX|{name}",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
    }


def test_oil_and_gas_resolves_provider_spelling_without_changing_governed_identity():
    provider = _provider({
        "Nifty Oil & Gas": [],
        "Nifty Oil And Gas": [_index(
            "Nifty Oil And Gas",
            "NIFTY_OIL_AND_GAS",
            "NSE_INDEX|Nifty Oil And Gas",
        )],
    })
    key, governed_name = provider.resolve_nse_index("Nifty Oil & Gas")
    assert key == "NSE_INDEX|Nifty Oil And Gas"
    assert governed_name == "Nifty Oil & Gas"


def test_financial_services_existing_provider_alias_remains_exact():
    provider = _provider({
        "Nifty Financial Services": [],
        "Nifty Fin Service": [_index(
            "Nifty Fin Service",
            "FINNIFTY",
            "NSE_INDEX|Nifty Fin Service",
        )],
    })
    key, governed_name = provider.resolve_nse_index("Nifty Financial Services")
    assert key == "NSE_INDEX|Nifty Fin Service"
    assert governed_name == "Nifty Financial Services"


@pytest.mark.parametrize("governed", [
    "Nifty Private Bank",
    "Nifty PSU Bank",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Healthcare",
    "Nifty Auto",
    "Nifty FMCG",
    "Nifty Metal",
    "Nifty Realty",
    "Nifty Media",
    "Nifty Consumer Durables",
])
def test_governed_sector_benchmarks_resolve_exact_provider_identity(governed):
    symbol = governed.upper().replace(" & ", "_AND_").replace(" ", "_")
    provider = _provider({governed: [_index(governed, symbol)]})
    key, resolved = provider.resolve_nse_index(governed)
    assert key == f"NSE_INDEX|{governed}"
    assert resolved == governed


def test_sector_resolver_never_falls_back_to_nifty50():
    provider = _provider({
        "Nifty Oil & Gas": [_index("Nifty 50", "NIFTY", "NSE_INDEX|Nifty 50")],
        "Nifty Oil And Gas": [_index("Nifty 50", "NIFTY", "NSE_INDEX|Nifty 50")],
        "NIFTY_OIL_AND_GAS": [_index("Nifty 50", "NIFTY", "NSE_INDEX|Nifty 50")],
    })
    with pytest.raises(AcquisitionError, match="INSTRUMENT_NOT_FOUND"):
        provider.resolve_nse_index("Nifty Oil & Gas")


def test_ambiguous_governed_alias_fails_closed():
    provider = _provider({
        "Nifty Oil & Gas": [
            _index("Nifty Oil And Gas", "NIFTY_OIL_AND_GAS", "NSE_INDEX|OIL_A"),
            _index("Nifty Oil And Gas", "NIFTY_OIL_AND_GAS", "NSE_INDEX|OIL_B"),
        ],
    })
    with pytest.raises(AcquisitionError, match="AMBIGUOUS_INSTRUMENT"):
        provider.resolve_nse_index("Nifty Oil & Gas")
