# Gil Brain — Workflow 4 bước (Knowledge → Rule cards → Experiment)

Cursor dùng 2 sách Gil làm **rule library**. Hypothesis **do bạn quyết định**; Cursor chỉ encode thành code/rulecard.

---

## Bước 1 — Thêm nội dung sách (bạn làm 1 lần)

- **File cần điền:**  
  `docs/books/gil_2010_trade_like_oneil_disciple.md`  
  `docs/books/gil_2012_trading_cockpit.md`
- **Cách:** Convert MOBI/EPUB → Markdown (Calibre: `ebook-convert <path.mobi> <path.md>`) hoặc copy/paste chương quan trọng vào 2 file trên.
- Sau khi có text, Cursor search (Ctrl+P) mới tìm được "pocket pivot", "buyable gap-up", "distribution cluster", v.v.

---

## Bước 2 — Extract / cập nhật rule cards

- **Prompt:** Mở `prompts/gil_rule_extractor.md`, làm theo instruction.
- **Ví dụ prompt cho Cursor:**  
  *"From docs/books/gil_2012_trading_cockpit.md, extract rules for Buyable Gap-Up and encode into pp_backtest/rulecards/BGU.md using the rulecard template. Do not invent numeric thresholds; if none, mark as adaptation."*
- **Vocabulary:** Dùng `docs/books/GIL_RULE_TAGS.md` (PP, CPP, BGU, 3WT, FTD, distribution, …).

---

## Bước 3 — Sinh Make targets (trong phạm vi YAML)

- **Contract:** `docs/EXPERIMENT_SPACE_GIL.yaml` — không thêm entry/mode/exit mới.
- **Prompt:** Mở `prompts/experiment_planner.md`; hoặc hỏi Cursor:  
  *"Using docs/EXPERIMENT_SPACE_GIL.yaml and docs/BOOK_TEST_LADDER.md, list Makefile targets for validation runs only. Do not add new parameters."*
- **Gợi ý chạy (validation, tối đa 3/session):**  
  `make book-c1-val` | `make book-c2-val` | `make book-b1a-val`  
  Ablation C1/C2: `make book-c1-val-m0`, `book-c1-val-m1`, `book-c1-val-m2`, `book-c2-val-m0`, …

---

## Bước 4 — Chạy & đọc kết quả

- **Bạn chạy** `make ...` (Cursor không chạy thay).
- Paste kết quả (PF, trades, tail5, max_drawdown, Top 5 % nếu có) vào chat.
- **Đọc kết quả:** Dùng role `prompts/research_auditor.md` — đọc theo IC Scorecard (Gate 1–4), báo pass/fail, **không sửa rule** sau khi thấy số.
- **Final:** Chỉ chạy final cho top 1–2 model đã chọn: `make book-c1-final`, `make book-c2-final`, `make book-b1a-final`.

---

## Guardrails (luôn áp)

- `max_experiments_per_session: 3`
- `rule_source: book_only`
- `human_approval_required: true`
- Hypothesis = bạn; Cursor = encode only.

---

## Chạy trong session này (max 3 experiments)

**1. Convert sách (sau khi cài Calibre):** từ repo root chạy  
`.\scripts\convert_gil_books_to_md.ps1`  
Hoặc chạy tay 2 lệnh in ra khi script báo "Calibre chua cai".

**2. Validation — chọn tối đa 3 run, ví dụ:**  
`make book-c1-val`  
`make book-c2-val`  
`make book-b1a-val`  
Hoặc ablation: `make book-c2-val-m0`, `make book-c2-val-m1`, `make book-c2-val-m2`.

**3. Sau khi chạy make:** paste kết quả (PF, trades, tail5, max_drawdown, [aggregate] dòng) vào chat → dùng role `prompts/research_auditor.md` đọc theo IC Scorecard.

**4. Final (chỉ khi đã chọn model từ validation):**  
`make book-c1-final` hoặc `make book-c2-final` hoặc `make book-b1a-final` — chạy **đúng 1 lần** cho model đã lock.

---

## Kết quả validation 2023–2024 (chạy session này)

| Setup | trades | PF | tail5 | max_drawdown | Ghi chú (IC Scorecard) |
|-------|--------|-----|-------|--------------|------------------------|
| **C1** Weekly PP (m2) | 204 | 1.65 | -11.69% | -70.0% | Gate 1 pass (PF>1.05); Gate 2 pass (≥40). |
| **C2** Weekly 3WT (m2) | 323 | 1.59 | -9.07% | -83.6% | Gate 1 pass; Gate 2 pass. |
| **B1a** BGU fixed 10 (book regime) | 50 | 1.33 | -16.60% | -60.5% | Gate 1 pass (PF>1.10); Gate 2 **chưa đạt** (50 < 80 trades cho daily BGU). |

**Đọc nhanh:** C1 và C2 đạt validation; B1a PF tốt nhưng sample ít (50 < 80). Final chỉ chạy cho C1 và/hoặc C2 khi đã lock model; đọc thêm Top 5 winners % và so PF validation vs final (Gate 4). *Convert sách: chạy `.\scripts\convert_gil_books_to_md.ps1` sau khi cài Calibre.*

---

## Kết quả Final 2025–2026 (đã chạy)

| Setup | trades | PF | tail5 | max_drawdown | Top 5 % |
|-------|--------|-----|-------|--------------|---------|
| **C1** Weekly PP (m2) final | 54 | 3.53 | -11.74% | -57.9% | (ledger ghi đè bởi C2) |
| **C2** Weekly 3WT (m2) final | 191 | 3.75 | -7.58% | -71.8% | 26.14% |

**IC Scorecard (Final):**

| Gate | C1 final | C2 final |
|------|----------|----------|
| **1** PF > 1.05 | ✅ 3.53 | ✅ 3.75 |
| **2** trades ≥ 40 | ✅ 54 | ✅ 191 |
| **3** Top 5 < 60% | (chưa đo) | ✅ 26.14% |
| **4** Stability (trades không sụt >50%) | ❌ 54 vs 204 val (−73%) | ✅ 191 vs 323 val (−41%) |

**Kết luận:** **C2 final pass** (Gate 1–4). C1 final PF đẹp nhưng **trades sụt >50%** so validation → Gate 4 fail; đọc là conditional / sample period ngắn. **Deploy gợi ý:** C2 (Weekly 3WT, m2) đủ điều kiện; C1 cẩn thận (theo dõi trades khi roll forward).

---

Ref: `docs/BOOK_TEST_LADDER.md`, `docs/EXPERIMENT_SPACE_GIL.yaml`, `docs/commands.md` (mục Gil knowledge integration).
