"""Live, non-publishing EDGE shadow harness.

Acquires current read-only Upstox evidence for one NSE equity, applies the
conservative autonomous interpreter and frozen EDGE computation core, and emits
only a bounded summary. It never persists a recommendation and never calls any
trading/order/account endpoint.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.autonomous_evidence_acquisition import AutonomousEvidenceAcquirer
from src.autonomous_interpreter import ConservativeAutonomousInterpreter
from src.market_providers import AcquisitionError, UpstoxReadOnlyStockProvider, safe_diagnostic
from src.shadow_pipeline import compute_shadow_recommendation
from src.upstox_research import UpstoxReadOnlyResearchProvider


def run_live_shadow(ticker: str, token: str, run_at: datetime | None = None) -> dict:
    run_at = run_at or datetime.now(timezone.utc)
    market = UpstoxReadOnlyStockProvider(token)
    research = UpstoxReadOnlyResearchProvider(token)
    bundle = AutonomousEvidenceAcquirer(market, [research]).acquire(
        ticker,
        run_at,
        options_decision_requested=False,
    )
    if not bundle.gate.ready:
        return {
            "status": "SHADOW_BLOCKED_EVIDENCE",
            "ticker": ticker.upper(),
            "run_timestamp": run_at.isoformat(),
            "blockers": list(bundle.gate.blockers),
            "warnings": list(bundle.gate.warnings),
            "publishing_enabled": False,
            "trading_enabled": False,
        }

    result = compute_shadow_recommendation(
        bundle,
        run_at,
        ConservativeAutonomousInterpreter(),
    )
    return {
        "status": "SHADOW_COMPUTED",
        "ticker": result.ticker,
        "run_timestamp": result.run_timestamp.isoformat(),
        "des": round(result.des, 3),
        "directional_agreement": round(result.directional_agreement, 3),
        "market_trust": round(result.market_trust, 3),
        "market_trust_band": result.market_trust_band,
        "probabilities": {
            "bull": round(result.bull_probability, 3),
            "base": round(result.base_probability, 3),
            "bear": round(result.bear_probability, 3),
        },
        "definitive_forecast": result.definitive_forecast,
        "bot_score": round(result.bot_score, 3),
        "bot_grade": result.bot_grade,
        "expected_price_zone": [
            result.recommendation.expected_price_zone_low,
            result.recommendation.expected_price_zone_high,
        ],
        "recommendation": result.recommendation.definitive_recommendation,
        "evidence_count": len(bundle.evidence),
        "publishing_enabled": False,
        "trading_enabled": False,
    }


if __name__ == "__main__":
    ticker = os.getenv("EDGE_TICKER", "LTF").strip().upper()
    token = os.getenv("UPSTOX_ANALYTICS_TOKEN", "")
    try:
        print(json.dumps(run_live_shadow(ticker, token), sort_keys=True))
    except AcquisitionError as exc:
        print(json.dumps({
            "status": "SHADOW_BLOCKED_ACQUISITION",
            "ticker": ticker,
            "diagnostic_code": safe_diagnostic(exc),
            "publishing_enabled": False,
            "trading_enabled": False,
        }, sort_keys=True))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({
            "status": "SHADOW_BLOCKED_INTERNAL",
            "ticker": ticker,
            "diagnostic_code": "SHADOW_VALIDATION_FAILED",
            "publishing_enabled": False,
            "trading_enabled": False,
        }, sort_keys=True))
        raise SystemExit(3)
