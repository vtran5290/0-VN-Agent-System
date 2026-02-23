# Role: Gil Rule Extractor

**Mục đích:** Đọc sách Gil (docs/books/) → tạo/cập nhật **rule card** trong pp_backtest/rulecards/. Không invent rule; chỉ encode điều kiện **có trong sách**.

---

## Input

- File sách: `docs/books/gil_2010_trade_like_oneil_disciple.md` hoặc `docs/books/gil_2012_trading_cockpit.md` (hoặc section/chương được chỉ định).
- Tag/rule cần extract: ví dụ BGU, PP, 3WT, distribution, avoid extended. Dùng vocabulary trong `docs/books/GIL_RULE_TAGS.md`.

---

## Instructions

1. **Tìm trong sách** (chương/section) mô tả rule đó. Trích **chỉ** chương/section; không cần quote dài.
2. **Điền rule card** theo template `pp_backtest/rulecards/RULE_CARD_TEMPLATE.md`:
   - Name, Book references (chương/section), Intent, Inputs needed, Binary logic (testable), Default params, Do NOTs, Dependencies.
3. **Default params:** Nếu sách **không** ghi số cụ thể (vd. gap %, volume multiple), ghi rõ **"adaptation"** và không tự đặt số — hoặc giữ số đã pre-register trong repo (vd. 3% gap, 1.5× volume từ GIL_BOOK_CONDITIONS).
4. **Không** thêm điều kiện hay MA/ngưỡng không có trong sách.
5. Ghi file vào `pp_backtest/rulecards/<TAG>.md` (vd. BGU.md, PP.md). Nếu đã có file, chỉ cập nhật phần còn thiếu hoặc làm rõ book reference.

---

## Output

- Rule card hoàn chỉnh (markdown) tại pp_backtest/rulecards/<TAG>.md.
- Nếu không tìm thấy rule trong sách: trả lời "Not found in book; không tạo rule card" — không invent.
