"""2E-01 research-only classifier for historical IPO NV/PARTIAL assessments.

Classifies supplied historical evidence only; no live acquisition, persistence,
recommendation, canonical selection, deployment, or production operation.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum


class FailureClass(str, Enum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MISSING_DATA = "MISSING_DATA"
    ORCHESTRATION_FAILURE = "ORCHESTRATION_FAILURE"
    GENUINE_INSUFFICIENCY = "GENUINE_INSUFFICIENCY"


@dataclass(frozen=True)
class AuditRecord:
    assessment_id: str
    classification: FailureClass
    reasons: tuple[str, ...]


def _required_bool(record: Mapping[str, object], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def classify_record(record: Mapping[str, object]) -> AuditRecord:
    if not isinstance(record, Mapping):
        raise ValueError("historical record must be a mapping")
    assessment_id = record.get("assessment_id")
    if not isinstance(assessment_id, str) or not assessment_id.strip():
        raise ValueError("assessment_id must be a non-blank string")
    assessment_id = assessment_id.strip()
    orchestration_ok = _required_bool(record, "orchestration_ok")
    source_available = _required_bool(record, "source_available")
    required_data_complete = _required_bool(record, "required_data_complete")
    evidence_sufficient = _required_bool(record, "evidence_sufficient")
    if not orchestration_ok:
        return AuditRecord(assessment_id, FailureClass.ORCHESTRATION_FAILURE, ("historical orchestration did not complete successfully",))
    if not source_available:
        return AuditRecord(assessment_id, FailureClass.SOURCE_UNAVAILABLE, ("required source was unavailable at assessment time",))
    if not required_data_complete:
        return AuditRecord(assessment_id, FailureClass.MISSING_DATA, ("required source existed but required data was missing",))
    if not evidence_sufficient:
        return AuditRecord(assessment_id, FailureClass.GENUINE_INSUFFICIENCY, ("available complete evidence was genuinely insufficient",))
    raise ValueError("record does not describe an NV/PARTIAL failure")


def classify_sample(records: Sequence[Mapping[str, object]]) -> tuple[AuditRecord, ...]:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise ValueError("historical sample must be a sequence of mappings")
    if not records:
        raise ValueError("historical sample must be non-empty")
    seen: set[str] = set()
    output = []
    for record in records:
        result = classify_record(record)
        if result.assessment_id in seen:
            raise ValueError(f"duplicate assessment_id: {result.assessment_id}")
        seen.add(result.assessment_id)
        output.append(result)
    return tuple(output)
