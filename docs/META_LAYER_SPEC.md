# Meta-layer v1 — Spec (codeable)

> **Ý tưởng:** Darvas+RS = engine kiếm tiền trong TRENDING. Ngoài TRENDING = chủ yếu không trade (capital preservation).

---

## 0. Index vs Stock MA (quan trọng)

| Loại filter | Áp trên | Bản chất | Tác dụng |
|-------------|----------|----------|----------|
| **Index MA (meta v1)** | VN30 | Regime filter | Bật/tắt toàn hệ thống theo trend index |
| **Stock MA** | Từng cổ phiếu | Trend alignment filter | Lọc breakout yếu (stock close &lt; MA50) |

- **Meta v1 hiện tại:** MA(period), slope, ATR% tính trên **VN30** → `meta_trending` merge vào mọi symbol → mask entry. **Không** áp MA50 trên từng cổ phiếu.
- **Stock-level:** Dùng `--above-ma50` (PP_GIL_V4.2). Entry chỉ khi `stock close > stock MA50`. Hoạt động với mọi entry mode (PP, Darvas, Livermore). Đây là **trend alignment**, không phải meta regime.

---

## 1. Regime classifier (tối giản)

Dùng VN30 (index):

- **TRENDING** = True khi đồng thời:
  - `index_close > MA(period)` (mặc định period=50; test 100)
  - `MA_slope > 0` (slope over 5 bars)
  - `ATR14(index)/close < vol_max` (mặc định vol_max=0.05)
- Nếu không đạt ⇒ **NON_TRENDING**.

**Mapping:**

- TRENDING → bật entry (Darvas+RS khi chạy Darvas).
- NON_TRENDING → NO TRADE (entry_signal bị mask).

**Tùy chọn:** `regime_stability_bars` (mặc định 0): chỉ flip regime khi điều kiện giữ ổn định N bar (ví dụ 3) để tránh whipsaw.

---

## 2. CLI (đã implement)

```bash
--meta-v1                    # Bật meta-layer v1
--regime-ma-period 50        # MA period (test 50 vs 100)
--regime-vol-max 0.05        # ATR14/close < 0.05
--regime-stability-bars 3     # Optional: ổn định 3 bar mới flip
```

---

## 3. Backtest design (3 đường cong)

| Run | Mô tả | Lệnh gợi ý |
|-----|--------|------------|
| **1** | Darvas+RS only (full 2012–2024) | `--entry darvas --exit darvas_box --rs-filter --universe liquidity_topn --liq-topn 50` |
| **2** | Meta v1 (Darvas+RS in TRENDING, else cash) | Thêm `--meta-v1` (có thể `--regime-stability-bars 3`) |
| **3** | Meta v1.1 (sau này: TRENDING Darvas+RS, else RPP small) | Chưa implement |

So sánh: PF, maxDD, tail5, exposure%, turnover/year.

---

## 4. Kỳ vọng

- Meta v1: **giảm maxDD mạnh**, giảm churn; PF có thể giảm nhẹ hoặc không đổi; **exposure giảm** (đúng mục đích).

---

## 5. Kết quả đã chạy (full 2012–2024, liquidity_topn 50)

| Run | #trades | PF | avg_ret | tail5 | max_drawdown | median_hold_bars |
|-----|--------|-----|---------|-------|--------------|------------------|
| **1. Darvas+RS only** | 285 | 2.47 | 7.36% | -16.88% | **-71.32%** | 42 |
| **2. Meta v1 (TRENDING only, stability 3)** | 207 | 2.46 | 7.21% | -16.77% | **-66.17%** | 43 |

**So sánh:**
- Meta v1 **giảm 78 trades** (285 → 207) → exposure giảm, tránh trade trong NON_TRENDING.
- **PF gần như giữ** (2.47 → 2.46).
- **maxDD cải thiện** (-71.3% → -66.2%, ~5 điểm phần trăm).
- tail5 tương đương.

👉 **Kết luận:** Meta v1 đạt mục tiêu: giảm DD, giảm churn, không làm mất edge (PF > 2). Có thể deploy logic “trade only TRENDING”.

---

## 5. Verdict & Next Phase (đã chấm)

**Kết luận cứng:** Meta v1 (index MA filter) **không deploy**. maxDD xấu hơn baseline (-66~-67%). DD xảy ra khi thị trường vẫn TRENDING (breakout failure cluster). **Next:** Test 1 `--above-ma50` (stock alignment); Test 2 Distribution Day entry filter (VN30 dist ≥4/20d). If dist filter giảm DD >25% → deploy; không cải thiện → vấn đề exit Darvas.

---

## 5b. Bảng so sánh chuẩn (copy-paste output → kết luận)

**Checklist metrics (bắt buộc cùng output cho run 1 & run 2):** trades, PF, tail5, maxDD, exposure_pct, turnover_per_year, skipped_due_to_regime (chỉ run 2). Expectancy_R nếu có thì thêm; chưa có thì skip.

**Format bảng (paste vào đây sau khi chạy 4 run):**

| Run | trades | PF | tail5 | maxDD | exposure% | turnover/yr | skipped_due_to_regime |
|-----|--------|-----|-------|-------|-----------|-------------|------------------------|
| Darvas+RS only | 186 | 2.43 | -17.10% | -58.90% | 5.11 | 22.9 | — |
| Meta v1 (MA50, vol 0.05, stab 0) | 137 | 2.42 | -17.21% | -65.87% | 3.64 | 16.8 | 79 |
| Meta v1 (MA50, vol 0.05, stab 3) | 128 | 2.49 | -17.08% | -67.06% | 3.41 | 15.7 | 98 |
| Meta v1 (MA100, vol 0.05, stab 3) | 135 | 3.11 | -17.02% | -66.86% | 3.95 | 16.6 | 81 |

*Period: 2018-01-01 → 2026-02-21 (config default). Meta v1 dùng `meta_trending.shift(1)` cho entry gate.*

**Đọc nhanh:** Meta v1 giảm trades & exposure đúng hướng; **maxDD tệ hơn baseline** (-59% → -66/-67%). → Red flag: DD chủ yếu xảy ra khi TRENDING hoặc regime chưa cắt đúng đoạn xấu. MA100+stab3 cho PF cao nhất (3.11) nhưng maxDD vẫn ~-67%. Cần bạn “chấm”: MA50 vs MA100, stability default, có deploy v1 không.

Sau khi chạy, lấy từ dòng `[summary]` in ra cuối mỗi run (trades= PF= tail5= maxDD= exposure_pct= turnover_yr= [skipped=]).

---

## 6. Kỳ vọng hợp lý (đọc đúng kết quả)

Vì Meta v1 chỉ tắt entry khi NON_TRENDING:

- **trades:** giảm  
- **exposure%:** giảm  
- **maxDD:** giảm rõ (thường mạnh nhất)  
- **PF:** có thể tăng hoặc giảm nhẹ tùy slice  
- **tail5:** thường cải thiện (ít trades trong chop)

**Red flags:**

- Meta v1 mà **maxDD không giảm đáng kể** → regime filter chưa “đúng chỗ” hoặc Darvas DD chủ yếu xảy ra ngay cả khi TRENDING.
- Meta v1 mà **PF tăng nhưng exposure &lt;10–12%** → capital efficiency thấp; meta đúng nhưng engine thiếu “non-trending alpha”.

---

## 7. Ba lỗi hay gặp khi meta mask entry_signal (audit)

| # | Lỗi | Fix | Trạng thái |
|---|-----|-----|------------|
| **1** | Regime computed using same-day close for entry bar → look-ahead. Entry at open bar i nên dùng data đến ngày i-1. | Khi mask entry: dùng `meta_trending.shift(1)` (regime bar i-1 cho entry fill bar i+1). | ✅ Đã fix: backtest dùng `_meta_trending_entry = meta_trending.shift(1).fillna(False)` để gate entry. |
| **2** | Merge date alignment: index_df thiếu ngày (holiday, gap) → merge inner/left sai → NaN→False (tắt quá nhiều) hoặc ffill sai. | Merge theo trading calendar của symbol_df; index reindex/ffill cẩn thận; tốt nhất same calendar. | ⚠️ Hiện merge left; NaN→False (conservative). Nếu index thiếu ngày nhiều cần audit. |
| **3** | stability_bars áp sau merge / không “freeze” regime trên index. | Implement stability trên index_df (market_df) **trước** merge. | ✅ Đã đúng: stability tính trong run.py trên market_df trước merge. |

---

## 8. Bốn run cần chạy (lệnh)

**(A) Baseline**  
Run 1 — Darvas+RS only:
```bash
python -m pp_backtest.run --entry darvas --exit darvas_box --rs-filter --universe liquidity_topn --liq-topn 50 --no-gate
```

**(B) Meta v1 MA50**  
Run 2a — stability 0:
```bash
python -m pp_backtest.run --entry darvas --exit darvas_box --rs-filter --universe liquidity_topn --liq-topn 50 --no-gate --meta-v1 --regime-ma-period 50 --regime-stability-bars 0
```
Run 2b — stability 3:
```bash
python -m pp_backtest.run --entry darvas --exit darvas_box --rs-filter --universe liquidity_topn --liq-topn 50 --no-gate --meta-v1 --regime-ma-period 50 --regime-stability-bars 3
```

**(C) Meta v1 MA100**  
Run 2c:
```bash
python -m pp_backtest.run --entry darvas --exit darvas_box --rs-filter --universe liquidity_topn --liq-topn 50 --no-gate --meta-v1 --regime-ma-period 100 --regime-stability-bars 3
```

Paste 4 dòng `[summary]` vào bảng §5 → AI/research lead đọc và kết luận: MA50 vs MA100, stability=3 có đáng không, rule mặc định meta.

---

## 9. If X happens → do Y

| If | Do |
|----|-----|
| Meta v1 giảm DD mạnh mà PF ≥ baseline | Deploy v1. |
| Meta v1 làm exposure &lt;10–12% | Cân nhắc engine khác cho NON_TRENDING (mean reversion) hoặc chấp nhận cash. |
| MA100 cải thiện DD nhưng PF tụt | Quay lại MA50 + stability. |
| stability=3 cải thiện DD mà PF gần không đổi | Set stability=3 default. |

---

## 10. Thứ tự test MA (đã dừng — meta v1 không deploy)

*(Không tối ưu thêm MA combination; chuyển sang internal filters.)*

---

## 11. Distribution Day Engine (code-ready spec) — Next phase Test 2

**Ý tưởng (O'Neil):** No new Darvas entries khi thị trường tích lũy quá nhiều distribution days (bán nặng + volume tăng) → tránh mở position mới trong lúc breadth xấu.

**Định nghĩa distribution day (đã có trong code):** Close &lt; prior close, volume &gt; prior volume, và %change ≤ -min_drop_pct (mặc định 0.2%). `distribution_day_count_series(df, lb=20)` = số ngày distribution trong 20 phiên gần nhất.

**Rule entry:** No new entry khi `VN30_dist_days_20 >= N` (mặc định N=4). Tức cho phép entry chỉ khi `mkt_dd_count < N`. Dùng **mkt_dd_count** đã merge từ VN30 (lb=20) trong run.py — không cần merge thêm.

**Timing:** Giống meta_trending: entry at open bar i+1 dùng thông tin đến bar i (hoặc shift(1) nếu muốn dùng bar i-1). Implement: mask entry khi `mkt_dd_count.shift(1) >= dist_entry_max` (hoặc `mkt_dd_count >= dist_entry_max` tại bar i).

**CLI (đã thêm):** `--dist-entry-max 4` — bật filter; no entry when VN30 distribution days in last 20 ≥ 4. `0` hoặc không truyền = tắt.

**Lệnh test:** So với baseline Darvas+RS và với Darvas+RS+above-ma50:
```bash
python -m pp_backtest.run --entry darvas --exit darvas_box --rs-filter --universe liquidity_topn --liq-topn 50 --no-gate --dist-entry-max 4
```

**Kỳ vọng:** Giảm DD (cắt entry trước cluster breakdown), PF không sụp mạnh. Nếu DD giảm >25% → deploy thay index MA filter.
