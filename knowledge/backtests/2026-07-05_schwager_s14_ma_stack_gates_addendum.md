# Gates Addendum: S14 MA Stack — locked IS diagnostics
# Written: 2026-07-05 (before OOS gate evaluation)
# Pre-reg: knowledge/backtests/2026-07-05_schwager_s14_ma_stack_prereg.md

## Baseline verification
- S1-filtered OOS MAR: **1.7844** (locked ref 1.7844)
- N_OOS: **1732**
- Baseline drift flag: **False**

## IS diagnostics (binary MA stack — no tunable threshold)
- IS evaluable S1 signals: **1269**
- IS MA-stack pass count: **171**
- IS pass rate: **13.48%**

## Locked OOS gate parameters
- G1a: MA-stack pool OOS MAR >= **1.85**
- G1b: MA-stack pool OOS MAR >= **0.516**
- G2: MA-stack MAR > non-stack MAR
- G3: N_OOS (MA-stack pool) >= **30**
- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE
- Sub-B N < 30: flag [SUB-B-THIN] only (not a gate fail)