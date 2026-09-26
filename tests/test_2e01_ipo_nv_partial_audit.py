import pytest

from research.ipo_nv_partial_audit import FailureClass, classify_record, classify_sample


def row(**overrides):
    value = dict(
        assessment_id="ipo-1",
        orchestration_ok=True,
        source_available=True,
        required_data_complete=True,
        evidence_sufficient=False,
    )
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"orchestration_ok": False, "source_available": False, "required_data_complete": False}, FailureClass.ORCHESTRATION_FAILURE),
        ({"source_available": False, "required_data_complete": False}, FailureClass.SOURCE_UNAVAILABLE),
        ({"required_data_complete": False}, FailureClass.MISSING_DATA),
        ({}, FailureClass.GENUINE_INSUFFICIENCY),
    ],
)
def test_causal_taxonomy(overrides, expected):
    assert classify_record(row(**overrides)).classification is expected


def test_complete_sufficient_record_is_not_failure():
    with pytest.raises(ValueError, match="does not describe"):
        classify_record(row(evidence_sufficient=True))


@pytest.mark.parametrize("field", ["orchestration_ok", "source_available", "required_data_complete", "evidence_sufficient"])
def test_boolean_evidence_is_fail_closed(field):
    with pytest.raises(ValueError, match="must be boolean"):
        classify_record(row(**{field: "unknown"}))


@pytest.mark.parametrize("record", [None, [], "bad-record", 7, True])
def test_record_container_is_fail_closed(record):
    with pytest.raises(ValueError, match="must be a mapping"):
        classify_record(record)


@pytest.mark.parametrize("records", [None, {}, "bad-sample", b"bad-sample", 7])
def test_sample_container_is_fail_closed(records):
    with pytest.raises(ValueError, match="sequence of mappings"):
        classify_sample(records)


def test_assessment_ids_are_normalized_before_duplicate_detection():
    with pytest.raises(ValueError, match="duplicate assessment_id: ipo-1"):
        classify_sample([row(assessment_id=" ipo-1 "), row(assessment_id="ipo-1")])


def test_sample_requires_unique_ids():
    with pytest.raises(ValueError, match="duplicate"):
        classify_sample([row(), row()])


def test_sample_must_be_nonempty():
    with pytest.raises(ValueError, match="non-empty"):
        classify_sample([])
