# Điều kiện trong sách Gil & Kacher → Encode để test tại VN

> Chỉ trích điều kiện **có trong sách** (2010, 2012); không tự chế thêm. Mỗi nhóm ghi: có thể encode như thế nào để test tại VN.

---

## I. MARKET CONTEXT (điều kiện thị trường)

### 1. Follow-through day (FTD) — O’Neil, Gil tôn trọng

**Sách:** Không aggressive buy khi market chưa có FTD. Distribution cluster quan trọng hơn 1–2 DD lẻ.

**Hiện tại:** MARKET_DD ≥ 5/20 → exit. Chưa encode: chỉ buy khi market confirmed uptrend.

**Encode testable (FTD-style proxy):**
- **Research integrity:** Điều kiện dưới đây là **trend proxy**, không phải FTD theo đúng nghĩa O'Neil (FTD có định nghĩa day-based cụ thể). Trong code/doc ghi **"FTD-style proxy"**.
- `regime_ftd = (VN30_close > MA50) AND (MA50_slope > 0)`. Implement: `pp_backtest/market_regime.py`.

### 2. Distribution cluster thay vì threshold cứng

**Sách 2012:** 3–4 distribution days trong 7–10 ngày là warning; không cần đợi tới 5/20.

**Encode testable:**
- `if dist_days_last_10 >= 3: no_new_positions = True` (stop buying, không exit toàn bộ).

---

## II. SUPPLY–DEMAND CLUES (hành vi cung cầu)

### 3. Tight weekly closes

**Sách:** Stock đóng cửa tight nhiều tuần liên tiếp; weekly range thu hẹp.

**Encode testable:**
- `weekly_range_last_3 < weekly_range_avg`
- Hoặc: `abs(weekly_close - weekly_open)` nhỏ trong 2–3 tuần.  
VN có thể hợp weekly-based hơn daily.

### 4. Volume dry-up at lows

**Sách:** Khi pullback, volume phải khô dần.

**Encode testable:**
- `volume_today < 50% average_volume` chỉ khi ở near MA support.  
(Đã có tightness; có thể refine.)

### 5. Shakeout + reversal với volume confirmation

**Sách:** Không chỉ U&R; break low intraday, close high in range, volume tăng so với prior days.

**Encode testable:** U&R hiện tại có thể bổ sung: close position strength (close trong upper % of range) + volume > prior N days.

---

## III. BUY SETUPS NGOÀI PP / U&R

### 6. Buyable Gap-Up (BGU)

**Sách 2010, 2012:** Gap up mạnh, volume lớn, mua trong gap range. Stop ở low của gap day.

**Encode testable:**
- `gap_percent > 3%` AND `volume > 1.5 * avg_volume`  
BGU có thể hợp VN hơn PP pullback — nhưng **occurrence có thể rất hiếm** (gap thật sự mua được trong gap range với T+2.5/ATC).

### 7. Three-weeks-tight (3WT)

**Sách (O’Neil):** 3 tuần đóng cửa gần nhau, sau đó breakout.

**Encode testable (weekly):**
- `max(close_last_3w) - min(close_last_3w) < 3%`  
VN có nhiều base kiểu này.

### 8. Pocket Pivot off 10-week MA (weekly)

**Sách:** PP trên weekly — volume_week vs down_volume, close vs MA10_week.

**Encode testable:**
- `volume_week > max(down_volume_last_10w)` AND `close_week > MA10_week`  
Có thể phù hợp hơn với T+2.5 (ít bar hơn, “large leg”).

---

## IV. SELL LOGIC NGOÀI MA VIOLATION

### 9. Selling into strength (climactic run)

**Sách 2012:** Sau 3–5 ngày tăng mạnh liên tục, volume tăng, range mở rộng → có thể partial sell.

**Encode testable:**
- 3 consecutive up days AND range expanding AND volume increasing.

### 10. Late-stage base failure (LSFB)

**Sách:** Nhiều base liên tiếp, break MA50 decisively, không reclaim.

**Encode testable:**
- `count_bases >= 3` AND `close < MA50`.

---

## V. PATTERN STRUCTURE (base, position, extension)

### 11. Right-side-of-base only

**Sách:** PP có giá trị cao nhất ở phần bên phải của base.

**Encode testable (đơn giản):**
- `close > midpoint_of_last_3m_range`.

### 12. Avoid extended

**Book 2:** Không mua khi extended quá xa MA10/20.

**Encode testable:**
- `distance_from_MA10 < 5%`.

### 13. MA50 must be rising

**Sách:** Đã test close > MA50; slope MA50 chưa bắt buộc > 0.

**Encode testable:**
- `MA50_slope > 0`.

---

## VI. Combination vs permutation

**Không brute-force all combinations.**  
Theo đúng scientific method:

- Chọn **1 setup** (ví dụ BGU hoặc Weekly PP).
- Chọn **1 market regime**.
- Chọn **1 exit logic**.
- **Freeze** → test full + hold-out + final.  
Không mix 8 điều kiện cùng lúc.

---

## VII. Thực tế sau các test vừa rồi

- **Daily PP continuation** mechanical không survive VN cost + T+2.5.
- **U&R** mechanical không survive (PF holdout < 1.0).

→ Gợi ý: VN market không reward short-duration daily setups.  
Nếu tiếp tục nghiên cứu continuation: **chuyển sang weekly timeframe** hoặc **breakout thrust lớn** (BGU, 3WT).

---

## VIII. Ba hướng đáng test nhất từ sách (thứ tự)

| # | Setup | Ghi chú |
|---|--------|--------|
| 1 | **Buyable Gap-Up (BGU)** | Lý thuyết tốt; **occurrence ở VN có thể rất hiếm** (gap mua được trong range + T+2.5). Nếu chỉ 50–100 lần / 12 năm / 80 symbol → sample size không đủ. |
| 2 | **Weekly Pocket Pivot** | Nhiều occurrence hơn, ít bị execution constraint. **Recommend test trước BGU.** |
| 3 | **Three-weeks-tight (3WT)** | Nhiều occurrence, ít bị T+2.5. |

**Nhận định:** BGU và 3WT có đủ occurrence trong VN universe để test không? BGU với gap > 3% + volume > 1.5x và execution VN (T+2.5, ATC) → rất hiếm. **Weekly PP và 3WT có nhiều occurrence hơn** → recommend **test Weekly PP trước**, không phải BGU.

---

## IX. Pre-registered spec: Weekly Pocket Pivot (nếu proceed)

**Entry (weekly bars):**
- `volume_week > max(down_volume_last_10_weeks)`
- `close_week > MA10_week`
- `close_week > MA50_week` (above-MA50 gate)
- `liquidity_regime_on` (VN30: 30d vol > 126d vol, áp dụng weekly hoặc từ daily aggregate)

**Exit:**
- `close_week < MA10_week` (weekly violation)
- OR `MARKET_DD >= 3/10` (weekly: 3 distribution days trong 10 tuần)

**Universe:** 80 symbols (config/watchlist_80.txt).

**Train:** 2012–2022.  
**Hold-out:** 2023–2026.

**Fee:** 30 bps + slip (realistic).  
**Constraint:** Tối đa 1 trade per week per symbol (tránh overtrade cùng symbol).

**Decision rule (pre-registered):** Hold-out PF > 1.0 với fee 30 bps → Weekly PP có deployable edge; ngược lại không deploy.

---

## X. Market regime luôn bật khi test book

Khi chạy bất kỳ setup “book” nào (Weekly PP, 3WT, BGU, PP + pattern filters), **điều kiện market nên luôn bật**:

- **FTD-style:** VN30 close > MA50 và MA50 slope > 0 → mới cho phép entry.
- **Distribution cluster:** dist_days trong 10 ngày gần nhất ≥ 3 → **no new positions** (chỉ dừng mua mới, không exit toàn bộ).

**Implement:** `pp_backtest/market_regime.py` (`add_book_regime_columns`, `weekly_regime_from_daily`). Daily run: `--book-regime`. Weekly run: `run_weekly.py` tự bật regime (không cần flag).

## XI. Cách chạy và kết hợp

| Chế độ | Lệnh | Ghi chú |
|--------|------|--------|
| Daily PP + book regime | `python -m pp_backtest.run --no-gate --book-regime` | Market FTD + no_new_positions |
| Daily U&R + book regime | `python -m pp_backtest.run --no-gate --book-regime --entry-undercut-rally` | Exit mặc định fixed 5 bars |
| Daily BGU + book regime | `python -m pp_backtest.run --no-gate --book-regime --entry-bgu` | Gap ≥3%, vol ≥1.5×avg |
| Pattern filters (daily) | `--right-side` và/hoặc `--avoid-extended` | Kết hợp với bất kỳ entry nào |
| Weekly PP (market luôn bật) | `python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt` | 1 trade/week/symbol, fee 30 bps |
| Weekly PP + 3WT | `python -m pp_backtest.run_weekly --entry-3wt` | Entry = Weekly PP hoặc 3WT breakout |

**Quy tắc:** Khi test theo sách (Gil/Kacher/O'Neil), luôn bật market regime (daily: `--book-regime`; weekly: mặc định đã bật).

## XII. Tóm tắt

- Toàn bộ điều kiện trên **đều bám sách**, encode dạng testable, không tự chế.
- **Priority:** Weekly PP → 3WT → BGU (sau khi kiểm tra occurrence BGU).
- **Market:** FTD + no new positions (dist_10 ≥ 3) luôn bật khi chạy book experiments.
- **Next step:** Chạy Weekly PP train 2012–2022, hold-out 2023–2026; báo trades / PF / tail5 / median_hold_weeks. So sánh với daily PP + book regime.
