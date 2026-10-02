import os
import sys
from types import SimpleNamespace

from src.production_orchestrator import HoldingState


def test_live_candidate_workflow_defaults_to_unknown_holding_semantics():
    assert HoldingState("UNKNOWN") is HoldingState.UNKNOWN


def test_cli_source_does_not_enable_publish():
    from pathlib import Path
    text=Path("src/production_candidate_cli.py").read_text(encoding="utf-8")
    assert "publish=False" in text
    assert "publish=True" not in text


def test_candidate_forwards_governed_research_bundle_without_enabling_publish(monkeypatch):
    from src import production_candidate_cli as cli
    calls = []
    connection = SimpleNamespace(close=lambda: None)
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda _: connection))
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "test-db")
    monkeypatch.setenv("EDGE_RESEARCH_BUNDLE_ID", "research-test-id")
    monkeypatch.setenv("EDGE_HOLDING_STATE", "UNKNOWN")
    def build(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status="PRODUCTION_CANDIDATE_READY", blockers=(), canonical_bundle=None, report_markdown=None)
    monkeypatch.setattr(cli, "build_production_candidate", build)
    assert cli.main() == 0
    assert calls[0]["research_bundle_id"] == "research-test-id"
    assert calls[0]["publish"] is False
