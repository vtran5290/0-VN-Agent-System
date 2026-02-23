# [Rule Name] — Rule card template

Mỗi rule card **bắt buộc** có các mục dưới. Copy template này khi tạo card mới từ sách.

---

## Name

(Tên rule, trùng với tag trong GIL_RULE_TAGS.md)

## Book references

- **Chỉ** chương/section; không cần quote dài.
- Ví dụ: "Gil 2010, Ch 5 — Pocket Pivot"; "Gil 2012, Ch 3 — Distribution".

## Intent

(Mục đích: entry / exit / filter / market context; 1–2 câu.)

## Inputs needed

- OHLCV: daily / weekly.
- MA: MA10, MA50, slope (nếu cần).
- Volume: avg, down_volume, volume_week.
- Khác: gap_percent, range, dist_days…

## Binary logic (testable)

- Điều kiện TRUE/FALSE rõ ràng, không mơ hồ.
- Ví dụ: `volume_week > max(down_volume_last_10w)` AND `close_week > MA10_week`.

## Default params

- Nếu sách **có** số: ghi rõ (vd. gap > 3%, volume > 1.5× avg).
- Nếu sách **không** có số: ghi **"adaptation"** và lý do (vd. "3% gap — adaptation for VN volatility").

## Do NOTs

- Tránh curve-fit: không thêm MA/ngưỡng không có trong sách.
- Không mix rule này với rule khác trong cùng 1 experiment (trừ khi pre-registered combo).

## Dependencies

- Rule nào phải có trước (vd. CPP requires uptrend established).
- Code path: file/function nào implement (vd. `signals_weekly.py`, `market_regime.py`).
