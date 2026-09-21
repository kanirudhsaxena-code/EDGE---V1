from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

from src.canonical_governance import (
    IST,
    classify_stock_run,
    canonical_key,
    last_nyse_close_before,
)


def test_legacy_run_is_legacy_candidate_before_activation():
    run=datetime(2026,9,21,14,30,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,9,21)
    assert out["candidate_type"]=="LEGACY_CANDIDATE"


def test_preopen_0855_is_canonical_candidate():
    run=datetime(2026,9,22,8,55,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,9,22)
    assert out["candidate_type"]=="PREOPEN_CANONICAL"


def test_after_0855_is_not_ordinary_preopen_candidate():
    run=datetime(2026,9,22,8,56,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["candidate_type"]=="DIAGNOSTIC_SNAPSHOT"


def test_overnight_after_us_close_is_fallback_candidate():
    run=datetime(2026,9,22,2,45,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["candidate_type"]=="OVERNIGHT_FALLBACK_CANONICAL"


def test_previous_day_post_close_is_not_overnight_fallback():
    run=datetime(2026,9,21,16,0,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["target_trading_date"]==date(2026,9,22)
    assert out["candidate_type"]=="DIAGNOSTIC_SNAPSHOT"


def test_intraday_after_open_is_diagnostic_only():
    run=datetime(2026,9,22,10,30,tzinfo=IST)
    out=classify_stock_run(run)
    assert out["candidate_type"]=="DIAGNOSTIC_SNAPSHOT"


def test_canonical_key_includes_ticker_target_and_horizon():
    assert canonical_key("ltf",date(2026,9,22),"5D")=="LTF|2026-09-22|5D"


def test_nyse_close_uses_dst_aware_time():
    target_open=datetime(2026,9,22,9,0,tzinfo=IST)
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


def test_workflow_finalizes_after_nse_preopen_boundary():
    text=Path(".github/workflows/canonical-selection.yml").read_text(encoding="utf-8")
    assert "cron: '35 3 * * 1-5'" in text
    assert "python -m src.canonical_governance_cli" in text
