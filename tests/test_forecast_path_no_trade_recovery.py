from datetime import date, datetime, timezone

from src.forecast_path import ForecastPathRow, ForecastPathWrite, forecast_path_hash
from src.forecast_path_read import ForecastPathReadAdapter
from tests.test_forecast_path_read import Conn


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


def test_no_trade_path_recovers_all_five_rows_with_identity_and_lineage():
    original=no_trade_fixture()
    recovered=ForecastPathReadAdapter(lambda:Conn(original)).recover(original.recommendation_id)
    assert tuple(r.horizon_label for r in recovered.rows)==("D","D+1","D+2","D+3","D+4")
    assert forecast_path_hash(recovered)==forecast_path_hash(original)
    assert all(r.lineage["recommendation_state"]=="NO_TRADE" for r in recovered.rows)
    assert all(r.lineage["production_visible"] is False for r in recovered.rows)
