import json
from datetime import date, datetime, timezone

from src.historical_cache import _build_document, _record_from_candle
from src.market_providers import ProviderEnvelope, UpstoxReadOnlyStockProvider


class FakeCache:
    def __init__(self, hit=None):
        self.hit=hit
        self.reads=[]
        self.writes=[]

    def read_daily(self,instrument_key,start,end):
        self.reads.append((instrument_key,start,end))
        return self.hit

    def write_daily(self,instrument_key,envelope,requested_start,requested_end):
        self.writes.append((instrument_key,envelope,requested_start,requested_end))
        return "a"*64


class Response:
    def __init__(self,url,payload):
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


class CountingOpener:
    def __init__(self):
        self.calls=[]

    def open(self,request,timeout=20):
        self.calls.append(request.full_url)
        return Response(request.full_url,{
            "status":"success",
            "data":{"candles":[["2026-09-18T00:00:00+00:00",100,105,99,104,1000,0]]},
        })


def test_cache_document_is_sha_bound_and_consumer_namespaced():
    record=_record_from_candle(["2026-09-18T00:00:00+00:00",100,105,99,104,1000,0])
    document=_build_document(
        "EDGE_STOCK:PRICE_CANDLES:NSE_EQ|ABC:1d",
        [record],
        [{"event":"WRITE_THROUGH"}],
    )
    assert document["schema"]=="market-cache-document-v1"
    assert document["series_id"].startswith("EDGE_STOCK:")
    assert len(document["dataset_sha256"])==64
    assert len(document["document_sha256"])==64
    assert document["record_count"]==1


def test_provider_uses_cache_hit_without_upstox_history_call():
    cached=ProviderEnvelope(
        source_ref="upstox:cache:EDGE_STOCK:PRICE_CANDLES:NSE_EQ|ABC:1d#sha256="+"a"*64,
        received_at=datetime.now(timezone.utc),
        path="cache://EDGE_STOCK",
        parameters={},
        payload={"status":"success","data":{"candles":[["2026-09-18T00:00:00+00:00",100,105,99,104,1000,0]]}},
    )
    cache=FakeCache(hit=cached)
    opener=CountingOpener()
    provider=UpstoxReadOnlyStockProvider("token",opener=opener,sleep=lambda _:None,historical_cache=cache)
    result=provider.daily("NSE_EQ|ABC",date(2026,9,18),date(2026,9,18))
    assert result is cached
    assert opener.calls==[]
    assert len(cache.reads)==1
    assert cache.writes==[]


def test_provider_writes_through_after_cache_miss():
    cache=FakeCache(hit=None)
    opener=CountingOpener()
    provider=UpstoxReadOnlyStockProvider("token",opener=opener,sleep=lambda _:None,historical_cache=cache)
    result=provider.daily("NSE_EQ|ABC",date(2026,9,18),date(2026,9,18))
    assert result.payload["status"]=="success"
    assert len(opener.calls)==1
    assert len(cache.writes)==1


def test_cache_failure_never_blocks_authenticated_provider_read():
    class BrokenCache(FakeCache):
        def read_daily(self,*args,**kwargs):
            raise ValueError("corrupt")
        def write_daily(self,*args,**kwargs):
            raise ValueError("unavailable")

    opener=CountingOpener()
    provider=UpstoxReadOnlyStockProvider("token",opener=opener,sleep=lambda _:None,historical_cache=BrokenCache())
    result=provider.daily("NSE_EQ|ABC",date(2026,9,18),date(2026,9,18))
    assert result.payload["data"]["candles"]
    assert len(opener.calls)==1
