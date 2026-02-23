# Run playbook — Đóng vòng nhanh (không cần bàn thêm)

Chạy từ **repo root**. Output mặc định nằm trong `minervini_backtest/` (hoặc `minervini_backtest/outputs/` nếu dùng `--out-dir`).

---

## 1) Run bộ 3 output tối thiểu (A/B + realism + walk-forward)

### (A) Decision Matrix (realism + gross)

```bash
python minervini_backtest/scripts/decision_matrix.py --fetch --out minervini_backtest/decision_matrix.csv
```

### (B) Gate waterfall (2 universe)

```bash
python minervini_backtest/scripts/gate_attribution.py --universe both --fetch --out-dir minervini_backtest/outputs/gates
```

→ Tạo thư mục nếu chưa có. Output:
- `minervini_backtest/outputs/gates/gate_attribution_A.csv`
- `minervini_backtest/outputs/gates/gate_attribution_B.csv`

### (C) Walk-forward realism cho M3/M4

```bash
python minervini_backtest/scripts/walk_forward.py --realism --versions M3 M4 --fetch --out minervini_backtest/walk_forward_results.csv
```

(Mở rộng M9/M10/M11 sau: thêm vào `--versions M3 M4 M9 M10 M11`.)

---

## 2) Generate Decision layer nháp tự động

```bash
python minervini_backtest/scripts/decision_layer_from_outputs.py \
  --matrix minervini_backtest/decision_matrix.csv \
  --gate-a minervini_backtest/outputs/gates/gate_attribution_A.csv \
  --gate-b minervini_backtest/outputs/gates/gate_attribution_B.csv
```

→ Ra file **decision_layer_draft.md** trong `minervini_backtest/`.

---

## 3) Check deploy gates D1/D2/D3

```bash
python minervini_backtest/scripts/deploy_gates_check.py \
  --walk-forward minervini_backtest/walk_forward_results.csv \
  --matrix minervini_backtest/decision_matrix.csv
```

→ Kết quả: **DEPLOY** hoặc **ITERATE** + lý do fail (D1/D2/D3).

---

## 3b) Funnel diagnostics (khi trade count = 0 hoặc quá ít)

Để biết trade chết ở gate nào (TT / setup / trigger / retest):

```bash
python minervini_backtest/scripts/funnel_diagnostics.py --universe A --versions M4 M9 --fetch --out minervini_backtest/funnel_diagnostics.csv
```

→ Output: `tt_pass`, `setup_pass`, `trigger_pass`, `retest_pass`, `entries`, `exits` (fee=30, min_hold=3).

**Đọc nhanh:** Nếu setup_pass >> trigger_pass → nghẽn ở **trigger** (vol_mult / close strength / HH); nới vol_mult hoặc pivot-tight. Nếu trigger_pass >> retest_pass (M4) → nghẽn **retest** (undercut/window). Nếu tt_pass >> setup_pass → nghẽn **setup** (VCP/VDU quá chặt).

---

## 4) Nếu fail → iterate đúng 1 vòng (thứ tự ưu tiên VN)

1. **I2** (M4+M10): retest + gap filter — thử trước.
2. **I1** (M9+M6): pivot contraction + no chase.
3. **I3** (M7 + core): ATR stop rescue — chỉ khi stop-out nhỏ quá nhiều.

Sau mỗi iterate, chạy lại đủ **(A) + (B) + (C)** rồi chạy lại bước 2 và 3.

---

## 5) Decision layer: template + điền bằng 4 cụm số

- **Template (format chuẩn):** `minervini_backtest/docs/DECISION_LAYER_TEMPLATE.md`  
  Gồm: Survivors (core/backup/experimental), Top 3 actions, Top 3 risks, Watchlist, Signals, If X→do Y + **checklist interpret nhanh** (nhìn 10 dòng → T1/T2/T3 + core).

- **Điền bằng outputs:** Paste **4 cụm** (raw 10–20 dòng mỗi cụm) vào chat:
  1. **decision_matrix.csv** — fee=30, min_hold=3 cho M3, M4, M9, M10, M11 (hoặc M1–M11)
  2. **gate_attribution_A.csv** — G0..G5
  3. **gate_attribution_B.csv** — G0..G5
  4. **walk_forward_results.csv** — M3/M4 (2023 validate, 2024 holdout)

→ Trả 1 message điền đủ template: Survivors + Top 3 actions + Top 3 risks + Watchlist update + Signals + If X → do Y. Không hỏi thêm ngoài 4 cụm số.
