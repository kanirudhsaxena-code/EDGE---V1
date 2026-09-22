# MDOS VNext specification binding — 22 Sep 2026

Status: IMPLEMENTATION BINDING / NON-PRODUCTION

This repository branch is governed by the approved additive VNext specification package. This binding authorizes implementation and validation only. It does not authorize a change to frozen production methodology, canonical selection, official efficacy, recommendation semantics, or trading execution.

## Accepted production baseline

- 5DR-V2 main: `4c04992e17a785c06c1d4d5c6a2df95af14d19c5`
- EDGE-CONSOLE main: `000e3ecd93712c525de4a19aac70337b3b58b67f`
- EDGE---V1 main: `cc6539832356ff0881388e5f23039fc23de76d5a`

## Approved Drive authorities

- MDOS Output, Learning Lab & Core Zone Amendment V1.0 — APPROVED FOR VNEXT BUILD — Drive ID `1lwqZEhZVCWOAH2mZ-YIDyGqTk6v7h112-vnogm3kyz4`
- MDOS Learning Lab Daily Output & Approval Governance V1.0 — APPROVED FOR VNEXT BUILD — Drive ID `1ooExDRSuFED7xLLNk1Wb2DlYeg3BDCtWW1LRsq1T1qw`
- MDOS Core Zone Master Specification V1.0 — APPROVED SHADOW DESIGN — Drive ID `1tRhB75r44OvhFlN4m1sWsTk4VrTLD1iTJZjTrIn1c0w`
- 5DR V2.2.3 - CANONICAL SPECIFICATION — Drive ID `1bXpByuaDvBSE8caviNxROOl5OhHraTHRo77FX6tw41U`
- 00 - EDGE Console Master Specification — Drive ID `154KpSBHfmRUEDlClnYZLA1iYjuAkSchIlDZMCw4pUQo`
- Market & Evidence Data Architecture - Master Specification V1.0 — Drive ID `1c3NbYZCIfi5LOuKBGxQDePuTdInnlJ45eV62Zjh3JPE`
- EDGE V1 Master Specification - Production Backbone Addendum — Drive ID `1QkdyzEFrQZQnyuxipYQvd5NkuWc3hq_sYvY7Bqg5SoE`

## VNext implementation invariants

1. Official efficacy stays canonical-only.
2. Learning evidence may include CANONICAL, DIAGNOSTIC, MANUAL and SHADOW runs, with explicit run-role metadata and target-date normalization.
3. Learning Lab failures never invalidate an otherwise valid production forecast.
4. User approval of a Learning Lab candidate authorizes governed build/validation only; production promotion is a separate explicit event.
5. Core Zone remains SHADOW until separately promoted.
6. PVPO Grid V1 is explanatory/read-model only until separately promoted.
7. Forecast payload completeness, assessment state and official-efficacy eligibility are separate states.
8. Exact-run report views are immutable and identified by a version and content hash.
9. Historical missing issuance-time evidence is never reconstructed as official forward evidence.
10. No branch in this workstream may place orders or enable trading execution.

## Build sequence

G3 — shared read-only/additive Learning Lab data model, observation ingestion, daily snapshots, hypotheses/challenger records and approval ledger.
G4 — Console Learning Lab overview/drill-down and stale/failure/approval UI.
G5 — EDGE Stocks D through D+4 forecast path.
G6 — Core Zone SHADOW implementation after engine annexes.
G7 — PVPO Grid V1 read model/rendering.
G8 — exact-run report view and Console/ChatGPT parity.
G9 — regression and non-disruption acceptance before any promotion.

## Repository role

EDGE Stocks remains the authority for stock analytical methodology. The existing autonomous learning cycle is evolved rather than duplicated. VNext changes initially enrich its immutable learning snapshot/handoff while EDGE_V1 scoring, Market Trust, BOT, recommendation ladder and execution rules remain frozen.
