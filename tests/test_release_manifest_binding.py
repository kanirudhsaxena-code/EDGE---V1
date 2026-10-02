import json
from pathlib import Path

def test_release_manifest_binds_edge_v13_contract():
    data = json.loads(Path("governance/production_release_manifest.json").read_text(encoding="utf-8"))
    contract = Path("docs/EDGE_STOCKS_OUTPUT_CONTRACT_V1_3.md").read_text(encoding="utf-8")
    assert data["consumer"] == "EDGE_STOCKS"
    assert data["binding_status"] == "BOUND"
    spec = data["master_spec"]
    binding = data["production_binding"]
    assert len(spec["content_sha256_lf"]) == 64
    int(spec["content_sha256_lf"], 16)
    assert binding["analytical_core"] == "EDGE_V1"
    assert binding["user_facing_contract"] == "EDGE_STOCKS_V1_3"
    assert binding["presentation_semantics"] == "EFFICACY_V2"
    assert "EDGE_STOCKS_V1_3" in contract
    assert "EFFICACY V2" in contract
    assert "supersedes" in contract.lower()


def test_g5_release_manifest_requires_complete_27_gate_evidence():
    manifest = json.loads(Path("governance/production_release_manifest.json").read_text(encoding="utf-8"))
    g5 = manifest["g5_stock_dd4_release"]
    evidence = json.loads(Path(g5["acceptance_evidence"]).read_text(encoding="utf-8"))

    assert g5["status"] == "ACCEPTED"
    assert g5["methodology_version"] == "G5_STOCK_DD4_V1.0"
    assert g5["forecast_path_contract"] == "EDGE_STOCK_FORECAST_PATH_V1"
    assert g5["acceptance_gate_set"] == "G5-01..G5-27"
    assert g5["methodology_status"] == "ADDITIVE_FROZEN_CORE_UNCHANGED"

    expected = [f"G5-{i:02d}" for i in range(1, 28)]
    assert list(evidence["gates"]) == expected
    assert evidence["acceptance_status"] == "ACCEPTED"
    assert evidence["gate_set"] == "G5-01..G5-27"
    assert all(evidence["gates"][gate]["status"] == "PASS" for gate in expected)
    assert evidence["production_recommendation_id"] == g5["production_recommendation_id"]
    assert evidence["forecast_path_hash"] == g5["forecast_path_hash"]
