from datetime import date
from pathlib import Path

def test_autonomous_publisher_has_daily_idempotency_guard():
    text=Path("src/autonomous_publish_cli.py").read_text(encoding="utf-8")
    assert "ALREADY_PUBLISHED_TODAY" in text
    assert "run_timestamp at time zone 'Asia/Kolkata'" in text


def test_autonomous_publish_workflow_runs_after_nse_close_on_weekdays():
    from pathlib import Path
    text=Path(".github/workflows/autonomous-publish.yml").read_text(encoding="utf-8")
    assert 'cron: "45 10 * * 1-5"' in text
    assert "EDGE_RUN_MODE" in text


def test_autonomous_publisher_enforces_post_close_and_trading_day_guard():
    from pathlib import Path
    text=Path("src/autonomous_publish_cli.py").read_text(encoding="utf-8")
    assert "BEFORE_MARKET_CLOSE" in text
    assert "NON_TRADING_DAY" in text
    assert "is_nse_trading_day" in text
