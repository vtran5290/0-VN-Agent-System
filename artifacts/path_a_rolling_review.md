# Path A Rolling Config Review — Champion vs Challenger

- Champion: ranking_mode=extension_first, max_positions=8
- Challenger: ranking_mode=simple_composite, max_positions=12
- Windows from 2022-01-01 to 2026-02-21, 6m and 12m, step=quarterly.

## 6m windows — MAR win counts

- Windows where **Champion** MAR > Challenger MAR: 4
- Windows where **Challenger** MAR > Champion MAR: 9

## 12m windows — MAR win counts

- Windows where **Champion** MAR > Challenger MAR: 7
- Windows where **Challenger** MAR > Champion MAR: 8

## Average MAR by config — 6m windows

- champion: mean MAR=2.0276
- challenger: mean MAR=5.8427

## Average MAR by config — 12m windows

- champion: mean MAR=1.1858
- challenger: mean MAR=3.0073

## Average chosen_rate and rejected_max_positions by config (all windows)

- champion: mean chosen_rate=0.03322, mean rejected_max_positions=490.9
- challenger: mean chosen_rate=0.03437, mean rejected_max_positions=159.5

## Promotion rule (for future decisions)

- **Rule:** Only review switching the default to Challenger if, in the rolling review, Challenger beats Champion on MAR in at least **60% of the last 10 rolling windows** and does **not** materially worsen MDD (no more than 5 percentage points deeper on average).

## Conclusion

- **Challenger deserves formal baseline review:** Challenger shows higher mean MAR in both 6m and 12m rolling windows; apply the promotion rule and reassess in more detail.
