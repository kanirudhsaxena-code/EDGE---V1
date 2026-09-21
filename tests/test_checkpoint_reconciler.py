from datetime import date, datetime, timezone

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
