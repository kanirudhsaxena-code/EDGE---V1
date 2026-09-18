from src.frozen_engine import (
    BotInputs,
    ComponentInput,
    TrustInputs,
    bot_hunter,
    compute_des,
    market_trust,
    probabilities,
)


def test_des_full_weight_model_matches_simple_weighted_sum():
    rows = [
        ComponentInput("PRICE_STRUCTURE", 2),
        ComponentInput("PV_PVPO", 1),
        ComponentInput("SPECIFIC_CHART_PATTERN", 0),
        ComponentInput("NEWS_EVENTS_CATALYSTS", -1),
        ComponentInput("BUSINESS_FUNDAMENTALS", 1),
        ComponentInput("INSTITUTIONAL_BEHAVIOUR", 0),
        ComponentInput("RELATIVE_STRENGTH", 1),
        ComponentInput("VALUATION", 0),
        ComponentInput("EVENT_SHOCK", -2),
    ]
    r = compute_des(rows)
    expected = 18 + 9 + 0 - 6 + 5 + 0 + 4 + 0 - 5
    assert abs(r.des - expected) < 1e-9


def test_missing_optional_component_is_excluded_and_weights_renormalize():
    rows = [
        ComponentInput("PRICE_STRUCTURE", 2),
        ComponentInput("PV_PVPO", 0),
        ComponentInput("SPECIFIC_CHART_PATTERN", 0),
        ComponentInput("NEWS_EVENTS_CATALYSTS", 0),
        ComponentInput("BUSINESS_FUNDAMENTALS", 0),
        ComponentInput("INSTITUTIONAL_BEHAVIOUR", None, verified=False),
        ComponentInput("RELATIVE_STRENGTH", 0),
        ComponentInput("VALUATION", 0),
        ComponentInput("EVENT_SHOCK", 0),
    ]
    r = compute_des(rows)
    # 90 points remain eligible, so Price Structure becomes 20% normalized.
    assert abs(r.des - 20.0) < 1e-9
    inst = [x for x in r.components if x.component == "INSTITUTIONAL_BEHAVIOUR"][0]
    assert inst.weighted_contribution is None


def test_directional_agreement_frozen_formula():
    rows = [
        ComponentInput("PRICE_STRUCTURE", 2),
        ComponentInput("PV_PVPO", -2),
    ]
    r = compute_des(rows)
    assert r.directional_agreement == 0


def test_market_trust_frozen_weights():
    r = market_trust(TrustInputs(100, 100, 100, 50, 100))
    assert abs(r.score - 90.0) < 1e-9
    assert r.band == "VERY HIGH"


def test_ltf_17_sep_probability_replay():
    r = probabilities(38.5, 92.974, override="O1")
    assert abs(r.bull - 43.117) < 0.01
    assert abs(r.base - 55.313) < 0.01
    assert abs(r.bear - 1.570) < 0.01
    assert r.definitive_forecast == "BASE_RANGE"
    assert r.cap_applied is None


def test_negative_des_assigns_directional_pool_to_bear():
    r = probabilities(-60, 90)
    assert r.bear > r.bull
    assert abs(r.bull + r.base + r.bear - 100) < 1e-9


def test_o1_cap_reduces_directional_conviction_into_base():
    r = probabilities(100, 100, override="O1")
    assert abs(r.bull - 70) < 1e-9
    assert abs(r.bull + r.base + r.bear - 100) < 1e-9
    assert r.cap_applied == "O1"


def test_o3_refuses_normal_probability_engine():
    try:
        probabilities(50, 90, override="O3")
    except ValueError as exc:
        assert "supersedes" in str(exc)
    else:
        raise AssertionError("O3 must not run through normal probability engine")


def test_ltf_17_sep_bot_replay():
    r = bot_hunter(BotInputs(
        leading_probability=55.313,
        market_trust=92.974,
        structure_pattern_quality=75,
        pv_pvpo_confirmation=80,
        catalyst_asymmetry=45,
        execution_quality=60,
    ))
    assert abs(r.forecast_edge - 38.8236) < 0.01
    assert abs(r.score - 65.80) < 0.02
    assert r.grade == "B"
