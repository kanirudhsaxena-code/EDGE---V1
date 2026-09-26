from datetime import date, datetime, timezone
import json
import pytest

from src.forecast_path import ForecastPathRow, ForecastPathWrite, forecast_path_hash
from src.forecast_path_read import ForecastPathReadAdapter


def fixture_path():
    rows=[]
    for i,(label,target) in enumerate(zip(("D","D+1","D+2","D+3","D+4"),(date(2026,9,18),date(2026,9,21),date(2026,9,22),date(2026,9,23),date(2026,9,24)))):
        rows.append(ForecastPathRow(label,target,"BASE",30,50,20,295+i,310+i,"TEST/SYNTHETIC/SHADOW realistic past-style fixture","RANGE","VERIFIED",{"mode":"TEST/SYNTHETIC/SHADOW","evidence_ref":f"fixture:{i}","production_visible":False},302+i))
    return ForecastPathWrite("TEST-SYNTHETIC-SHADOW-EDGE-LTF-20260918-01","test-shadow-run-1",datetime(2026,9,18,4,0,tzinfo=timezone.utc),tuple(rows))


class Cursor:
    def __init__(self,path,tamper=False): self.path=path; self.tamper=tamper; self.step=0
    def execute(self,sql,params): self.step += 1
    def fetchone(self):
        p=self.path
        return (p.version,p.source_run_id,p.issued_at,forecast_path_hash(p))
    def fetchall(self):
        out=[]
        for i,r in enumerate(self.path.rows):
            low=r.outer_expected_zone_low + (1 if self.tamper and i==2 else 0)
            out.append((i,r.horizon_label,r.target_trading_date,r.direction,r.bull_probability,r.base_probability,r.bear_probability,r.expected_centre,low,r.outer_expected_zone_high,r.evidence_basis,r.regime_context,r.verification_state,json.dumps(dict(r.lineage))))
        return out
    def close(self): pass


class Conn:
    def __init__(self,path,tamper=False): self.cur=Cursor(path,tamper); self.closed=False
    def cursor(self): return self.cur
    def close(self): self.closed=True


def test_exact_recovery_returns_all_five_ordered_horizons_and_lineage():
    original=fixture_path(); conn=Conn(original)
    recovered=ForecastPathReadAdapter(lambda:conn).recover(original.recommendation_id)
    assert tuple(r.horizon_label for r in recovered.rows)==("D","D+1","D+2","D+3","D+4")
    assert forecast_path_hash(recovered)==forecast_path_hash(original)
    assert [dict(r.lineage) for r in recovered.rows]==[dict(r.lineage) for r in original.rows]
    assert all(r.lineage["mode"]=="TEST/SYNTHETIC/SHADOW" and r.lineage["production_visible"] is False for r in recovered.rows)
    assert conn.closed


def test_repeat_retrieval_is_byte_semantically_stable():
    original=fixture_path()
    first=ForecastPathReadAdapter(lambda:Conn(original)).recover(original.recommendation_id)
    second=ForecastPathReadAdapter(lambda:Conn(original)).recover(original.recommendation_id)
    assert forecast_path_hash(first)==forecast_path_hash(second)==forecast_path_hash(original)


def test_tampered_persisted_row_fails_immutable_hash_verification():
    original=fixture_path()
    with pytest.raises(RuntimeError,match="immutable payload-hash"):
        ForecastPathReadAdapter(lambda:Conn(original,tamper=True)).recover(original.recommendation_id)


def test_incomplete_persisted_path_fails_closed():
    original=fixture_path()
    class ShortCursor(Cursor):
        def fetchall(self): return super().fetchall()[:4]
    class ShortConn(Conn):
        def __init__(self,path): self.cur=ShortCursor(path); self.closed=False
    with pytest.raises(RuntimeError,match="incomplete or misordered"):
        ForecastPathReadAdapter(lambda:ShortConn(original)).recover(original.recommendation_id)
