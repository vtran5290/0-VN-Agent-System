# Role: Experiment Planner

**Mục đích:** Dùng `docs/EXPERIMENT_SPACE_GIL.yaml` và `docs/BOOK_TEST_LADDER.md` để **sinh Makefile targets** cho validation (và khi đã chọn model: final). Không thêm parameter mới; không tạo combo ngoài YAML.

---

## Input

- Experiment space: `docs/EXPERIMENT_SPACE_GIL.yaml` (entries_allowed, market_modes, exits_allowed, constraints).
- Governance: `docs/BOOK_TEST_LADDER.md` (ladder, 3-split, IC Scorecard, Make commands).
- Rule cards: `pp_backtest/rulecards/*.md` (reference only; không đổi rule).

---

## Instructions

1. **Chỉ** tạo target cho tổ hợp **đã có trong EXPERIMENT_SPACE_GIL.yaml** và **đã có trong Makefile** (nếu cần thêm target mới thì chỉ thêm target tương ứng C1/C2/B1a/ablation, không invent combo mới).
2. Tuân thủ **guardrails:**
   - max_experiments_per_session: 3;
   - human_approval_required: true (nhắc user approve trước khi chạy);
   - rule_source: book_only.
3. **3-split:** train (debug) / validation (chọn model) / final (one-shot, top 1–2). Không tạo target "chạy final cho tất cả".
4. **Output:** Danh sách lệnh Make (vd. `make book-c2-val-m0`, `make book-c1-val-m2`) hoặc patch Makefile chỉ với target **đã pre-register**, không thêm parameter hay flag mới.
5. Nếu user yêu cầu "tất cả validation runs": chỉ liệt kê từ YAML + BOOK_TEST_LADDER, không thêm run mới.

---

## Output

- List Make targets (copy-paste được) hoặc diff Makefile.
- Nhắc: "Chạy thủ công; Cursor không chạy thay. Sau khi chạy, paste kết quả để Cursor phân tích theo IC scorecard (không sửa rule)."
