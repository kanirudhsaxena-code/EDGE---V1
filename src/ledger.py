"""Recommendation-ledger invariants for EDGE V1 + Efficacy Engine V2."""

# Legacy checkpoint types are retained for historical records, but all new V2
# recommendations use the D+1 ... D+5 sequence only.
CHECKPOINT_TYPES = ("D+1", "D+2", "D+3", "D+4", "D+5", "D+10", "D+15", "HORIZON")
D5_CHECKPOINT_TYPES = ("D+1", "D+2", "D+3", "D+4", "D+5")


def recommendation_id(ticker: str, yyyymmdd: str, sequence: int) -> str:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    if sequence < 1:
        raise ValueError("sequence must be >= 1")
    return f"EDGE-{ticker}-{yyyymmdd}-{sequence:02d}"
