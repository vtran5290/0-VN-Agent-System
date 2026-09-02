# S17 Buy/Sell Flow Harness Results

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_schwager_s17_buysell_flow_prereg.md`
**Gates addendum:** `knowledge/backtests/2026-07-05_schwager_s17_gates_addendum.md`
**Source:** FireAnt REST `buyQuantity`/`sellQuantity` (method=REST API)
**Test design:** S1+S17 combined (re-scoped 2026-07-05 opus REDIRECT)
**Q2 verdict:** PASS
**FINAL VERDICT:** FAIL

S1 baseline OOS MAR: 1.7844 (locked 1.7844) | G1a floor: 1.85 | G1b: 0.516
S1-filtered IS signal days for P75: **1304**

## IS P75 thresholds (locked before OOS)

| Candidate | Window | IS P75 | n (S1 IS days w/ ratio) |
|-----------|--------|--------|-------------------------|
| C1_ratio1d | 1d | 1.1564 | 1300 |
| C2_ratio5d | 5d | 1.1543 | 1304 |
| C3_ratio20d | 20d | 1.1213 | 1304 |

## OOS gate results

| Candidate | OOS MAR | sub-A MAR | sub-B MAR | N_OOS | G1a | G1b | G2 | Verdict |
|-----------|---------|-----------|-----------|-------|-----|-----|----|---------|
| C1_ratio1d | 0.7752 | 1.7926 | 0.5544 | 307 | FAIL | PASS | PASS | FAIL |
| C2_ratio5d | 1.7533 | 3.9455 | 0.0976 | 271 | FAIL | PASS | PASS | FAIL |
| C3_ratio20d | 1.1525 | 2.3837 | 0.4359 | 201 | FAIL | PASS | PASS | FAIL |