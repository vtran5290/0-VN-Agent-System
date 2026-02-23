# U&R — Undercut-and-Rally

## Name

U&R (Undercut-and-Rally).

## Book references

- Gil 2010 — Break prior low rồi reverse, volume confirmation.
- GIL_BOOK_CONDITIONS.md § II.5: shakeout + reversal, close high in range, volume > prior N days.

## Intent

Entry: break low intraday, close high in range, volume tăng vs prior days. Đã test mechanical → holdout PF < 1.0; ưu tiên weekly/3WT hơn.

## Inputs needed

- Daily: low vs prior low, close position in range, volume vs prior N days.

## Binary logic (testable)

- Undercut prior low + close in upper % of range + volume > prior N days (pre-register N).

## Default params

- Adaptation: N days, % range — ghi rõ nếu không có trong sách. Exit: fixed 5 bars (historical test).

## Do NOTs

- Không thêm condition để "cứu" sau khi fail holdout. Escape hatch: pivot sang weekly/3WT (BOOK_TEST_LADDER § 4).

## Dependencies

- Implement: `pp_backtest/signals.py` (entry_undercut_rally). Hiện không ưu tiên test thêm cho VN.
