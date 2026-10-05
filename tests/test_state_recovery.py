from datetime import date, datetime, timezone

from src.state_recovery import recover_pre_run_state


class Cursor:
    def __init__(self, report_row, open_rows):
        self.report_row=report_row
        self.open_rows=open_rows
        self.mode=None
        self.calls=[]
    def execute(self,sql,params=None):
        self.calls.append((" ".join(sql.split()),params))
        self.mode="report" if "from v_edge_stock_report" in sql else "open"
    def fetchone(self):
        return self.report_row if self.mode=="report" else None
    def fetchall(self):
        return list(self.open_rows) if self.mode=="open" else []
    def close(self): pass


class Conn:
    def __init__(self,report_row,open_rows):
        self.c=Cursor(report_row,open_rows)
    def cursor(self): return self.c


def test_recover_maps_canonical_views_into_gate_state():
    report=(0,None,None,3,3,2,1,3,3,0)
    rows=[(
        "EDGE-LTF-1","LTF","OPEN",date(2026,9,24),
        5,1,datetime(2026,9,17,11,17,tzinfo=timezone.utc),0
    )]
    state=recover_pre_run_state(
        Conn(report,rows),"LTF",datetime(2026,9,18,6,0,tzinfo=timezone.utc)
    )
    assert state.efficacy_snapshot.official_sample_size==0
    assert state.efficacy_snapshot.provisional_forecast_hits==2
    assert len(state.open_recommendations)==1
    assert state.open_recommendations[0].overdue_checkpoint_count==0


def test_new_ticker_without_report_gets_zero_snapshot():
    state=recover_pre_run_state(
        Conn(None,[]),"NEW",datetime(2026,9,18,6,0,tzinfo=timezone.utc)
    )
    assert state.efficacy_snapshot.official_sample_size==0
    assert state.efficacy_snapshot.provisional_captured_checkpoints==0
    assert state.open_recommendations==()


def test_same_day_due_checkpoint_is_not_classified_overdue_by_recovery_query():
    # 15:00 UTC = 20:30 IST: after cash close, while provider EOD publication may still lag.
    conn=Conn(None,[])
    recover_pre_run_state(
        conn,"LTF",datetime(2026,10,5,15,0,tzinfo=timezone.utc)
    )
    open_call=[call for call in conn.c.calls if "from recommendations r" in call[0]][0]
    sql,params=open_call
    assert "oc.due_date < %s" in sql
    assert "oc.due_date = %s" not in sql
    assert params==(date(2026,10,5),"LTF")
