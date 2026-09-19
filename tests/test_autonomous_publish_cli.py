from pathlib import Path


def test_publisher_has_explicit_release_approval_and_no_trading_path():
    text=Path("src/autonomous_publish_cli.py").read_text(encoding="utf-8")
    assert "publish=True" in text
    assert "ReleaseApproval(" in text
    assert "autonomous_publishing_approved=True" in text
    assert "trading_enabled" in text
    lowered=text.lower()
    for forbidden in ("/order","place_order","modify_order","cancel_order","positions","funds"):
        assert forbidden not in lowered


def test_publish_workflow_is_separate_from_candidate_workflow():
    text=Path(".github/workflows/autonomous-publish.yml").read_text(encoding="utf-8")
    assert "EDGE Autonomous Publish" in text
    assert "production_candidate_cli" not in text


def test_manual_run_is_not_blocked_by_close_or_non_trading_day_gate():
    text=Path("src/autonomous_publish_cli.py").read_text(encoding="utf-8")
    assert 'run_mode=os.getenv("EDGE_RUN_MODE","MANUAL")' in text
    assert 'if run_mode == "SCHEDULED" and (' in text
    assert 'if run_mode == "SCHEDULED" and not is_nse_trading_day' in text
    assert 'if existing and run_mode == "SCHEDULED"' in text
