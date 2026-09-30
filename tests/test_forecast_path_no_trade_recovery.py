from datetime import date, datetime, timezone
import json

from src.forecast_path import ForecastPathRow, ForecastPathWrite, forecast_path_hash
from src.forecast_path_read import ForecastPathReadAdapter


def no_trade_fixture():
    rows=[]
    targets=(date(2026,9,18),date(2026,9,21),date(2026,9,22),date(2026,9,23),date(2026,9,24))
    for i,(label,target) in enumerate(zip(("D","D+1","D+2","D+3","D+4"),targets)):
        rows.append(ForecastPathRow(
            label,target,"BASE",25.0,50.0,25.0,280.0+i,320.0+i,
            "TEST/SYNTHETIC/SHADOW NO TRADE engineering fixture",
            "NO_TRADE/RANGE","VERIFIED",
            {"mode":"TEST/SYNTHETIC/SHADOW","recommendation_state":"NO_TRADE","production_visible":False,"evidence_ref":f"no-trade-fixture:{i}"},
            300.0+i,
        ))
    return ForecastPathWrite(
        "TEST-SYNTHETIC-SHADOW-NO-TRADE-LTF-20260918-01",
        "test-shadow-no-trade-run-1",
        datetime(2026,9,18,4,0,tzinfo=timezone.utc),
        tuple(rows),
    )


class Cursor:
    def __init__(self,path): self.path=path
    def execute(self,sql,params): pass
    def fetchone(self):
        p=self.path
        return (p.version,p.source_run_id,p.issued_at,forecast_path_hash(p))
    def fetchall(self):
        return [
            (i,r.horizon_label,r.target_trading_date,r.direction,r.bull_probability,r.base_probability,
             r.bear_probability,r.expected_centre,r.outer_expected_zone_low,r.outer_expected_zone_high,
             r.evidence_basis,r.regime_context,r.verification_state,json.dumps(dict(r.lineage)))
            for i,r in enumerate(self.path.rows)
        ]
    def close(self): pass


class Conn:
    def __init__(self,path): self.cur=Cursor(path)
    def cursor(self): return self.cur
    def close(self): pass


def test_no_trade_path_recovers_all_five_rows_with_identity_and_lineage():
    original=no_trade_fixture()
    recovered=ForecastPathReadAdapter(lambda:Conn(original)).recover(original.recommendation_id)
    assert tuple(r.horizon_label for r in recovered.rows)==("D","D+1","D+2","D+3","D+4")
    assert forecast_path_hash(recovered)==forecast_path_hash(original)
    assert all(r.lineage["recommendation_state"]=="NO_TRADE" for r in recovered.rows)
    assert all(r.lineage["production_visible"] is False for r in recovered.rows)
