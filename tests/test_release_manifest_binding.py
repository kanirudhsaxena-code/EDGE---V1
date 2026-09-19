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
