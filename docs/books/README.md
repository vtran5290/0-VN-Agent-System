# Gil Morales — Book index (Brain for Cursor)

Hai sách Gil Morales (và Kacher) dùng làm **rule library + hypothesis generator**. Cursor dùng để encode rules thành spec testable, **không** để tự tìm combo tối ưu.

---

## Bước 1: Thêm nội dung sách (làm 1 lần)

Để Cursor search được, cần có text trong 2 file dưới:

| File | Nguồn |
|------|--------|
| [gil_2010_trade_like_oneil_disciple.md](gil_2010_trade_like_oneil_disciple.md) | Convert MOBI → MD hoặc paste chương |
| [gil_2012_trading_cockpit.md](gil_2012_trading_cockpit.md) | Convert EPUB → MD hoặc paste chương |

**Script (tự động, khi đã cài Calibre):** từ repo root:  
`.\scripts\convert_gil_books_to_md.ps1`  
Script đọc 2 file từ `c:\Users\LOLII\Downloads\` (tên dài Anna's Archive) và ghi ra `docs/books/gil_2010_*.md`, `gil_2012_*.md`. Nếu chưa cài Calibre, script in ra 2 lệnh để chạy tay sau khi cài.

**Calibre thủ công:**  
`ebook-convert "đường_dẫn/file.mobi" "docs/books/gil_2010_trade_like_oneil_disciple.md"`  
`ebook-convert "đường_dẫn/file.epub" "docs/books/gil_2012_trading_cockpit.md"`  

Sau đó workflow: extract rule → rule card → experiment planner → bạn chạy make → research auditor. Chi tiết: `docs/GIL_BRAIN_WORKFLOW.md`.

---

## Files

| File | Nội dung |
|------|----------|
| [gil_2010_trade_like_oneil_disciple.md](gil_2010_trade_like_oneil_disciple.md) | *Trade Like an O'Neil Disciple* (2010) — full text hoặc chương quan trọng |
| [gil_2012_trading_cockpit.md](gil_2012_trading_cockpit.md) | *In the Trading Cockpit* (2012) — full text hoặc chương quan trọng |
| [GIL_RULE_TAGS.md](GIL_RULE_TAGS.md) | Tag dictionary: PP, CPP, BGU, U&R, 3WT, extended, character change, FTD, distribution… |

---

## Cách dùng trong Cursor

1. **Search:** Ctrl+P hoặc Cmd+P → gõ cụm từ (vd. "buyable gap-up", "pocket pivot", "distribution cluster") → Cursor index từ 2 file markdown.
2. **Rule cards:** Khi extract rule, luôn trích **chương/section** từ sách; không invent. Dùng [GIL_RULE_TAGS.md](GIL_RULE_TAGS.md) làm vocabulary.
3. **Hypothesis:** Con người quyết định hypothesis; Cursor chỉ encode thành code/rulecard, không generate hypothesis mới.

---

## Chapter mapping (điền khi đã có full text)

### Gil 2010 — *Trade Like an O'Neil Disciple*

| Chương / Section | Keywords |
|------------------|----------|
| (điền khi có sách) | pocket pivot, buyable gap-up, undercut-and-rally, base, volume, MA |

### Gil 2012 — *In the Trading Cockpit*

| Chương / Section | Keywords |
|------------------|----------|
| (điền khi có sách) | distribution, follow-through, selling into strength, character change, extended |

---

## Mục lục / Keywords chung

- **Entry:** pocket pivot (PP), continuation pocket pivot (CPP), buyable gap-up (BGU), undercut-and-rally (U&R), three-weeks-tight (3WT).
- **Market:** follow-through day (FTD), distribution days, no new positions.
- **Pattern:** right-side-of-base, avoid extended, late-stage base.
- **Exit:** MA violation, character change, selling into strength, stop at BGU low.

Chi tiết tag → [GIL_RULE_TAGS.md](GIL_RULE_TAGS.md).
