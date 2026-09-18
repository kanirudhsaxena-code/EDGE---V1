from src.pre_run_gate import (
    EfficacySnapshot,
    OpenRecommendationState,
    evaluate_pre_run_gate,
)


def valid_snapshot():
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


def valid_open_call():
    return OpenRecommendationState(
        recommendation_id="EDGE-LTF-20260917-01",
        ticker="LTF",
        lifecycle_status="OPEN",
        expiry_trading_date="2026-09-24",
        due_checkpoint_count=5,
        captured_checkpoint_count=1,
        latest_checkpoint_observed_at="2026-09-18T10:00:00Z",
    )


def test_pre_run_gate_passes_valid_current_state():
    result = evaluate_pre_run_gate([valid_open_call()], valid_snapshot())
    assert result.ready is True
    assert result.blockers == ()
    assert result.assessed_open_recommendations == 1


def test_pre_run_gate_keeps_official_metrics_na_when_no_closed_sample():
    snapshot = EfficacySnapshot(**{
        **valid_snapshot().__dict__,
        "recommendation_hit_rate_pct": 100.0,
    })
    result = evaluate_pre_run_gate([valid_open_call()], snapshot)
    assert result.ready is False
    assert any("official efficacy must remain N/A" in blocker for blocker in result.blockers)


def test_pre_run_gate_rejects_incoherent_provisional_counts():
    snapshot = EfficacySnapshot(**{
        **valid_snapshot().__dict__,
        "provisional_forecast_hits": 3,
        "provisional_forecast_misses": 1,
    })
    result = evaluate_pre_run_gate([valid_open_call()], snapshot)
    assert result.ready is False
    assert any("forecast hit/miss counts" in blocker for blocker in result.blockers)


def test_pre_run_gate_rejects_unassessed_captured_checkpoint():
    call = OpenRecommendationState(**{
        **valid_open_call().__dict__,
        "latest_checkpoint_observed_at": None,
    })
    result = evaluate_pre_run_gate([call], valid_snapshot())
    assert result.ready is False
    assert any("no observation timestamp" in blocker for blocker in result.blockers)


def test_pre_run_gate_allows_zero_open_recommendations():
    result = evaluate_pre_run_gate([], valid_snapshot())
    assert result.ready is True
    assert result.assessed_open_recommendations == 0


def test_overdue_due_checkpoint_blocks_new_run():
    row=OpenRecommendationState(
        recommendation_id="EDGE-X-1",ticker="X",lifecycle_status="OPEN",
        expiry_trading_date="2026-09-25",due_checkpoint_count=5,
        captured_checkpoint_count=1,latest_checkpoint_observed_at="2026-09-17T10:00:00Z",
        overdue_checkpoint_count=1,
    )
    result=evaluate_pre_run_gate([row],valid_snapshot())
    assert result.ready is False
    assert any("overdue DUE checkpoint" in b for b in result.blockers)
