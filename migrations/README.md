# Database migrations

Production migrations are applied to Neon only after testing on a temporary branch and explicit approval where required.

- `001_initial_schema.sql` — EDGE PostgreSQL schema v1
- `002_recommendation_immutability.sql` — prevents UPDATE/DELETE of committed recommendations

Never include credentials in migration files.
