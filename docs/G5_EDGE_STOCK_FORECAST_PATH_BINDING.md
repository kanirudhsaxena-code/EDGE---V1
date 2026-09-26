# G5 / 2A-L06 — EDGE Stocks D:D+4 SHADOW Forecast Path Binding

Status: **G5 BUILD ACCEPTANCE COMPLETE; SHADOW/additive only**  
Canonical binding: **EDGE V1 Master Specification - Production Backbone Addendum**, G5 bindings, plus **MDOS Output, Learning Lab & Core Zone Amendment V1.0**, additive G5 closure clarification dated 26-Sep-2026. Prior versions remain authoritative history; this clarification changes gate sequencing only and does not promote forecasting methodology.  
Authoritative programme gate: MDOS Master Programme Tracker → Phase 2.0 Fresh Plan → G5.

## Information Requirements

Each issuance contains exactly five ordered stock horizons: D, D+1, D+2, D+3 and D+4. Every row carries its target trading session, complete BULL/BASE/BEAR probability vector, dominant direction, expected centre, Outer Expected Zone, evidence basis, regime context, verification state and immutable lineage. The path is linked to the parent recommendation and source run. Stock calibration evidence must be attributable and cover ATR/realised volatility, liquidity, gap/event risk and stock/sector regime. Missing evidence fails closed.

Engineering acceptance may use realistic fixtures only when unmistakably `TEST/SYNTHETIC/SHADOW`. Such fixtures are engineering-only, must remain ephemeral or hard-isolated, and are never permitted to enter production readers, canonical selection, official efficacy, Learning Lab production populations, Market Trust, recommendations or trading behavior.

## Logic / Methodology

The producer may reuse the 5DR explicit-horizon architecture pattern, but not NIFTY numerical widths or parameters. It must not manufacture future rows by decaying/interpolating the aggregate EDGE call. Genuine production-calibration numerics remain separately stock-specific and evidence-derived. The persisted path remains SHADOW/additive. If a parent recommendation is published with a governed path, recommendation and all five horizon rows commit in one transaction or roll back together. NO TRADE does not suppress the path.

The 26-Sep-2026 recovery directive separates **build acceptance** from **evidence maturation** so historical sample accumulation cannot indefinitely block the engineering programme:

- **G5-A** atomic exact-five D:D+4 SHADOW storage — build gate.
- **G5-B** exact recovery/repeat retrieval/immutability/lineage — build gate.
- **G5-C** NO TRADE storage+recovery — build gate.
- **G5-D** Engine→persistence→Console/ChatGPT exact read-model integration — build gate.
- **G5-G** repository/programme evidence alignment for the accepted build — build gate.
- Former **G5-E** genuine real-input calibration proof and **G5-F** genuine canonical/matured efficacy are transferred to the parallel **2C-02 / EDGE evidence-validation track**. They remain mandatory before any empirical calibration is represented as validated or before any methodology promotion, but they no longer block completion of the G5 engineering build or the start of G6 SHADOW engineering.

This separation does not weaken evidence standards. Synthetic fixtures may prove storage/recovery/read-model engineering only; they can never prove calibration quality or efficacy.

Frozen production behavior is unchanged: recommendation logic, Market Trust, canonical selection, official efficacy population, presentation/routing and trading action.

## Output Contract

Persistence version is `EDGE_STOCK_FORECAST_PATH_V1`. One immutable path header is keyed by `recommendation_id`; exactly five immutable issuance rows are keyed by recommendation plus horizon index. Issuance rows are never rewritten. Exact recovery reproduces the same canonical payload hash and lineage and fails closed on missing, misordered or tampered persisted rows. Later outcomes/evaluations remain separate governed lifecycle records.

## Safeguards / Dependencies / Acceptance

No Phase 2 build-acceptance evidence authorizes an uncontrolled write to live production, canonical replacement, methodology promotion, Market Trust change or trading-behavior change. Production-calibrated numerical D:D+4 forecasting remains subject to genuine attributable evidence and the 2C-02 validation track.

**G5 BUILD DONE** requires G5-A/B/C/D plus build-evidence alignment G5-G. Those gates are now satisfied on the governed branches with green CI. G6 may therefore proceed in SHADOW mode without waiting for historical efficacy maturation. The 2C-02 evidence-validation track remains open in parallel and must fail closed rather than manufacture missing evidence.

## Current gate state — 26-Sep-2026

- **G5-A — ACCEPTED:** atomic exact-five D:D+4 SHADOW storage proven.
- **G5-B — ACCEPTED:** exact recovery, repeat retrieval, lineage preservation, incomplete-path rejection and tamper rejection pass after canonical numeric hash normalization across DB round trips.
- **G5-C — ACCEPTED:** explicit NO TRADE five-horizon recovery proof passes in the same green suite.
- **G5-D — ACCEPTED:** EDGE-CONSOLE current-read integration reads the immutable path header plus exact ordered five rows by recommendation ID, exposes payload hash and lineage-bearing rows to the Console/ChatGPT read model, and fails closed on incomplete/misordered persistence. Console CI #462 and the companion Learning Lab acceptance pass.
- **G5-G — ACCEPTED for build closure:** repository binding and MDOS programme tracker aligned to the accepted A:D implementation and green evidence.
- **2C-02 real-input calibration validation — OPEN / NON-BLOCKING TO G6 SHADOW BUILD:** genuine stock-specific empirical calibration is not yet proven and must not be fabricated.
- **2C-02 matured efficacy validation — OPEN / NON-BLOCKING TO G6 SHADOW BUILD:** genuine canonical/matured cases including misses remain required before empirical efficacy claims.

## Traceability

- PR #72 — governed G5 engine branch.
- `3453243c` — transaction-bound forecast-path persistence primitive.
- `bb6c11d3` — atomic parent recommendation + SHADOW path binding.
- `a2ccd14d` — atomic binding, rollback and parent-ID guard tests.
- `3650f2cb` — G5-B read-only exact SHADOW recovery adapter with stored-hash verification.
- `580e7e22` — G5-B regression coverage for exact five-slot recovery, repeat retrieval, lineage preservation, tamper rejection and incomplete-path rejection using TEST/SYNTHETIC/SHADOW fixtures.
- `89c76524` — canonical numeric hash normalization fix for DB round-trip stability.
- `be5aa2a3` — isolated G5-C NO TRADE recovery acceptance fixture.
- `709330e9` — removes unintended connection-lifecycle regression while preserving the hash fix.
- EDGE V1 CI **#264 / run 36235052057** — **SUCCESS**; full pytest suite green with G5-B recovery and G5-C NO TRADE coverage included.
- EDGE-CONSOLE `380dc915` — current-read integration for persisted exact D:D+4 path.
- EDGE-CONSOLE `c50cabbb` — regression lock for exact five-row read model and no-write/no-efficacy-mutation boundary.
- EDGE Console CI **#462 / run 36235368163** — **SUCCESS**; companion G4 Learning Lab Acceptance **#14 / run 36235368198** also **SUCCESS**.
- MDOS Master Programme Tracker → Phase 2.0 Fresh Plan → G5 updated 26-Sep-2026 to record A:D acceptance, the build/evidence separation, and the remaining non-blocking 2C-02 evidence work.
