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
