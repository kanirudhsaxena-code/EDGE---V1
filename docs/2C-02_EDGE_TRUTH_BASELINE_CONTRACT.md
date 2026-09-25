# 2C-02 — EDGE Frozen Truth Baseline Evidence Contract

Status: RESEARCH / READ-ONLY BASELINE CONTRACT — no methodology promotion
Date: 2026-09-25
Programme binding: Phase 2.0 Fresh Plan, parallel-safe 2C-02; supports G5 evidence only after populated with attributable historical observations.

## Purpose

Define the reproducible evidence artifact required before G5 may derive stock/horizon calibration. This contract does **not** define probability decay, zone-width multipliers, expected-centre formulas, or any production recommendation methodology. An empty or incomplete baseline is not calibration evidence.

## Information Requirements

Each historical observation must identify the stock, issuance/as-of session, and D/D+1/D+2/D+3/D+4 target trading sessions. Issuance-time state must be attributable rather than reconstructed from future information. At minimum retain or reference:

- ticker and stable instrument identifier;
- issuance/as-of timestamp and exchange trading calendar/version;
- target horizon and target trading session;
- issuance-time spot/reference price;
- ATR14 and its source/window;
- realised-volatility measure, window and source;
- liquidity evidence (including the governed liquidity ratio or sufficient source reference to reproduce it);
- gap-risk and event-risk state, with UNKNOWN/UNVERIFIED preserved when evidence is unavailable;
- stock regime and sector regime, plus sector-relative-strength evidence when available;
- source identifiers, source timestamps and immutable content/payload hashes sufficient to reproduce attribution;
- target-session OHLC outcome and source reference, stored or pulled reproducibly after maturity.

No unavailable issuance-time field may be backfilled from later knowledge and represented as contemporaneous truth.

## Logic / Methodology

1. The baseline is frozen evidence, not a forecasting model.
2. Build observations only from attributable historical/current evidence whose as-of timing can be proven.
3. Resolve D:D+4 with the governed exchange trading calendar; never substitute calendar-day offsets.
4. Keep raw observations separate from any later calibration aggregates.
5. Any calibration derived for G5 must be stock/horizon specific where evidence supports it and must expose sample size, coverage and provenance.
6. Sparse evidence must remain sparse. Do not interpolate missing horizons, copy NIFTY parameters, infer arbitrary probability decay, or manufacture width multipliers.
7. Event/gap/liquidity/regime fields may be UNKNOWN/UNVERIFIED; they must not be silently imputed.
8. Later calibration/challenger analysis must be reproducible from the frozen observation set and must preserve the baseline version/hash.

## Output Contract

A populated baseline artifact must expose:

- `baseline_contract_version`;
- `baseline_id` and immutable baseline hash;
- extraction/generated timestamp;
- source-system and source-version references;
- observation count and distinct ticker/session counts;
- coverage by ticker and horizon;
- explicit missing/unverified-field counts;
- ordered immutable observation records containing the Information Requirements above;
- target-session outcome attribution after maturity;
- zero production recommendation fields and zero promoted calibration parameters.

A consumer must fail closed for G5 calibration when the artifact is missing, empty, hash-invalid, timing-unattributable, or insufficient for the claimed calibration slice.

## Safeguards / Dependencies

- Research/read-only work only; distinct from approved G0-G9 implementation IDs.
- Does not alter EDGE production recommendation, TRADE/NO TRADE, Market Trust, canonical selection, official efficacy population or trading action.
- Does not authorize G6; G6 remains gated on G5 DONE.
- Historical outcomes may be obtained after maturity, but issuance-time state must remain historically attributable and must never use look-ahead information.
- Baseline freezing precedes any claim that empirical calibration exists.

## Acceptance

2C-02 is not complete until a populated, reproducible artifact exists and validation proves: schema completeness; immutable hash; exchange-session D:D+4 mapping; issuance-time provenance; no look-ahead leakage; explicit missingness; outcome attribution; and deterministic re-read/recalculation from the same frozen baseline.

G5 calibration remains outstanding until empirical calibration is derived from an accepted populated baseline (or equivalently governed attributable evidence) and separately reviewed/tested.

## Traceability

Approved authority: MDOS Master Programme Tracker → Phase 2.0 Fresh Plan, 2C-02 parallel-safe frozen EDGE truth baseline and G5 evidence requirements.

Repository evidence: this document freezes the baseline evidence contract only. It intentionally records no invented methodology and no calibration result. CI/PR evidence for implementation or populated-baseline tooling must be appended when available.