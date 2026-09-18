from datetime import date, datetime, timezone

from src.state_recovery import recover_pre_run_state


class Cursor:
    def __init__(self, report_row, open_rows):
        self.report_row=report_row
        self.open_rows=open_rows
        self.mode=None
    def execute(self,sql,params=None):
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
