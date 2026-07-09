# S15 FIP S2-Pool Backtest — Delta Report
Date: 2026-07-09
Pre-reg: knowledge/backtests/2026-07-09_S15reopen_FIP_S2pool_prereg.md
Baseline OOS MAR (locked): 0.8386

## Methodology
- FIP%: % of 52 weekly (5-bar) periods with positive return in 260-bar lookback.
- Cohort MAR: capital-sim on combo OR trade subsets (gate from A3_RS stack).
- Gate thresholds reference locked primary baseline 0.8386; pool ALL-S2-OOS MAR shown for context.

## Data
- OOS trades: 3353 (signal_date >= 2020-01-01)
- FIP-MISSING: 21 (excluded from H/L analysis)
- FIP-HIGH: 1282 | FIP-LOW: 1840 | FIP-SINGLE: 210
- FIP compute time: 5.2s

## MAR Results
| Cohort | N | CAGR | MaxDD | MAR |
|--------|---|------|-------|-----|
| ALL-S2-OOS | 3353 | 0.1449 | -0.0936 | 1.5477 |
| FIP-HIGH | 1282 | 0.2025 | -0.0728 | 2.7798 |
| FIP-LOW | 1840 | 0.1298 | -0.0931 | 1.3946 |
| FIP-HIGH sub-B (2023-2026) | 824 | 0.0514 | -0.0728 | 0.7051 |

## Gate Evaluation
| Gate | Threshold | FIP-HIGH Result | PASS/FAIL |
|------|-----------|-----------------|-----------|
| G1a | >= 0.8886 | 2.7798 | PASS |
| G1b | >= 0.4193 | 2.7798 | PASS |
| G2 | >= 0.50 (sub-B) | 0.7051 | PASS |
| G3 | FIP-HIGH > FIP-LOW | 2.7798 vs 1.3946 | PASS |

## VN-Specific Flags
- VN band flag: 93.1% of FIP-HIGH trades had >=1 limit-up/down day in lookback — **FLAG [VN-BAND-RISK]**
- S2/FIP tension: vol_mult vs FIP% correlation r=-0.158, p=0.0000 — **TENSION**

## Terminal State
**COMPLETED-SUCCESS**
Rationale: G1a PASS — FIP-HIGH OOS MAR meets entry-class threshold.

RESEARCH_ONLY_NOT_PRODUCTION
