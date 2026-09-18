"""Map gated autonomous evidence into canonical persistence rows."""
from __future__ import annotations

import hashlib
from typing import Iterable

from src.evidence_gate import EvidenceItem
from src.persistence import CanonicalEvidenceWrite


def canonical_evidence_records(
    evidence: Iterable[EvidenceItem],
) -> tuple[CanonicalEvidenceWrite, ...]:
    rows=[]
    for item in evidence:
        if not item.verified:
            raise ValueError("unverified evidence cannot enter canonical persistence")
        ref=item.source_ref.strip()
        if not ref:
            raise ValueError("source_ref is required")

        parts=[p for p in ref.split("|") if p]
        if parts and all(p.startswith("upstox:") for p in parts):
            source_kind="UPSTOX"
        elif parts and all(p.startswith(("http://","https://","web:")) for p in parts):
            source_kind="WEB"
        else:
            source_kind="MIXED"

        digest=hashlib.sha256(ref.encode("utf-8")).hexdigest()
        rows.append(
            CanonicalEvidenceWrite(
                ticker=item.ticker.strip().upper(),
                evidence_type=item.category.strip().upper(),
                source_kind=source_kind,
                capture_timestamp=item.captured_at,
                freshness="FRESH",
                quality="HIGH",
                verification_status="VERIFIED",
                source_ref=ref,
                observation=f"Autonomous normalized evidence: {item.category.strip().upper()}",
                content_hash=digest,
            )
        )
    return tuple(rows)
