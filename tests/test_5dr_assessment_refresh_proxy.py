from pathlib import Path
import re


WORKFLOW=Path(".github/workflows/5dr-assessment-refresh-proxy.yml")


def text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_proxy_rebuilds_authoritative_assessment_on_demand():
    body=text()
    assert "src.assessment_handoff_cli" in body
    assert "DATABASE_URL: ${{ secrets.DATABASE_URL }}" in body
    assert "Build fresh authoritative 5DR assessment from production database" in body
    assert "ASSESSMENT_REFRESH_PROXY_REBUILD=PASS" in body
    assert "state/assessment-handoff/runtime/5dr-assessment-handoff.json" not in body


def test_proxy_pins_canonical_5dr_commit():
    body=text()
    match=re.search(r"FIVEDR_REF:\s*([0-9a-f]{40})",body)
    assert match, "assessment producer must be pinned to an immutable 5DR commit"
    assert 'git -C fivedr fetch --depth 1 origin "$FIVEDR_REF"' in body
    assert 'test "$(git -C fivedr rev-parse HEAD)" = "$FIVEDR_REF"' in body


def test_proxy_requires_newly_generated_assessment_not_two_hour_cache():
    body=text()
    assert "assert -300 <= age <= 300" in body
    assert "FIVEDR_HANDOFF_MAX_AGE_SECONDS" not in body
    assert "7200" not in body


def test_proxy_preserves_complete_assessment_and_import_contract():
    body=text()
    for token in (
        "assessment_snapshot_complete",
        "recommendation_ledger_complete",
        "'D','D+1','D+2','D+3','D+4'",
        "len(ledger)==int(metrics.get('all_recommendations_count',-1))",
        "/api/5dr/assessment-import",
        "ASSESSMENT_REFRESH_PROXY_IMPORT=PASS",
    ):
        assert token in body
