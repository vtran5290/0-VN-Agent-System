# PA-011 — PM-C >=5x avg Exit-Class OOS Harness

**Generated:** 2026-07-09
**Pre-reg:** `knowledge/backtests/2026-07-09_pa011_pmc_exit_prereg.md`
**Baseline repro:** `data/research/cortex_pa010_pa011_combined/baseline_repro.json`

## Baseline reference

| Metric | Value |
|--------|-------|
| OOS MAR | 2.5193 |
| OOS MaxDD | -0.0557 |
| OOS CAGR | 0.1403 |
| sub-A MAR | 4.4083 |
| sub-B MAR | 1.1254 |

## Two-leg accounting

| Leg | N | Share |
|-----|---|-------|
| Leg A (overlay exit) | 2184 | 92.0% |
| Leg B (passthrough) | 191 | 8.0% |
| Median fire day (Leg A) | 11 | — |

### Fire-day histogram (Leg A)

| Bucket | Count |
|--------|-------|
| fire_day ≤ 3 | 194 |
| fire_day ≥ 10 | 1244 |

## OOS metrics (combined Leg A + Leg B)

| Metric | Overlay | Baseline | Delta |
|--------|---------|----------|-------|
| OOS MAR | 0.3082 | 2.5193 | -2.2111 |
| OOS MaxDD | -0.1900 | -0.0557 | -0.1343 |
| OOS CAGR | 0.0586 | 0.1403 | -0.0817 |
| sub-A MAR | 2.8708 | 4.4083 | -1.5374 |
| sub-B MAR | -0.1093 | 1.1254 | -1.2348 |

## Exit-class dual gate

| Gate | Threshold | Value | Result |
|------|-----------|-------|--------|
| OOS MAR | 2.1448 | 0.3082 | FAIL |
| OOS MaxDD | -0.0334 | -0.1900 | FAIL |
| OOS CAGR | 0.0000 | 0.0586 | PASS |
| sub-A MAR | 0.0000 | 2.8708 | PASS |
| sub-B MAR | 0.0000 | -0.1093 | FAIL |

## Overall status: **PARKED [ADVERSE-REVERSAL]**

### Root-cause note

Gate failure: G1a, G1b, G1d_sub_b; MaxDD -0.1900 worse than baseline -0.0557

RESEARCH_ONLY_NOT_PRODUCTION
