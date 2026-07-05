# Gates Addendum: S18 — locked IS diagnostics
# Written: 2026-07-05 (before OOS run)
# Pre-reg: knowledge/backtests/2026-07-05_schwager_s18_sector_persistence_prereg.md

## Baseline verification
- S1-filtered OOS MAR: **1.7844** (locked ref 1.7844)
- N_OOS: **1732**
- Baseline drift flag: **False**

## Locked rolling window
- **N=20** (candidates C1/C2 use N=20; N=60 IS diagnostics recorded for reference)

## IS diagnostics

| Roll | Candidate | IS persistence | IS trigger n | IS fire rate |
|------|-----------|----------------|--------------|--------------|
| 20 | C2_thresh075 | 55.6% | 3248 | 23.3% |
| 20 | C1_thresh100 | 55.8% | 2303 | 16.5% |
| 60 | C2_thresh075 | 55.5% | 3072 | 22.0% |
| 60 | C1_thresh100 | 55.8% | 2113 | 15.1% |

## Locked OOS gate parameters (pre-reg)
- G1a: OOS MAR >= **1.844**
- G1b: OOS MAR >= **0.516**
- G2 continuation: OOS >= **55%**
- G3: N_OOS >= **30**
- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE (requires pre-registered follow-up)