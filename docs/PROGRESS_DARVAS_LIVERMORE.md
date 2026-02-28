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

## 5. STEP 1 & STEP 2 — Kết quả đã chạy (5 mã: MBB SSI VCI SHS SHB)

### STEP 1 — Pure Edge (no RS, no pyramid)

| Slice      | Engine        | #trades | PF   | avg_ret | tail5   | max_drawdown | median_hold_bars |
|------------|----------------|--------|------|---------|---------|--------------|------------------|
| 2012–2017  | Darvas strict  | 14     | 6.88 | 12.2%   | -8.98%  | -14.1%       | 51.5             |
| 2018–2022  | Darvas strict  | 13     | 15.1 | 19.8%   | -7.54%  | -3.9%        | 55               |
| 2023–2026  | Darvas strict  | 7      | 4.06 | 8.8%    | -9.06%  | -10.4%       | 67               |
| 2012–2017  | Livermore CPP  | 123    | 0.47 | -0.8%   | -4.60%  | -67.3%       | 1                |
| 2018–2022  | Livermore CPP  | 133    | 1.14 | 0.2%    | -4.83%  | -38.8%       | 2                |
| 2023–2026  | Livermore CPP  | 104    | 0.87 | -0.1%   | -3.76%  | -30.8%       | 1                |

### STEP 2 — Darvas + RS filter (stock_ret_60d > index_ret_60d)

| Slice      | #trades | PF   | avg_ret | tail5   | max_drawdown | median_hold_bars |
|------------|--------|------|---------|---------|--------------|------------------|
| 2012–2017  | 11     | 8.77 | 12.9%   | -7.32%  | -14.3%       | 53               |
| 2018–2022  | 13     | 10.4 | 15.6%   | -7.54%  | -3.9%        | 54               |
| 2023–2026  | 5      | 9.77 | 14.7%   | -5.29%  | -2.4%        | 70               |

### So sánh Darvas: có RS vs không RS

| Slice      | Không RS (STEP 1) | Có RS (STEP 2) | Nhận xét |
|------------|-------------------|----------------|----------|
| 2012–2017  | 14 trades, PF 6.9, tail -9.0% | 11 trades, PF 8.8, tail -7.3% | RS loại bớt 3 trade, PF tăng, tail nhẹ hơn. |
| 2018–2022  | 13 trades, PF 15.1, tail -7.5% | 13 trades, PF 10.4, tail -7.5% | Cùng số trade; PF giảm (bỏ vài trade tốt?) nhưng vẫn rất cao. |
| 2023–2026  | 7 trades, PF 4.1, tail -9.1% | 5 trades, PF 9.8, tail -5.3% | RS loại 2 trade; PF tăng mạnh, tail và maxDD cải thiện rõ. |

**Kết luận STEP 2:** RS filter cải thiện chất lượng (PF/tail/maxDD) ở slice 1 và 3; slice 2 giữ số trade, PF vẫn >10. Nên **giữ --rs-filter** cho Darvas khi chạy thực.

---

## 6. Lệnh nhanh

- **Darvas strict (đã dùng):**  
  `python -m pp_backtest.run --no-gate --entry darvas --exit darvas_box --symbols MBB SSI VCI SHS SHB --start 2018-01-01 --end 2024-12-31`
- **STEP 1 slice 1:** `--start 2012-01-01 --end 2017-12-31` (đổi start/end cho slice 2, 3).
- **STEP 2 có RS:** thêm `--rs-filter` (cần market index merge).
- **KPI từ ledger:** `python -m pp_backtest.kpi_from_ledger pp_backtest/pp_trade_ledger.csv`

---

**Tóm một dòng:** Sửa xong bug Darvas (breakout prior bar); strict chạy ổn, relaxed vẫn 0 trades. Hướng đi: ưu tiên **STEP 1 (strict + Livermore)** và **STEP 2 (RS)**; Option A nới thêm hoặc tạm gác; audit trailing/pyramid làm sau khi có cột ledger và pyramid bật.

---

## 7. Universe expansion (liquidity_topn) — đã implement

**Mục tiêu:** Tăng sample size, tránh selection bias; universe freeze theo năm, không forward bias.

**Đã làm:**
- **`pp_backtest/universe_liquidity.py`:**  
  - `build_liquidity_universe_by_year(candidates, start, end, top_n, fetch, ...)`  
  - Mỗi năm Y: lấy 60 trading days trước ngày giao dịch đầu tiên của Y; median(volume×close); filter close ≥ 5,000 VND, ≥ 250 bars trước đầu năm; xếp hạng, lấy top N.  
  - Trả về `dict[year, list[symbol]]`.
- **`run.py`:**  
  - `--universe liquidity_topn` → build universe theo năm, `tickers` = union tất cả năm; mask entry: chỉ vào lệnh khi symbol nằm trong universe của năm đó (`in_universe`).
  - CLI: `--universe watchlist | liquidity_topn`, `--liq-topn N` (default 50), `--candidates path` (default `config/universe_186.txt`).  
  - Year-band (optional): có thể mở rộng sau bằng args dạng `liq_topn_2012_2016` → N cho năm 2012–2016.

**Lệnh mẫu:**
```bash
python -m pp_backtest.run --no-gate --entry darvas --exit darvas_box --universe liquidity_topn --liq-topn 50 --candidates config/universe_186.txt --start 2012-01-01 --end 2024-12-31
```

**Bước tiếp (theo thứ tự ưu tiên):**
1. ~~Chạy lại **STEP 1 + STEP 2** với `--universe liquidity_topn --liq-topn 50`~~ → **Đã chạy** (xem bảng dưới).  
2. Kiểm tra: trades per slice (mục tiêu ≥ 40), exposure %, PF stability, expectancy_R.  
3. Sau khi đủ trade (tổng > 100, mỗi slice > 30) mới làm STEP 3 (vol regime) và pyramiding.

---

## 8. STEP 1 & STEP 2 — Liquidity Top-N universe (đã chạy)

**Universe:** `--universe liquidity_topn --liq-topn 50`, candidates = 186.  
**Slices:** 2012–2017, 2018–2022, 2023–2024.

### STEP 1 — Darvas strict, no RS (liquidity_topn)

| Slice      | #trades | PF   | avg_ret | tail5   | max_drawdown | median_hold_bars |
|------------|--------|------|---------|---------|--------------|------------------|
| 2012–2017  | 145    | 2.13 | 5.2%    | -16.0%  | -66.8%       | 38               |
| 2018–2022  | 110    | 3.83 | 13.8%   | -15.9%  | -67.7%       | 46               |
| 2023–2024  | 29     | 0.73 | -1.3%   | -13.0%  | -49.3%       | 30               |

### STEP 2 — Darvas strict + RS (liquidity_topn)

| Slice      | #trades | PF   | avg_ret | tail5   | max_drawdown | median_hold_bars |
|------------|--------|------|---------|---------|--------------|------------------|
| 2012–2017  | 125    | 2.37 | 6.0%    | -16.0%  | -53.1%       | 42               |
| 2018–2022  | 96     | 3.67 | 13.9%   | -17.0%  | -60.9%       | 45               |
| 2023–2024  | 26     | 0.76 | -1.1%   | -12.8%  | -40.7%       | 30               |

### So sánh có RS vs không RS (liquidity_topn)

| Slice      | Không RS    | Có RS       | Nhận xét |
|------------|-------------|-------------|----------|
| 2012–2017  | 145, PF 2.13, maxDD -66.8% | 125, PF 2.37, maxDD -53.1% | RS giảm 20 trade; PF và maxDD cải thiện. |
| 2018–2022  | 110, PF 3.83 | 96, PF 3.67 | RS giảm 14 trade; PF gần như giữ. |
| 2023–2024  | 29, PF 0.73, maxDD -49.3% | 26, PF 0.76, maxDD -40.7% | RS giảm 3 trade; maxDD cải thiện, PF vẫn < 1. |

**Kết luận (research-grade):**
- **Sample size:** Slice 1–2 đạt > 90 trades; slice 3 chỉ 26–29 → chưa đủ cho vol regime (mục tiêu > 30/slice).  
- **PF:** Giảm mạnh so với 5 mã (từ 6–15 xuống 2–4 ở slice 1–2); **slice 2023–2024 PF < 1** → edge biến mất ở regime gần đây với universe mở rộng.  
- **RS filter:** Cải thiện chất lượng (PF/maxDD) ở slice 1; slice 2 tương đương; slice 3 vẫn âm. Nên **giữ RS** khi deploy.  
- **Bước tiếp:** Có đủ trade cho slice 1–2 để xem xét STEP 3 (vol regime) trên 2012–2022; slice 2023–2024 cần phân tích regime hoặc điều chỉnh entry/exit trước khi thêm pyramid.

---

## 9. Livermore CPP/RPP full period + So sánh 2023–2024 (liquidity_topn)

**Đã chạy theo đề xuất:** A) CPP 2012–2024, B) RPP 2012–2024, C) So sánh 2023–2024 (Darvas+RS vs CPP vs RPP).

### A) Livermore CPP — full 2012–2024 (liquidity_topn 50)

| Metric | Value |
|--------|--------|
| #trades | 3,051 |
| PF | **0.62** |
| avg_ret | -0.54% |
| tail5 | -4.55% |
| max_drawdown | **-100%** |
| median_hold_bars | 1 |

👉 CPP standalone trên universe rộng: **không có edge**, high churn, drawdown cực lớn.

### B) Livermore RPP — full 2012–2024 (liquidity_topn 50)

| Metric | Value |
|--------|--------|
| #trades | 671 |
| PF | **0.42** |
| avg_ret | -0.83% |
| tail5 | -4.43% |
| max_drawdown | **-99.7%** |
| median_hold_bars | 1 |

👉 RPP standalone: **cũng không có edge**, ít trade hơn CPP nhưng PF thấp hơn.

### C) So sánh 2023–2024 — engine nào “ít tệ” nhất?

| Engine | #trades | PF | avg_ret | tail5 | max_drawdown | median_hold_bars |
|--------|--------|-----|---------|-------|--------------|------------------|
| **Darvas + RS** | 26 | **0.76** | -1.1% | -12.8% | -40.7% | 30 |
| Livermore CPP | 243 | 0.35 | -0.75% | -3.6% | -85.5% | 1 |
| Livermore RPP | 85 | 0.56 | -0.42% | -2.6% | **-32.3%** | 1 |

**Đọc đúng:**
- **Không engine nào có edge (PF > 1)** trong 2023–2024 với universe rộng.
- Darvas+RS: PF cao nhất (0.76), ít trade, maxDD -40.7% — **breakout system “chết” nhưng chưa chết nặng nhất**.
- CPP: nhiều trade, PF thấp nhất (0.35), maxDD rất lớn (-85.5%) — **tactical continuation chịu nhiều false breakout**.
- RPP: maxDD “đỡ” nhất (-32.3%), PF 0.56 — **reversal catch ít lộ nhiều hơn nhưng vẫn âm**.

**Kết luận cho meta-layer:**  
Regime 2023–2024 (chop/transition) không engine standalone nào sống được. Meta-layer cần: **TRENDING → Darvas (+ RS)**; **TRANSITION/CHOP → tạm không trade hoặc RPP với size nhỏ / filter chặt**. Data đã sẵn sàng để thiết kế rule TRENDING (e.g. VN30 > MA50, MA50 slope > 0) và chạy full 2012–2024.
