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


def acquired_from_snapshot(
    market: MarketAcquisition,
    provider_research,
    ticker: str,
    run_at: datetime,
    *,
    options_decision_requested: bool = False,
) -> AcquiredEvidenceBundle:
    """Build the governed evidence bundle from a previously captured DATA snapshot.

    No provider call occurs here. This is the computation-side enforcement of
    DATA -> RESEARCH -> COMPUTE: market and provider-research observations must
    already exist in the immutable snapshot before this function is called.
    """
    symbol=ticker.strip().upper()
    observations=list(market.observations)+list(provider_research.observations)
    payloads=dict(market.payloads)
    payloads.update(provider_research.payloads)
    evidence=tuple(_to_evidence(item) for item in observations)
    gate=validate_fresh_evidence(
        symbol,
        evidence,
        run_at,
        options_decision_requested=options_decision_requested,
    )
    return AcquiredEvidenceBundle(
        ticker=symbol,
        instrument_key=market.instrument_key,
        evidence=evidence,
        payloads=payloads,
        gate=gate,
    )


def with_auction_payload(
    acquired: AcquiredEvidenceBundle,
    *,
    auction_source_ref: str,
    auction_payload: Mapping,
    captured_at: datetime,
) -> AcquiredEvidenceBundle:
    """Attach the frozen pre-open auction quote to already validated PREP evidence.

    The auction quote is a second-stage market observation, not research. It is
    deliberately added after DATA-bound research and before computation so the
    pre-open reference price is attributable to the governed auction window.
    """
    evidence=tuple(acquired.evidence)+(EvidenceItem(
        category="PRICE_STRUCTURE",
        ticker=acquired.ticker,
        captured_at=captured_at,
        source_ref=auction_source_ref,
        verified=True,
        payload_ref="EDGE_AUCTION_SNAPSHOT",
    ),)
    payloads=dict(acquired.payloads)
    payloads[auction_source_ref]=dict(auction_payload)
    gate=validate_fresh_evidence(
        acquired.ticker,
        evidence,
        captured_at,
        options_decision_requested=False,
    )
    return AcquiredEvidenceBundle(
        ticker=acquired.ticker,
        instrument_key=acquired.instrument_key,
        evidence=evidence,
        payloads=payloads,
        gate=gate,
    )
