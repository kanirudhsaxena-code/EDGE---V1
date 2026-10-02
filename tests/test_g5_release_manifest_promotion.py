import json
import re
from pathlib import Path

HEX40=re.compile(r"^[0-9a-f]{40}$")
HEX64=re.compile(r"^[0-9a-f]{64}$")


def test_g5_release_manifest_is_promoted_only_with_bounded_governed_proof():
    data=json.loads(Path("governance/production_release_manifest.json").read_text(encoding="utf-8"))
    g5=data["g5_stock_dd4_release"]

    assert g5["promotion_status"]=="PROMOTED_AFTER_GOVERNED_PROOF"
    assert g5["scope"]=="EDGE_STOCKS_D_THROUGH_D_PLUS_4_FORECAST_PATH"
    assert g5["methodology_version"]=="G5_STOCK_DD4_V1.0"
    assert g5["frozen_core_methodology_changed"] is False
    assert g5["forecast_sessions"]==["D","D+1","D+2","D+3","D+4"]
    assert "D+5" not in g5["forecast_sessions"]
    assert g5["d_plus_5_current_forecast_prohibited"] is True

    baseline=g5["runtime_baseline"]
    assert HEX40.fullmatch(baseline["engine_main_sha"])
    assert HEX40.fullmatch(baseline["console_main_sha"])

    evidence=g5["acceptance_evidence"]
    for key in (
        "ltf_candidate_run_id","cupid_candidate_run_id",
        "ltf_e2e_run_id","cupid_e2e_run_id",
        "ltf_console_chat_parity_run_id","cupid_console_chat_parity_run_id",
        "missing_evidence_run_id","engine_main_ci_run_id",
        "console_main_ci_run_id","console_deploy_run_id","console_smoke_run_id",
    ):
        assert isinstance(evidence[key],int) and evidence[key]>0

    assert evidence["ltf_recommendation_id"]=="EDGE-LTF-20261002-171436-AUTO"
    assert evidence["cupid_recommendation_id"]=="EDGE-CUPID-20261002-171606-AUTO"
    assert HEX64.fullmatch(evidence["ltf_forecast_path_hash"])
    assert HEX64.fullmatch(evidence["cupid_forecast_path_hash"])
    assert evidence["missing_evidence_diagnostic"]=="FRESH_GOVERNED_RESEARCH_REQUIRED"

    invariants=g5["invariants"]
    assert invariants
    assert all(value is True for value in invariants.values())

    roles={row["role"]:row["drive_file_id"] for row in g5["governance_sources"]}
    assert roles["FROZEN_EDGE_V1_CORE"]=="13i-KF2ylid2AF3ZTfwMe932GUDMmIL4z"
    assert roles["PRODUCTION_BACKBONE_G5_INPUT_MAPPING"]=="1QkdyzEFrQZQnyuxipYQvd5NkuWc3hq_sYvY7Bqg5SoE"
    assert roles["VNEXT_G5_IMPLEMENTATION_BINDING"]=="1lwqZEhZVCWOAH2mZ-YIDyGqTk6v7h112-vnogm3kyz4"
    assert roles["G5_EVIDENCE_DATA_BINDING"]=="1c3NbYZCIfi5LOuKBGxQDePuTdInnlJ45eV62Zjh3JPE"
