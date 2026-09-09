# EDGE database schema

Canonical production database: Neon PostgreSQL, database `edge`.

Schema v1 contains:
- runs
- immutable recommendations
- evidence and recommendation/evidence links
- component scores
- Market Trust
- BOT / Decision Ladder
- execution plans
- outcome checkpoints
- efficacy
- failure codes
- model versions
- change log

The executable schema is maintained in `migrations/001_initial_schema.sql`.
