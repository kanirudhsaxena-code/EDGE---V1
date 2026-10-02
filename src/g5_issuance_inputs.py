"""Deterministic G5 issuance-input adapter for G5_STOCK_DD4_V1.0.

This module is additive to the frozen EDGE V1 engine. It only converts verified
runtime evidence into the already-approved G5 inputs P0, ATR14, Rs, Rsec, L, E
plus exact lineage. It never changes DES, Market Trust, BOT, recommendation,
canonical selection, efficacy or execution logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from statistics import median
from typing import Any, Mapping, Optional, Sequence

from src.autonomous_interpreter import price_structure_raw_score


G5_INPUT_MAPPING_VERSION = "G5_INPUT_MAPPING_V1.0"
G5_SECTOR_REGISTRY_VERSION = "G5_SECTOR_REGISTRY_V1"


class G5InputError(ValueError):
    """Fail-closed G5 issuance-input error."""


@dataclass(frozen=True)
class G5Lineage:
    source_id: str
    provider: str
    as_of: str
    acquired_at: datetime
    verification_state: str
    data_hash: str
    derivation_version: str = G5_INPUT_MAPPING_VERSION


@dataclass(frozen=True)
class G5IssuanceInputs:
    p0: float
    atr14: float
    stock_regime: str
    sector_regime: str
    liquidity_state: str
    event_gap_risk_state: str
    target_trading_dates: tuple[date, date, date, date, date]
    calendar_version: str
    lineage: Mapping[str, G5Lineage]
    sector_name: str
    sector_benchmark: str


# Ordered, conservative mapping from the Upstox company-profile sector field
# to a governed NSE sector/index benchmark name. Unsupported/ambiguous sectors
# fail closed instead of silently falling back to Nifty 50.
_SECTOR_INDEX_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("private bank",), "Nifty Private Bank"),
    (("psu bank", "public sector bank"), "Nifty PSU Bank"),
    (("bank", "banking"), "Nifty Bank"),
    (("nbfc", "finance", "financial services"), "Nifty Financial Services"),
    (("information technology", "software", "it services"), "Nifty IT"),
    (("pharmaceutical", "pharma", "healthcare"), "Nifty Healthcare"),
    (("automobile", "auto"), "Nifty Auto"),
    (("fast moving consumer goods", "fmcg"), "Nifty FMCG"),
    (("metal", "mining"), "Nifty Metal"),
    (("realty", "real estate"), "Nifty Realty"),
    (("media", "entertainment"), "Nifty Media"),
    (("oil & gas", "oil and gas", "refiner", "refineries", "petroleum"), "Nifty Oil & Gas"),
    (("consumer durable",), "Nifty Consumer Durables"),
)


def _normalise_text(value: str) -> str:
    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .replace("&", " and ")
        .replace("-", " ")
        .replace("/", " ")
        .split()
    )


def sector_benchmark_name(sector: str) -> str:
    """Resolve a governed NSE sector benchmark name or fail closed."""
    normalized = _normalise_text(sector)
    if not normalized:
        raise G5InputError("G5 sector identity is unavailable")
    for needles, benchmark in _SECTOR_INDEX_RULES:
        if any(_normalise_text(needle) in normalized for needle in needles):
            return benchmark
    raise G5InputError(f"G5 sector is unsupported by governed registry: {sector}")


def extract_profile_sector(payloads: Mapping[str, Mapping[str, Any]]) -> tuple[str, str]:
    """Return sector and profile source_ref from the verified Upstox profile payload."""
    matches = [
        (source_ref, payload)
        for source_ref, payload in payloads.items()
        if "/fundamentals/" in source_ref and "/profile" in source_ref
    ]
    if len(matches) != 1:
        raise G5InputError("G5 requires exactly one attributable company profile payload")
    source_ref, payload = matches[0]
    data = payload.get("data") if isinstance(payload, Mapping) else None
    sector = data.get("sector") if isinstance(data, Mapping) else None
    if not isinstance(sector, str) or not sector.strip():
        raise G5InputError("G5 company profile sector is unavailable")
    return sector.strip(), source_ref


def candles_from_payload(payload: Mapping[str, Any]) -> list[list[Any]]:
    data = payload.get("data") if isinstance(payload, Mapping) else None
    rows = data.get("candles") if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        raise G5InputError("G5 candle payload is unavailable")
    candles = [row for row in rows if isinstance(row, list) and len(row) >= 6]
    try:
        candles.sort(key=lambda row: str(row[0]))
    except Exception as exc:
        raise G5InputError("G5 candle timestamps are invalid") from exc
    if not candles:
        raise G5InputError("G5 candle history is empty")
    return candles


def stock_daily_payload(
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    instrument_key: str,
) -> tuple[list[list[Any]], str]:
    encoded = instrument_key.replace("|", "%7C")
    matches = [
        (source_ref, payload)
        for source_ref, payload in payloads.items()
        if "/historical-candle/" in source_ref
        and "/days/1/" in source_ref
        and (instrument_key in source_ref or encoded in source_ref)
    ]
    if len(matches) != 1:
        raise G5InputError("G5 requires exactly one attributable stock daily-candle payload")
    source_ref, payload = matches[0]
    return candles_from_payload(payload), source_ref


def compute_atr14(candles: Sequence[Sequence[Any]]) -> float:
    """Approved ATR14: arithmetic mean of 14 true ranges from 15 completed bars."""
    if len(candles) < 15:
        raise G5InputError("G5 ATR14 requires at least 15 completed daily candles")
    rows = list(candles)[-15:]
    trs: list[float] = []
    for prev, cur in zip(rows[:-1], rows[1:]):
        try:
            high = float(cur[2])
            low = float(cur[3])
            prev_close = float(prev[4])
        except (TypeError, ValueError, IndexError) as exc:
            raise G5InputError("G5 ATR14 candle values are invalid") from exc
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        if tr <= 0:
            raise G5InputError("G5 ATR14 true range must be positive")
        trs.append(tr)
    if len(trs) != 14:
        raise G5InputError("G5 ATR14 did not resolve exactly 14 true ranges")
    return sum(trs) / 14.0


def regime_from_price_structure(raw_score: int) -> str:
    """Approved Rs/Rsec bridge from frozen EDGE Price Structure raw score."""
    if raw_score in (1, 2):
        return "BULLISH"
    if raw_score == 0:
        return "NEUTRAL"
    if raw_score in (-1, -2):
        return "BEARISH"
    raise G5InputError(f"G5 price-structure score is outside frozen range: {raw_score}")


def regime_from_candles(candles: Sequence[list[Any]]) -> str:
    return regime_from_price_structure(price_structure_raw_score(candles))


def liquidity_ratio(candles: Sequence[Sequence[Any]]) -> float:
    """Latest-5 median traded value divided by immediately preceding-20 median."""
    if len(candles) < 25:
        raise G5InputError("G5 liquidity requires at least 25 completed daily candles")
    rows = list(candles)[-25:]
    values: list[float] = []
    for row in rows:
        try:
            close = float(row[4])
            volume = float(row[5])
        except (TypeError, ValueError, IndexError) as exc:
            raise G5InputError("G5 liquidity candle values are invalid") from exc
        traded_value = close * volume
        if close <= 0 or volume <= 0 or traded_value <= 0:
            raise G5InputError("G5 liquidity requires positive close and volume")
        values.append(traded_value)
    prior20 = median(values[:20])
    latest5 = median(values[20:])
    if prior20 <= 0:
        raise G5InputError("G5 liquidity denominator is invalid")
    return latest5 / prior20


def liquidity_state_from_ratio(ratio: float) -> str:
    try:
        value = float(ratio)
    except (TypeError, ValueError) as exc:
        raise G5InputError("G5 liquidity ratio is invalid") from exc
    if value <= 0:
        raise G5InputError("G5 liquidity ratio must be positive")
    if value >= 0.75:
        return "NORMAL"
    if value >= 0.40:
        return "CAUTION"
    return "WEAK"


def liquidity_state_from_candles(candles: Sequence[Sequence[Any]]) -> str:
    return liquidity_state_from_ratio(liquidity_ratio(candles))


def event_gap_risk_state(
    *,
    event_shock_raw_score: Optional[int],
    active_override: Optional[str],
) -> str:
    """Bridge existing EDGE Event-Shock output into the approved G5 E state."""
    override = str(active_override or "").strip().upper()
    if override in {"O1", "O2", "O3"}:
        return "HIGH_RISK"
    if event_shock_raw_score is None:
        raise G5InputError("G5 Event-Shock Risk is not verified")
    if event_shock_raw_score < 0:
        return "MODERATE"
    return "NO_MATERIAL_RISK"


def sha256_from_source_ref(source_ref: str) -> str:
    marker = "#sha256="
    if marker in source_ref:
        digest = source_ref.rsplit(marker, 1)[1].strip()
        if len(digest) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in digest):
            return digest.lower()
    return hashlib.sha256(source_ref.encode("utf-8")).hexdigest()


def lineage_from_source(
    *,
    source_ref: str,
    provider: str,
    as_of: str,
    acquired_at: datetime,
    verification_state: str = "VERIFIED",
    derivation_version: str = G5_INPUT_MAPPING_VERSION,
) -> G5Lineage:
    if acquired_at.tzinfo is None:
        raise G5InputError("G5 lineage acquired_at must be timezone-aware")
    if not source_ref.strip() or not as_of.strip():
        raise G5InputError("G5 lineage source and as-of timestamp are required")
    if verification_state != "VERIFIED":
        raise G5InputError("G5 input lineage must be VERIFIED")
    return G5Lineage(
        source_id=source_ref,
        provider=provider,
        as_of=as_of,
        acquired_at=acquired_at,
        verification_state=verification_state,
        data_hash=sha256_from_source_ref(source_ref),
        derivation_version=derivation_version,
    )


def combined_lineage(
    *,
    source_refs: Sequence[str],
    provider: str,
    as_of: str,
    acquired_at: datetime,
    derivation_version: str = G5_INPUT_MAPPING_VERSION,
) -> G5Lineage:
    refs = tuple(dict.fromkeys(str(ref).strip() for ref in source_refs if str(ref).strip()))
    if not refs:
        raise G5InputError("G5 combined lineage requires at least one source")
    source_id = "|".join(refs)
    canonical = json.dumps(refs, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return G5Lineage(
        source_id=source_id,
        provider=provider,
        as_of=as_of,
        acquired_at=acquired_at,
        verification_state="VERIFIED",
        data_hash=digest,
        derivation_version=derivation_version,
    )


def producer_lineage_maps(
    inputs: G5IssuanceInputs,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    required = (
        "p0",
        "atr14",
        "stock_regime",
        "sector_regime",
        "liquidity",
        "event_gap_risk",
        "calendar",
    )
    missing = [key for key in required if key not in inputs.lineage]
    if missing:
        raise G5InputError("G5 lineage missing required inputs: " + ",".join(missing))
    ids = {key: inputs.lineage[key].source_id for key in required}
    timestamps = {key: inputs.lineage[key].as_of for key in required}
    hashes = {key: inputs.lineage[key].data_hash for key in required}
    return ids, timestamps, hashes


def latest_candle_as_of(candles: Sequence[Sequence[Any]]) -> str:
    if not candles:
        raise G5InputError("G5 candle lineage requires a latest candle")
    value = str(candles[-1][0]).strip()
    if not value:
        raise G5InputError("G5 latest candle timestamp is blank")
    return value
