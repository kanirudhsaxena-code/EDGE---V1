from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

from src.canonical_governance import (
    IST,
    classify_stock_run,
    canonical_key,
    register_recommendation_governance_values,
    last_nyse_close_before,
    market_session_as_of,
    user_evidence_mode,
)


def test_legacy_run_is_legacy_candidate_before_activation():
    run=datetime(2026,9,21,14,30,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,9,21)
    assert out["candidate_type"]=="LEGACY_CANDIDATE"


def test_preopen_0910_is_canonical_candidate():
    run=datetime(2026,9,22,9,10,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,9,22)
    assert out["candidate_type"]=="PREOPEN_CANONICAL"


def test_preopen_0914_is_canonical_candidate():
    run=datetime(2026,9,22,9,14,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["candidate_type"]=="PREOPEN_CANONICAL"


def test_0915_normal_open_is_valid_user_canonical_snapshot():
    run=datetime(2026,9,22,9,15,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["candidate_type"]=="USER_CANONICAL_SNAPSHOT"


def test_overnight_after_us_close_is_fallback_candidate():
    run=datetime(2026,9,22,2,45,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,9,22)
    assert out["candidate_type"]=="OVERNIGHT_FALLBACK_CANONICAL"


def test_previous_day_post_close_is_valid_user_snapshot_for_next_session():
    run=datetime(2026,9,21,16,0,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,9,22)
    assert out["candidate_type"]=="USER_CANONICAL_SNAPSHOT"


def test_intraday_after_open_is_valid_user_canonical_snapshot():
    run=datetime(2026,9,22,10,30,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["candidate_type"]=="USER_CANONICAL_SNAPSHOT"


def test_weekend_after_last_us_close_remains_overnight_fallback_candidate():
    run=datetime(2026,10,4,21,0,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,10,5)
    assert out["candidate_type"]=="OVERNIGHT_FALLBACK_CANONICAL"


def test_canonical_key_includes_ticker_target_and_horizon():
    assert canonical_key("ltf",date(2026,9,22),"5D")=="LTF|2026-09-22|5D"


def test_nyse_close_uses_dst_aware_time():
    target_open=datetime(2026,9,22,9,15,tzinfo=IST)
    close=last_nyse_close_before(target_open)
    # Sep is U.S. daylight-saving time: 16:00 ET = 01:30 IST next day.
    assert close.isoformat().startswith("2026-09-22T01:30:00")


def test_migration_freezes_latest_legacy_and_future_default_is_noncanonical():
    text=Path("migrations/005_canonical_efficacy_timing.sql").read_text(encoding="utf-8")
    assert "DISTINCT ON (g.canonical_key)" in text
    assert "ORDER BY g.canonical_key,r.run_timestamp DESC" in text
    assert "ALTER COLUMN include_in_master_metrics SET DEFAULT false" in text
    assert "LEGACY_CANONICAL" in text


def test_persistence_registers_governance_and_does_not_auto_include_master_metrics():
    text=Path("src/persistence.py").read_text(encoding="utf-8")
    assert "register_recommendation_governance" in text
    assert "values (%s,%s,false,%s,%s,'OPEN',100,false)" in text


def test_workflow_finalizes_after_normal_open_without_recomputing_candidate():
    text=Path(".github/workflows/canonical-selection.yml").read_text(encoding="utf-8")
    assert "cron: '50 3 * * 1-5'" in text
    assert "python -m src.canonical_governance_cli" in text


def test_g51_migration_separates_all_run_from_benchmark_membership():
    text=Path("migrations/009_anytime_invocation_governance.sql").read_text(encoding="utf-8")
    assert "USER_CANONICAL_SNAPSHOT" in text
    assert "v_edge_all_run_assessment" in text
    assert "v_edge_stock_all_run_assessment" in text
    # Benchmark membership remains controlled by the existing selection path;
    # the additive all-run view must not rewrite lifecycle membership.
    assert "UPDATE recommendation_lifecycle" not in text
    assert "SET include_in_master_metrics" not in text


def test_anytime_evidence_modes_preserve_market_state():
    assert user_evidence_mode(datetime(2026,10,4,21,0,tzinfo=IST))=="CLOSED_SESSION"
    assert user_evidence_mode(datetime(2026,10,5,9,12,tzinfo=IST))=="PREOPEN"
    assert user_evidence_mode(datetime(2026,10,5,11,0,tzinfo=IST))=="LIVE_INTRADAY"
    assert user_evidence_mode(datetime(2026,10,5,16,0,tzinfo=IST))=="SESSION_FINAL"


def test_market_session_as_of_does_not_fabricate_weekend_freshness():
    assert market_session_as_of(datetime(2026,10,4,21,0,tzinfo=IST))==date(2026,10,1)
    assert market_session_as_of(datetime(2026,10,5,8,0,tzinfo=IST))==date(2026,10,1)
    assert market_session_as_of(datetime(2026,10,5,11,0,tzinfo=IST))==date(2026,10,5)


class _CaptureCursor:
    def __init__(self):
        self.params=None
    def execute(self,sql,params):
        self.params=params


class _CaptureConn:
    def __init__(self):
        self.cur=_CaptureCursor()
    def cursor(self):
        return self.cur


def _registered_governance(*,run,trigger_type="USER",slot=None):
    conn=_CaptureConn()
    out=register_recommendation_governance_values(
        conn,
        recommendation_id="EDGE-TEST",
        ticker="LTF",
        run_at=run,
        completed_at=run,
        horizon="D+5",
        research_fresh_at=run,
        requested_at=run,
        canonical_attempt_slot=slot,
        trigger_type=trigger_type,
    )
    return out,conn.cur.params


def test_user_weekend_run_never_competes_as_overnight_fallback():
    run=datetime(2026,10,4,4,40,tzinfo=IST)
    raw=classify_stock_run(run)
    assert raw["candidate_type"]=="OVERNIGHT_FALLBACK_CANONICAL"
    out,params=_registered_governance(run=run,trigger_type="USER")
    assert out["candidate_type"]=="USER_CANONICAL_SNAPSHOT"
    assert params[5]=="USER_CANONICAL_SNAPSHOT"
    assert params[12]=="USER"
    assert params[13]=="CLOSED_SESSION"
    assert params[15]=="NONE"


def test_scheduled_overnight_run_retains_fallback_eligibility():
    run=datetime(2026,10,4,4,40,tzinfo=IST)
    out,params=_registered_governance(run=run,trigger_type="SCHEDULED")
    assert out["candidate_type"]=="OVERNIGHT_FALLBACK_CANONICAL"
    assert params[5]=="OVERNIGHT_FALLBACK_CANONICAL"
    assert params[12]=="SCHEDULED"
    assert params[15]=="NONE"


def test_preopen_slot_is_scheduled_even_when_transport_is_workflow_dispatch():
    run=datetime(2026,10,5,9,12,tzinfo=IST)
    out,params=_registered_governance(run=run,trigger_type="USER",slot="09:12")
    assert out["candidate_type"]=="PREOPEN_CANONICAL"
    assert params[12]=="SCHEDULED"
    assert params[13]=="PREOPEN"
    assert params[15]=="SESSION_PREOPEN"
