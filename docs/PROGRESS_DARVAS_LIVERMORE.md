# Progress — Darvas & Livermore (tóm tắt + hướng đi)

> **Trạng thái:** Darvas strict đã chạy được; Option A (relaxed) vẫn 0 trades. Research ladder (STEP 1–3) chưa chạy. Cảm giác "stuck" chủ yếu ở: relaxed không sinh trade, và chưa có audit trailing/pyramid trên ledger.

---

## 1. Đã làm xong

| Hạng mục | Chi tiết |
|----------|----------|
| **Darvas 0-trades bug** | Breakout sai: `close > box_high` (cùng bar) không bao giờ xảy ra (vì box_high ≥ high ≥ close). **Sửa:** so sánh với `box_high.shift(1)` (break above prior resistance). |
| **Ledger** | Đổi tên: `hold_days` → `hold_cal_days`, `hold_bars` → `hold_trading_bars`. Thêm: `engine`, `entry_bar_index`. Stats + `kpi_from_ledger` đọc cả tên mới/cũ. |
| **Darvas Option A** | `darvas_box()`: thêm `stability_bars`, `touch_min_gap`, `max_range_pct`. CLI: `--darvas-relaxed`, `--darvas-tol`, `--darvas-stability-bars`, `--darvas-touch-gap`, `--darvas-max-range-pct`. |
| **Debug Darvas** | CLI: `--darvas-no-new-high`, `--darvas-no-confirm`, `--darvas-vol-k` (0 = bỏ volume) để tìm nút nghẽn. |
| **Livermore** | Ledger đã có `engine`, `entry_bar_index`; 10 trades audit (n_units=1, chưa có stop/add) — sequencing chưa kiểm tra được. |

---

## 2. Hiện trạng (số liệu đã chạy)

- **Universe:** MBB, SSI, VCI, SHS, SHB; 2018–01–01 → 2024–12–31.
- **Darvas strict (default):** 18 trades, PF ≈ 10.8, avg_ret ≈ 16.9%, win_rate ≈ 72%, max_drawdown ≈ -10.4%. Ledger ghi đủ.
- **Darvas Option A (`--darvas-relaxed`):** 0 trades. Nguyên nhân khả dĩ: với relaxed, `box_confirm` (stability_bars=2 + touch run + max_range_pct) vẫn quá chặt trên 5 mã này → không bar nào pass.
- **Darvas debug (no confirm, vol_k=0, no new high):** 89 trades → xác nhận nghẽn trước đây là breakout same-bar + có thể thêm volume/confirm.

---

## 3. Chỗ đang “stuck”

1. **Option A vẫn 0 trades** — Nới tham số chưa đủ để `box_confirm` True trên dataset hiện tại; hoặc cần nới thêm (stability_bars=0, max_range_pct lớn hơn) hoặc tách test “relaxed” vs “strict” bằng slice/universe khác.
2. **Research ladder chưa chạy** — STEP 1 (3 slice), STEP 2 (market filter on/off), STEP 3 (vol regime) trong `RESEARCH_DESIGN_DARVAS_LIVERMORE.md` chưa có output.
3. **Audit trailing/pyramid** — Ledger chưa có cột `stop_at_entry`, `stop_at_exit`, `add_date`, `add_px`, `avg_entry_1`, `avg_entry_final`; chưa có đủ trade Darvas với `n_units>1` để kiểm tra stop monotonic và add sequencing.

---

## 4. Hướng đi tiếp theo (ưu tiên)

| Ưu tiên | Việc | Ghi chú |
|--------|------|--------|
| **A** | **Chạy STEP 1** (Pure Edge) với **Darvas strict** trên 3 slice (2012–17, 2018–22, 2023–26). Ghi PF, win_rate, tail5, max_drawdown, #trades, median_hold_bars theo slice. | Không cần Option A; strict đã có trade. So sánh 3 slice → regime dependency. |
| **B** | **Chạy STEP 1 cho Livermore CPP** (cùng 3 slice). So với Darvas strict theo từng slice. | Có sẵn ledger Livermore; chỉ cần chạy đủ slice và tổng hợp. |
| **C** | **STEP 2:** Darvas strict **có vs không** `--rs-filter` (cùng slice). So PF/tail/#trades. | Xem market filter cải thiện chất lượng hay chỉ giảm số trade. |
| **D** | **Option A:** Hoặc (1) nới thêm (stability_bars=0, max_range_pct=0.03–0.05) và chạy lại; hoặc (2) tạm bỏ Option A, chỉ dùng strict + sweep tol/range thủ công khi cần. | Tránh kẹt ở “relaxed 0 trades”; ưu tiên strict + research ladder. |
| **E** | **Ledger audit (sau khi có đủ trade):** Thêm cột `stop_at_entry`, `stop_at_exit`, `add_date`, `add_px`, `avg_entry_1`, `avg_entry_final` khi entry/exit/add. Bật `--pyramid-darvas` (hoặc livermore) để có `n_units>1` rồi audit. | Không block STEP 1/2; làm khi cần audit chi tiết. |

---

## 5. Lệnh nhanh

- **Darvas strict (đã dùng):**  
  `python -m pp_backtest.run --no-gate --entry darvas --exit darvas_box --symbols MBB SSI VCI SHS SHB --start 2018-01-01 --end 2024-12-31`
- **STEP 1 slice 1:** `--start 2012-01-01 --end 2017-12-31` (đổi start/end cho slice 2, 3).
- **STEP 2 có RS:** thêm `--rs-filter` (cần market index merge).
- **KPI từ ledger:** `python -m pp_backtest.kpi_from_ledger pp_backtest/pp_trade_ledger.csv`

---

**Tóm một dòng:** Sửa xong bug Darvas (breakout prior bar); strict chạy ổn, relaxed vẫn 0 trades. Hướng đi: ưu tiên **STEP 1 (strict + Livermore)** và **STEP 2 (RS)**; Option A nới thêm hoặc tạm gác; audit trailing/pyramid làm sau khi có cột ledger và pyramid bật.
