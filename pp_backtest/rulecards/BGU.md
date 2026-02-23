# BGU — Buyable Gap-Up

## Name

BGU (Buyable Gap-Up).

## Book references

- Gil 2010, 2012 — Gap up mạnh, volume lớn, mua trong gap range. Stop ở low của gap day.
- GIL_BOOK_CONDITIONS.md § III.6; BOOK_TEST_LADDER Block B1a.

## Intent

Entry: gap up đủ lớn + volume confirmation; stop at gap day low. Có thể phù hợp VN thrust hơn PP pullback; occurrence có thể hiếm.

## Inputs needed

- Daily: open, prior close, volume, avg_volume.
- gap_percent = (open - prior_close) / prior_close * 100.

## Binary logic (testable)

- `gap_percent > 3%` AND `volume > 1.5 * avg_volume` (adaptation: sách không luôn ghi số).
- Entry trong gap range (execution: VN T+2.5/ATC — có thể hiếm).

## Default params

- 3% gap, 1.5× volume — **adaptation** (VN). Exit: fixed 10 bars (B1a) hoặc stop at BGU low (B1b).

## Do NOTs

- Không tune gap% hay volume multiple sau khi thấy PF.
- Không thêm filter ngoài sách trong cùng experiment.

## Dependencies

- Book regime (market context) khi test: `--book-regime`. Implement: `pp_backtest/signals.py` (entry_bgu), `run.py`.
