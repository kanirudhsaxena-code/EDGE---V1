"""Read-only intake audit for candidate 2C-02 EDGE historical evidence.

This helper does not fetch, repair, impute, calibrate, or persist evidence. It only
classifies supplied rows into structurally complete and incomplete ticker+issuance
groups so bounded attributable subsets can be frozen without hiding rejected rows.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.edge_truth_baseline import HORIZONS


def _group_key(row: Mapping[str, Any]) -> str:
    return f"{row.get('ticker', '')}|{row.get('issuance_asof', '')}"


def audit_candidate_evidence(
    observations: Sequence[Mapping[str, Any]],
    session_sequences: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[_group_key(row)].append(row)

    accepted: list[str] = []
    rejected: dict[str, dict[str, Any]] = {}
    for key in sorted(groups):
        rows = groups[key]
        horizon_counts = Counter(str(row.get("horizon", "")) for row in rows)
        missing = [h for h in HORIZONS if horizon_counts[h] == 0]
        duplicates = sorted(h for h, count in horizon_counts.items() if h in HORIZONS and count > 1)
        unexpected = sorted(h for h in horizon_counts if h not in HORIZONS)
        sequence = session_sequences.get(key)
        reasons: list[str] = []
        if any(not str(row.get("ticker", "")).strip() for row in rows):
            reasons.append("MISSING_TICKER")
        if any(not str(row.get("issuance_asof", "")).strip() for row in rows):
            reasons.append("MISSING_ISSUANCE_ASOF")
        if any(not str(row.get("target_session", "")).strip() for row in rows):
            reasons.append("MISSING_TARGET_SESSION")
        if missing:
            reasons.append("MISSING_HORIZONS")
        if duplicates:
            reasons.append("DUPLICATE_HORIZONS")
        if unexpected:
            reasons.append("UNEXPECTED_HORIZONS")
        if sequence is None:
            reasons.append("MISSING_SESSION_SEQUENCE")
        elif list(sequence.get("sessions", [])) != [row.get("target_session") for row in sorted(rows, key=lambda r: HORIZONS.index(str(r.get("horizon"))) if r.get("horizon") in HORIZONS else 99) if row.get("horizon") in HORIZONS]:
            reasons.append("SESSION_SEQUENCE_MISMATCH")

        if reasons:
            rejected[key] = {
                "reasons": reasons,
                "missing_horizons": missing,
                "duplicate_horizons": duplicates,
                "unexpected_horizons": unexpected,
                "row_count": len(rows),
            }
        else:
            accepted.append(key)

    orphan_sequences = sorted(set(session_sequences) - set(groups))
    return {
        "candidate_row_count": len(observations),
        "candidate_group_count": len(groups),
        "accepted_complete_groups": accepted,
        "accepted_group_count": len(accepted),
        "rejected_groups": rejected,
        "rejected_group_count": len(rejected),
        "orphan_session_sequences": orphan_sequences,
    }


def extract_complete_evidence_subset(
    observations: Sequence[Mapping[str, Any]],
    session_sequences: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Return only structurally complete groups plus their exact calendar proofs.

    This is a loss-accounted filter, not evidence repair: rejected groups remain fully
    described in ``audit`` and no observation value or session proof is synthesized.
    The returned subset is suitable as bounded input to the governed baseline builder,
    whose stricter provenance/content validator remains authoritative.
    """
    audit = audit_candidate_evidence(observations, session_sequences)
    accepted = set(audit["accepted_complete_groups"])
    rows = [deepcopy(dict(row)) for row in observations if _group_key(row) in accepted]
    rows.sort(key=lambda row: (_group_key(row), HORIZONS.index(str(row["horizon"]))))
    proofs = {key: deepcopy(dict(session_sequences[key])) for key in sorted(accepted)}
    return {
        "observations": rows,
        "session_sequences": proofs,
        "audit": audit,
    }
