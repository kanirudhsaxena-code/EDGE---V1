# 2C-02 — EDGE Frozen Truth Baseline Evidence Contract

Status: RESEARCH / READ-ONLY BASELINE CONTRACT — no methodology promotion
Date: 2026-09-25
Programme binding: Phase 2.0 Fresh Plan, parallel-safe 2C-02; supports G5 evidence only after populated with attributable historical observations.

## Purpose

Define the reproducible evidence artifact required before G5 may derive stock/horizon calibration. This contract does **not** define probability decay, zone-width multipliers, expected-centre formulas, or any production recommendation methodology. An empty or incomplete baseline is not calibration evidence.

## Information Requirements

Each historical observation must identify the stock, issuance/as-of session, and D/D+1/D+2/D+3/D+4 target trading sessions. Issuance-time state must be attributable rather than reconstructed from future information. At minimum retain or reference ticker/stable instrument ID; timezone-aware issuance timestamp and exchange calendar/version; target horizon/session; issuance-time spot; ATR14/window; realised volatility/window; liquidity ratio; gap/event risk; stock/sector regime; source identifiers, source timestamps and immutable hashes; and matured target-session OHLC plus outcome source reference. Matured OHLC must contain finite open/high/low/close values with valid session geometry (`low <= open,close <= high`), and the outcome source reference must identify both source and immutable hash. UNKNOWN/UNVERIFIED must remain explicit when evidence is unavailable.

For every ticker+issuance group the frozen artifact must additionally carry `session_sequences`: exactly five ordered target sessions corresponding to D,D+1,D+2,D+3,D+4, the same governed `trading_calendar_version` used by all five observation rows, and an attributable immutable `calendar_source_ref` containing source identity and hash. This is evidence of the exchange-session mapping; bare calendar-day arithmetic is not accepted as proof.

No unavailable issuance-time field may be backfilled from later knowledge and represented as contemporaneous truth.

## Logic / Methodology

1. The baseline is frozen evidence, not a forecasting model.
2. Build observations only from attributable evidence whose as-of timing can be proven; every issuance-time source timestamp must be timezone-aware and no later than `issuance_asof`.
3. Resolve D:D+4 with the governed exchange trading calendar; never substitute calendar-day offsets. Validation requires one complete horizon set per ticker+issuance group, unique/increasing target sessions, exact row-to-sequence equality, one calendar version across all five rows, and immutable calendar-source attribution. The validator does not invent exchange holidays.
4. Keep raw observations separate from later calibration aggregates.
5. Any later G5 calibration must expose sample size, coverage and provenance.
6. Sparse evidence remains sparse: no horizon interpolation, NIFTY parameter copying, arbitrary probability decay or manufactured width multipliers.
7. Event/gap/liquidity/regime fields may be UNKNOWN/UNVERIFIED and must not be silently imputed.
8. The immutable artifact hash is deterministic SHA-256 of canonical UTF-8 JSON for the complete top-level artifact excluding only `baseline_hash`, using lexicographically sorted object keys, compact separators, Unicode preserved and non-finite numbers rejected. Stored form is `sha256:<lowercase hex>`.
9. Population tooling may derive only artifact metadata (counts, coverage, explicit missing/unverified counts, deterministic ordering/hash) from supplied attributable rows. It must copy evidence values and calendar proofs without fetching, reconstructing, imputing or calibrating them.
10. Matured outcome validation is evidence-integrity only: reject missing/non-finite/impossible OHLC geometry and unattributable outcome source references. It does not score forecast quality or define calibration methodology.

## Output Contract

A populated artifact exposes contract version; baseline ID/hash; generated timestamp; source-system/version references; observation/ticker/session counts; ticker+horizon coverage; missing/unverified counts; governed `session_sequences` proof; ordered immutable observations; matured outcome attribution; and zero production recommendation fields or promoted calibration parameters.

A consumer fails closed when the artifact is missing, empty, hash-invalid, timing-unattributable, exchange-session proof is missing/inconsistent, matured OHLC is incomplete/non-finite/geometrically impossible, outcome source identity/hash is absent, or evidence is insufficient for the claimed calibration slice.

## Safeguards / Dependencies

- Research/read-only work only; distinct from approved G0-G9 implementation IDs.
- Does not alter EDGE production recommendation, TRADE/NO TRADE, Market Trust, canonical selection, official efficacy population or trading action.
- Does not authorize G6; G6 remains gated on G5 DONE.
- Outcomes may be obtained after maturity, but issuance-time state must never use look-ahead information.
- Baseline freezing precedes any claim that empirical calibration exists.
- Calendar proof is provenance, not a new forecasting parameter or methodology.
- Population tooling is not a market-data source and cannot convert unattributable rows into accepted evidence.
- Matured-OHLC geometry validation is an implementation/data-integrity safeguard, not a new forecast or efficacy definition.

## Acceptance

2C-02 is not complete until a populated, reproducible artifact exists and validation proves schema completeness; immutable hash; governed exchange-session D:D+4 mapping; issuance-time provenance; no look-ahead leakage; explicit missingness; attributable and geometrically valid matured OHLC outcomes; and deterministic re-read/recalculation from the same frozen baseline.

G5 calibration remains outstanding until empirical calibration is derived from accepted populated evidence and separately reviewed/tested.

## Traceability

Approved authority: MDOS Master Programme Tracker → Phase 2.0 Fresh Plan, 2C-02 parallel-safe frozen EDGE truth baseline and G5 evidence requirements.

2026-09-25 structural increment: `src/edge_truth_baseline.py` and `tests/test_edge_truth_baseline.py` pin non-empty observations, required evidence/provenance, exact coverage and rejection of production/calibration semantics. Contract head `e7feb46e` passed EDGE V1 CI #194 (run 36075726420). Structural validator head `560820b2` passed EDGE V1 CI #197 (run 36080058206).

2026-09-25 integrity/timing increment: commits `2ab837f5` + `07d8c602` add deterministic baseline SHA-256 verification, timezone-aware generated/issuance/source timestamps, fail-closed rejection of issuance-time source evidence timestamped after issuance, and regression tests proving mutation invalidates the frozen hash and future provenance is rejected. Aligned contract head `c9249f51` passed EDGE V1 CI #200 (run 36084965592); documentation evidence head `1017033b` passed CI #201 (run 36085103003).

2026-09-25 exchange-session proof increment: commits `04250f74` + `b0ef9c10` require complete ticker+issuance D:D+4 groups, unique/increasing target sessions, exact `session_sequences` row equality, a single governed calendar version and immutable calendar-source attribution. This closes the validator-side exchange-session proof gap only; it does not populate historical evidence or assert calendar correctness without a source. The governed PR #72 head `b230a81e1685be5f50f18e7a6c912c16e2d2be25` passed EDGE V1 CI #207 (workflow run `36092895697`). Documentation/evidence reconciliation head `30d5808b` passed EDGE V1 CI #211 (workflow run `36100795470`).

2026-09-25 population-tooling increment: `src/edge_truth_baseline_builder.py` plus `tests/test_edge_truth_baseline_builder.py` provide a deterministic bounded path from already-attributable evidence rows/calendar proofs to the frozen contract artifact, deriving only counts/coverage/missingness/order/hash and immediately re-validating the result. Implementation commits `5c870c7b`, `180cf65b`, `0dc9256b`. Later intake/subset/deep-freeze safeguards culminated at `e0c5b025`, which passed EDGE V1 CI #222 (run `36132695309`). This is substantive baseline-population tooling but not populated market evidence.

2026-09-25 matured-outcome integrity increment: commits `e8a97903` + `7237a5f0` make the research validator fail closed when target OHLC is incomplete, non-finite or geometrically impossible, or when `outcome_source_ref` lacks source identity/hash. This implements the already-approved requirement for attributable matured target-session OHLC; it introduces no scoring/calibration methodology and no production behavior. CI on the resulting governed head is pending.

2C-02 remains NOT DONE until attributable historical rows are supplied/frozen; empirical calibration remains outstanding.