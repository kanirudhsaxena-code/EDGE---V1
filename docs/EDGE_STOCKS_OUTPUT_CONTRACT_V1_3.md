# EDGE Stocks User-Facing Output Contract V1.3

Status: **CANONICAL PRESENTATION CONTRACT**  
Presentation semantics: **EFFICACY V2**  
Framework: EDGE V1 analytical core (unchanged)  
Contract version: `EDGE_STOCKS_V1_3`

## Authority and supersession

This contract supersedes `EDGE_STOCKS_V1_2` for every new standard `EDGE <stock/company/ticker>` output.

The Efficacy V2 presentation order is authoritative because it is the later master-spec amendment. The earlier two-table-only contract is retained only as historical audit material and must not be used for routing, rendering, validation, smoke testing, or production acceptance.

## Mandatory user-facing order

Every standard EDGE Stocks result must render exactly these four sections, in this order:

1. **EDGE MASTER ASSESSMENT**
2. **ACTIVE CALLS**
3. **CURRENT STOCK OUTCOME**
4. **DRILL-DOWN**

No presentation layer may collapse or reorder these sections without a separately approved new contract version.

## EDGE MASTER ASSESSMENT

Must surface system-wide and stock-level efficacy before the new stock outcome, including:
- tracked recommendations / stocks;
- OPEN vs CLOSED state;
- OFFICIAL scorable sample;
- OFFICIAL recommendation, directional, and target hit-rate fields;
- model gain/loss, MFE/MAE, and cumulative model P/L when scorable;
- PROVISIONAL D+1…D+5 checkpoint diagnostics;
- stock-specific provisional assessment.

OFFICIAL metrics use CLOSED/scorable recommendations only. PROVISIONAL checkpoints must never overwrite OFFICIAL efficacy. A zero official sample is N/A / 0 closed-scorable, never 0%.

## ACTIVE CALLS

Must precede the new stock outcome and expose the current governed active-call set, including ticker, immutable recommendation id, forecast/recommendation, current state, probabilities, price zone, and horizon/expiry where available.

## CURRENT STOCK OUTCOME

Must expose the governed current-run fields, including:
- immutable recommendation id;
- DES;
- Market Trust score/band;
- Directional Agreement;
- Effective Conviction;
- Bull / Base / Bear probabilities summing to 100% within 0.01;
- definitive forecast;
- expected price zone;
- forecast horizon;
- risk override;
- Decision Ladder;
- BOT score/grade;
- exactly one primary action;
- applicable execution controls.

## DRILL-DOWN

User-facing columns remain bounded to:
- Component
- Score / Level
- Key Outcome
- Interpretation

The machine contract additionally carries `verification_status`.

Allowed verification states:
`VERIFIED`, `NOT_VERIFIED`, `NOT_AVAILABLE`, `NOT_SCORABLE`, `N/A`.

For every `VERIFIED` component:
- **Key Outcome is mandatory.**
- **Interpretation is mandatory and must be evidence-grounded.**
- boilerplate such as “no additional interpretation recorded” or “component evidence retained in immutable audit record” is a publication blocker.
- interpretation must be derived only from the same governed evidence that produced the component result; no missing fact may be inferred.

For unverified or unavailable components, the output must explicitly state that evidence was not verified/available and must not infer an interpretation.

## Persistence invariant

Component-level `key_outcome` and `interpretation` must survive the full path:
interpreter → governed computation → immutable component audit row → production read model → renderer.

A VERIFIED component with missing semantic notes causes fail-closed publication validation.

## Acceptance invariant

Production acceptance requires semantic checks, not merely transport/schema checks:
- correct four-section order;
- assessment first;
- active calls before current stock outcome;
- probabilities valid;
- OFFICIAL/PROVISIONAL separation preserved;
- every VERIFIED drill-down row has meaningful interpretation;
- old V1.2 two-table output is rejected;
- live production smoke validates a fresh post-contract recommendation.

## Governance boundary

This is a presentation/persistence semantics correction only. It does **not** alter frozen EDGE V1 scoring, weights, DES, Market Trust, probabilities, BOT, Decision Ladder, execution rules, Efficacy calculation rules, historical recommendations, or Learning Lab governance.

Implementation checkpoints:
- EDGE V1 semantic persistence fix: `8d9c31789472e9176f2b986eb0cf6d8e0c3a86d0`
- EDGE Console V1.3 semantic enforcement: `523bffa6e65ae40e9e365777147753d1234f5014`
- Production semantic smoke: run `35379877461`
