from datetime import datetime, timedelta, timezone

from src.evidence_gate import (
    EvidenceItem,
    REQUIRED_CORE_CATEGORIES,
    validate_fresh_evidence,
)

RUN_AT = datetime(2026, 9, 18, 4, 0, tzinfo=timezone.utc)


def item(category, *, minutes_old=5, ticker="LTF", verified=True, source_ref="src"):
    return EvidenceItem(
        category=category,
        ticker=ticker,
        captured_at=RUN_AT - timedelta(minutes=minutes_old),
        source_ref=source_ref,
        verified=verified,
    )


def complete_core():
    rows = []
    for category in REQUIRED_CORE_CATEGORIES:
        age = 5
        if category in {"NEWS_EVENTS_CATALYSTS", "BUSINESS_FUNDAMENTALS", "EVENT_SHOCK"}:
            age = 60
        rows.append(item(category, minutes_old=age))
    return rows


def test_complete_core_packet_passes_without_options():
    result = validate_fresh_evidence("LTF", complete_core(), RUN_AT)
    assert result.ready is True
    assert not result.blockers
    assert set(result.covered_categories) == set(REQUIRED_CORE_CATEGORIES)
    assert any("optional categories unavailable" in w for w in result.warnings)


def test_options_request_requires_fresh_derivatives():
    result = validate_fresh_evidence(
        "LTF", complete_core(), RUN_AT, options_decision_requested=True
    )
    assert result.ready is False
    assert any("DERIVATIVES_OPTIONS" in b for b in result.blockers)


def test_fresh_options_evidence_satisfies_options_gate():
    rows = complete_core() + [item("DERIVATIVES_OPTIONS", minutes_old=10)]
    result = validate_fresh_evidence(
        "LTF", rows, RUN_AT, options_decision_requested=True
    )
    assert result.ready is True


def test_stale_intraday_evidence_blocks():
    rows = complete_core()
    rows = [
        item(r.category, minutes_old=31 if r.category == "PRICE_STRUCTURE" else 5)
        for r in rows
    ]
    result = validate_fresh_evidence("LTF", rows, RUN_AT)
    assert result.ready is False
    assert any("PRICE_STRUCTURE" in b and "stale evidence" in b for b in result.blockers)


def test_unverified_source_cannot_satisfy_required_category():
    rows = complete_core()
    rows = [
        item(r.category, verified=False if r.category == "PV_PVPO" else True)
        for r in rows
    ]
    result = validate_fresh_evidence("LTF", rows, RUN_AT)
    assert result.ready is False
    assert any("PV_PVPO" in b and "not verified" in b for b in result.blockers)
    assert any("missing required fresh categories: PV_PVPO" in b for b in result.blockers)


def test_ticker_mismatch_blocks():
    rows = complete_core()
    rows[0] = item(rows[0].category, ticker="OTHER")
    result = validate_fresh_evidence("LTF", rows, RUN_AT)
    assert result.ready is False
    assert any("ticker mismatch" in b for b in result.blockers)


def test_blank_source_ref_blocks():
    rows = complete_core()
    rows[0] = item(rows[0].category, source_ref="")
    result = validate_fresh_evidence("LTF", rows, RUN_AT)
    assert result.ready is False
    assert any("source_ref is required" in b for b in result.blockers)


def test_future_dated_evidence_blocks():
    rows = complete_core()
    rows[0] = EvidenceItem(
        category=rows[0].category,
        ticker="LTF",
        captured_at=RUN_AT + timedelta(minutes=10),
        source_ref="src",
        verified=True,
    )
    result = validate_fresh_evidence("LTF", rows, RUN_AT)
    assert result.ready is False
    assert any("captured_at is in the future" in b for b in result.blockers)
