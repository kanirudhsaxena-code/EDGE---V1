from datetime import date, datetime, timezone

# Upstox checkpoint fallback regression coverage

from src.checkpoint_reconciler import (
    _candle_for_date,
    reconcile_overdue_checkpoints,
)


class Cursor:
    def __init__(self,due_rows):
        self.due_rows=due_rows
        self.mode=None
        self.rowcount=1
        self.calls=[]
    def execute(self,sql,params=None):
        self.calls.append((" ".join(sql.split()),params))
        self.mode="due" if "select oc.checkpoint_id" in sql else "update"
    def fetchall(self):
        return list(self.due_rows) if self.mode=="due" else []
    def close(self): pass


class Conn:
    def __init__(self,due_rows):
        self.c=Cursor(due_rows)
        self.committed=False
        self.rolled=False
    def cursor(self): return self.c
    def commit(self): self.committed=True
    def rollback(self): self.rolled=True


class Env:
    def __init__(self,due):
        self.source_ref="upstox:daily#x"
        self.payload={"status":"success","data":{"candles":[
            [due.isoformat()+"T00:00:00+05:30",300,305,295,302,1000,0]
        ]}}


class Provider:
    def resolve_nse_equity(self,ticker):
        return ("NSE_EQ|X","X")
    def daily(self,key,start,end):
        assert end-start == __import__('datetime').timedelta(days=7)
        return Env(end)
    def daily_legacy(self,key,start,end):
        return Env(end)


def test_candle_exact_date_is_required():
    p={"data":{"candles":[["2026-09-18T00:00:00+05:30",1,3,0.5,2,10,0]]}}
    close,high,low=_candle_for_date(p,date(2026,9,18))
    assert (close,high,low)==(2,3,0.5)


def test_overdue_checkpoint_is_captured_atomically():
    due=date(2026,9,17)
    conn=Conn([(7,"EDGE-LTF-1","LTF","D+1",due)])
    out=reconcile_overdue_checkpoints(
        conn,Provider(),"LTF",datetime(2026,9,18,6,0,tzinfo=timezone.utc)
    )
    assert len(out)==1
    assert out[0].actual_price==302
    assert conn.committed is True
    sql="\n".join(x[0] for x in conn.c.calls)
    assert "update outcome_checkpoints" in sql


def test_today_checkpoint_before_close_is_not_overdue():
    # 06:00 UTC = 11:30 IST, before the 15:35 technical cutoff.
    today=date(2026,9,18)
    conn=Conn([])
    out=reconcile_overdue_checkpoints(
        conn,Provider(),"LTF",datetime(2026,9,18,6,0,tzinfo=timezone.utc)
    )
    assert out==()
    assert conn.committed is False


def test_reconciliation_uses_bounded_lookback_but_requires_exact_due_date():
    due=date(2026,9,18)
    class MultiEnv:
        source_ref="upstox:daily#multi"
        payload={"status":"success","data":{"candles":[
            ["2026-09-17T00:00:00+05:30",290,295,285,292,1000,0],
            ["2026-09-18T00:00:00+05:30",300,307,298,305,1200,0],
        ]}}
    class MultiProvider:
        def resolve_nse_equity(self,ticker): return ("NSE_EQ|X","X")
        def daily(self,key,start,end):
            assert start==date(2026,9,11)
            assert end==due
            return MultiEnv()
    conn=Conn([(8,"EDGE-LTF-2","LTF","D+1",due)])
    out=reconcile_overdue_checkpoints(
        conn,MultiProvider(),"LTF",datetime(2026,9,21,4,30,tzinfo=timezone.utc)
    )
    assert out[0].actual_price==305
    assert out[0].period_high==307
    assert out[0].period_low==298


def test_reconciliation_falls_back_to_upstox_v2_when_v3_omits_due_session():
    due=date(2026,9,18)
    class MissingEnv:
        source_ref="upstox:v3#missing"
        payload={"status":"success","data":{"candles":[
            ["2026-09-17T00:00:00+05:30",290,295,285,292,1000,0]
        ]}}
    class LegacyEnv:
        source_ref="upstox:v2#exact"
        payload={"status":"success","data":{"candles":[
            ["2026-09-18T00:00:00+05:30",300,307,298,305,1200,0]
        ]}}
    class FallbackProvider:
        def resolve_nse_equity(self,ticker): return ("NSE_EQ|X","X")
        def daily(self,key,start,end): return MissingEnv()
        def daily_legacy(self,key,start,end):
            assert start==due and end==due
            return LegacyEnv()
    conn=Conn([(9,"EDGE-LTF-3","LTF","D+1",due)])
    out=reconcile_overdue_checkpoints(
        conn,FallbackProvider(),"LTF",datetime(2026,9,21,4,30,tzinfo=timezone.utc)
    )
    assert out[0].actual_price==305
    assert out[0].source_ref=="upstox:v2#exact"


def test_legacy_nse_holiday_checkpoint_rolls_forward_to_next_trading_session():
    due=date(2026,9,14)  # NSE holiday
    class HolidayEnv:
        source_ref="upstox:v3#holiday-roll"
        payload={"status":"success","data":{"candles":[
            ["2026-09-15T00:00:00+05:30",300,306,294,304,1400,0]
        ]}}
    class HolidayProvider:
        def resolve_nse_equity(self,ticker): return ("NSE_EQ|X","X")
        def daily(self,key,start,end):
            assert end==date(2026,9,15)
            return HolidayEnv()
        def daily_legacy(self,key,start,end):
            raise AssertionError("legacy fallback should not be needed")
    conn=Conn([(10,"EDGE-LTF-HOLIDAY","LTF","D+1",due)])
    out=reconcile_overdue_checkpoints(
        conn,HolidayProvider(),"LTF",datetime(2026,9,22,4,0,tzinfo=timezone.utc)
    )
    assert len(out)==1
    assert out[0].actual_price==304
    assert "calendar_rollforward:2026-09-14->2026-09-15" in out[0].source_ref
    assert conn.committed is True
