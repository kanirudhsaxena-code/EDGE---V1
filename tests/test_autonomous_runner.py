from datetime import datetime, timedelta, timezone

from src.autonomous_runner import RecommendationEnvelope, run_governed_edge
from src.evidence_gate import EvidenceItem, REQUIRED_CORE_CATEGORIES
from src.pre_run_gate import EfficacySnapshot, OpenRecommendationState
from src.release_gate import ReleaseApproval

RUN_AT = datetime(2026, 9, 18, 4, 0, tzinfo=timezone.utc)


def efficacy():
    return EfficacySnapshot(
        official_sample_size=0,
        recommendation_hit_rate_pct=None,
        directional_accuracy_pct=None,
        forecast_accuracy_pct=None,
        provisional_captured_checkpoints=3,
        provisional_forecast_scorable=3,
        provisional_forecast_hits=2,
        provisional_forecast_misses=1,
        provisional_zone_scorable=3,
        provisional_zone_hits=3,
        provisional_zone_misses=0,
    )


def open_calls():
    return [
        OpenRecommendationState(
            recommendation_id="EDGE-LTF-20260917-01",
            ticker="LTF",
            lifecycle_status="OPEN",
            expiry_trading_date="2026-09-24",
            due_checkpoint_count=5,
            captured_checkpoint_count=1,
            latest_checkpoint_observed_at="2026-09-18T03:30:00Z",
        )
    ]


def evidence():
    rows = []
    for category in REQUIRED_CORE_CATEGORIES:
        age = 5 if category not in {"NEWS_EVENTS_CATALYSTS", "BUSINESS_FUNDAMENTALS", "EVENT_SHOCK"} else 60
        rows.append(
            EvidenceItem(
                category=category,
                ticker="LTF",
                captured_at=RUN_AT - timedelta(minutes=age),
                source_ref=f"src:{category}",
                verified=True,
            )
        )
    return rows


def good_engine(ticker, rows, run_at, options_requested):
    refs = tuple(r.source_ref for r in rows)
    return RecommendationEnvelope(
        ticker=ticker,
        run_timestamp=run_at,
        framework_version="EDGE_V1",
        definitive_forecast="BASE_RANGE",
        definitive_recommendation="HOLD existing delivery; NO OPTION TRADE.",
        bull_probability=43.117,
        base_probability=55.313,
        bear_probability=1.570,
        horizon_trading_days=5,
        expected_price_zone_low=298.0,
        expected_price_zone_high=315.0,
        evidence_refs=refs,
    )


def test_shadow_run_reaches_ready_state_only_after_both_gates_pass():
    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=efficacy(),
        evidence=evidence(),
        engine=good_engine,
        publish=False,
    )
    assert result.status == "SHADOW_READY"
    assert result.recommendation is not None
    assert result.persistence_id is None


def test_pre_run_failure_blocks_engine_invocation():
    called = {"value": False}

    def engine(*args):
        called["value"] = True
        return good_engine(*args)

    bad = efficacy()
    bad = EfficacySnapshot(
        official_sample_size=0,
        recommendation_hit_rate_pct=50.0,
        directional_accuracy_pct=None,
        forecast_accuracy_pct=None,
        provisional_captured_checkpoints=3,
        provisional_forecast_scorable=3,
        provisional_forecast_hits=2,
        provisional_forecast_misses=1,
        provisional_zone_scorable=3,
        provisional_zone_hits=3,
        provisional_zone_misses=0,
    )
    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=bad,
        evidence=evidence(),
        engine=engine,
    )
    assert result.status == "BLOCKED_PRE_RUN_EFFICACY"
    assert called["value"] is False


def test_stale_evidence_blocks_engine_invocation():
    called = {"value": False}

    def engine(*args):
        called["value"] = True
        return good_engine(*args)

    rows = evidence()
    rows[0] = EvidenceItem(
        category=rows[0].category,
        ticker="LTF",
        captured_at=RUN_AT - timedelta(minutes=60),
        source_ref=rows[0].source_ref,
        verified=True,
    )
    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=efficacy(),
        evidence=rows,
        engine=engine,
    )
    assert result.status == "BLOCKED_EVIDENCE"
    assert called["value"] is False


def test_engine_output_with_bad_probability_sum_is_blocked():
    def bad_engine(ticker, rows, run_at, options_requested):
        rec = good_engine(ticker, rows, run_at, options_requested)
        return RecommendationEnvelope(
            **{**rec.__dict__, "bull_probability": 40.0}
        )

    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=efficacy(),
        evidence=evidence(),
        engine=bad_engine,
    )
    assert result.status == "BLOCKED_ENGINE_OUTPUT"
    assert any("must equal 100" in b for b in result.blockers)


def test_engine_cannot_invent_evidence_refs():
    def bad_engine(ticker, rows, run_at, options_requested):
        rec = good_engine(ticker, rows, run_at, options_requested)
        return RecommendationEnvelope(
            **{**rec.__dict__, "evidence_refs": ("invented",)}
        )

    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=efficacy(),
        evidence=evidence(),
        engine=bad_engine,
    )
    assert result.status == "BLOCKED_ENGINE_OUTPUT"
    assert any("evidence_refs" in b for b in result.blockers)


class MemoryPersistence:
    def __init__(self):
        self.saved = []

    def persist(self, recommendation):
        self.saved.append(recommendation)
        return "EDGE-LTF-20260918-01"


def test_publish_is_blocked_by_default_release_governance():
    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=efficacy(),
        evidence=evidence(),
        engine=good_engine,
        publish=True,
    )
    assert result.status == "BLOCKED_RELEASE_GOVERNANCE"
    assert any("autonomous publishing" in b for b in result.blockers)


def test_publish_requires_persistence_after_explicit_release_approval():
    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=efficacy(),
        evidence=evidence(),
        engine=good_engine,
        publish=True,
        release_approval=ReleaseApproval(True,True,True),
    )
    assert result.status == "BLOCKED_PERSISTENCE"


def test_publish_persists_only_after_all_validations_pass():
    persistence = MemoryPersistence()
    result = run_governed_edge(
        ticker="LTF",
        run_at=RUN_AT,
        open_recommendations=open_calls(),
        efficacy_snapshot=efficacy(),
        evidence=evidence(),
        engine=good_engine,
        persistence=persistence,
        publish=True,
        release_approval=ReleaseApproval(True,True,True),
    )
    assert result.status == "PUBLISHED"
    assert result.persistence_id == "EDGE-LTF-20260918-01"
    assert len(persistence.saved) == 1
