"""Provider-neutral autonomous evidence acquisition orchestration for EDGE Stocks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional, Sequence

from src.evidence_gate import EvidenceItem, EvidenceGateResult, validate_fresh_evidence
from src.market_providers import (
    MarketAcquisition,
    ProviderObservation,
    ResearchProvider,
    UpstoxReadOnlyStockProvider,
)


@dataclass(frozen=True)
class AcquiredEvidenceBundle:
    ticker: str
    instrument_key: str
    evidence: tuple[EvidenceItem, ...]
    payloads: Mapping[str, Mapping]
    gate: EvidenceGateResult


def _to_evidence(item: ProviderObservation) -> EvidenceItem:
    return EvidenceItem(
        category=item.category,
        ticker=item.ticker,
        captured_at=item.captured_at,
        source_ref=item.source_ref,
        verified=item.verified,
        payload_ref=item.payload_ref,
    )


class AutonomousEvidenceAcquirer:
    """Collect market + research evidence and run the frozen freshness gate.

    The market provider may be Upstox today, but the orchestration depends only
    on the provider output contract. Research remains separately injectable so
    no single broker becomes the authority for news/fundamentals/event shock.
    """

    def __init__(
        self,
        market_provider: UpstoxReadOnlyStockProvider,
        research_providers: Sequence[ResearchProvider] = (),
    ):
        self._market = market_provider
        self._research = tuple(research_providers)

    def acquire(
        self,
        ticker: str,
        run_at: datetime,
        *,
        options_decision_requested: bool = False,
    ) -> AcquiredEvidenceBundle:
        market: MarketAcquisition = self._market.acquire_market(
            ticker,
            run_at,
            options_decision_requested=options_decision_requested,
        )
        observations = list(market.observations)
        payloads = dict(market.payloads)
        for provider in self._research:
            research = provider.collect(ticker.strip().upper(), run_at)
            observations.extend(research.observations)
            payloads.update(research.payloads)

        evidence = tuple(_to_evidence(item) for item in observations)
        gate = validate_fresh_evidence(
            ticker,
            evidence,
            run_at,
            options_decision_requested=options_decision_requested,
        )
        return AcquiredEvidenceBundle(
            ticker=ticker.strip().upper(),
            instrument_key=market.instrument_key,
            evidence=evidence,
            payloads=payloads,
            gate=gate,
        )
