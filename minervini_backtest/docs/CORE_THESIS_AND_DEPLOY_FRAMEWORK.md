# Core Thesis & Deploy Framework — Minervini x VN

Không build thêm; ra quyết định từ outputs và khóa **core thesis** của hệ thống.

**Playbook chạy đóng vòng (copy-paste lệnh):** `RUN_PLAYBOOK_CLOSED_LOOP.md`

---

## 1) Core thesis (chốt từ gate waterfall)

Chạy gate attribution A (VN30/top liquidity) và B (broad). Nhìn **gate nào tạo delta lớn nhất** (delta expectancy_r, delta PF) → chốt **một** trong ba thesis:

### Thesis T1 — Edge chủ yếu từ Trend Template / Regime (không phải VCP)

**Dấu hiệu:**
- G0 (TT + breakout) đã có expectancy_r tốt
- Thêm VDU/CS/VCP chỉ tăng nhẹ hoặc giảm
- G5 (retest) cải thiện ít

**Hành động:**
- Simplify: giữ TT + regime (M11) + pivot tốt (M9)
- VCP proxy chỉ dùng như “soft filter” (không gating cứng)
- Focus giảm false breakout: no-chase (M6) + fill realism

---

### Thesis T2 — Edge chủ yếu từ Retest (VN break-fail market)

**Dấu hiệu:**
- **G5 (retest)** là bước nhảy lớn nhất: delta expectancy_r rõ, PF tăng, MaxDD giảm
- M4 outperform M3/M1 ở realism

**Hành động:**
- Deploy core = M4 / M10 (retest / gap-retest)
- Tối ưu retest window & undercut cap (sweep nhỏ, không brute)
- Kết hợp M11 nếu universe B quá noisy

---

### Thesis T3 — Edge thật từ Supply contraction (VCP proxy, đúng “Minervini DNA”)

**Dấu hiệu:**
- **G3/G4** (VCP + close strength) làm expectancy_r tăng bền ở cả A và B
- Trade count giảm nhưng payoff_ratio tăng rõ
- top10_pct_pnl không phình to

**Hành động:**
- Deploy core = M2 / M9 (pivot contraction) + risk engine Champion
- Ưu tiên ATR stop (M7) nếu stop-out nhỏ nhiều
- Cân nhắc “no chase cap” để tránh mua extended

---

## 2) Deploy Gates (khóa deploy, không tranh luận)

Ba điều kiện bắt buộc trước khi deploy:

| Gate | Điều kiện | Cách kiểm tra |
|------|-----------|----------------|
| **D1** | Walk-forward stability | 2023 validate & 2024 holdout đều expectancy_r > 0; không quá lệch (một năm ăn hết) |
| **D2** | Concentration control | top10_pct_pnl < 60% **ở holdout** (không chỉ full-period) |
| **D3** | Realism survives | fee=30 + min_hold=3: PF ≥ 1.05 và expectancy_r ≥ 0.10 (ít nhất một candidate M3/M4) |

**Chạy kiểm tra:**
```bash
# Tạo walk_forward với realism và R-metrics
python minervini_backtest/scripts/walk_forward.py --realism --versions M3 M4 [--fetch] --out walk_forward_results.csv

# Kiểm tra D1/D2/D3 (cần cả decision_matrix.csv)
python minervini_backtest/scripts/deploy_gates_check.py [--wf-csv walk_forward_results.csv] [--matrix-csv decision_matrix.csv]
```

**Nếu fail D1/D2/D3 → không deploy, chỉ iterate.**

---

## 3) Iterate một vòng “ít nhưng trúng” (khi chưa có survivor)

**Thứ tự ưu tiên (xác suất cứu sống trong VN):**

| Ưu tiên | Iterate | Combo | Lý do |
|--------|--------|--------|------|
| **1** | **I2** | M4 (retest) + M10 (gap filter), retest 1–7, undercut 2–3% | Giảm false breakout + news spike; thử trước. |
| **2** | **I1** | M9 (pivot tight) + M6 (no-chase), fee 30, min_hold 3 | Pivot contraction + no chase; giảm mua extended. |
| **3** | **I3** | M7 (ATR stop) + core (M4/M9), risk_pct 0.5% | Chỉ khi stop-out nhỏ quá nhiều → expectancy rescue. |

Sau mỗi iterate, chạy lại đủ 3 output (1A + 1B + 1C) rồi check D1/D2/D3.

---

## 4) Deploy thực chiến (hai tầng, đúng tinh thần Champion)

Kể cả có survivor, deploy nên chạy **2 tầng**:

**Tier A — Scanner (fully mechanical)**  
- Chạy version thắng (M4/M9/M3 tùy thesis) → list candidates + entry levels + stop + R sizing.

**Tier B — Discretionary checklist (5 phút/mã)**  
- Thanh khoản đủ (giá trị khớp)  
- Gần earnings/news không (nếu track được)  
- Thị trường/sector risk-on không  
- Base “clean” không (nhìn chart)  

Minervini thực chiến luôn có Tier B. Mechanical-only thường mỏng edge.

---

## 5) Từ outputs → Decision layer (format chuẩn)

Sau khi có:
- `decision_matrix.csv` (fee=30, min_hold=3; split universe nếu có)
- `gate_attribution_A.csv` và `gate_attribution_B.csv` (waterfall)

Chạy:
```bash
python minervini_backtest/scripts/decision_layer_from_outputs.py [--matrix path] [--gate-a path] [--gate-b path]
```

Hoặc paste (tóm tắt) 2 file → điền theo format:

- **Survivors:** 1 core + 1 backup + 1 experimental  
- **Top 3 actions:** deploy / sweep / refactor  
- **Top 3 risks:** edge source, concentration, regime dependency  
- **Watchlist update:** version nào dùng cho scan hàng tuần  

Chi tiết script: `scripts/decision_layer_from_outputs.py`.
