# 3WT — Three-Weeks-Tight

## Name

3WT (Three-Weeks-Tight) breakout.

## Book references

- O'Neil, Gil 2010 — 3 tuần đóng cửa gần nhau, sau đó breakout.
- GIL_BOOK_CONDITIONS.md § III.7; BOOK_TEST_LADDER Block C2.

## Intent

Entry: weekly — 3 tuần close trong range chặt (< 3%), sau đó breakout (vd. close > max(high_last_3w)). Ít bar, phù hợp T+2.5.

## Inputs needed

- OHLCV **weekly**.
- close_last_3w, high_last_3w; range = max(close_last_3w) - min(close_last_3w).

## Binary logic (testable)

- `(max(close_last_3w) - min(close_last_3w)) / min(close_last_3w) < 0.03` (3% — adaptation).
- Breakout: e.g. `close_week > max(high_last_3w)` hoặc spec tương đương (pre-register).

## Default params

- 3% tight — adaptation (VN). Fee 30 bps, max 1 trade/week/symbol. Exit: MA10_week + weekly DD ≥ 3/10.

## Do NOTs

- Không tune % tight hay breakout definition sau khi thấy validation result.
- Không mix 3WT + PP trong cùng run trừ khi pre-registered (C3).

## Dependencies

- Market regime: ablation m0/m1/m2 (BOOK_TEST_LADDER § 7). Implement: `pp_backtest/signals_weekly.py`, `run_weekly.py --entry-3wt`.
