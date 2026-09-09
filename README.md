# EDGE V1

EDGE is the frozen individual-stock decision, execution and efficacy framework.

## Canonical architecture

- **Neon PostgreSQL** — canonical recommendation, outcome and efficacy database
- **Google Drive** — canonical EDGE V1 Master Specification and evidence archive
- **GitHub** — technical code, schema, migrations, tests and version history
- **SQLite** — offline/development/disaster-recovery fallback only

## Standard operating model

Upload current stock chart evidence (and option-chain/OI/premium evidence when an options decision is required), then invoke:

`EDGE — <STOCK>`

The analytical workflow uses only:
1. current user screenshots
2. fresh deep-web research

No continuous live-data feed is required.

## Frozen output

Standard EDGE runs produce exactly two tables:
1. Outcome
2. Drill-down

## Security

Never commit:
- Neon passwords
- connection strings
- API keys
- tokens
- private user data

Model: EDGE V1  
Database schema: v1  
Status: Phase-13 implementation/validation
