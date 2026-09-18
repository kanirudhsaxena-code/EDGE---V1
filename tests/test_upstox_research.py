import json
from datetime import datetime, timezone

from src.upstox_research import UpstoxReadOnlyResearchProvider

RUN_AT = datetime(2026,9,18,4,0,tzinfo=timezone.utc)


class Response:
    def __init__(self, url, payload):
        self._url=url
        self._raw=json.dumps(payload).encode()
    def read(self,n):
        return self._raw
    def geturl(self):
        return self._url
    def __enter__(self):
        return self
    def __exit__(self,*args):
        pass


class Opener:
    def open(self, request, timeout=20):
        url=request.full_url
        if "/v2/instruments/search" in url:
            payload={"status":"success","data":[{
                "name":"L&T FINANCE LTD",
                "segment":"NSE_EQ",
                "instrument_type":"EQ",
                "instrument_key":"NSE_EQ|INE498L01015",
                "isin":"INE498L01015",
                "trading_symbol":"LTF"
            }]}
        elif "/v2/news" in url:
            payload={"status":"success","data":{"NSE_EQ|INE498L01015":[{
                "heading":"test","summary":"test","published_time":1789700000000
            }]}}
        elif "/profile" in url:
            payload={"status":"success","data":{"company_profile":"NBFC"}}
        elif "/income-statement" in url:
            payload={"status":"success","data":[{"period":"Q1"}]}
        elif "/balance-sheet" in url:
            payload={"status":"success","data":{"balance_sheet":[]}}
        elif "/cash-flow" in url:
            payload={"status":"success","data":{"cash_flow":[]}}
        elif "/share-holdings" in url:
            payload={"status":"success","data":[{"holder":"FII"}]}
        elif "/key-ratios" in url:
            payload={"status":"success","data":[{"name":"P/E","company_value":"20","sector_value":"18"}]}
        elif "/corporate-actions" in url:
            payload={"status":"success","data":[]}
        elif "/market-quote/quotes" in url:
            payload={"status":"success","data":{"quote":{"last_price":15}}}
        else:
            raise AssertionError(url)
        return Response(url,payload)


def test_research_provider_covers_core_and_optional_research_categories():
    p=UpstoxReadOnlyResearchProvider("token",opener=Opener(),sleep=lambda _:None)
    result=p.collect("LTF",RUN_AT)
    cats={x.category for x in result.observations}
    assert {
        "NEWS_EVENTS_CATALYSTS",
        "BUSINESS_FUNDAMENTALS",
        "EVENT_SHOCK",
        "INSTITUTIONAL_BEHAVIOUR",
        "VALUATION",
    } <= cats
    assert len(result.payloads) == 10


def test_research_provider_is_read_only():
    p=UpstoxReadOnlyResearchProvider("token",opener=Opener(),sleep=lambda _:None)
    result=p.collect("LTF",RUN_AT)
    refs=" ".join(result.payloads)
    assert "order" not in refs.lower()
    assert "position" not in refs.lower()
    assert "holding?" not in refs.lower()
