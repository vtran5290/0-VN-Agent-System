# Parallel Paths Plan

## Path A (current)
- Weekly pivot / accumulation: weekly_pp on weekly bars, weekly EMA21/MA50/MA10.
- Signal -> next week open execution.
- Same risk framework: VND, fees, regime, liquidity cap, PIT eligibility.

## Path B
- True daily Pocket Pivot (signals.pocket_pivot on daily OHLCV).
- Trend: EMA21_daily > MA50_daily. Exit: close < EMA21 or < MA50 or EMA21 cross below MA50.
- Entry/exit at next day open. Same risk framework as Path A.
