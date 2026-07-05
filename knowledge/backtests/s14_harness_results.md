# S14 Minervini MA Stack Harness Results

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_schwager_s14_ma_stack_prereg.md`
**Gates addendum:** `knowledge/backtests/2026-07-05_schwager_s14_ma_stack_gates_addendum.md`

**FINAL VERDICT:** DEGRADING-REJECT

S1 baseline OOS MAR: **1.7844** (locked 1.7844) | G1a floor: **1.85**

## Baseline verification
- S1-only OOS MAR: 1.7844 | N=1732 | drift=False

## Pool sizes (OOS trades)
- MA-stack pool (criteria 1-6 pass): **262**
- Non-stack pool (removed): **1467**

## OOS gate results

| Arm | OOS MAR | OOS MaxDD | OOS CAGR | N_OOS |
|-----|---------|-----------|----------|-------|
| MA-stack | 0.4517 | -18.81% | 8.50% | 262 |
| Non-stack | 1.6211 | -7.58% | 12.29% | 1467 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | MAR >= 1.85 | FAIL |
| G1b | MAR >= 0.516 | FAIL |
| G2 | stack > non-stack (0.4517 vs 1.6211) | FAIL |
| G3 | N_OOS >= 30 | PASS |

## Sub-window (MA-stack pool)
- Sub-A (2020-2022): MAR **2.6615**, N **163**
- Sub-B (2023-2026): MAR **-0.0872**, N **99**