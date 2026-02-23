# PP / Buy-Sell Tweaks Research (Gil 2010/2012 — VN applicability)

> **Điều kiện đầy đủ từ sách (market, supply-demand, buy, sell, pattern):** `docs/GIL_BOOK_CONDITIONS.md`. Next recommend: **Weekly PP** (pre-registered spec), không BGU trước (occurrence có thể quá ít).

> Nguồn: Gil Morales/Kacher 2010, 2012. Tách FACTS (sách) vs INTERPRETATION (ưu tiên VN).  
> **Thứ tự thực tế:** 1 thing = test U&R trên 80 symbols. Nếu U&R có gross edge dày hơn PP → room survive VN cost.

---

## I. BUY SIDE — Tweaks có thể test

### 1️⃣ Position within base (Right-side filter)

**Sách:** PP có giá trị cao nhất khi ở **phần bên phải của base**, không giữa hay đáy lỏng lẻo. Hiện chưa encode "base structure".

**Mechanical test (pre-registered):**
- `Close > highest(close, 20)[-5]`  
  hoặc  
- Close trong **30% phía trên** của 3-month range  

**Ý tưởng:** Chỉ mua khi stock đã hồi phục phần lớn base.  
⚠ Khác "gần 52w high" — đây là "right side of structure".

**Status:** Interesting nhưng "position within base" khó encode sạch không overfit. **Không ưu tiên lúc này.**

---

### 2️⃣ Volume lookback 10 vs 15

**Sách:** Nếu volume pattern lộn xộn → dùng **15 ngày** thay vì 10. Hiện hard-code 10.

**Test:** `vol > max(down_vol last 15)` vs 10. **Không grid search** — chỉ 2 variant.

**Ưu tiên VN:** #3. Test sạch nhất, ít DoF. Chạy 2 variant, so PF. Nếu không material → giữ 10 (simpler).

---

### 3️⃣ CPP (Continuation Pocket Pivot) — Established uptrend

**Sách 2012:** CPP khi uptrend đã established, MA50 dốc lên, stock giữ MA10 nhiều tuần. Hiện chưa encode "established uptrend".

**Test (pre-registered):**
- `MA50_slope = (MA50 - MA50[20]) / MA50[20] > 0`
- AND `close > MA50` trong ít nhất **15/20 bar** gần nhất  

→ Loại bỏ PP "recovery bounce".

**Ưu tiên VN:** #2. Encode CPP distinction ít DoF. Test trên 80 symbols, 2012–2026, cùng methodology.

---

### 4️⃣ Undercut & Rally (U&R)

**Sách:** U&R = giá xuyên đáy trước, sau đó đảo chiều và reclaim. Buy setup quan trọng trong market choppy. Chưa encode.

**Test (pre-registered):**
- `Low < prior significant low`  
- AND `Close > prior low` (reclaim)  
- (Prior significant low: ví dụ low của 5–20 bar trước, hoặc swing low — lock 1 definition.)

**Ưu tiên VN:** **#1.** VN hay shakeout; U&R capture demand burst sau shakeout, thường resolve nhanh 1–3 bars → gross edge có thể dày hơn PP continuation, ít bị min_hold_bars ảnh hưởng.

---

### 5️⃣ Pocket Pivot off 50-day sau shakeout

**Sách:** Stock bị shakeout dưới MA50, lấy lại MA50 với volume signature mạnh. MA50 gate hiện tại có thể loại bỏ case này.

**Test:** Cho phép **close cross back above MA50** AND PP volume signature — chỉ case reclaim MA50, không phải đang dưới MA50.

**Status:** Có thể làm sau khi U&R và Established Uptrend đã test.

---

## II. SELL SIDE — Tweaks trong sách

### 6️⃣ Partial Sell (bán 50% khi violate MA10)

**Sách 2010:** Khi vi phạm 10dma → bán 1/2, trail MA20 phần còn lại. Hiện full exit.

**Status:** **Không làm lúc này** — implementation phức tạp, exit không phải root cause đã proven.

---

### 7️⃣ Selling into strength (climactic action)

**Sách:** Nhiều ngày tăng liên tiếp + volume climax + range mở rộng → sell into strength. Proxy: 3 up days + range > 1.5*ATR + volume spike.

**Status:** **Không làm lúc này** — phức tạp, effort nên dồn entry.

---

### 8️⃣ Violation definition chặt (confirmation_closes = 2)

**Sách:** Violation = Day 1 close dưới MA, Day 2 phá low Day 1. confirmation_closes=1 có thể exit nhạy.

**Status:** Đã test soft-sell (confirmation_closes=2) — PF giảm. Không ưu tiên.

---

### 9️⃣ Shortable gap-up (SGU) — sell filter

**Sách:** Gap-up quá mạnh = exhaustion, tránh mua near climax.

**Status:** **Không làm lúc này** — phức tạp, focus entry.

---

## III. Tweaks KHÔNG nên test (curve fitting)

- Tune slope tolerance 0.1% → 0.12%
- Tune MA touch 0.3% → 0.25%
- Tune ugly ATR multiplier 1.2 → 1.3  

→ Không encode.

---

## IV. Ba tweak đáng test nhất cho VN (thứ tự ROI)

| # | Tweak | Lý do |
|---|--------|--------|
| **1** | **U&R (Undercut & Rally)** | VN microstructure: continuation edge mỏng, T+2.5 kill. U&R khác cơ chế — demand burst sau shakeout, resolve nhanh 1–3 bars → gross edge có thể dày hơn, ít bị min_hold_bars ảnh hưởng. |
| **2** | **Established Uptrend (MA50 slope + time above MA50)** | CPP distinction, ít DoF. Pre-register 1 definition, test 80 symbols 2012–2026. |
| **3** | **Volume lookback 10 vs 15** | Ít DoF nhất. 2 variant, so PF. Nếu không material → giữ 10. |

---

## V. Thực tế thẳng thắn

Hai sách Gil xây trên: US institutional flow, deep liquidity, trend persistence cao, no T+2.5.  
Mechanical PP continuation **không survive** VN cost + settlement constraint (đã chứng minh).  
→ Tweak buy/sell có thể cải thiện nhẹ, nhưng **unlikely** đưa PF từ 0.97 lên 1.3 realistic.

**Câu hỏi quan trọng nhất còn lại:** U&R có gross edge dày hơn PP không (median f10 > 1%)? Nếu có → đủ room survive VN cost.

---

## VI. Thứ tự thực tế — 1 thing tiếp theo

**Nếu chỉ có time làm 1 thing:** Test **U&R** trên **80 symbols** (hoặc filtered_universe 140).  
Nếu U&R median f10 > 1% → có đủ room survive cost.  
Sau đó: Established Uptrend filter → Volume 10 vs 15.

---

## VII. Pre-registered definitions (để implement sạch)

### U&R (Undercut & Rally)

- **Prior significant low:** `prior_low = min(low) over bars [i-20, i-2]` (exclude yesterday; 20-bar lookback lock).
- **Undercut:** `low[i] < prior_low` (today’s low xuyên dưới prior low).
- **Rally/reclaim:** `close[i] > prior_low` (đóng cửa trên prior low).
- **Entry signal:** Bar i thỏa Undercut AND Rally. (Có thể thêm volume: vol > avg(vol,20) — lock 1 variant.)
- **Exit:** Cùng exit stack hiện tại (hoặc fixed 5 bar cho test pure edge).  
Test: 80 symbols, 2012–2026, report trades, PF, median hold, tail5, median f5/f10.  
**Implementation:** `pp_backtest.signals.undercut_rally_signal(df, prior_low_bars=20, volume_filter=True)`.

**Exit logic U&R (pre-registered):**
- **Option B (research):** Fixed 5-bar hold, exit at open bar 6. Đo gross edge thuần, không confound bởi exit. Khi dùng `--entry-undercut-rally` thì mặc định `--exit-fixed-bars 5` nếu không truyền.
- **Option A (production, sau nếu f5 > 1%):** Stop = low của phiên undercut; trail = SELL_V4 hiện tại.
- **Decision rule:** ur_80_holdout_realistic PF > 1.0 với fee=30bps + min_hold_bars=3 → U&R có deployable edge trên VN.

**Kết quả đã chạy (85 symbols từ config/watchlist_80.txt, Option B fixed 5-bar):**

| Run | trades | PF | tail5 | max_drawdown | median_hold_bars | avg_ret | win_rate |
|-----|--------|-----|-------|--------------|------------------|---------|----------|
| ur_80_full (2012-01-01 → 2026-02-21, fee 15+5) | 2491 | 0.79 | -10.70% | -100% | 5.0 | -0.51% | 44.00% |
| ur_80_holdout_realistic (2023-01-01 → 2026-02-21, fee 30+5, min_hold_bars=3) | 577 | 0.69 | -8.32% | -99.46% | 5.0 | -0.68% | 42.98% |

**Kết luận:** ur_80_holdout_realistic PF = 0.69 < 1.0 → U&R **không** đạt deployable edge với fee=30bps + min_hold_bars=3. Không deploy cơ học; có thể thử Option A (stop at undercut low + trail) sau nếu muốn.

### Established Uptrend (CPP filter)

- `ma50_slope_pct = (MA50 - MA50.shift(20)) / MA50.shift(20)`; condition: `ma50_slope_pct > 0`.
- `bars_above_ma50 = (close > MA50).rolling(20).sum()`; condition: `bars_above_ma50 >= 15`.
- **PP_entry_established = PP AND ma50_slope > 0 AND bars_above_ma50 >= 15.**  
Test: so với PP baseline (cùng exit), 80 symbols, 2012–2026.  
**Implementation:** `pp_backtest.signals.established_uptrend_filter(df, ma50_slope_bars=20, min_bars_above_ma50=15, lookback=20)`.

### Volume lookback 10 vs 15

- **Variant A (hiện tại):** `vol > max(down_vol last 10)`.
- **Variant B:** `vol > max(down_vol last 15)`.  
So sánh PF / trades trên cùng window, không tune thêm.

---

## VIII. Không làm lúc này

- Partial sell (6), Selling into strength (7), SGU (9) — exit không phải root cause.
- Right-side filter (1) — khó encode sạch không overfit.
