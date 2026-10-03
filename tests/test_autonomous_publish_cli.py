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
    assert 'if (run_mode == "SCHEDULED" or canonical_requested_at is not None) and not is_nse_trading_day' in text
    assert 'if existing and (run_mode == "SCHEDULED" or canonical_requested_at is not None)' in text


def test_preopen_retry_publication_is_serialized_and_idempotent():
    workflow=Path(".github/workflows/autonomous-publish.yml").read_text(encoding="utf-8")
    publisher=Path("src/autonomous_publish_cli.py").read_text(encoding="utf-8")
    assert "group: edge-autonomous-publish-" in workflow
    assert "cancel-in-progress: false" in workflow
    assert 'canonical_requested_at is not None' in publisher
    assert "ALREADY_PUBLISHED_TODAY" in publisher


def test_5dr_console_proxies_are_pinned_to_g51_anytime_capable_revision():
    expected="74aa9ecdd107e4b0142e8208e42db78ed6b11de6"
    normal=Path(".github/workflows/5dr-console-acquire-proxy.yml").read_text(encoding="utf-8")
    execute=Path(".github/workflows/5dr-console-execute-proxy.yml").read_text(encoding="utf-8")
    preopen=Path(".github/workflows/5dr-console-preopen-acquire-proxy.yml").read_text(encoding="utf-8")
    assert expected in normal
    assert expected in execute
    assert expected in preopen
    assert "experiments.console_preopen_evidence" in preopen
    assert "tests.test_console_preopen_evidence" in preopen
    assert "trading" not in preopen.lower() or "trading_enabled" not in preopen.lower()


def test_stock_preopen_has_runtime_and_publication_hard_deadlines():
    text=Path("src/production_orchestrator.py").read_text(encoding="utf-8")
    assert "BLOCKED_PREOPEN_DEADLINE" in text
    assert "pre-open canonical execution is outside the governed 09:10-09:15 IST window" in text
    assert "pre-open canonical publication crossed the 09:15 IST hard boundary" in text
    assert "publication_now=(runtime_clock or (lambda: datetime.now(timezone.utc)))()" in text
    assert "_same_ist_date(canonical_requested_at,publication_now)" in text


def test_stock_preopen_requires_auction_price_and_no_ltp_fallback():
    text=Path("src/production_orchestrator.py").read_text(encoding="utf-8")
    assert "preopen_iep_required=preopen_canonical" in text
    assert "indicative_equilibrium_price" in text
    assert 'ltpc.get("iep")' in text
    assert "pre-open indicative equilibrium price is unavailable" in text
