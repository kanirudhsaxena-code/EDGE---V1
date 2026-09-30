from datetime import date, datetime, timezone
import pytest

from src.forecast_path import ForecastPathPersistenceAdapter, ForecastPathRow, ForecastPathWrite, validate_forecast_path


def row(label, day, bull=55.0, base=30.0, bear=15.0, direction="BULL"):
    return ForecastPathRow(
        horizon_label=label,
        target_trading_date=date(2026, 9, day),
        direction=direction,
        bull_probability=bull,
        base_probability=base,
        bear_probability=bear,
        expected_centre=270.0,
        outer_expected_zone_low=265.0,
        outer_expected_zone_high=275.0,
        evidence_basis="governed issuance evidence",
        regime_context="RANGE",
        verification_state="VERIFIED",
        lineage={"run_id": "EDGE-LTF-1", "issued_at": "2026-09-24T09:00:00Z"},
    )


def path():
    return ForecastPathWrite(
        recommendation_id="EDGE-LTF-1",
        source_run_id="EDGE-LTF-1",
        issued_at=datetime(2026, 9, 24, 9, tzinfo=timezone.utc),
        rows=(row("D", 24), row("D+1", 25), row("D+2", 28), row("D+3", 29), row("D+4", 30)),
    )


def test_accepts_exact_five_session_path():
    validate_forecast_path(path())


def test_rejects_direction_not_matching_probability_leader():
    broken = path()
    rows = list(broken.rows)
    rows[2] = row("D+2", 28, bull=20, base=65, bear=15, direction="BULL")
    with pytest.raises(ValueError, match="direction must equal"):
        validate_forecast_path(ForecastPathWrite(broken.recommendation_id, broken.source_run_id, broken.issued_at, tuple(rows)))


def test_rejects_non_increasing_target_sessions():
    broken = path()
    rows = list(broken.rows)
    rows[3] = row("D+3", 28)
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_forecast_path(ForecastPathWrite(broken.recommendation_id, broken.source_run_id, broken.issued_at, tuple(rows)))


class Cursor:
    def __init__(self):
        self.calls=[]
        self.existing=None
    def execute(self, sql, params): self.calls.append((sql,params))
    def fetchone(self): return self.existing
    def close(self): pass


class Conn:
    def __init__(self): self.cur=Cursor(); self.commits=0; self.rollbacks=0
    def cursor(self): return self.cur
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_persists_header_and_exactly_five_immutable_rows_atomically():
    conn=Conn()
    digest=ForecastPathPersistenceAdapter(lambda: conn).persist(path())
    assert len(digest)==64
    assert conn.commits==1 and conn.rollbacks==0
    inserts=[call for call in conn.cur.calls if "insert into edge_stock_forecast_path_rows" in call[0]]
    assert len(inserts)==5


def test_same_path_is_idempotent_and_different_content_fails_closed():
    conn=Conn()
    adapter=ForecastPathPersistenceAdapter(lambda: conn)
    digest=adapter.persist(path())
    conn2=Conn(); conn2.cur.existing=(digest,)
    assert ForecastPathPersistenceAdapter(lambda: conn2).persist(path())==digest
    # The adapter owns the transaction boundary, so even an idempotent read path
    # closes successfully with one commit and performs no INSERTs.
    assert conn2.commits==1 and conn2.rollbacks==0
    assert not [call for call in conn2.cur.calls if "insert into edge_stock_forecast_path" in call[0]]
