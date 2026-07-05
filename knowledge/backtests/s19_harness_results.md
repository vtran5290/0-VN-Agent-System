# S19 Buy-Strongest Harness Results

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_schwager_s19_buy_strongest_prereg.md`

**FINAL VERDICT (primary C1):** MECHANISM-FAIL

S1 baseline OOS MAR: **1.7844** (locked 1.7844)
G1a floor (aggregate): **1.82**
IS leader-laggard spread: **0.0239** OK
G2 mechanism: **FAIL** — MECHANISM-FAIL: leader_mar=0.2848 laggard_mar=0.7012 spread=-0.0791 sectors_win=109
S1 overlap on leader picks: **100.0%** (HIGH-OVERLAP)

| Candidate | OOS MAR | N_OOS | G1a | G1b | G2 | Verdict |
|-----------|---------|-------|-----|-----|----|---------|
| C1_leader_only | 0.2848 | 253 | FAIL | FAIL | FAIL | MECHANISM-FAIL |
| C2_leader_weight | 1.4917 | 575 | FAIL | PASS | FAIL | MECHANISM-FAIL |
| C3_exclude_laggard | 0.3188 | 264 | FAIL | FAIL | FAIL | MECHANISM-FAIL |