"""Recommendation-ledger invariants for EDGE V1."""

CHECKPOINT_TYPES = ("D+1", "D+3", "D+5", "D+10", "D+15", "HORIZON")

def recommendation_id(ticker: str, yyyymmdd: str, sequence: int) -> str:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    if sequence < 1:
        raise ValueError("sequence must be >= 1")
    return f"EDGE-{ticker}-{yyyymmdd}-{sequence:02d}"
