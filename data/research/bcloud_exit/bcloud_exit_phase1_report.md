# B_cloud Phase 1 (Exit-Mode) — Research Report

**Generated:** 2026-07-08
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-08_bcloud_exit_program_prereg.md`
**Architecture:** B_cloud PRIMARY (EMA20/100, partial_tp baseline vs exit-mode variants)

## Baseline (B_cloud PRIMARY, partial_tp — recomputed this run)

- OOS MAR (2020-2026): **0.4698**
- Phase 1+2 program measured baseline: 0.4698 (MATCH)
- G1a threshold (binding): **0.5357** (= baseline + 0.06584962500721156)
- G1b threshold (advisory): **0.2349**

## Results by Exit Mode

| Exit mode | OOS MAR | Sub-A | Sub-B | Delta vs baseline | N_OOS | Verdict |
|-----------|---------|-------|-------|-------------------|-------|---------|
| **fixed_60** | 0.3956 | 0.6142 | 0.3764 | -0.0743 | 7445 | **FAIL** |
| **fixed_120** | 0.4204 | 1.3141 | 0.1323 | -0.0494 | 7445 | **FAIL** |
| **trail_only** | 0.0268 | 0.2294 | -0.1052 | -0.4430 | 7445 | **FAIL** |

## Detailed Results

### fixed_60 (fixed_hold, max_hold=60) — FAIL

| Metric | Baseline (partial_tp) | Candidate |
|--------|----------------------|-----------|
| Full MAR | — | 0.3241 |
| OOS MAR | 0.4698 | 0.3956 |
| OOS MaxDD | — | -42.6% |
| OOS CAGR | — | 16.8% |
| OOS sub-A MAR | — | 0.6142 |
| OOS sub-B MAR | — | 0.3764 |
| N_OOS | — | 7445 |
| Delta vs baseline | — | -0.0743 |

### fixed_120 (fixed_hold, max_hold=120) — FAIL

| Metric | Baseline (partial_tp) | Candidate |
|--------|----------------------|-----------|
| Full MAR | — | 0.3378 |
| OOS MAR | 0.4698 | 0.4204 |
| OOS MaxDD | — | -33.2% |
| OOS CAGR | — | 13.9% |
| OOS sub-A MAR | — | 1.3141 |
| OOS sub-B MAR | — | 0.1323 |
| N_OOS | — | 7445 |
| Delta vs baseline | — | -0.0494 |

### trail_only (trailing_2.5, max_hold=250) — FAIL

| Metric | Baseline (partial_tp) | Candidate |
|--------|----------------------|-----------|
| Full MAR | — | 0.0138 |
| OOS MAR | 0.4698 | 0.0268 |
| OOS MaxDD | — | -43.0% |
| OOS CAGR | — | 1.2% |
| OOS sub-A MAR | — | 0.2294 |
| OOS sub-B MAR | — | -0.1052 |
| N_OOS | — | 7445 |
| Delta vs baseline | — | -0.4430 |

## Phase 1->2 Advisory Gate

Required: best Phase 1 OOS MAR delta >= +0.200
Best achieved: -0.0494
Result: **FAIL -> CLOSED-NEGATIVE (exit-mode program ends)**

## Conclusion

No candidates ADVANCE G1a gate.
Best delta: -0.0494 vs Phase 1->2 advisory threshold of +0.200.

`RESEARCH_ONLY_NOT_PRODUCTION`