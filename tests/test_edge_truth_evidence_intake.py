from src.edge_truth_evidence_intake import audit_candidate_evidence

HORIZONS = ("D", "D+1", "D+2", "D+3", "D+4")
SESSIONS = ("2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07")
ISSUANCE = "2026-09-01T15:30:00+05:30"


def _rows(ticker="TEST"):
    return [
        {"ticker": ticker, "issuance_asof": ISSUANCE, "horizon": horizon, "target_session": session}
        for horizon, session in zip(HORIZONS, SESSIONS)
    ]


def _sequences(ticker="TEST"):
    return {f"{ticker}|{ISSUANCE}": {"sessions": list(SESSIONS)}}


def test_accepts_only_complete_five_horizon_group_with_matching_sequence():
    audit = audit_candidate_evidence(_rows(), _sequences())
    assert audit["accepted_group_count"] == 1
    assert audit["rejected_group_count"] == 0
    assert audit["accepted_complete_groups"] == [f"TEST|{ISSUANCE}"]


def test_reports_incomplete_group_without_repairing_it():
    rows = _rows()[:-1]
    audit = audit_candidate_evidence(rows, _sequences())
    item = audit["rejected_groups"][f"TEST|{ISSUANCE}"]
    assert audit["accepted_group_count"] == 0
    assert "MISSING_HORIZONS" in item["reasons"]
    assert item["missing_horizons"] == ["D+4"]
    assert audit["candidate_row_count"] == 4


def test_reports_duplicate_and_sequence_mismatch():
    rows = _rows() + [_rows()[0]]
    sequences = _sequences(); sequences[f"TEST|{ISSUANCE}"]["sessions"] = list(reversed(SESSIONS))
    item = audit_candidate_evidence(rows, sequences)["rejected_groups"][f"TEST|{ISSUANCE}"]
    assert "DUPLICATE_HORIZONS" in item["reasons"]
    assert "SESSION_SEQUENCE_MISMATCH" in item["reasons"]


def test_reports_missing_and_orphan_session_proofs():
    audit = audit_candidate_evidence(_rows(), {"ORPHAN|2026-01-01": {"sessions": []}})
    item = audit["rejected_groups"][f"TEST|{ISSUANCE}"]
    assert "MISSING_SESSION_SEQUENCE" in item["reasons"]
    assert audit["orphan_session_sequences"] == ["ORPHAN|2026-01-01"]
