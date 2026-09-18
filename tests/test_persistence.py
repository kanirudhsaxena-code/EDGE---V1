from datetime import date, datetime, timezone

from src.persistence import (
    AtomicNeonPersistenceAdapter,
    BotScoreWrite,
    CanonicalEvidenceWrite,
    CanonicalRecommendationWrite,
    ComponentScoreWrite,
    ExecutionPlanWrite,
    MarketTrustWrite,
)


class FakeCursor:
    def __init__(self, evidence_rows=None, fail_on=None):
        self.calls = []
        self._fetchone = None
        self._fetchall = []
        self.evidence_rows = evidence_rows or []
        self.fail_on = fail_on

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))
        if self.fail_on and self.fail_on in normalized:
            raise RuntimeError("forced failure")
        if "insert into edge_runs" in normalized:
            self._fetchone = (99,)
        elif "select evidence_id,source_ref" in normalized:
            self._fetchall = list(self.evidence_rows)

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def bundle():
    components = (
        ComponentScoreWrite("Price Structure",18,1,0.5,"HIGH","AVAILABLE",18,9,True),
        ComponentScoreWrite("PV/PVPO",18,1,0.5,"HIGH","AVAILABLE",18,9,True),
    )
    mt = MarketTrustWrite(97,100,100,69.369,100,92.974,"VERY HIGH")
    bot = BotScoreWrite(38.823,92.974,75,80,45,60,65.801,"B","INVESTIGATION")
    ep = ExecutionPlanWrite(
        instrument="NONE",
        risk_unit_category="0",
        execution_quality_score=60,
        execution_quality_level="MODERATE",
        option_suitability_status="NO_OPTION_TRADE",
    )
    return CanonicalRecommendationWrite(
        recommendation_id="EDGE-LTF-20260918-01",
        parent_recommendation_id="EDGE-LTF-20260917-01",
        ticker="LTF",
        company_name="L&T Finance",
        run_timestamp=datetime(2026,9,18,4,0,tzinfo=timezone.utc),
        forecast_horizon="D+5",
        bull_probability=43.117,
        base_probability=55.313,
        bear_probability=1.570,
        definitive_forecast="BASE_RANGE",
        expected_price_zone_low=298,
        expected_price_zone_high=315,
        des=38.5,
        market_trust_score=92.974,
        market_trust_band="VERY HIGH",
        bot_score=65.801,
        bot_grade="B",
        decision_ladder="INVESTIGATION",
        definitive_recommendation="HOLD existing delivery; NO OPTION TRADE.",
        holding_status_known=True,
        event_shock_level="HIGH",
        active_override="O1",
        evidence_gate_status="PASS",
        rationale="governed test payload",
        tracking_policy="EDGE_D5_V2",
        horizon_days=5,
        expiry_trading_date=date(2026,9,25),
        reference_price=302.3,
        evidence_source_refs=("ref:a","ref:b"),
        component_scores=components,
        market_trust=mt,
        bot=bot,
        execution_plan=ep,
        checkpoint_dates=(
            date(2026,9,21),date(2026,9,22),date(2026,9,23),
            date(2026,9,24),date(2026,9,25),
        ),
    )


def test_atomic_persistence_commits_all_canonical_layers():
    cur = FakeCursor(evidence_rows=[(10,"ref:a"),(11,"ref:b")])
    conn = FakeConnection(cur)
    adapter = AtomicNeonPersistenceAdapter(lambda: conn)
    rid = adapter.persist(bundle())
    assert rid == "EDGE-LTF-20260918-01"
    assert conn.committed is True
    assert conn.rolled_back is False
    sql = "\n".join(call[0] for call in cur.calls)
    for expected in (
        "insert into edge_runs",
        "insert into recommendations",
        "insert into recommendation_lifecycle",
        "insert into recommendation_performance",
        "insert into recommendation_evidence",
        "insert into component_scores",
        "insert into market_trust",
        "insert into bot_scores",
        "insert into execution_plans",
        "insert into outcome_checkpoints",
        "update edge_runs set status='COMMITTED'",
    ):
        assert expected in sql


def test_missing_verified_evidence_rolls_back():
    cur = FakeCursor(evidence_rows=[(10,"ref:a")])
    conn = FakeConnection(cur)
    adapter = AtomicNeonPersistenceAdapter(lambda: conn)
    try:
        adapter.persist(bundle())
    except RuntimeError as exc:
        assert "verified canonical evidence not found" in str(exc)
    else:
        raise AssertionError("missing evidence must fail closed")
    assert conn.committed is False
    assert conn.rolled_back is True


def test_any_mid_transaction_failure_rolls_back():
    cur = FakeCursor(
        evidence_rows=[(10,"ref:a"),(11,"ref:b")],
        fail_on="insert into market_trust",
    )
    conn = FakeConnection(cur)
    adapter = AtomicNeonPersistenceAdapter(lambda: conn)
    try:
        adapter.persist(bundle())
    except RuntimeError:
        pass
    else:
        raise AssertionError("transaction failure must propagate")
    assert conn.committed is False
    assert conn.rolled_back is True


def test_invalid_probability_sum_is_rejected_before_connection():
    bad = bundle()
    bad = CanonicalRecommendationWrite(**{**bad.__dict__, "bull_probability": 40})
    called = {"value": False}
    def factory():
        called["value"] = True
        raise AssertionError("should not connect")
    adapter = AtomicNeonPersistenceAdapter(factory)
    try:
        adapter.persist(bad)
    except ValueError as exc:
        assert "probabilities must sum to 100" in str(exc)
    else:
        raise AssertionError("bad probability sum must fail")
    assert called["value"] is False


def test_verified_evidence_can_be_inserted_atomically_before_recommendation():
    cur = FakeCursor(evidence_rows=[(10,"ref:a"),(11,"ref:b")])
    conn = FakeConnection(cur)
    records=(
        CanonicalEvidenceWrite(
            ticker="LTF",evidence_type="PRICE_STRUCTURE",source_kind="UPSTOX",
            capture_timestamp=datetime(2026,9,18,4,0,tzinfo=timezone.utc),
            freshness="FRESH",quality="HIGH",verification_status="VERIFIED",
            source_ref="ref:a",content_hash="hash-a",
        ),
        CanonicalEvidenceWrite(
            ticker="LTF",evidence_type="PV_PVPO",source_kind="UPSTOX",
            capture_timestamp=datetime(2026,9,18,4,0,tzinfo=timezone.utc),
            freshness="FRESH",quality="HIGH",verification_status="VERIFIED",
            source_ref="ref:b",content_hash="hash-b",
        ),
    )
    adapter = AtomicNeonPersistenceAdapter(lambda: conn,evidence_records=records)
    rid=adapter.persist(bundle())
    assert rid=="EDGE-LTF-20260918-01"
    sql="\n".join(call[0] for call in cur.calls)
    assert "insert into evidence_items" in sql
    assert sql.index("insert into evidence_items") < sql.index("insert into edge_runs")
    assert conn.committed is True


def test_unverified_evidence_record_rolls_back_and_blocks_commit():
    cur=FakeCursor(evidence_rows=[(10,"ref:a"),(11,"ref:b")])
    conn=FakeConnection(cur)
    bad=CanonicalEvidenceWrite(
        ticker="LTF",evidence_type="PRICE_STRUCTURE",source_kind="UPSTOX",
        capture_timestamp=datetime(2026,9,18,4,0,tzinfo=timezone.utc),
        freshness="FRESH",quality="HIGH",verification_status="NOT_VERIFIED",
        source_ref="ref:a",content_hash="hash-a",
    )
    adapter=AtomicNeonPersistenceAdapter(lambda:conn,evidence_records=(bad,))
    try:
        adapter.persist(bundle())
    except ValueError as exc:
        assert "VERIFIED" in str(exc)
    else:
        raise AssertionError("unverified evidence must fail closed")
    assert conn.rolled_back is True
