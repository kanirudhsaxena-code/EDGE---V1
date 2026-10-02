"""G5 issuance-input adapter contract (frozen methodology)."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping

@dataclass(frozen=True)
class G5Lineage:
    source_id: str
    provider: str
    as_of: str
    acquired_at: datetime
    verification_state: str
    data_hash: str
    derivation_version: str = "G5_STOCK_DD4_V1.0"

@dataclass(frozen=True)
class G5IssuanceInputs:
    p0: float
    atr14: float
    stock_regime: str
    sector_regime: str
    liquidity_state: str
    event_gap_risk_state: str
    target_trading_dates: tuple[date,date,date,date,date]
    calendar_version: str
    lineage: Mapping[str,G5Lineage]
