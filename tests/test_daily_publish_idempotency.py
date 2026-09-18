from datetime import date
from pathlib import Path

def test_autonomous_publisher_has_daily_idempotency_guard():
    text=Path("src/autonomous_publish_cli.py").read_text(encoding="utf-8")
    assert "ALREADY_PUBLISHED_TODAY" in text
    assert "run_timestamp at time zone 'Asia/Kolkata'" in text
