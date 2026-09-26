# G5 / 2A-L06 — EDGE Stocks D:D+4 SHADOW Forecast Path Binding

Status: build in progress; SHADOW/additive only  
Canonical binding: **EDGE V1 Master Specification - Production Backbone Addendum**, G5 bindings, plus **MDOS Output, Learning Lab & Core Zone Amendment V1.0**, additive **G5 Closure Acceptance Addendum V1.1** (26-Sep-2026). Prior versions remain authoritative history; this closure addendum clarifies acceptance and does not promote methodology.  
Authoritative programme gate: MDOS Master Programme Tracker → Phase 2.0 Fresh Plan → G5.

## Information Requirements

Each issuance contains exactly five ordered stock horizons: D, D+1,D+2,D+3,D+4. Every row carries its target trading session, complete BULL/BASE/BEAR probability vector, dominant direction, expected centre, Outer Expected Zone, evidence basis, regime context, verification state and immutable lineage. The path is linked to the parent recommendation and source run. Stock calibration evidence must be attributable and cover ATR/realised volatility, liquidity, gap/event risk and stock/sector regime. Missing evidence fails closed.

Engineering acceptance may use realistic fixtures only when unmistakably `TEST/SYNTHETIC/SHADOW`. Such fixtures are not efficacy evidence and must be ephemeral or hard-isolated from production readers, canonical selection, official efficacy, Learning Lab production populations, Market Trust, recommendations and trading behavior.

## Logic / Methodology

The producer may reuse the 5DR explicit-horizon architecture pattern, but not NIFTY numerical widths or parameters. It must not manufacture future rows by decaying/interpolating the aggregate EDGE call. Numerical calibration must be separately stock-specific and evidence-derived. The path remains SHADOW and additive. If a parent recommendation is published with a G5 path, recommendation and all five horizon rows must commit in one transaction or roll back together. NO TRADE does not suppress the path.

G5 closure is separated into: **G5-A** atomic exact-five storage; **G5-B** exact recovery/repeat retrieval/immutability/lineage; **G5-C** NO TRADE storage+recovery; **G5-D** Engine→persistence→Console/ChatGPT read-model integration; **G5-E** genuine real-input producer; **G5-F** measurable genuine canonical/matured efficacy including misses; **G5-G** documentation/evidence alignment. Historical calibration/sample depth does not block A:D. Synthetic fixtures can prove engineering only, never efficacy.

Frozen production behavior is unchanged: recommendation logic, Market Trust, canonical selection, official efficacy population, presentation/routing and trading action.

## Output Contract

Persistence version is `EDGE_STOCK_FORECAST_PATH_V1`. One immutable path header is keyed by `recommendation_id`; exactly five immutable issuance rows are keyed by recommendation plus horizon index. Issuance rows are never rewritten. Exact recovery must reproduce the same payload hash and lineage and fail closed on missing/misordered/tampered persisted rows. Later outcomes/evaluations are separate governed lifecycle records.

## Safeguards / Dependencies / Acceptance

No Phase 2 write to main/default, live DB mutation, canonical replacement, deployment/recovery/import trigger, or production behavior/presentation change is authorized. G5 is DONE only when G5-A:G pass; G6 implementation remains blocked until then.

## Current gate state — 26-Sep-2026

- **G5-A — accepted:** atomic exact-five D:D+4 SHADOW storage proven on the governed branch.
- **G5-B — accepted:** exact recovery, repeat retrieval, lineage preservation, incomplete-path rejection and tamper rejection pass after canonical numeric hash normalization across DB round trips.
- **G5-C — accepted:** explicit NO TRADE five-horizon recovery proof passes in the same CI suite.
- **G5-D — accepted:** EDGE-CONSOLE current-read integration now reads the immutable path header plus exact ordered five rows by recommendation ID, exposes payload hash and lineage-bearing rows to the Console/ChatGPT read model, and fails closed on incomplete/misordered persistence. Console CI #462 and the companion Learning Lab acceptance both pass.
- **G5-E — open:** genuine real-input producer remains to be proven without invented/interpolated horizon parameters.
- **G5-F — open:** genuine canonical/matured efficacy population must record both hits and misses where evidence is available.
- **G5-G — in progress:** repository evidence aligned through the A:D engineering acceptance checkpoint; final closure still depends on E/F evidence.

## Traceability

- PR #72 — governed G5 engine branch, OPEN/DRAFT.
- `3453243c` — transaction-bound forecast-path persistence primitive.
- `bb6c11d3` — atomic parent recommendation + SHADOW path binding.
- `a2ccd14d` — atomic binding, rollback and parent-ID guard tests.
- `95cc2fe5` — mandatory calibration evidence-reference value integrity; passed CI #237 / run 36199407423.
- `e138a0d9` — intake identity/session guard checkpoint; passed EDGE V1 CI #249 / run 36222436584.
- `3650f2cb` — G5-B read-only exact SHADOW recovery adapter with stored-hash verification.
- `580e7e22` — G5-B regression coverage for exact five-slot recovery, repeat retrieval, lineage preservation, tamper rejection and incomplete-path rejection using TEST/SYNTHETIC/SHADOW fixtures.
- `89c76524` — canonical numeric hash normalization fix for DB round-trip stability.
- `be5aa2a3` — isolated G5-C NO TRADE recovery acceptance fixture.
- `709330e9` — removes unintended connection-lifecycle regression while preserving the hash fix.
- EDGE V1 CI **#264 / run 36235052057** — **SUCCESS**; full pytest suite green with G5-B recovery and G5-C NO TRADE coverage included.
- EDGE-CONSOLE `380dc915` — current-read integration for persisted exact D:D+4 path.
- EDGE-CONSOLE `c50cabbb` — regression lock for exact five-row read model and no-write/no-efficacy-mutation boundary.
- EDGE Console CI **#462 / run 36235368163** — **SUCCESS**; companion G4 Learning Lab Acceptance **#14 / run 36235368198** also **SUCCESS**.
- Drive amendment remains additive under **G5 Closure Acceptance Addendum V1.1 — 26-Sep-2026**; prior document history preserved.
