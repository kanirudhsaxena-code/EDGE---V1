# G5 D:D+4 Critical Path — 30 Sep 2026

Status: IMPLEMENTATION IN PROGRESS

## Outcome
A standard EDGE Stocks run must publish exactly five ordered NSE trading-session forecast rows: D, D+1, D+2, D+3, D+4. D+5 is not part of a new current forecast. Frozen EDGE_V1 methodology remains unchanged.

## Sequence
1. Bind output contract.
2. Include D in canonical forecast calendar and append next four valid NSE sessions.
3. Add five-row governed forecast payload.
4. Persist/read back rows immutably.
5. Hand off to EDGE Console renderer and governed Chat capture.
6. Run LTF and CUPID targeted regression.
7. Promote only after fresh governed end-to-end proof.

## Frozen boundaries
No change to scoring, weights, probabilities, DES, Market Trust, BOT, Decision Ladder, execution rules, canonical selection, efficacy rules, or historical recommendations.

## Acceptance checklist
- [x] Canonical calendar helper added for D:D+4.
- [x] Calendar regression excludes D+5.
- [x] User-facing contract amended to require D:D+4.
- [ ] Engine payload carries exactly five day-wise rows.
- [ ] Persistence/readback preserves the five rows.
- [ ] LTF regression passes.
- [ ] CUPID regression passes.
- [ ] Fresh production proof passes.
