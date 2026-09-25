# G5 / 2A-L06 — EDGE Stocks D:D+4 SHADOW Forecast Path Binding

Status: build in progress; SHADOW/additive only  
Canonical binding: **EDGE V1 Master Specification - Production Backbone Addendum**, sections **G5 / 2A-L06 — EDGE STOCKS D:D+4 SHADOW FORECAST-PATH BINDING — V1.1** (24-Sep-2026) and **G5 / 2C-02 EVIDENCE READINESS ALIGNMENT — V1.2** (25-Sep-2026). V1.2 refines evidence proof only; it does not promote forecasting methodology.  
Authoritative programme gate: MDOS Master Programme Tracker → Phase 2.0 Fresh Plan → G5.

## Information Requirements

Each issuance contains exactly five ordered stock horizons: D, D+1, D+2, D+3 and D+4. Every row carries its target trading session, complete BULL/BASE/BEAR probability vector, dominant direction, expected centre, Outer Expected Zone, evidence basis, regime context, verification state and immutable lineage. The path is linked to the parent recommendation and source run. Stock calibration evidence must be attributable and cover the governed ATR/realised-volatility, liquidity, gap/event-risk and stock/sector-regime boundary. Missing evidence fails closed.

Before historical evidence may support calibration, each ticker+issuance group must also expose an immutable D:D+4 session-sequence proof: five ordered target sessions, one governed trading-calendar version shared by all five rows, and attributable calendar-source identity/hash. This prevents calendar-day offsets or inferred holidays from masquerading as exchange-session evidence.

## Logic / Methodology

The producer may reuse the 5DR explicit-horizon architecture pattern, but not NIFTY numerical widths or parameters. It must not manufacture future rows by decaying/interpolating the aggregate EDGE call. Numerical calibration must be separately stock-specific and evidence-derived. The path remains SHADOW and additive. If a parent recommendation is published with a G5 path, recommendation and all five horizon rows must commit in one transaction or roll back together. NO TRADE does not suppress the path.

2C-02 validation is evidence governance, not forecast calibration: complete horizon sets, exact row-to-session-sequence equality, unique/increasing target sessions, one calendar version and immutable calendar-source attribution fail closed when absent or inconsistent. No probability decay, width multiplier or expected-centre formula is introduced by this validation.

Frozen production behavior is unchanged: recommendation logic, Market Trust, canonical selection, official efficacy population and trading action.

## Output Contract

Persistence version is `EDGE_STOCK_FORECAST_PATH_V1`. One immutable path header is keyed by `recommendation_id`; exactly five immutable issuance rows are keyed by recommendation plus horizon index. Issuance rows are never rewritten. Later outcomes/evaluations must be appended separately under their governed lifecycle contract.

The separate 2C-02 research baseline exposes immutable baseline identity/hash, source and missingness metadata, session-sequence proof, ordered historical observations and attributable matured outcomes. It is not a production output or official efficacy record.

## Safeguards / Dependencies / Acceptance

G5 remains incomplete until genuine evidence-derived stock calibration is implemented without invented parameters, wired into publishing including NO TRADE, validated in engine and Console cross-repo acceptance, and all canonical/repository documentation remains aligned. G6 implementation remains blocked until G5 is DONE. 2C-02 remains incomplete until real historical observations populate and reproducibly validate the frozen contract.

## Traceability

- PR #72 — governed G5 engine branch.
- `3453243c` — transaction-bound forecast-path persistence primitive.
- `bb6c11d3` — atomic parent recommendation + SHADOW path binding.
- `a2ccd14d` — atomic binding, rollback and parent-ID guard tests; atomic slice later accepted by CI #193.
- Calibration-evidence-boundary head `a23409f` passed EDGE V1 CI #188.
- 2C-02 integrity/timing head `1017033b` passed EDGE V1 CI #201 (run 36085103003).
- `04250f74` + `b0ef9c10` — exchange-session proof validator and tests.
- `cabac2c0` — aligned 2C-02 repository evidence contract; CI pending at time of this binding update.
- Canonical Drive companion advanced additively to G5 / 2C-02 Evidence Readiness Alignment V1.2 on 25-Sep-2026; V1.1 and earlier history preserved.
