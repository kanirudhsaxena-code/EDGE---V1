# EDGE V1 Technical Architecture

## Canonical systems
1. Neon PostgreSQL: structured system of record.
2. Google Drive: canonical master specification and evidence archive.
3. GitHub: technical implementation and version history.
4. SQLite: offline/development fallback.

The analytical methodology remains governed by the canonical EDGE V1 Master Specification in Google Drive. This repository must not silently redefine frozen methodology.

## Persistence rules
- Recommendations are immutable after commit.
- EDGE UPDATE creates a linked child recommendation.
- Outcomes never overwrite issuance data.
- Due checkpoints survive later runs.
- Model version is attached to every historical call.
- Aggregate efficacy is derived from underlying recommendation/outcome records.

## Evidence
Permitted run-time analytical inputs are current user screenshots and fresh deep-web research. Unverified facts remain Not Verified; missing evidence is not converted to neutral evidence.

## No live-feed dependency
EDGE is snapshot/run-on-command based. It does not claim knowledge of market changes between verified observations.

## EDGE Efficacy Engine V2 (approved 10 Sep 2026)

Every `EDGE <STOCK>` run is now a closed-loop assessment plus a new recommendation.
The mandatory visible order is:

1. EDGE Master Assessment across all tracked stocks.
2. Active Calls summary, one row per stock (latest call plus count of open calls).
3. Current Stock Outcome for the requested ticker.
4. Current Stock Drill-down.

Every new recommendation is immutable and has a maximum horizon of five trading days.
It is independently tracked until target, stop, explicit manual closure, or D+5 final evaluation.
All surviving recommendations are assessed on every later EDGE run when data is available.
Historical pre-V2 recommendations are never rewritten and may be excluded from V2 master metrics if their original horizon exceeds five days.

Efficacy is separated into forecast/recommendation accuracy, opportunity quality (MFE/MAE), model P/L, and actual-user P/L when the user confirms an executed trade. A standardized model-capital ledger is used for comparability, while `model_portfolio_positions` prevents more than one simultaneous simulated position per ticker so overlapping recommendations cannot artificially multiply portfolio exposure.
