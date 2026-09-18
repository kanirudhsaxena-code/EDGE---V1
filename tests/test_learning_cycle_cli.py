from src.learning_cycle_cli import classify_learning_cycle


def test_deferred_without_mature_outcomes():
    state = classify_learning_cycle(5, 0)
    assert state.status == "DEFERRED"
    assert state.independent_sample_size == 0


def test_completed_when_mature_outcomes_exist():
    state = classify_learning_cycle(12, 3)
    assert state.status == "COMPLETED"
    assert state.independent_sample_size == 3


def test_methodology_free_classifier_rejects_negative_samples():
    import pytest
    with pytest.raises(ValueError):
        classify_learning_cycle(-1, 0)
