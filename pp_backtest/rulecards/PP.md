# PP — Pocket Pivot (Weekly)

## Name

PP (Pocket Pivot) — weekly timeframe.

## Book references

- Gil 2010, Gil 2012 — Pocket Pivot off 10-week MA.
- GIL_BOOK_CONDITIONS.md § III.8; BOOK_TEST_LADDER Block C1.

## Intent

Entry: volume surge off support (MA10_week), close above MA10_week; weekly bars để giảm noise và phù hợp T+2.5 VN.

## Inputs needed

- OHLCV **weekly**.
- MA10_week, MA50_week (optional gate).
- volume_week, down_volume last 10 weeks.

## Binary logic (testable)

- `volume_week > max(down_volume_last_10w)` AND `close_week > MA10_week`.
- Optional: `close_week > MA50_week` (above-MA50 gate).

## Default params

- Down volume: max of down-volume over last 10 weeks (sách).
- Fee: 30 bps (pre-registered). Max 1 trade/week/symbol.

## Do NOTs

- Không thêm MA khác (MA20, MA30…) nếu sách không nói.
- Không tune threshold sau khi thấy kết quả.

## Dependencies

- Market regime (FTD-style, no_new_positions) thường bật khi test book — xem MARKET_CONTEXT.md.
- Implement: `pp_backtest/signals_weekly.py`, `run_weekly.py`.
