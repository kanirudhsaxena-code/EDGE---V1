# EDGE V1

EDGE is a decision and efficacy framework for individual-stock analysis.

## Architecture

- **Neon PostgreSQL** — canonical structured database and recommendation history
- **Google Drive** — canonical EDGE Master Specification and evidence archive
- **GitHub** — code, schema, migrations, tests and version history
- **SQLite** — offline/development fallback

## EDGE Efficacy Engine V2

Every `EDGE <STOCK>` run follows a closed-loop process:

1. EDGE Master Assessment across all tracked stocks
2. Active Calls summary
3. Current Stock Outcome
4. Current Stock Drill-down

Every new recommendation:

- has a maximum horizon of **5 trading days**
- receives an immutable recommendation ID
- is tracked through D+1 to D+5
- is assessed on subsequent EDGE runs
- closes on target, stop, explicit exit, or D+5
- records MFE and MAE
- contributes to stock-level and overall efficacy
- keeps forecast accuracy separate from execution accuracy

## Performance Tracking

EDGE tracks:

- Recommendation Hit Rate
- Direction Hit Rate
- Target Hit Rate
- Average Gain / Loss
- Maximum Favourable Excursion (MFE)
- Maximum Adverse Excursion (MAE)
- Model P/L
- Potential P/L
- Actual User P/L when an executed trade is confirmed
- Cumulative standardized portfolio performance

Historical pre-V2 recommendations remain immutable and are not retrospectively converted into D+5 recommendations.

## Governance

The analytical methodology is governed by the canonical **EDGE V1 Master Specification** stored in Google Drive.

GitHub contains the technical implementation and must not silently redefine frozen EDGE methodology.

Missing or unverified evidence must never be fabricated.


## Canonical User-Facing Output Contract

All new standard `EDGE <stock/company/ticker>` outputs use `EDGE_STOCKS_V1_2`.

The presentation contract is defined in `docs/EDGE_STOCKS_OUTPUT_CONTRACT_V1_2.md` and is presentation/governance only. It does not alter the frozen EDGE V1 analytical core.

A standard EDGE run must:
- render exactly two standard tables: Outcome / Decision, then Institutional Drill-down;
- expose DES, Market Trust, Directional Agreement, frozen Effective Conviction, Bull/Base/Bear probabilities, definitive forecast, expected zone, horizon, risk override, Decision Ladder/BOT and one governed primary action;
- keep OFFICIAL closed/scorable efficacy separate from PROVISIONAL D+1 to D+5 checkpoint diagnostics;
- display missing evidence as Not Verified / Not Available / Not Scorable rather than infer it;
- fail closed if the contract is incomplete.
