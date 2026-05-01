# Path A regime_off Audit — Week ending 2026-03-20

## Summary

- Weekly date used: **2026-03-20**
- Daily benchmark date used for mapping: **2026-03-18**
- regime_ftd on that daily row: **False**
- no_new_positions on that daily row: **False**
- Exact reason regime_ftd is False: **VN30 close <= MA50 and MA50 slope <= 0**

## Weekly mapping proof

- `weekly_regime_from_daily(..., week_end='W-FRI')` takes the **last daily** value in the week bucket.
- For week ending **2026-03-20**, the last available VN30 daily row is **2026-03-18**.

## Concrete VN30 inputs on the mapped daily row

- VN30 close: 1868.84
- MA50: 1998.90
- MA50 slope (20d): -0.001436
- close > MA50: False
- MA50 slope > 0: False
- dist_days_last_10: 2.0

## Why this blocked all Champion buy executions

- Portfolio entry gate requires `regime_ftd=True` and `no_new_positions=False`.
- On 2026-03-18, `regime_ftd=False` and `no_new_positions=False`.
- Therefore **regime_off** rejected all otherwise-ranked candidates for that week.
