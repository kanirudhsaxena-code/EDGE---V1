import pytest

from src.edge_truth_evidence_intake import audit_candidate_evidence, extract_complete_evidence_subset

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


def test_rejects_complete_shape_when_group_identity_or_target_session_is_missing():
    rows = _rows("")
    rows[0]["target_session"] = ""
    key = f"|{ISSUANCE}"
    sequences = {key: {"sessions": ["", *SESSIONS[1:]]}}
    audit = audit_candidate_evidence(rows, sequences)
    item = audit["rejected_groups"][key]

    assert audit["accepted_group_count"] == 0
    assert "MISSING_TICKER" in item["reasons"]
    assert "MISSING_TARGET_SESSION" in item["reasons"]

    rows = _rows("TEST")
    for row in rows:
        row["issuance_asof"] = ""
    sequences = {"TEST|": {"sessions": list(SESSIONS)}}
    item = audit_candidate_evidence(rows, sequences)["rejected_groups"]["TEST|"]
    assert "MISSING_ISSUANCE_ASOF" in item["reasons"]


def test_extracts_only_complete_groups_and_keeps_rejection_accounting():
    complete = _rows("GOOD")
    incomplete = _rows("BAD")[:-1]
    sequences = {**_sequences("GOOD"), **_sequences("BAD")}
    subset = extract_complete_evidence_subset(complete + incomplete, sequences)

    assert [row["ticker"] for row in subset["observations"]] == ["GOOD"] * 5
    assert list(subset["session_sequences"]) == [f"GOOD|{ISSUANCE}"]
    assert subset["audit"]["accepted_group_count"] == 1
    assert subset["audit"]["rejected_group_count"] == 1
    assert subset["audit"]["candidate_row_count"] == 9
    assert subset["audit"]["rejected_groups"][f"BAD|{ISSUANCE}"]["missing_horizons"] == ["D+4"]


def test_subset_does_not_mutate_supplied_observations_or_proofs():
    rows = _rows("GOOD")
    sequences = _sequences("GOOD")
    subset = extract_complete_evidence_subset(rows, sequences)
    subset["observations"][0]["target_session"] = "CHANGED"
    subset["session_sequences"][f"GOOD|{ISSUANCE}"]["sessions"] = []

    assert rows[0]["target_session"] == SESSIONS[0]
    assert sequences[f"GOOD|{ISSUANCE}"]["sessions"] == list(SESSIONS)


@pytest.mark.parametrize("observations", [None, "rows", b"rows", 7, {"row": "value"}])
def test_rejects_malformed_observation_containers(observations):
    with pytest.raises(ValueError, match="observations must be a sequence of mappings"):
        audit_candidate_evidence(observations, {})


@pytest.mark.parametrize("bad_row", [None, "row", 7, True, ["row"]])
def test_rejects_non_mapping_observation_rows(bad_row):
    with pytest.raises(ValueError, match="observation 0 must be a mapping"):
        audit_candidate_evidence([bad_row], {})


@pytest.mark.parametrize("field", ["ticker", "issuance_asof", "horizon", "target_session"])
@pytest.mark.parametrize("bad_value", [7, True, [], {}])
def test_rejects_non_string_identity_and_session_fields(field, bad_value):
    row = _rows()[0]
    row[field] = bad_value
    with pytest.raises(ValueError, match=rf"observation 0 {field} must be a string when supplied"):
        audit_candidate_evidence([row], {})


@pytest.mark.parametrize("session_sequences", [None, "proofs", [], 7, True])
def test_rejects_malformed_session_sequence_containers(session_sequences):
    with pytest.raises(ValueError, match="session_sequences must be a mapping"):
        audit_candidate_evidence([], session_sequences)


def test_rejects_malformed_session_sequence_entries():
    with pytest.raises(ValueError, match="keys must be non-blank strings"):
        audit_candidate_evidence([], {"": {"sessions": []}})
    with pytest.raises(ValueError, match="keys must be non-blank strings"):
        audit_candidate_evidence([], {7: {"sessions": []}})
    with pytest.raises(ValueError, match="must be a mapping"):
        audit_candidate_evidence([], {"TEST|2026-09-01": None})
