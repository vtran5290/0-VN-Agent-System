# Book conditions — Test Ladder & decision tree

> Ma trận test có kiểm soát: mỗi block chỉ đổi **1 thứ**, giữ nguyên phần còn lại. Tránh permutation explosion và peeking.
>
> **Rule lock:** Đọc kết quả theo **IC Scorecard** (mục 2) đúng thứ tự Gate 1 → 4. Không diễn giải linh tinh — dùng đúng ngưỡng và failure modes (mục 3) để kết luận.

---

## 1. IC Scorecard — đọc kết quả đúng thứ tự

Sau khi chạy validation rồi final, **đọc theo thứ tự** bốn gate dưới đây. Pass/fail phải dựa trên ngưỡng cố định, không dịch chuyển sau khi thấy số.

### A. Gate 1 — “Có edge không?”

| Timeframe | Pass tối thiểu |
|-----------|-----------------|
| **Weekly** (C1, C2, C3) | PF_final > **1.05** |
| **Daily** (B1a BGU) | PF_final > **1.10** |

Daily cần ngưỡng cao hơn vì turnover/cost sensitivity cao hơn.

- So sánh: PF_validation vs PF_final (cả hai phải đạt ngưỡng tương ứng).

### B. Gate 2 — “Có đủ sample không?”

| Timeframe | Pass tối thiểu |
|-----------|-----------------|
| **Weekly** | trades_final ≥ **40** |
| **Daily BGU (fixed-hold 10)** | trades_final ≥ **80** |

Nếu trades quá thấp, “PF đẹp” không đáng tin.

### C. Gate 3 — “Tail / MDD chịu được không?”

- **tail5** không xấu hơn baseline materially (so với daily PP baseline hoặc giữa các model).
- **max_drawdown** trong mức chấp nhận (phải so sánh giữa các model; tự đặt ngưỡng trước khi chạy).

Nếu PF cao nhưng tail5 và MDD tệ → **“fragile alpha”** → không deploy.

### D. Gate 4 — “Stability: validation → final”

- **PF_final** không được sụp kiểu 1.2 → 0.8 (giống PP trước đây).
- Nếu sụp nặng: coi như **fail**, dù validation đẹp. Không được sửa gate để “cứu” — kết luận regime shift hoặc model không robust.
- **Trades drop:** **trades_final** không được giảm quá **50%** so với validation (vd. validation 120, final 45 → PF có thể là noise).

---

## 2. Kỳ vọng hợp lý trước khi chạy (tránh bias)

Dựa trên nghiên cứu trước trong repo:

- **Daily PP / U&R:** đã fail realistic → khả năng Block A (book regime cho daily PP) giúp **ít**.
- **Weekly + breakout/thrust (3WT, Weekly PP):** xác suất sống **cao hơn** vì: lower turnover, bigger legs, giảm micro noise. **C-block là trọng tâm**, đúng như ladder.
- **BGU daily fixed-hold:** có thể sống nếu VN có gap-thrust regimes; nhưng **sample có thể ít** (trades_final ≥ 80 mới đáng tin).

Đừng kỳ vọng cả ba (C1, C2, B1a) đều pass final; ưu tiên đọc C-block trước.

---

## 3. Ba failure modes hay gặp ở VN (đọc output đúng)

**(i) PF nhìn ổn nhưng thực ra do 1–2 trade cực lớn**

- **Kiểm tra:** Top 5 winners đóng góp % total profit (từ ledger).
- **Ngưỡng cảnh báo:** > 40–50% → alpha rất fragile.
- **Rule cứng:** Nếu **Top 5 winners > 60% total profit → auto fail**. Không tranh luận.

**(ii) Weekly model pass validation nhưng fail final (2025 regime khác)**

- Đây là **test quan trọng nhất**. Nếu validation đẹp, final sụp → **đừng sửa thêm gate**. Kết luận: regime shift hoặc overfit validation → **stop**.

**(iii) no_new_positions (dist cluster) làm trades giảm quá mạnh**

- Trades thấp → PF dễ “ảo”. **Quy tắc:** Nếu trades_final < 40 (weekly) hoặc < 80 (daily BGU) → model **“không deployable”** dù PF đẹp.

**Conditional alpha (2025 regime khác):** Nếu 2025 là distribution-heavy và weekly breakout chết, **không có nghĩa model sai**. Có thể pattern alpha chỉ sống trong expansion regime → **conditional alpha**, không phải unconditional. Có thể ghi: nếu model chỉ sống trong Mode2 (trend+dist) → **deploy only when market breadth > X%**; không cố làm model universal.

---

## 4. Escape hatch — pre-commit “nếu tất cả fail thì làm gì?”

**Nếu sau Block C không có model nào pass Gate 1–4 trên final:**

→ **Dừng** pattern-based mechanical research.  
→ **Chuyển sang** Regime/Rotation engine (xem mục 4b).

Không được: chỉnh ngưỡng, thêm MA khác, nới rule, tìm combination mới. Đó là đường dẫn tới data-mining.

### 4b. Pivot nếu C-block fail (không thêm condition)

- **Regime-first model:** Thay vì “pattern → filter regime”, chuyển thành **regime state machine → sau đó mới chọn pattern**. VD: liquidity expansion regime, credit growth acceleration, VNIndex > 6M high; chỉ trong regime đó mới dùng breakout.
- **Relative strength rotation:** VN có thể sector/beta/margin driven; pattern alpha yếu hơn sector strength alpha. Khi đó: sector rotation, beta rotation, margin/flow driven.

---

## 5. Universe / survivorship bias

**Watchlist_80:** static 80 mã hiện tại (confirmed).  
→ Universe **không** dynamic theo thời gian → **survivorship bias có thể có** → PF có thể **inflated**. Trước khi tin kết quả, ghi nhận giới hạn này và cân nhắc khi diễn giải.

---

## 6. Nguyên tắc test

- **Knobs hiện có:** Entry (daily PP / BGU / weekly PP / 3WT / PP+3WT), Market (book regime), Pattern (right-side, avoid-extended), Exit (daily stack vs weekly MA10 + weekly DD).
- **Quy tắc:** Mỗi block chỉ thay **1** khía cạnh; so sánh với baseline của block đó. Không mix nhiều thay đổi trong một run.
- **3-split (tránh peeking):**
  - **Train:** 2018–2022 — chỉ debug logic, không dùng để chọn model.
  - **Validation:** 2023–2024 — dùng để **chọn** model trong Block A–D.
  - **Final untouched:** 2025–2026-02-21 — chạy **đúng 1 lần** cho model đã lock. Nếu đã peek 2023–2026 nhiều thì final càng phải nghiêm.

---

## 7. Market Regime Modes (ablation cho C-block)

Bật/tắt theo **3 mode cố định**, pre-register, không thêm mode. Mục đích: trả lời “edge phụ thuộc regime nào?” và “regime filter có thật sự cần thiết hay chỉ vô tình fit?”.

| Mode | Mô tả | regime_ftd | no_new_positions |
|------|--------|------------|------------------|
| **0** | No market filter (baseline) | off | off |
| **1** | Trend only (FTD-style proxy) | on | off |
| **2** | Trend + Distribution stop-buy (Book) | on | on (dist_days_10 ≥ 3) |

- **C1/C2 chạy Mode 0 vs 1 vs 2:** giữ entry/exit y hệt, chỉ đổi market mode. Lệnh: `--market-mode 0|1|2` (run_weekly). Make: `book-c1-val-m0`, `book-c1-val-m1`, `book-c1-val-m2`, `book-c2-val-m0`, `book-c2-val-m1`, `book-c2-val-m2`.
- **Quy tắc giữ market filter:** PF_final tăng **và** trades_final vẫn đủ **và** tail/MDD không xấu. Nếu PF tăng nhưng trades tụt dưới ngưỡng → filter **không deployable**.
- **Khi nào “always on” (Mode 2):** Khi mục tiêu là “book-faithful test”. Khi mục tiêu là “edge deployable ở VN” → cần ablation m0/m1/m2 để biết strategy phụ thuộc regime nào. Nếu Weekly 3WT sống ở Mode 0 → alpha tự thân, đáng deploy hơn.

### Cách đọc kết quả ablation (6 pattern outcome)

So C1 (Weekly PP) và C2 (3WT) trên m0 / m1 / m2. Đọc theo **một** trong các case dưới đây — không diễn giải linh tinh.

| Case | Pattern | Ý nghĩa | Hành động |
|------|--------|--------|-----------|
| **A** | m0 tốt nhất (vd. m0 1.18, m1 1.07, m2 1.02) | Market filter đang **làm hại** alpha. Pattern có **alpha tự thân**. | Deploy **m0**. Không tranh luận. |
| **B** | m1 tốt nhất, m2 kém (vd. m0 0.98, m1 1.15, m2 1.01) | **Trend filter** quan trọng. Distribution stop-buy làm trades giảm quá mạnh. | Deploy **m1**. |
| **C** | m2 tốt nhất (vd. m0 0.90, m1 1.04, m2 1.18) | Alpha phụ thuộc **full book condition** → **conditional alpha**. | Deploy **chỉ khi** market breadth confirm. Không cố universal. |
| **D** | m0 ≈ m1 ≈ m2 (vd. 1.03, 1.04, 1.02) | Market filter **không phải driver**. Pattern strength yếu / random. | Cẩn thận; có thể không deployable. |
| **E** | Validation tốt, final collapse (vd. val m2 1.20, final m2 0.82) | **Regime shift**. | Không chỉnh rule. Ghi nhận conditional alpha only. |
| **F** | Trades tụt mạnh ở m2 (vd. m1 90 trades, m2 35) | Dù PF đẹp, m2 **không deployable** theo Gate 2. | Ưu tiên m1 nếu đạt ngưỡng. |

**Insight cần trả lời:** Edge nằm ở **pattern** hay ở **regime**?  
- **m0 tốt** → pattern edge (alpha tự thân).  
- **m1/m2 tốt** → regime edge.  
→ Đây là insight cấu trúc thị trường VN.

### Kết quả ablation validation 2023–2024 (chạy 2025-02-21)

| Setup | Mode | trades | PF | tail5 | max_drawdown |
|-------|------|--------|-----|-------|--------------|
| **C1 Weekly PP** | m0 | 301 | 1.70 | -10.6% | -82.0% |
| C1 Weekly PP | m1 | 225 | 1.64 | -11.7% | -72.6% |
| C1 Weekly PP | m2 | 204 | 1.65 | -11.7% | -70.0% |
| **C2 3WT** | m0 | 638 | **1.69** | -8.9% | -95.1% |
| C2 3WT | m1 | 355 | 1.53 | -9.0% | -85.2% |
| C2 3WT | m2 | 323 | 1.59 | -9.1% | -83.6% |

**Đọc nhanh:** C1: m0/m1/m2 gần nhau (Case D hướng) — filter giảm trades và cải thiện MDD nhưng không đổi PF mạnh. C2: **m0 tốt nhất** (PF 1.69, nhiều trades) → **Case A**: pattern có alpha tự thân; market filter làm giảm edge. Cần kiểm tra Top 5 winners % (Gate 3) và chạy final cho model đã chọn.

### Bước quan trọng tiếp theo (đúng thứ tự, trước khi chạy final)

**1️⃣ Kiểm tra concentration**

Tính **Top 5 winners contribution %** (tổng lợi nhuận của 5 trade thắng lớn nhất / tổng profit).

| Ngưỡng | Kết luận |
|--------|----------|
| **≥ 60%** | **Auto fail** (theo rule đã lock) |
| 40–60% | Fragile |
| < 40% | Healthy |

Cái này quan trọng hơn PF lúc này.

**2️⃣ Kiểm tra distribution của returns**

Không chỉ tail5. Xem:

- **median_return**
- **% trades > 10%** (winners lớn)
- **% trades < -10%** (losers lớn)

PF có thể bị inflate bởi few 100% trades.

### Lựa chọn model đưa vào Final (theo logic lạnh)

Đưa vào final **2** model:

| # | Model | Lý do |
|---|--------|-------|
| **1** | **C2 m0** (3WT, no filter) | Alpha strongest; trades nhiều (robust sample). |
| **2** | **C1 m2** (Weekly PP + full book) | Risk profile tốt hơn; balanced candidate. |

**Không** đưa C1 m0 vào final — redundant với C2 m0.

### MDD và capital allocation (ghi nhận quan trọng)

**MDD -95%** trong backtest nghĩa là: đang compound **toàn bộ capital**, không có position sizing. Backtest hiện tại là **“fully invested per signal”**.

Thực tế deploy:

- Position sizing  
- Capital cap per symbol  
- Max concurrent trades  

→ Sẽ làm **MDD giảm mạnh**. PF ít thay đổi.  
→ **Sau final**, nếu alpha sống, cần layer thêm **capital allocation model**.

### Script chuẩn: concentration + distribution

**Concentration (Top 5 %, median, % >10%, % <-10%):**
```bash
# Sau khi chạy make book-c2-val-m0 (hoặc book-c1-val-m2), ledger = pp_backtest/pp_weekly_ledger.csv
python -m pp_backtest.ledger_concentration pp_backtest/pp_weekly_ledger.csv
```

**Cách đọc (theo rule đã lock):**
- **Top 5 winners %:** ≥60% → Auto FAIL; 40–60% → Fragile; <40% → Healthy.
- **Median return:** ≈0 hoặc dương → distribution ổn; âm nặng → PF có thể do skew.
- **% >10% vs % <-10%:** Healthy breakout thường % >10% khoảng 10–20%; nếu % <-10% >> % >10% → model dựa vào few huge winners.

**Position sizing (K=5, w=1/K) — MDD thực tế hơn:**
```bash
python -m pp_backtest.portfolio_sim pp_backtest/pp_weekly_ledger.csv
```
→ In: Portfolio MDD, Total return, CAGR, Avg exposure, Worst weekly loss, # trades executed (sau khi giới hạn K). *Sizing không tạo alpha; chỉ làm equity path bớt gãy.*

### Kết quả concentration + portfolio (validation 2023–2024)

**Model: C2 m0 (Weekly 3WT, market_mode=0)**  
Trades: 638  
Median return: -1.85%  
% trades > +10%: 12.23%  
% trades < -10%: 3.29%  
Top 5 winners contribution: **53.66%** (Fragile; <60% nên không auto fail)  
Portfolio (K=5): MDD **-18.39%**, Total return 20.60%, CAGR 10.56%, # trades executed 111

**Model: C1 m2 (Weekly PP, market_mode=2)**  
Trades: 204  
Median return: -1.74%  
% trades > +10%: 11.76%  
% trades < -10%: 7.35%  
Top 5 winners contribution: **111.37%** → **Auto FAIL** (≥60%; profit tập trung cực mạnh)  
Portfolio (K=5): MDD -13.13%, Total return -7.20%, # trades executed 35

**Kết luận đọc theo IC Scorecard:** C1 m2 **bị loại** vì Top 5 >60%. Chỉ **C2 m0** đủ điều kiện đưa vào Final. Position sizing giảm MDD từ ~-95% xuống ~-18% (validation) — đúng kỳ vọng.

### C2 m0 — Final (2025-01-01 → 2026-02-21) — đã chạy

| Metric | Validation 2023–2024 | Final 2025–2026 |
|--------|------------------------|------------------|
| Trades | 638 | **322** |
| PF | 1.69 | **2.89** |
| tail5 | -8.88% | -8.61% |
| Top 5 % | 53.66% (Fragile) | **57.26%** (<60%, không auto fail) |
| Portfolio MDD (K=5) | -18.39% | **-11.49%** |
| Portfolio Total return | 20.60% | **12.88%** |
| Portfolio CAGR | 10.56% | **12.62%** |

**Exec subset (K=5) – Final metrics:**  
- Executed trades: **78**  
- PF_exec (on executed trades): **1.47**  
- EV_exec (mean ret): **+1.08%**  
- Median_ret_exec: **-1.65%**  
- **Exposure_tw (time-weighted):** **58.5%** — định nghĩa: slot-weeks used / total slot-weeks (trùng với logic portfolio_sim: số vị thế mở trong tuần / K, trung bình theo tuần). *Exposure snapshot trong bản in cũ của portfolio_exec_stats không dùng để quyết định deploy.*

**Cost stress test (trên executed subset, `--stress`):**

| Scenario | PF_exec | EV | Exp_tw |
|----------|---------|-----|--------|
| RT 30bps (base, in ledger) | 1.474 | +1.08% | 58.5% |
| RT 40bps (+10bps extra) | 1.417 | +0.98% | 58.5% |
| RT 60bps (+30bps extra) | 1.314 | +0.78% | 58.5% |

**Decision rule (pre-registered):** RT40 PF_exec > 1.15 và EV > 0 → pilot ok. RT60 PF_exec ~1.0 và EV ~0 → không scale. Kết quả: RT40 đạt (1.42 > 1.15, EV dương) → pilot 4 tuần được phép.

**Gate check:** PF_final 2.89 > 1.05 ✓; trades_final 322 ≥ 40 ✓; Top 5 < 60% ✓; PF không sụp (val 1.69 → final 2.89) ✓. **C2 m0 (Weekly 3WT, no filter) pass Final** — conditional deploy với position sizing (K=5), monitor concentration & live PF.

**Signals to monitor (pilot):** Cost stress RT40/RT60 (PF_exec, EV, Exposure_tw); Rolling Top5% (57% sát ngưỡng); Execution misses (3WT nhạy fill).

**If X then Y:**  
- Nếu RT40 PF_exec vẫn khỏe → pilot 4 tuần, K=5, no margin.  
- Nếu RT40 làm PF_exec gần 1 → không pilot, chuyển robustness universe (alt watchlist).  
- Nếu Exposure_tw < 50% → hạ kỳ vọng CAGR live, vẫn có thể pilot để kiểm chứng tail winners.

**Final deploy-ready summary (Operating Manual):** C2 m0 Weekly 3WT, no market filter; K=5, 20% per slot; fee 30 bps. Deploy khi PF_exec > 1.15 và EV > 0 trên executed subset; monitor Top5 < 60%, exposure_tw; kill-switch khi PF live < 1.2 sau 30 trades hoặc Top5 > 60% rolling 6 tháng.

---

## 8. Test Ladder (từng tầng)

### Block A — Market regime effect (book regime “always on”)

**Mục tiêu:** Xác nhận regime filter không làm hại (giảm trades nhưng tăng quality).

| ID  | Mô tả | Entry | Market | Exit | So sánh |
|-----|--------|-------|--------|------|---------|
| A0  | Baseline | daily PP | off | daily stack | — |
| A1  | + book regime | daily PP | **book-regime** | daily stack | A1 vs A0 |

**Metrics:** PF, trades, tail5, avg_hold_bars (median_hold_bars).

**Decision:** Nếu A1 không cải thiện (hoặc tệ hơn) → dừng book regime cho daily, chuyển hẳn sang weekly/breakout.

---

### Block B — Breakout thrust (BGU)

BGU là setup “thrust” mạnh, phù hợp VN cost/T+2.5 hơn PP pullback.

| ID  | Mô tả | Entry | Market | Exit | Ghi chú |
|-----|--------|-------|--------|------|---------|
| B1a | BGU + book, exit fixed 10 | **BGU** | book-regime | **fixed 10 bars** | Xem entry edge (oracle exit) |
| B1b | BGU + book, exit stack | BGU | book-regime | daily stack | Phase 2: stop at BGU low + trail MA20/MA50 nếu B1a có edge |

**Decision:** Nếu BGU B1a (fixed 10) đã PF < 1 → không cần exit fancy (B1b).

---

### Block C — Weekly timeframe

Hợp logic nhất sau khi daily PP/U&R fail realistic.

| ID  | Mô tả | Entry | Exit | Fee |
|-----|--------|-------|------|-----|
| C1  | Weekly PP | weekly PP | MA10_week + weekly DD ≥ 3/10 | 30 bps |
| C2  | Weekly 3WT | **3WT breakout** | same | 30 bps |
| C3  | Weekly PP + 3WT | **PP OR 3WT** | same | 30 bps |

**Constraint:** max 1 trade/week/symbol. Market regime: mặc định Mode 2 (Book); ablation với `--market-mode 0|1|2` (xem mục 7).

**Decision rule (gợi ý):**
- PF_holdout > **1.05** (fee 30 bps) — weekly trades ít → 1.05 đủ.
- trades_holdout ≥ **40** — tránh sample noise.

---

### Block D — Pattern filters (sau khi đã có “best weekly”)

Chỉ bật **sau** khi entry + timeframe đã có tín hiệu tốt (filters dễ làm PF đẹp bằng cách giảm trades).

| ID  | Mô tả | Thêm pattern |
|-----|--------|---------------|
| D1  | Best weekly + right-side | right_side only |
| D2  | Best weekly + avoid-extended | avoid_extended only |
| D3  | Best weekly + both | right_side + avoid_extended |

**Decision:** Chỉ giữ filter nếu: **PF tăng** và trades giảm **không quá cực đoan** và **tail cải thiện**.

---

## 9. Decision tree (chạy tuần tự)

```
1. A0 (daily PP, no regime) → A1 (daily PP + book-regime)
   → Nếu A1 ≤ A0: bỏ book regime cho daily; ưu tiên Block C.

2. B1a (BGU + book-regime, exit fixed 10 bars)
   → Nếu PF < 1: không đầu tư B1b. Nếu PF ≥ 1: test B1b (exit stack / BGU low + trail).

3. C1 (Weekly PP) → C2 (Weekly 3WT) → C3 (Weekly PP+3WT)
   → Chọn best (PF_holdout > 1.05, trades ≥ 40). Nếu không đạt: dừng weekly hoặc chỉ báo “no deploy”.

4. D1/D2/D3 chỉ chạy trên “best weekly” (C1/C2/C3 đã chọn).
   → Giữ filter chỉ nếu PF↑, trades không sụt quá mạnh, tail↑.
```

---

## 10. FTD-style proxy & MA50 (research integrity)

### FTD-style proxy

Điều kiện market hiện tại: **VN30 close > MA50** và **MA50 slope > 0**. Đây là **trend proxy**, không phải FTD theo đúng nghĩa O’Neil. Implement: `pp_backtest/market_regime.py` (`regime_ftd`).

### Vì sao MA50 (không phải MA20/MA200)?

- **Sách (O’Neil/Gil):** MA50 = intermediate trend; MA20 quá noise, MA200 quá lag. Stock giữ MA50 trong uptrend; breakdown dưới MA50 = character change. MA50 không phải magic number — proxy cho institutional trend.
- **MA20:** quá nhạy, dễ whipsaw ở VN. **MA200:** vào rất trễ; sóng trung hạn 3–6 tháng có thể bỏ lỡ.
- **Test MA đúng (không overfit):** Chỉ 3 bucket — **short (MA20) / intermediate (MA50) / long (MA200)**. Không test MA30/40/60. Nếu intermediate outperform rõ → giữ MA50; nếu short → VN cần regime nhanh; nếu long → macro alignment.
- **Slope** có thể quan trọng hơn length: `regime = close > MA50 AND slope(MA50) > 0`. Phase 2 có thể test: Mode A MA50 only, B distribution stop-buy only, C MA50+dist (xem distribution có phải driver không).

---

## 11. Chạy ngay — thứ tự và quy tắc

**Thứ tự chạy Make (đúng ladder):**

### Validation 2023–2024 (chạy theo thứ tự)

1. **`make book-c2-val`** — Weekly 3WT (thường ít trade nhưng “đậm chất breakout”).
2. **`make book-c1-val`** — Weekly PP (thường nhiều trade hơn).
3. **`make book-b1a-val`** — Daily BGU fixed-hold 10 (sample phụ thuộc market).

### Final 2025–2026-02-21

- **Chỉ chạy final cho top 1–2 models** theo validation và **trades đủ** (Gate 2: weekly ≥ 40, daily BGU ≥ 80).
- **Đừng chạy final** cho model có trades validation quá thấp — phí thời gian và tạo “peek temptation”.

### Lệnh từng run (nếu không dùng Make)

**C2 — Weekly 3WT**
```bash
# Validation
python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --start 2023-01-01 --end 2024-12-31
# Final (chỉ khi đã chọn từ validation)
python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --start 2025-01-01 --end 2026-02-21
```

**C1 — Weekly PP**
```bash
# Validation
python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --start 2023-01-01 --end 2024-12-31
# Final (chỉ khi đã chọn từ validation)
python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --start 2025-01-01 --end 2026-02-21
```

**B1a — Daily BGU + book-regime, fixed 10 bars**
```bash
# Validation
python -m pp_backtest.run --no-gate --book-regime --entry-bgu --exit-fixed-bars 10 --watchlist config/watchlist_80.txt --start 2023-01-01 --end 2024-12-31
# Final (chỉ khi đã chọn từ validation)
python -m pp_backtest.run --no-gate --book-regime --entry-bgu --exit-fixed-bars 10 --watchlist config/watchlist_80.txt --start 2025-01-01 --end 2026-02-21
```

**Make (repo root, venv đã kích hoạt):**  
Validation theo thứ tự: `make book-c2-val` → `make book-c1-val` → `make book-b1a-val`.  
Ablation market mode (C1/C2): `make book-c1-val-m0`, `book-c1-val-m1`, `book-c1-val-m2`, `book-c2-val-m0`, `book-c2-val-m1`, `book-c2-val-m2`.  
Final (khi đã chọn model): `make book-c1-final`, `make book-c2-final`, `make book-b1a-final`.

---

## 12. Phase 2 — chỉ sau khi final xong

**Chỉ test các tweak dưới đây sau khi đã chạy final và có kết luận.** Không thêm gate/tweak để “cứu” model fail final.

**(A) MA50 rising (uptrend established)**  
- **Weekly:** bắt buộc MA50_week slope > 0. Book-consistent, ít curve-fit.

**(B) Selling into strength (cho weekly winners)**  
- Chỉ test nếu weekly model có **tail winners rõ ràng**: partial sell khi “climactic weekly range + volume”; còn lại trail MA10_week.

**(C) Stop buying vs exit positions**  
- Sách: “stop buying new” trước khi “sell aggressively”. Hiện đã encode: `no_new_positions` chỉ ngăn entry, không ép exit — **giữ nguyên**. Phase 2 có thể chỉ làm rõ doc hoặc test tách biệt “no new” vs “exit all” nếu cần.

---

## 13. Tóm tắt

| Block | Mục đích | Decision |
|-------|----------|----------|
| A     | Regime có giúp daily PP? | A1 vs A0; nếu không → ưu tiên weekly |
| B     | BGU có edge? | B1a fixed 10; nếu PF < 1 → bỏ B1b |
| C     | Weekly PP / 3WT / PP+3WT | PF_holdout > 1.05, trades ≥ 40 |
| D     | Pattern filters | Chỉ trên best weekly; giữ nếu PF↑, tail↑, trades không sụt quá |

**Chạy ngay:** Validation theo thứ tự C2 → C1 → B1a. Ablation C1/C2: chạy m0/m1/m2 để so sánh (mục 7). Final chỉ cho top 1–2 model đạt Gate 1+2. **Escape hatch (mục 4):** nếu không model nào pass final → dừng pattern research, pivot regime/rotation. **Universe:** static 80 → survivorship bias có thể (mục 5). Đọc theo **IC Scorecard (mục 1)** và **failure modes (mục 3)**.
