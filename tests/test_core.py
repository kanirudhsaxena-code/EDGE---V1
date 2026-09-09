from src.ledger import recommendation_id
from src.scoring import validate_probabilities

def test_recommendation_id():
    assert recommendation_id("ltf", "20260909", 1) == "EDGE-LTF-20260909-01"

def test_probabilities():
    validate_probabilities(60, 25, 15)
