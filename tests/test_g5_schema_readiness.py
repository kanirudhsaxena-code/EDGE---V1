from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_g5_forecast_path_migration_declares_required_schema_and_immutability():
    sql = (ROOT / "migrations" / "007_edge_stock_forecast_path.sql").read_text(encoding="utf-8")
    required = (
        "create table if not exists edge_stock_forecast_paths",
        "create table if not exists edge_stock_forecast_path_rows",
        "trg_edge_stock_forecast_paths_immutable",
        "trg_edge_stock_forecast_path_rows_immutable",
    )
    lowered = sql.lower()
    for token in required:
        assert token.lower() in lowered


def test_g5_production_e2e_applies_schema_before_publish():
    workflow = (ROOT / ".github" / "workflows" / "g5-production-e2e-acceptance.yml").read_text(encoding="utf-8")
    apply_pos = workflow.index("Apply and verify G5 forecast-path schema")
    publish_pos = workflow.index("Run governed production E2E publish")
    assert apply_pos < publish_pos
    assert "migrations/007_edge_stock_forecast_path.sql" in workflow
    assert "G5_SCHEMA_READINESS':'PASS" in workflow


def test_autonomous_publish_fails_closed_on_schema_drift():
    workflow = (ROOT / ".github" / "workflows" / "autonomous-publish.yml").read_text(encoding="utf-8")
    verify_pos = workflow.index("Verify required G5 forecast-path schema")
    publish_pos = workflow.index("Run governed autonomous publisher")
    assert verify_pos < publish_pos
    assert "G5_SCHEMA_NOT_READY" in workflow


def test_g5_float_precision_migration_is_required_for_exact_readback():
    sql = (ROOT / "migrations" / "008_edge_stock_forecast_path_float_precision.sql").read_text(encoding="utf-8").lower()
    required_columns = (
        "bull_probability",
        "base_probability",
        "bear_probability",
        "expected_centre",
        "outer_expected_zone_low",
        "outer_expected_zone_high",
    )
    for column in required_columns:
        assert f"alter column {column} type double precision" in sql


def test_g5_production_e2e_applies_precision_migration_before_publish():
    workflow = (ROOT / ".github" / "workflows" / "g5-production-e2e-acceptance.yml").read_text(encoding="utf-8")
    apply_pos = workflow.index("migrations/008_edge_stock_forecast_path_float_precision.sql")
    publish_pos = workflow.index("Run governed production E2E publish")
    assert apply_pos < publish_pos
    assert "double precision" in workflow
