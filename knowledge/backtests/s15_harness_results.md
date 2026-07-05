# S15 FIP Quality Momentum Harness Results

**Generated:** 2026-07-05
**Research label:** RESEARCH_ONLY_NOT_PRODUCTION
**Pre-registration:** `knowledge/backtests/2026-07-05_schwager_s15_fip_quality_prereg.md`
**Gates addendum:** `knowledge/backtests/2026-07-05_schwager_s15_fip_gates_addendum.md`

**FINAL VERDICT:** DEGRADING-REJECT

S1 baseline OOS MAR: **1.7844** (locked 1.7844) | G1a floor: **1.844**

## Baseline verification
- S1-only OOS MAR: 1.7844 | N=1732 | drift=False

## IS FIP threshold (locked before OOS)
- IS FIP P50 (median): **-0.0079** | P25=-0.0397 | P75=0.0238
- Split: per signal_date bottom 50% FIP (quality half)

## OOS gate results (quality half vs lottery half)

| Arm | OOS MAR | OOS MaxDD | OOS CAGR | N_OOS |
|-----|---------|-----------|----------|-------|
| Quality (bottom 50% FIP) | 1.1275 | -9.45% | 10.65% | 943 |
| Lottery (top 50% FIP) | 0.6468 | -14.97% | 9.68% | 785 |

| Gate | Criterion | Pass |
|------|-----------|------|
| G1a | MAR >= 1.844 | FAIL |
| G1b | MAR >= 0.516 | PASS |
| G2 | quality MAR > lottery MAR (1.1275 vs 0.6468) | PASS |
| G3 | N_OOS >= 30 | PASS |

## Sub-window (quality half)
- Sub-A (2020-2022): **1.7217**
- Sub-B (2023-2026): **0.7711**
- **[REGIME-SPLIT]** sub-B MAR materially below sub-A (>2× ratio)