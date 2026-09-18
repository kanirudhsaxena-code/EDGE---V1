from pathlib import Path


def test_publisher_has_explicit_release_approval_and_no_trading_path():
    text=Path("src/autonomous_publish_cli.py").read_text(encoding="utf-8")
    assert "publish=True" in text
    assert "ReleaseApproval(" in text
    assert "autonomous_publishing_approved=True" in text
    assert "trading_enabled" in text
    assert "order" not in text.lower()


def test_publish_workflow_is_separate_from_candidate_workflow():
    text=Path(".github/workflows/autonomous-publish.yml").read_text(encoding="utf-8")
    assert "EDGE Autonomous Publish" in text
    assert "production_candidate_cli" not in text
