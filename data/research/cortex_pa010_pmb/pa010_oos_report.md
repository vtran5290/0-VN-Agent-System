# PA-010 — PM-B >=8% Exit-Class OOS Harness

**Generated:** 2026-07-09
**Pre-reg:** `knowledge/backtests/2026-07-09_pa010_pmb_exit_prereg.md`
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
| Leg A (overlay exit) | 673 | 28.3% |
| Leg B (passthrough) | 1702 | 71.7% |
| Median fire day (Leg A) | 33 | — |

### Fire-day histogram (Leg A)

| Bucket | Count |
|--------|-------|
| fire_day ≤ 3 | 64 |
| fire_day ≥ 10 | 502 |

## OOS metrics (combined Leg A + Leg B)

| Metric | Overlay | Baseline | Delta |
|--------|---------|----------|-------|
| OOS MAR | 0.6236 | 2.5193 | -1.8957 |
| OOS MaxDD | -0.1493 | -0.0557 | -0.0936 |
| OOS CAGR | 0.0931 | 0.1403 | -0.0472 |
| sub-A MAR | 1.0940 | 4.4083 | -3.3142 |
| sub-B MAR | 0.4620 | 1.1254 | -0.6634 |

## Exit-class dual gate

| Gate | Threshold | Value | Result |
|------|-----------|-------|--------|
| OOS MAR | 2.1448 | 0.6236 | FAIL |
| OOS MaxDD | -0.0334 | -0.1493 | FAIL |
| OOS CAGR | 0.0000 | 0.0931 | PASS |
| sub-A MAR | 0.0000 | 1.0940 | PASS |
| sub-B MAR | 0.0000 | 0.4620 | PASS |

## Overall status: **PARKED [ADVERSE-REVERSAL]**

### Root-cause note

Gate failure: G1a, G1b; MaxDD -0.1493 worse than baseline -0.0557

RESEARCH_ONLY_NOT_PRODUCTION
