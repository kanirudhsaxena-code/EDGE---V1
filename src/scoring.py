"""Small deterministic scoring primitives.

Authoritative weights/formulas remain those in the frozen Master Specification.
"""

def validate_probabilities(bull: float, base: float, bear: float, tolerance: float = 0.01) -> None:
    vals = (bull, base, bear)
    if any(v < 0 or v > 100 for v in vals):
        raise ValueError("probabilities must be between 0 and 100")
    if abs(sum(vals) - 100.0) > tolerance:
        raise ValueError("Bull + Base + Bear must equal 100")
