# 2C-02 — EDGE Frozen Truth Baseline Evidence Contract

Status: RESEARCH / READ-ONLY BASELINE CONTRACT — no methodology promotion
Date: 2026-09-25
Programme binding: Phase 2.0 Fresh Plan, parallel-safe 2C-02; supports G5 evidence only after populated with attributable historical observations.

## Purpose

Define the reproducible evidence artifact required before G5 may derive stock/horizon calibration. This contract does **not** define probability decay, zone-width multipliers, expected-centre formulas, or any production recommendation methodology. An empty or incomplete baseline is not calibration evidence.

## Information Requirements

Each historical observation must identify the stock, issuance/as-of session, and D/D+1/D+2/D+3/D+4 target trading sessions. Issuance-time state must be attributable rather than reconstructed from future information. At minimum retain or reference ticker/stable instrument ID; timezone-aware issuance timestamp and exchange calendar/version; target horizon/session; issuance-time spot; ATR14/window; realised volatility/window; liquidity ratio; gap/event risk; stock/sector regime; source identifiers, source timestamps and immutable hashes; and matured target-session OHLC plus outcome source reference. UNKNOWN/UNVERIFIED must remain explicit when evidence is unavailable.

No unavailable issuance-time field may be backfilled from later knowledge and represented as contemporaneous truth.

## Logic / Methodology

1. The baseline is frozen evidence, not a forecasting model.
2. Build observations only from attributable evidence whose as-of timing can be proven; every issuance-time source timestamp must be timezone-aware and no later than `issuance_asof`.
3. Resolve D:D+4 with the governed exchange trading calendar; never substitute calendar-day offsets.
4. Keep raw observations separate from later calibration aggregates.
5. Any later G5 calibration must expose sample size, coverage and provenance.
6. Sparse evidence remains sparse: no horizon interpolation, NIFTY parameter copying, arbitrary probability decay or manufactured width multipliers.
7. Event/gap/liquidity/regime fields may be UNKNOWN/UNVERIFIED and must not be silently imputed.
8. The immutable artifact hash is deterministic SHA-256 of canonical UTF-8 JSON for the complete top-level artifact excluding only `baseline_hash`, using lexicographically sorted object keys, compact separators, Unicode preserved and non-finite numbers rejected. Stored form is `sha256:<lowercase hex>`.

## Output Contract

A populated artifact exposes contract version; baseline ID/hash; generated timestamp; source-system/version references; observation/ticker/session counts; ticker+horizon coverage; missing/unverified counts; ordered immutable observations; matured outcome attribution; and zero production recommendation fields or promoted calibration parameters.

A consumer fails closed when the artifact is missing, empty, hash-invalid, timing-unattributable, or insufficient for the claimed calibration slice.

## Safeguards / Dependencies

- Research/read-only work only; distinct from approved G0-G9 implementation IDs.
- Does not alter EDGE production recommendation, TRADE/NO TRADE, Market Trust, canonical selection, official efficacy population or trading action.
- Does not authorize G6; G6 remains gated on G5 DONE.
- Outcomes may be obtained after maturity, but issuance-time state must never use look-ahead information.
- Baseline freezing precedes any claim that empirical calibration exists.

## Acceptance

2C-02 is not complete until a populated, reproducible artifact exists and validation proves schema completeness; immutable hash; exchange-session D:D+4 mapping; issuance-time provenance; no look-ahead leakage; explicit missingness; outcome attribution; and deterministic re-read/recalculation from the same frozen baseline.

G5 calibration remains outstanding until empirical calibration is derived from accepted populated evidence and separately reviewed/tested.

## Traceability

Approved authority: MDOS Master Programme Tracker → Phase 2.0 Fresh Plan, 2C-02 parallel-safe frozen EDGE truth baseline and G5 evidence requirements.

2026-09-25 structural increment: `src/edge_truth_baseline.py` and `tests/test_edge_truth_baseline.py` pin non-empty observations, required evidence/provenance, exact coverage and rejection of production/calibration semantics. Contract head `e7feb46e` passed EDGE V1 CI #194 (run 36075726420). Structural validator head `560820b2` passed EDGE V1 CI #197 (run 36080058206).

2026-09-25 integrity/timing increment: commits `2ab837f5` + `07d8c602` add deterministic baseline SHA-256 verification, timezone-aware generated/issuance/source timestamps, fail-closed rejection of issuance-time source evidence timestamped after issuance, and regression tests proving mutation invalidates the frozen hash and future provenance is rejected. Aligned contract head `c9249f51` passed EDGE V1 CI #200 (run 36084965592). This is evidence-governance hardening only: it does not populate historical evidence, prove exchange-calendar D:D+4 mapping, define calibration parameters, or complete 2C-02/G5.
