# Frozen G5 runtime-binding evidence — 2026-10-02

Scope: existing frozen G5-06/G5-07 only. No gate definition changes.

## Verified production-path evidence

Inspection of `src/production_orchestrator.py` on `g5-bind-approved-dd4-v1` confirms the governed publishable path currently acquires authenticated Upstox evidence, selects a live/reference price, computes the frozen EDGE V1 recommendation, resolves the governed trading calendar, and persists the canonical parent recommendation. It does not construct or pass a G5 forecast path to `AtomicNeonPersistenceAdapter`.

Inspection of `src/horizon_calibration_inputs.py` confirms that the stock-horizon boundary requires independently attributable price history, volatility, liquidity, gap/event risk and regime evidence.

Inspection of `src/autonomous_interpreter.py` confirms its ATR helper returns None with fewer than 15 candles, while `_technical_scores` substitutes `max(0.01, close * 0.02)`. That fallback is not evidence-derived ATR14 and therefore must not be used as the G5 ATR14 input.

The current production orchestrator does not expose independently VERIFIED G5 categorical stock regime (Rs), sector regime (Rsec), liquidity state (L), or event/gap-risk state (E), with the required per-dimension lineage. Existing aggregate/component scores are not silently remapped.

## Attempted remedy

The safe binding point was identified: construct the approved G5 forecast only after the normal governed evidence acquisition has produced all required verified issuance inputs, then pass the exact-five forecast path into the existing atomic persistence adapter alongside the parent recommendation.

No production binding was committed because doing so with the currently surfaced runtime values would require inventing or silently remapping Rs/Rsec/L/E or accepting the interpreter's non-evidence ATR fallback, violating G5_STOCK_DD4_V1.0.

## Exact blocker

Frozen G5-06/G5-07 remain blocked on surfacing already-governed VERIFIED ATR14, Rs, Rsec, L and E plus independent source/timestamp/hash lineage into the normal EDGE Stocks publishable execution path.

P0, governed calendar resolution, parent recommendation production, and downstream persistence infrastructure are not identified as the source of this blocker.

Lane-1 and frozen EDGE_V1 aggregate scoring/recommendation logic are unchanged.
