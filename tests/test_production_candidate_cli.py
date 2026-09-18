import os

from src.production_orchestrator import HoldingState


def test_live_candidate_workflow_defaults_to_unknown_holding_semantics():
    assert HoldingState("UNKNOWN") is HoldingState.UNKNOWN


def test_cli_source_does_not_enable_publish():
    from pathlib import Path
    text=Path("src/production_candidate_cli.py").read_text(encoding="utf-8")
    assert "publish=False" in text
    assert "publish=True" not in text
