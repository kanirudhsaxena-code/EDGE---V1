from datetime import datetime, timezone

from src.evidence_gate import EvidenceItem
from src.evidence_persistence import canonical_evidence_records


def test_maps_verified_upstox_evidence_to_canonical_row():
    rows=canonical_evidence_records([
        EvidenceItem(
            category="PRICE_STRUCTURE",
            ticker="LTF",
            captured_at=datetime(2026,9,18,6,0,tzinfo=timezone.utc),
            source_ref="upstox:/v3/market-quote/quotes?instrument_key=x#sha256=a|upstox:/v3/historical-candle/x#sha256=b",
            verified=True,
        )
    ])
    assert len(rows)==1
    r=rows[0]
    assert r.ticker=="LTF"
    assert r.evidence_type=="PRICE_STRUCTURE"
    assert r.source_kind=="OTHER_PERMITTED"
    assert r.verification_status=="VERIFIED"
    assert len(r.content_hash)==64


def test_unverified_evidence_is_rejected():
    try:
        canonical_evidence_records([
            EvidenceItem(
                category="PRICE_STRUCTURE",ticker="LTF",
                captured_at=datetime(2026,9,18,6,0,tzinfo=timezone.utc),
                source_ref="x",verified=False,
            )
        ])
    except ValueError as exc:
        assert "unverified" in str(exc)
    else:
        raise AssertionError("unverified evidence must fail")
