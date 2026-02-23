# AVOID_EXTENDED — Avoid buying when extended

## Name

Avoid extended (không mua khi extended quá xa MA).

## Book references

- Gil 2012 — Không mua khi extended quá xa MA10/20.
- GIL_BOOK_CONDITIONS.md § V.12.

## Intent

Filter: loại bỏ entry khi price đã chạy xa MA10/20 (tránh mua đỉnh).

## Inputs needed

- close, MA10 (daily hoặc weekly tùy timeframe).
- distance_from_MA10 = (close - MA10) / MA10.

## Binary logic (testable)

- Chỉ cho entry khi `distance_from_MA10 < X%` (X pre-register; sách không luôn ghi số → **adaptation**).
- Ví dụ: < 5% (adaptation VN).

## Default params

- 5% — **adaptation** (ghi rõ trong rule card). Không tune sau khi thấy số.

## Do NOTs

- Không thêm MA khác (MA30, MA60) để "refine". Không dùng filter này để cứu model fail — chỉ test trên "best weekly" đã chọn (Block D).

## Dependencies

- Chỉ bật sau khi đã có best weekly (C1/C2/C3). BOOK_TEST_LADDER Block D2. Implement: pattern filter trong `run_weekly.py` / signals.
