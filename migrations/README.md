# Database migrations

Production migrations are applied to Neon only after testing on a temporary branch and explicit approval where required.

- `001_initial_schema.sql` — EDGE PostgreSQL schema v1
- `002_recommendation_immutability.sql` — prevents UPDATE/DELETE of committed recommendations

Never include credentials in migration files.

- `009_anytime_invocation_governance.sql` — G5.1 adds USER_CANONICAL_SNAPSHOT classification and separate all-run efficacy views while preserving benchmark selection semantics
