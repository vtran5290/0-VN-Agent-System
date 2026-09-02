# Cortex Book #2 — S1+S2 Interaction Test

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_cortex_book2_s1s2_interaction_prereg.md`
**Combined filter:** prox >= 0.85 (within_15pct) AND vol >= 1.4×

**VERDICT: DEGRADING-REJECT**

## Reference baselines

| Baseline | Full MAR | OOS MAR | N OOS | Sub-B MAR |
|----------|----------|---------|-------|-----------|
| A3_RS raw | 0.5321 | 0.8386 | 4889 | — |
| S1 standalone | 1.4435 | 1.7844 | 1732 | 0.5465 |

## Combined candidate metrics

- Full MAR: **0.5445**
- OOS MAR: **0.5821**
- OOS MaxDD: **-19.38%**
- OOS CAGR: **11.28%**
- N trades (full): **1503**
- N trades (OOS): **894**
- N trades (OOS sub-A): **318**
- N trades (OOS sub-B): **576**
- OOS sub-A MAR: **1.4937**
- OOS sub-B MAR: **0.4244**

## Locked gates

- G_ia: combined OOS MAR >= **1.8344**
- G_ib: combined OOS MAR >= **0.516**
- G_full: combined Full MAR >= **1.3935**

| Gate | Criterion | Pass |
|------|-----------|------|
| G_ia | combined OOS MAR >= 1.8344 (S1 + 0.050) | FAIL ✗ |
| G_ib | combined OOS MAR >= 0.516 | PASS ✓ |
| G_full | combined Full MAR >= 1.3935 (S1 Full − 0.050) | FAIL ✗ |
| N_OOS_full | >= 30 trades full OOS | PASS ✓ |
| N_OOS_sub_A | >= 12 trades sub-A (2020, 2022) | PASS ✓ |
| N_OOS_sub_B | >= 12 trades sub-B (2023, 2026) | PASS ✓ |
| Neg-OOS-cap | S1 baseline and combined OOS MAR positive | PASS ✓ |

## Mechanism checks

- **M1 Fire count:** 51.6% of S1 OOS signals remain (894/1732 S1 OOS trades)
- **M2 Marginal contribution:** OOS MAR delta vs S1 = -1.2023 (need >= 0.010 for meaningful add)
- **M3 Sub-B:** combined 0.4244 vs S1 baseline 0.5465 — volume filter does not raise S1 sub-B
- **M4 Monotonicity:** combined Full MAR 0.5445 vs S1 1.4435 — G_full FAIL

## Notes
- Filters on signal bar; entry T+1 open. Same realism as S1/S2 standalone.
- RESEARCH_ONLY_NOT_PRODUCTION
