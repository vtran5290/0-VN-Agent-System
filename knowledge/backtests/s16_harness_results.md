# S16 Seasonality Month-Exclusion Harness Results

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_schwager_s16_seasonality_prereg.md`
**Gates addendum:** `knowledge/backtests/2026-07-05_schwager_s16_seasonality_gates_addendum.md`

**FINAL VERDICT:** DEGRADING-REJECT

S1 baseline OOS MAR: **1.7844** (locked 1.7844) | G1a floor: **1.82**

## Baseline verification
- S1-only OOS MAR: 1.7844 | N=1732 | drift=False

## IS phase — bad months (LOCKED before OOS)
- Bad months: **Aug (8), May (5)**

| Month | IS N | IS mean return |
|-------|------|----------------|
| Aug | 87 | -1.54% **BAD** |
| May | 112 | 2.92% **BAD** |
| Jun | 114 | 7.05% |
| Nov | 148 | 7.99% |
| Apr | 76 | 8.02% |
| Jul | 150 | 8.28% |
| Jan | 132 | 8.38% |
| Dec | 75 | 10.04% |
| Sep | 82 | 16.56% |
| Oct | 147 | 22.39% |
| Mar | 103 | 24.74% |
| Feb | 79 | 41.45% |

## OOS pools

| Pool | OOS MAR | OOS MaxDD | OOS CAGR | N_OOS |
|------|---------|-----------|----------|-------|
| Good months (10 months) | 1.5895 | -8.30% | 13.19% | 1432 |
| Bad months (excluded) | 0.2169 | -10.08% | 2.19% | 300 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | MAR >= 1.82 | FAIL |
| G1b | MAR >= 0.516 | PASS |
| G2 | good > bad (1.5895 vs 0.2169) | PASS |
| G3 | N_OOS >= 30 | PASS |

## Sub-window (good-months pool)
- Sub-A (2020-2022): MAR **4.3358**, N **525**
- Sub-B (2023-2026): MAR **0.7064**, N **907**

## OOS diagnostic — mean trade return by entry month

| Month | N | Mean return |
|-------|---|-------------|
| Jan | 164 | 5.17% |
| Feb | 175 | 6.06% |
| Mar | 195 | 4.83% |
| Apr | 85 | -4.01% |
| May | 191 | 1.95% (bad) |
| Jun | 208 | 32.55% |
| Jul | 173 | 8.38% |
| Aug | 109 | 9.18% (bad) |
| Sep | 111 | 58.08% |
| Oct | 69 | 8.34% |
| Nov | 98 | 20.11% |
| Dec | 154 | 43.04% |