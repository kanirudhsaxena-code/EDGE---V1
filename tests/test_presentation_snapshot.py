from pathlib import Path

import pytest

from src.presentation_snapshot import (
    assert_presentation_snapshot,
    build_presentation_snapshot,
    semantic_presentation_hash,
)


def test_cross_language_semantic_hash_vector_matches_console():
    basis = {
        "presentation_contract_version": "P0_11_PRESENTATION_V1",
        "engine": "5DR",
        "identity": {"run_id": "run-42", "result_id": "forecast-7", "checkpoint_id": None},
        "governance_state": "SELECTED",
        "sections": [
            {"name": "TABLE_1_5DR_OUTCOME", "value": 1.0, "probability": 42.5, "verified": True},
            {"name": "TABLE_2_5DR_DRILL_DOWN", "items": ["PVPO", None, -0.0]},
        ],
        "source_payload_hash": "source-abc",
    }
    assert semantic_presentation_hash(basis) == "43cab49103f841c9a85d2213756ecb6db2ee54cbdbb5c0ec6545cc7dbb80b020"


def test_edge_snapshot_requires_v13_four_section_order():
    sections = [
        {"name": "EDGE_MASTER_ASSESSMENT", "rows": []},
        {"name": "ACTIVE_CALLS", "rows": []},
        {"name": "CURRENT_STOCK_OUTCOME", "rows": []},
        {"name": "DRILL_DOWN", "rows": []},
    ]
    snapshot = build_presentation_snapshot(
        run_id=91,
        result_id="LTF-rec-91",
        governance_state="SELECTED",
        source_payload_hash="source-edge",
        sections=sections,
    )
    assert snapshot["engine"] == "EDGE_STOCKS"
    assert snapshot["identity"]["run_id"] == "91"
    assert_presentation_snapshot(snapshot)

    with pytest.raises(ValueError, match="PRESENTATION_EDGE_SECTION_ORDER_MISMATCH"):
        build_presentation_snapshot(
            run_id=91,
            result_id="LTF-rec-91",
            governance_state="SELECTED",
            source_payload_hash="source-edge",
            sections=list(reversed(sections)),
        )


def test_tamper_fails_closed():
    snapshot = build_presentation_snapshot(
        run_id=91,
        result_id="LTF-rec-91",
        governance_state="SELECTED",
        source_payload_hash="source-edge",
        sections=[
            {"name": "EDGE_MASTER_ASSESSMENT"},
            {"name": "ACTIVE_CALLS"},
            {"name": "CURRENT_STOCK_OUTCOME"},
            {"name": "DRILL_DOWN"},
        ],
    )
    snapshot["sections"][2]["decision"] = "CHANGED_AFTER_FREEZE"
    with pytest.raises(ValueError, match="PRESENTATION_HASH_MISMATCH"):
        assert_presentation_snapshot(snapshot)


def test_migration_binds_native_run_and_recommendation_identity_and_is_append_only():
    sql = Path("migrations/007_p0_11_presentation_snapshots.sql").read_text(encoding="utf-8")
    assert "run_id bigint NOT NULL REFERENCES edge_runs(run_id)" in sql
    assert "result_id text NOT NULL REFERENCES recommendations(recommendation_id)" in sql
    assert "jsonb_array_length(sections)=4" in sql
    assert "COALESCE(checkpoint_id,0)" in sql
    assert "presentation_snapshots_no_update" in sql
    assert "presentation_snapshots_no_delete" in sql
    assert "INSERT INTO presentation_snapshots" not in sql
