# EDGE Stocks User-Facing Output Contract V1.3

Status: **CANONICAL PRESENTATION CONTRACT — G5 D:D+4 AMENDMENT**  
Presentation semantics: **EFFICACY V2**  
Framework: EDGE V1 analytical core (unchanged)  
Contract version: `EDGE_STOCKS_V1_3`

## Authority and supersession

This contract supersedes `EDGE_STOCKS_V1_2` for every new standard `EDGE <stock/company/ticker>` output.

The Efficacy V2 presentation order is authoritative because it is the later master-spec amendment. The earlier two-table-only contract is retained only as historical audit material and must not be used for routing, rendering, validation, smoke testing, or production acceptance.

The approved G5 horizon amendment is binding for all **new current EDGE Stocks forecasts**: the forecast path is exactly five ordered NSE trading sessions `D`, `D+1`, `D+2`, `D+3`, `D+4`. `D+5` is not part of a new current forecast path. Historical lifecycle/efficacy records may retain their immutable historical labels where required for audit, but they must not be used to render or validate a new current forecast.

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
- PROVISIONAL checkpoint diagnostics, preserving historical immutable labels where applicable;
- stock-specific provisional assessment.

OFFICIAL metrics use CLOSED/scorable recommendations only. PROVISIONAL checkpoints must never overwrite OFFICIAL efficacy. A zero official sample is N/A / 0 closed-scorable, never 0%.

## ACTIVE CALLS

Must precede the new stock outcome and expose the current governed active-call set, including ticker, immutable recommendation id, forecast/recommendation, current state, probabilities, price zone, and horizon/expiry where available.

For new current calls, horizon wording must be compatible with the canonical D:D+4 path and must not describe the current forecast as D+5.

## CURRENT STOCK OUTCOME

Must expose the governed current-run fields, including:
- immutable recommendation id;
- DES;
- Market Trust score/band;
- Directional Agreement;
- Effective Conviction;
- Bull / Base / Bear probabilities summing to 100% within 0.01;
- definitive forecast;
- expected aggregate price zone where governed;
- forecast horizon;
- **exactly five ordered day-wise forecast rows: `D`, `D+1`, `D+2`, `D+3`, `D+4`;**
- each row's governed NSE trading date;
- each row's governed direction;
- each row's governed expected price zone;
- each row's approved confidence/probability field(s), when produced by the frozen EDGE methodology;
- risk override;
- Decision Ladder;
- BOT score/grade;
- exactly one primary action;
- applicable execution controls.

### G5 day-wise forecast invariant

Publication of a new current EDGE Stocks result fails closed unless:
1. `forecast_path` contains exactly five rows;
2. row labels are exactly and only `D`, `D+1`, `D+2`, `D+3`, `D+4` in that order;
3. all five rows carry valid governed NSE trading dates;
4. `D` is the current governed forecast session;
5. no sixth `D+5` row exists;
6. day-wise values come only from the approved EDGE methodology and governed evidence; missing day-wise values must never be interpolated or invented by the Console or ChatGPT.

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

Component-level `key_outcome` and `interpretation`, plus all five G5 `forecast_path` rows, must survive the full path:
interpreter → governed computation → immutable persistence/audit row → production read model → renderer → governed Chat capture.

A VERIFIED component with missing semantic notes causes fail-closed publication validation. A new current forecast with missing, reordered, duplicated, extra, or reconstructed forecast-path rows also causes fail-closed publication validation.

## ChatGPT presentation invariant

For a standard `EDGE <ticker>` request, the live EDGE Console is the presentation source of truth. ChatGPT must not independently reconstruct or reformat the canonical EDGE result. The governed Chat path is:

`RUN → CONSOLE → CAPTURE → VALIDATE → DISPLAY`

If the five D:D+4 rows or any mandatory section cannot be captured from the governed Console presentation, the Chat run fails closed rather than synthesizing missing values.

## Acceptance invariant

Production acceptance requires semantic checks, not merely transport/schema checks:
- correct four-section order;
- assessment first;
- active calls before current stock outcome;
- probabilities valid;
- OFFICIAL/PROVISIONAL separation preserved;
- every VERIFIED drill-down row has meaningful interpretation;
- exactly five ordered D:D+4 current forecast rows exist end-to-end;
- current D+5 forecast semantics are rejected;
- old V1.2 two-table output is rejected;
- live production smoke validates a fresh post-contract recommendation;
- LTF and CUPID targeted regression cases pass without methodology drift;
- Console and governed Chat presentation preserve the same mandatory canonical fields.

## Governance boundary

This is a forecast-horizon/output/persistence semantics correction only. It does **not** alter frozen EDGE V1 scoring, weights, DES, Market Trust, probabilities, BOT, Decision Ladder, execution rules, Efficacy calculation rules, historical recommendations, or Learning Lab governance.

Implementation checkpoints from prior V1.3 remain historical evidence:
- EDGE V1 semantic persistence fix: `8d9c31789472e9176f2b986eb0cf6d8e0c3a86d0`
- EDGE Console V1.3 semantic enforcement: `523bffa6e65ae40e9e365777147753d1234f5014`
- Production semantic smoke: run `35379877461`

G5 acceptance requires a new post-amendment production proof before the production release manifest may be updated.
