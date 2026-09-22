from src.learning_snapshot import build_daily_snapshot, build_outcome_observation, content_hash


def test_hash_is_order_independent():
    assert content_hash({"b":2,"a":1}) == content_hash({"a":1,"b":2})


def test_noncanonical_outcome_is_learning_only():
    row=build_outcome_observation({
        "recommendation_id":"r1","ticker":"LTF","target_trading_date":"2026-09-22",
        "run_role":"DIAGNOSTIC","official_efficacy_eligible":False,
        "outcome_verdict":"LOSS","model_return_pct":-2.0,"observed_at":"2026-09-22T15:30:00+05:30",
    })
    assert row is not None
    assert row["exclusion_reason"]=="NON_CANONICAL"
    assert row["production_change_allowed"] is False


def test_cross_stock_snapshot_keeps_canonical_and_diagnostic_separate():
    runs=[
        {"ticker":"LTF","target_trading_date":"2026-09-22","run_role":"CANONICAL"},
        {"ticker":"LTF","target_trading_date":"2026-09-22","run_role":"DIAGNOSTIC"},
        {"ticker":"RELIANCE","target_trading_date":"2026-09-22","run_role":"CANONICAL"},
    ]
    observations=[
        {"target_trading_date":"2026-09-22","observation_type":"SUCCESS"},
        {"target_trading_date":"2026-09-22","observation_type":"ERROR"},
    ]
    snap=build_daily_snapshot(
        cycle_id="edge-20260922",as_of="2026-09-22T17:30:00+05:30",
        runs=runs,observations=observations,matured_outcomes=[{"scorable":True}],
    )
    assert snap["counts"]["canonical_runs"]==2
    assert snap["counts"]["diagnostic_runs"]==1
    assert snap["snapshot"]["ticker_count"]==2
    assert snap["snapshot"]["official_efficacy_population"]=="SELECTED_CANONICAL_ONLY"
    assert snap["snapshot"]["production_change_allowed"] is False
