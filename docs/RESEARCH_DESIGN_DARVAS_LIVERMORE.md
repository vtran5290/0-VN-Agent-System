# Research Design — Darvas & Livermore (Institutional-grade loop)

> **Nguyên tắc:** Không chạy tất cả cùng lúc. Chạy theo framework từng bước để tránh bias và đọc được regime dependency.

---

## I. Structural correctness (đã build)

- **Darvas box:** `box_confirm` = 2+ high touches AND 1+ low touch, tolerance = atr_tolerance_mult×ATR. Optional: stability_bars (chỉ đếm touch khi box stable N bar), touch_min_gap (đếm run, tránh double-count), max_range_pct (box_range_pct ≤ X).
- **Default (strict):** L=20, touch_high_min=2, touch_low_min=1, atr_tolerance_mult=0.2, stability_bars=0, touch_min_gap=0, max_range_pct=None. Trên VN có thể → 0 trades.
- **Option A (relaxed, audit):** `--darvas-relaxed` → tol=0.3, stability_bars=2, touch_min_gap=1, max_range_pct=1.5%. Hoặc sweep: `--darvas-tol 0.3 --darvas-stability-bars 2 --darvas-touch-gap 1 --darvas-max-range-pct 0.015` (và 0.02, 0.04 cho run 2/3).
- **Darvas exit:** Stateful trailing stop = max(box_low[entry:i]) − buffer; buffer = 0.25×ATR.
- **Livermore LOLR:** risk_on = close > MA50 & MA50 slope > 0; thêm **volatility filter** ATR(index)/close < 0.05.
- **Livermore reversal:** prior_trend = close.shift(1) < MA50 trước breakout (tránh continuation disguised as reversal).
- **Livermore pivot failure:** Exit khi close < trigger_level; **K-bar rule** (stateful): thoát nếu trong K bars sau entry mà close < trigger_at_entry. K sweep: 2 / 3 / 5.
- **Pyramiding:** Darvas add khi box mới cao hơn + unrealized > 0; Livermore add khi +X% từ entry + pivotal point mới (X sweep 5% / 8% / 12%).

---

## II. Research design — 3 bước (chạy tuần tự)

### STEP 1 — Pure Edge Test

**Mục tiêu:** PF stability, tail risk, regime dependency. **Không** bật market filter / RS / pyramid.

- **Darvas (no RS, no pyramid):**
  - Slice 1: `--start 2012-01-01 --end 2017-12-31`
  - Slice 2: `--start 2018-01-01 --end 2022-12-31`
  - Slice 3: `--start 2023-01-01 --end 2026-02-21`
- **Livermore (LOLR on, no pyramid):**
  - Cùng 3 slice trên.

**Output cần ghi:** PF, win_rate, tail5, max_drawdown, #trades, median_hold_trading_bars **theo từng slice**. So sánh 3 slice → regime dependency. (Ledger: `hold_cal_days`, `hold_trading_bars`; mọi rule/gate dùng `hold_trading_bars`.)

---

### STEP 2 — Market Dependency Test

Cùng entry (Darvas hoặc Livermore), **so sánh:**

- **A:** Có market filter (Darvas: `--rs-filter`; Livermore: LOLR đã bật sẵn).
- **B:** Không market filter (Darvas không --rs-filter; Livermore chạy với LOLR tắt bằng cách không merge lolr_risk_on).

**Mục tiêu:** Xem market filter cải thiện PF/tail hay chỉ giảm số trade.

*(Livermore đang luôn merge LOLR khi entry livermore_*; để test B cần tạm tắt trong code hoặc thêm flag --no-lolr.)*

---

### STEP 3 — Volatility Regime Test

- Tính ATR(VN30)/close theo ngày; xếp hạng percentile (e.g. 20% low vol, 80% high vol).
- Chạy cùng engine (Darvas hoặc Livermore), ghi lại mỗi trade thuộc low-vol hay high-vol regime.
- So PF / tail5 / win_rate **trong low-vol vs high-vol** → system chết ở đâu.

*(Cần post-process ledger với market ATR percentile; hoặc thêm cột regime_vol vào market_df và merge vào ledger.)*

---

## III. VN regime context (cảnh báo)

| Giai đoạn      | Đặc điểm        | Kỳ vọng engine      |
|----------------|-----------------|----------------------|
| 2012–2017      | Trending        | Darvas có thể mạnh   |
| 2018–2022      | Choppy          | Livermore có thể tốt hơn (transition) |
| 2023–2026      | Regime shift, FDI, policy | Gil early breakout có thể tốt |

→ **Meta layer (sau này):** regime_classifier → chọn engine (Darvas / Livermore / Gil).

---

## IV. Lệnh tham khảo (run từ repo root)

- **Darvas (strict, dễ 0 trades):**  
  `python -m pp_backtest.run --no-gate --entry darvas [--start ... --end ...]`
- **Darvas Option A (nới để có trades audit):**  
  `python -m pp_backtest.run --no-gate --entry darvas --darvas-relaxed`
- **Darvas sweep (3 run gợi ý):**  
  Run 1: `--darvas-tol 0.3 --darvas-stability-bars 2 --darvas-touch-gap 1 --darvas-max-range-pct 0.015`  
  Run 2: `--darvas-tol 0.4 --darvas-stability-bars 2 --darvas-touch-gap 1 --darvas-max-range-pct 0.02`  
  Run 3: `--darvas-tol 0.3 --darvas-stability-bars 3 --darvas-touch-gap 1 --darvas-max-range-pct 0.02`
- **Darvas + RS filter:**  
  `python -m pp_backtest.run --no-gate --entry darvas --darvas-relaxed --rs-filter`
- **Darvas + pyramiding:**  
  `python -m pp_backtest.run --no-gate --entry darvas --darvas-relaxed --pyramid-darvas`
- **Livermore CPP + pivot failure K=3:**  
  `python -m pp_backtest.run --no-gate --entry livermore_cpp --livermore-pf-k 3`
- **Livermore + pyramiding:**  
  `python -m pp_backtest.run --no-gate --entry livermore_cpp --pyramid-livermore`

---

## V. Ledger columns (audit)

- **hold_cal_days:** calendar days (entry_date → exit_date).
- **hold_trading_bars:** trading days (bar count); mọi rule/gate dùng cột này.
- **engine:** `darvas` | `livermore_rpp` | `livermore_cpp`.
- **entry_bar_index:** index của bar fill entry (bar i khi entry at i+1), không phải bar signal.
- **Darvas/Livermore audit:** `stop_at_entry`, `stop_at_exit`, `add_date`, `add_px`, `avg_entry_1`, `avg_entry_final`, `n_units`.

---

## VI. Checklist trước khi chạy full

- [ ] Đã chạy STEP 1 (3 slice) cho ít nhất 1 engine.
- [ ] So PF/tail/MDD giữa 3 slice → ghi regime dependency.
- [ ] STEP 2: so với/không market filter.
- [ ] STEP 3: chuẩn bị ATR percentile + split ledger theo vol regime.
