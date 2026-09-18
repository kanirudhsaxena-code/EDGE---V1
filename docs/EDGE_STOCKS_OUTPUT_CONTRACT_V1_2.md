# EDGE Stocks User-Facing Output Contract V1.2

Status: CANONICAL PRESENTATION CONTRACT  
Framework: EDGE V1 analytical core (unchanged)  
Contract version: `EDGE_STOCKS_V1_2`

## Purpose

This contract governs presentation only. It does not alter frozen EDGE scoring, weights, DES, Market Trust, probability architecture, Decision Ladder, BOT, execution rules, Efficacy V2 semantics, historical recommendations, or learning governance.

The command `EDGE <stock/company/ticker>` is a strict invocation of the EDGE Stocks protocol, not a generic stock-analysis request.

## Standard output invariant

A standard EDGE run contains exactly two user-facing tables, in this order:

1. **EDGE Outcome / Decision**
2. **Institutional Drill-down**

No alternate stock-analysis layout may replace these tables unless the user explicitly requests a different presentation.

Efficacy is displayed separately after the two standard tables and must preserve the OFFICIAL versus PROVISIONAL distinction.

## Table 1 — EDGE Outcome / Decision

The decision surface must expose the governed run values for:

- DES
- Market Trust score and band
- Directional Agreement
- Effective Conviction, using the frozen Phase 6 definition: `min(abs(DES)/100,1) * (Market Trust/100)`
- Bull / Base / Bear probabilities, normalized to exactly 100%
- Definitive forecast
- Expected price zone
- Forecast horizon
- Risk override status/code
- Decision Ladder
- BOT score/grade
- exactly one primary action / definitive recommendation
- execution controls (instrument, entry/zone, stop/invalidation, T1, T2, time exit, options contract fields when applicable)

The final recommendation remains declarative. Execution conditions do not turn it into a conditional menu.

## Table 2 — Institutional Drill-down

Each critical EDGE component is represented with no more than four user-facing columns:

- Component
- Score / Level
- Key Outcome
- Interpretation

The machine contract also carries `verification_status` for every drill-down row. Missing evidence is never inferred.

Allowed verification states:
`VERIFIED`, `NOT_VERIFIED`, `NOT_AVAILABLE`, `NOT_SCORABLE`, `N/A`.

## Efficacy

**OFFICIAL** metrics use CLOSED, scorable recommendations only.

**PROVISIONAL** checkpoint diagnostics may use captured D+1 through D+5 observations for still-open recommendations but must never overwrite official hit-rate, directional-accuracy, final forecast-accuracy, or other CLOSED-only metrics.

Zero official sample is rendered as N/A / 0 closed-scorable, never as 0%.

## Fail-closed rules

Publication is blocked if any of the following occurs:

- contract version is not `EDGE_STOCKS_V1_2`;
- standard table count is not exactly two;
- a mandatory decision field is missing;
- Bull + Base + Bear differs from 100 by more than 0.01;
- more than one primary action is emitted;
- required verification state is absent;
- a missing/unverified input is presented as verified;
- provisional efficacy is mixed into official efficacy;
- a presentation-layer change alters an analytical calculation.

## Versioning and compatibility

V1.1 remains a legacy contract. V1.2 is the canonical presentation contract for new standard EDGE Stocks outputs. Breaking presentation changes require a new contract version.

## Governance boundary

Google Drive `EDGE/01_Master_Specification/EDGE_V1_Master_Specification_CANONICAL.docx` remains the human-readable methodological source of truth. GitHub implements and tests this contract but must not silently redefine frozen EDGE methodology.
