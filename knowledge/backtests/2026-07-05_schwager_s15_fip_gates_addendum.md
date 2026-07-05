# Gates Addendum: S15 FIP — locked IS diagnostics
# Written: 2026-07-05 (before OOS evaluation)
# Pre-reg: knowledge/backtests/2026-07-05_schwager_s15_fip_quality_prereg.md

## Baseline verification
- S1-filtered OOS MAR: **1.7844** (locked ref 1.7844)
- N_OOS: **1732**
- Baseline drift flag: **False**

## IS FIP distribution (S1-filtered IS pool, LOOKBACK=252)
- IS signals with valid FIP: **1256**
- IS FIP P25: **-0.0397**
- IS FIP P50 (median): **-0.0079**
- IS FIP P75: **0.0238**

## Locked split method (pre-reg)
- Per **signal_date**: rank candidates by FIP ascending; keep **bottom 50%** (most negative = quality).
- IS P50 is diagnostic only — **not** used as a universal cutoff.

## Locked OOS gate parameters
- G1a: quality-half OOS MAR >= **1.844**
- G1b: quality-half OOS MAR >= **0.516**
- G2: quality-half MAR > lottery-half MAR
- G3: N_OOS (quality half) >= **30**
- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE