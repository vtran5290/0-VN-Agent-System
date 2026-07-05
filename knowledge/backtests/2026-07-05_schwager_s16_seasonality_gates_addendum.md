# Gates Addendum: S16 Seasonality — IS month rankings (LOCKED)
# Written: 2026-07-05 (before OOS evaluation)
# Pre-reg: knowledge/backtests/2026-07-05_schwager_s16_seasonality_prereg.md

## Baseline verification
- S1-filtered OOS MAR: **1.7844** (locked ref 1.7844)
- N_OOS: **1732**
- Baseline drift flag: **False**

## IS mean trade return by entry month (window 2013–2019)

| Month | N (IS) | Mean return |
|-------|--------|-------------|
| Aug (8) | 87 | -1.54% |
| May (5) | 112 | 2.92% |
| Jun (6) | 114 | 7.05% |
| Nov (11) | 148 | 7.99% |
| Apr (4) | 76 | 8.02% |
| Jul (7) | 150 | 8.28% |
| Jan (1) | 132 | 8.38% |
| Dec (12) | 75 | 10.04% |
| Sep (9) | 82 | 16.56% |
| Oct (10) | 147 | 22.39% |
| Mar (3) | 103 | 24.74% |
| Feb (2) | 79 | 41.45% |

## LOCKED bad months (bottom K=2 by IS mean return)
- **Aug (8), May (5)**

## Locked OOS gate parameters
- G1a: good-months pool OOS MAR >= **1.82**
- G1b: good-months pool OOS MAR >= **0.516**
- G2: good-months MAR > bad-months MAR (OOS)
- G3: N_OOS (good months) >= **30**
- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE