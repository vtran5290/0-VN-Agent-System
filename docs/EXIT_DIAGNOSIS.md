# Exit diagnosis (PP_GIL_V4) — Nhận định & flow (stratify, không re-attribute)

**Ledger columns:** `hold_cal_days` (calendar days), `hold_trading_bars` (trading days); mọi rule/gate dùng `hold_trading_bars`. Script `exit_diagnosis` đọc `hold_cal_days` (fallback `hold_days`). Header ví dụ: `engine,symbol,entry_date,exit_signal_date,exit_date,entry_px,exit_px,hold_cal_days,hold_trading_bars,n_units,entry_bar_index,exit_reason,...`

## Nguyên tắc: không re-attribute, stratify

**Exit_reason theo priority = logic trading system thực tế.** Trong live: nếu SELL_V4 trigger trước → exit vì SELL_V4. Attribution hiện tại phản ánh **decision engine thật**, không phải “nguyên nhân lý tưởng”. Nếu re-attribute → đang phân tích hypothetical system, không phải system đang chạy. Backtest phải phản ánh execution reality.

**Cách đúng:** Giữ exit_reason như hiện tại; **thêm dimension single vs multi** và chạy Test 1 & Test 2 trên từng stratum:
- SELL_V4 single
- SELL_V4 multi
- MARKET_DD single (only)
- MARKET_DD overlap (MARKET_DD|STOCK_DD)
- STOCK_DD (đã sạch)

→ Đo **attribution bias magnitude** và **behavior difference** giữa clean vs overlap, không sửa dữ liệu.

---

## Nhận định đúng (giữ)

- **"Preset fail hoàn toàn" là vội.** STOCK_DD subset có edge (PF 1.185) → hệ thống không chết hẳn.
- **SELL_V4 là subset tệ nhất** (PF 0.65) → nguồn lỗ lớn.
- **Drill-down SELL_V4** qua hold_cal_days + MFE/MAE **theo stratum** (single vs multi).

## Hai điểm đã chỉnh (không suy diễn quá)

- **"Entry PP đang hoạt động"** → Chưa kết luận được (post-selection bias).
- **"SELL_V4 implementation có vấn đề nghiêm trọng"** → Chưa đủ bằng chứng; câu chuẩn: *SELL_V4 exit as currently used is associated with negative outcomes; cần kiểm tra implementation + attribution (reason_set) + behavior post-exit.*

---

## Insight từ overlap table

- **STOCK_DD 100% single-reason** → logic rất deterministic, không bị overlap contamination; PF 1.185 = **clean signal**.
- **SELL_V4 33.6% multi-reason, PF 0.652** → nghiêng hypothesis: **SELL_V4 implementation hoặc condition trigger đang quá nhạy** (cần verify bằng hold_cal_days + MFE/MAE stratified).

## Đọc số liệu hold_cal_days (sửa lỗi)

- **MARKET_DD overlap:** median hold_cal_days = **1** (không phải 4). MARKET_DD single và STOCK_DD cũng **median = 1**.
- Rất nhiều lệnh chỉ giữ **1 ngày** rồi thoát → có thể do: exits trigger ngay sau entry (noise/whipsaw), hoặc execution (enter next open, exit next open) gây “overnight flip”. Cần xem: những trade hold 1 ngày là ai? ret phân phối ra sao?
- **“Panic exit đúng đáy local”** — chưa có dữ liệu để kết luận; PF thấp có thể do exit quá sớm rồi phục hồi, hoặc entry kém (PP quality thấp). Cần **Test 2 (MFE/MAE)** để phân biệt.

## MARKET_DD single PF 1.11 — caveat

- PF 1.11 là tốt, nhưng **median hold = 1** cho thấy behavior rất ngắn hạn; rule có thể đang đóng vai “stop-out filter” hơn là “market regime risk control”.
- Chỉ giữ rule sau khi **Test 2** xác nhận: MAE được giảm đáng kể và MFE bỏ lỡ không quá lớn.
- **Test 2 phải đo cả MAE và MFE.** So sánh nên dùng **median MFE vs median MAE** (median quan trọng hơn avg). Không kết luận “exit sớm” chỉ từ MFE avg > |MAE avg| — MFE và MAE xảy ra ở thời điểm khác nhau trong 20 bars (path-dependent); 20-bar window ≠ realistic holding.

## Lỗi logic: so MFE avg vs MAE avg

- **Không đủ cơ sở** để nói “MFE > |MAE| → exit sớm”. MAE có thể xảy ra bar 1–3, MFE bar 15–20; nếu MAE -8% xảy ra trước MFE +10% thì có thể bị stop-out. So MFE avg vs MAE avg **không chứng minh** exit sai.
- Decision tree đúng: (1) Kiểm tra **hold_cal_days = 1** distribution (ret describe + by exit_reason). (2) Kiểm tra **time-to-MAE vs time-to-MFE** (bar nào đạt trước). (3) So **median MFE vs median MAE**, không chỉ avg.

## Nhận định đúng từ Test 2 (sau khi sửa)

- **SELL_V4 single:** PF 0.57 (rất xấu), MFE median 8.27% lớn, MAE median -5.42% không cực đoan, median hold 7 → **ứng viên số 1 để soften** (“exit quá nhạy” hợp lý).
- **MARKET_DD overlap:** PF 0.42, MFE ≈ MAE magnitude → **không có bằng chứng mạnh** exit sai; có thể “entry near breakdown”. **Chưa đủ cơ sở** để convert sang trim-only.
- **MARKET_DD single:** PF 1.11, MFE ≈ MAE → nhóm ổn định; **giữ nguyên**.
- **STOCK_DD:** PF 1.19, MFE cao không paradox (volatility compression / technical bounce sau exit).

## Chưa đúng / quá sớm

- “Hệ thống exit sớm trên diện rộng” → chưa có bằng chứng đủ.
- “Convert MARKET_DD overlap thành trim-only” → quá sớm (cần delay-exit A/B test trước).

---

## Kết luận không vòng vo (evidence-based)

| Hành động | Trạng thái | Ghi chú |
|-----------|------------|--------|
| **Soften SELL_V4 (2 closes)** | ❌ Rollback | A/B: design mismatch — label shift, SELL_V4 median_hold=1 trong soft; root cause ở MARKET/STOCK_DD priority. Next: MARKET_DD delay k=2. |
| **Setup_quality gate BUY (50)** | ✅ Đã chạy | Không material impact. Experiment DONE. Next experiment: MARKET_DD delay k=2 bars. |
| **MARKET_DD overlap → trim-only** | 🔶 Chưa commit | Có tín hiệu nhưng cần delay-exit A/B (hold 3–5 bars); so median ret + tail. Chỉ xem xét sau aggregate PF > 1 in-sample + tail risk (5% worst) cho MARKET_DD. |

---

## Decision tree final (thứ tự tối ưu)

**Baseline (đã chốt):** **min_hold_bars=3** (VN realistic) cho mọi experiment. US-style chỉ reference. Đã chạy: structural correction thành công; PF ~ unchanged → system structurally near-zero edge.

**Next:** exit_reason breakdown + PF by exit_reason (VN realistic). Nếu mọi subset &lt;1 hoặc gần 1 → xem lại entry logic (PP definition). Sau đó mới quyết MARKET_DD delay có cần không.

**Đã xong:** Gate(50) — không material impact. SOFT_SELL — rollback. min_hold_bars=3 experiment — structural correction success, PF ~ unchanged.

**Làm sau:** MARKET_DD delay k=2 chỉ sau breakdown; MARKET_DD overlap test nếu cần; trim-only chỉ khi PF > 1 + tail check.

---

## Gate BUY: nơi áp dụng + rationale (tránh nhầm)

**Gate phải áp vào backtest entry**, không chỉ Decision layer. Nếu gate chỉ ở Decision output mà backtest vẫn vào lệnh như cũ → PF / hold_cal_days=1 không thay đổi → tưởng gate không tác dụng. **Đúng:** implement gate trong **pp_backtest** (run/backtest + signals): entry signal = **PP & setup_quality >= threshold**. Decision layer chỉ phản ánh kết quả; không gate ở report alone.

**Rationale threshold = 50 (pre-registered, không tune):**
- 50 = neutral acceptance (trend/tightness/volume không quá tệ).
- Mục tiêu gate là **giảm one-day flips (hold=1)**, không phải tối ưu PF ngay. Chốt trước khi nhìn kết quả → tránh overfitting.

**Warm-up và xử lý None/NaN (pre-registered):**
- Setup_quality cần warm-up: ATR14 ≥ 14 bars, MA50+slope ≥ 50+slope_bars, tightness percentile 126 bars → cần **≥ 126 bars**. Bars đầu series hoặc symbol lịch sử ngắn → `setup_quality_score = None`.
- **Option A (đã chọn):** Nếu gate bật và `setup_quality_score is None/NaN` → **block entry** (skip trade). Không cho "unknown" lọt qua; sample sạch. Không dùng Option B (None → pass) để tránh contaminate.
- **Hai log metrics khi gate bật** (sanity check, tránh trade count illusion):
  - **skipped_due_to_warmup:** số lần PP=True nhưng không entry vì thiếu bars (score None/NaN).
  - **skipped_due_to_gate:** số lần có score nhưng &lt; 50.
  - Dùng để phân biệt: PF tăng vì gate tốt vs PF tăng vì loại bỏ cả giai đoạn warmup/symbol ngắn.

---

## Next steps (pre-registered, ít DoF)

| Bước | Tham số | Ghi chú |
|------|---------|--------|
| Gate BUY | threshold = **50** | Pre-registered. Chạy 1 lần, không tune. Entry = PP & setup_quality >= 50 trong backtest. |
| SOFT_SELL | confirmation = **2 closes** | Pre-registered. Không tune. Spec bên dưới. |
| So sánh | 3 metric + sell_v4_exits | (1) PF (2) hold1_rate (3) tail5_loss (4) sell_v4_exits. Định nghĩa cố định bên dưới. |

**SOFT_SELL_V4 (2 closes) — spec (presets.yml + code):**
- **confirmation_scope: tier_ma** — MA dùng để confirm là MA của tier, không phải một MA cố định toàn cục.
- Tier 3 (Ride MA10): soft sell = **2 consecutive closes below MA10**. Tier 2 (Ride MA20): **2 consecutive closes below MA20**. Tier 1 (MA50): **2 consecutive closes below MA50** (không đụng linger/porosity).
- **UglyBar** và **MA50 linger** giữ nguyên (không soften ở phase này). SOFT_SELL chỉ áp nhánh Day1/Day2 (1-close → 2-close).
- Preset: `sell_v4_confirmation_closes: 2`, `confirmation_scope: tier_ma`. Chạy: `--soft-sell`.

**Định nghĩa KPI (cố định trước khi paste kết quả):**
- **hold1_rate** = (số trades có hold_cal_days == 1) / total_trades (từ pp_trade_ledger.csv).
- **tail5_loss** = 5th percentile của cột `ret` (p5; không dùng median of bottom 5%). Càng âm = tail càng xấu.
- **sell_v4_exits** = số trades thoát bởi exit_reason SELL_V4 (SOFT_SELL sẽ giảm/delay con số này).

**A/B isolate effect (bắt buộc):** Baseline đang là `--no-gate`, nên SOFT_SELL cũng chạy **`--soft-sell --no-gate`**. Cùng **--start/--end** (hoặc config), cùng **watchlist.txt**, cùng **fee/slippage**. Sau khi chạy baseline, **rename/move ngay** `pp_trade_ledger.csv` → `pp_trade_ledger_baseline.csv` rồi mới chạy soft-sell (tránh overwrite). Test "soft sell + gate" là experiment khác.

**Nếu sell_v4_exits không giảm hoặc median_hold không tăng** — debug theo thứ tự: **Check 1:** confirmation_closes có = 2 khi --soft-sell? (dòng [run] in config at runtime). **Check 2:** SELL_V4 giảm nhưng MARKET_DD/STOCK_DD tăng? (label shift). **Check 3:** stratified SELL_V4 single/multi (exit_diagnosis) xem soft-sell có tác dụng đúng chỗ đau (SELL_V4 single PF 0.57) không.

**Paste format (baseline vs soft_sell) + sanity hold_cal_days:**
```
baseline:   trades=884, PF=0.959, hold1=51.9%, tail5=-6.16%, sell_v4_exits=113, avg_hold_days=X, median_hold_days=X
soft_sell:  trades=N, PF=X, hold1=X%, tail5=X%, sell_v4_exits=?, avg_hold_days=X, median_hold_days=X
```
- Lấy từ `python -m pp_backtest.kpi_from_ledger <ledger.csv>` (có sell_v4_exits, avg_hold_days, median_hold_days).
- Sanity: soft sell đúng cơ chế thì thường sell_v4_exits ↓, hold_cal_days ↑ (ít nhất SELL_V4 stratum); PF có thể ↑ hoặc tail5 xấu hơn chút (trade-off). Có dòng hold_cal_days để tránh false read.
- Sau khi paste hai dòng (baseline + soft_sell), quyết định: **keep** / **rollback** / **keep nhưng chỉ apply Tier3&2**.

**Checklist 30s trước khi chạy:** Khi run baseline, confirm dòng `[run]` có `confirmation_closes=1 gate=False`; khi run soft_sell, `confirmation_closes=2 gate=False`. Hai dòng phải **identical trừ confirmation_closes** (cùng start, end, symbols). Nếu không → dừng lại.

**Thứ tự đọc khi paste kết quả:** (1) sell_v4_exits ↓? (2) median_hold ↑? (3) PF ≥ baseline? (4) tail5 có xấu hơn materially không?

**Decision logic (sau khi paste):**

| Condition | Action |
|-----------|--------|
| sell_v4_exits ↓ + median_hold ↑ + PF ↑ | **KEEP SOFT_SELL** |
| sell_v4_exits ↓ + PF ~ + tail5 xấu | **KEEP nhưng chỉ Tier3/2** |
| sell_v4_exits ~ + median_hold ~ | **DEBUG** (trigger không hoạt động) |
| PF ↓ | **ROLLBACK** |

**Kỳ vọng:** Soft sell thường tăng hold time, giảm whipsaw, nhưng có thể tăng tail risk nhẹ. PF từ 0.959 → ≥1.0 đã là major structural shift; không cần PF 1.2. Chỉ cần >1.0 là regime thay đổi.

---

## SOFT_SELL rollback — design mismatch (sau A/B)

**Kết quả A/B:** PF giảm (0.959 → 0.945), sell_v4_exits tăng (113 → 255), median_hold SELL_V4 = 1 trong soft (baseline SELL_V4 median = 7). Label shift: SELL_V4 ↑, MARKET_DD/STOCK_DD ↓ — delay 1 bar khiến thoát khỏi market/stock flag rồi exit bằng SELL_V4 nhưng vẫn hold ngắn.

**Rollback không vì PF giảm.** Rollback vì: (1) mechanism không đạt mục tiêu (soft sell không “cho runway”), (2) root cause nằm ở **exit priority**, (3) intervention sai layer. Delay SELL_V4 không có tác dụng vì MARKET_DD/STOCK_DD override trước. Sell hierarchy: UglyBar → MARKET_DD → STOCK_DD → SELL_V4. Khi MARKET/STOCK_DD trigger sớm, SELL_V4 confirm thêm 1 bar không giúp trade “develop”, chỉ thay đổi nhãn. **Đây là execution-order artifact, không phải implementation bug.**

**Insight VN tape:** Pullback/shakeout 1–2 ngày, phục hồi nhanh. MARKET_DD/STOCK_DD median_hold = 1 → majority exits xảy ra quá sớm để SELL_V4 logic có cơ hội hoạt động. Softening SELL_V4 là “đánh sai tầng”.

**Structural insight:** Gate BUY yếu; Soft SELL_V4 sai tầng. **Root cause nằm ở MARKET/STOCK_DD priority** — hệ thống không bị lỗi ở entry hoặc MA logic, mà bị “quá nhạy” ở **regime-level exits**.

---

## VN T+2.5 — structural constraint (thay đổi cách đọc toàn bộ kết quả)

**VN T+2.5 = trading days (bars), không phải calendar days.** Ví dụ: mua Thứ Sáu → Thứ Hai là +3 calendar days nhưng chỉ 1 trading day. **Implementation phải dùng bar count** (entry_bar_index; current_bar_index − entry_bar_index ≥ min_hold_bars). Dùng calendar days → allow exit quá sớm hoặc block quá lâu tùy weekend → median_hold, MARKET_DD, tail measurement méo. Nếu hệ thống đang exit ở hold_cal_days = 1, đó là giả định bán ngay hôm sau — trong thực tế bị khóa thanh khoản ~2.5 ngày. **Toàn bộ backtest hiện tại đánh giá exit speed sai điều kiện thị trường thật.** Đây là structural constraint.

**Hệ quả:** median_hold = 1, MARKET_DD/STOCK_DD median_hold = 1 — những exits đó **không thể thực hiện được** ở VN. Ta bị buộc hold tối thiểu ~3 **bars**. Vì vậy: “MARKET_DD quá nhạy?” có thể là artifact do backtest cho phép bán quá sớm. MARKET_DD delay k=2 có thể chỉ **replicate reality** (correction to realism), không phải optimization.

**T+2.5 ảnh hưởng exit hierarchy:** MARKET_DD/STOCK_DD exits có thể giảm, SELL_V4 exits tăng tự nhiên, avg_hold tăng, tail risk có thể tăng — nhưng đó là **reality-based backtest**. Hiện tại hệ thống đang test “ideal US-style liquidity”, không phải VN.

**Sequencing đúng (pre-register):** (1) **Trước:** Add **min_hold_bars = 3** (bar count), re-run baseline (no gate, no soft sell). Đọc 5 KPI: PF, hold1_rate, exit_reason, tail5, sell_v4_exits. (2) **Sau đó** mới quyết có cần MARKET_DD delay. Nếu sau min_hold_bars=3: hold1_rate biến mất, PF tăng, MARKET_DD giảm, soft sell irrelevant → root cause = **unrealistic liquidity assumption**.

**Experiment pre-registered:** **baseline_vn_realistic** = `min_hold_bars=3` (trading days / bar count), không tune. Chạy `python -m pp_backtest.run --no-gate --min-hold-bars 3` (cùng start/end/watchlist). So với baseline (min_hold_bars=0). **Cách đọc kết quả:** Nếu T+2.5 là root cause: hold1_rate → ~0, median_hold ↑, MARKET_DD ↓, PF ↑ (hoặc không ↓), sell_v4_exits ↑. Nếu PF ↓ mạnh + tail xấu → exit speed là edge. **Insight:** Nếu min_hold_bars=3 cải thiện PF materially → soft sell/gate/MARKET_DD delay có thể không cần.

**min_hold_bars=3 experiment — kết luận (sau khi chạy):** Structural correction **thành công** (hold1_rate → ~0, median_hold 1→5, exit hierarchy shift SELL_V4 ↑). PF gần như **không đổi** (0.959 → 0.957) → **exit speed không phải edge** (nếu là edge thì PF phải sụp khi ép hold ≥3). T+2.5 **không phải root cause của negative expectancy**; nó chỉ sửa realism. tail5 xấu hơn (-6.16% → -7.74%) là expected (hold lâu hơn → ăn thêm tail risk); **MARKET_DD có vai trò risk containment thật** → hypothesis “MARKET_DD delay sẽ giúp” yếu hơn. trades giảm 884→810 (ít churn) nhưng PF không cải thiện → **negative drift không đến từ overtrading**. **Sequencing:** Từ giờ **mọi experiment dùng min_hold_bars=3** làm baseline VN realistic; US-style chỉ còn reference. **MARKET_DD delay:** Chỉ xem xét sau khi có **exit_reason breakdown** (VN realistic): nếu MARKET_DD % vẫn cao và subset PF thấp → có thể test delay k=2; nếu MARKET_DD đã giảm đáng kể → delay có thể chỉ tăng tail risk. **Insight lớn:** Gate BUY không material, Soft SELL_V4 sai tầng, T+2.5 correction không cải thiện expectancy, PF ~0.96 giữ nguyên → **hệ thống structurally near-zero edge**. Câu hỏi lớn hơn: **PP entry có thực sự có edge ở VN không?** Đang sửa exit nhưng entry edge vẫn không xuất hiện. **Bước tiếp:** In exit_reason breakdown với min_hold_bars=3; in **PF theo exit_reason** (VN realistic); so subset PF. Nếu mọi subset vẫn &lt;1 hoặc gần 1 → cần xem lại **entry logic (PP definition)**.

---

## Gate(50) experiment — kết luận (scientific)

**Kết quả đo được:** PF +0.003, hold1_rate giảm ~1.7pp, tail5 gần không đổi. 55 trades bị loại (score &lt; 50) nhưng không cải thiện quality rõ rệt. **→ Gate 50 không tạo edge material.**

**Điều thí nghiệm này đã test:** “Score &lt; 50 có clearly tệ không?” → Không.  
**Điều chưa test:** “Top 30% setup có outperform không?” — hai câu hỏi khác nhau. Không kết luận “gate concept yếu” từ một threshold neutral (50).

**Distribution check (optional, chỉ để hiểu geometry, không để tune):** 55 trades bị loại có nằm ở bottom 20% distribution ret không? Hay score distribution quá compressed (vd 45–65)? Nếu narrow → threshold 50 đúng là “cắt lát mỏng” → experiment không đủ lực. Nếu wide mà gate vẫn không cải thiện → setup_quality không correlate. Check distribution không nhằm optimize threshold.

**Hypothesis 2 (execution):** hold1_rate vẫn ~50% sau gate. Nếu vấn đề là PP entry quá sát break → bị stop-out ngày hôm sau thì gate quality không fix được; đây là entry timing hoặc exit trigger quá nhạy. Align với SELL_V4 single PF 0.57, time_to_MAE trước MFE → **SOFT_SELL có evidence mạnh hơn gate rất nhiều.**

**Decision:** Gate(50) experiment = **DONE**. Không harmful, không impactful, không đủ ROI để justify complexity. Không tune 65/70 trừ khi thiết kế formal experiment mới.

---

## Evidence strength & sequencing (cập nhật)

| Strength | Hạng mục | Ghi chú |
|----------|----------|--------|
| **Baseline (đã chốt)** | min_hold_bars=3 (VN realistic) | Từ giờ mọi experiment dùng min_hold_bars=3. US-style chỉ reference. Đã chạy: structural correction thành công, PF ~ unchanged → exit speed không phải edge; system structurally near-zero edge. |
| **Moderate** | MARKET_DD delay k=2 | Chỉ sau **exit_reason breakdown + PF by exit_reason** (VN realistic). Nếu MARKET_DD % cao + subset PF thấp mới test; nếu MARKET_DD đã giảm nhiều → delay có thể chỉ tăng tail. |
| **Moderate** | MARKET_DD overlap | Cần delay-exit A/B trước khi quyết trim-only. |
| **Rollback** | SOFT_SELL (2 closes) | Design mismatch; root cause ở MARKET/STOCK_DD priority. |
| **Weak** | Gate BUY (50) | Đã chạy; không material impact. |

**Sequencing:** (1) **Baseline từ giờ:** **min_hold_bars=3** (VN realistic) cho mọi experiment; US-style chỉ reference. (2) **Next:** In **exit_reason breakdown** (min_hold_bars=3); in **PF theo exit_reason**; so subset PF. Nếu mọi subset &lt;1 hoặc gần 1 → xem lại entry logic (PP definition). (3) **MARKET_DD delay:** Chỉ sau khi có breakdown; nếu MARKET_DD % cao + subset PF thấp mới cân nhắc delay k=2; nếu MARKET_DD đã giảm nhiều thì delay có thể chỉ tăng tail. (4) Không soften SELL_V4 thêm; không tune gate 65/70.

---

## Next experiment (1): baseline_vn_realistic — min_hold_bars=3

- **Rationale:** VN T+2.5 = trading days (bars); exits hold_cal_days=1 không thực thi được. Correction to realism (bar count, không calendar days).
- **Pre-registered:** `min_hold_bars = 3`. Không tune. Chạy: **Baseline US-style** `--min-hold-bars 0` (hoặc không truyền); **Baseline VN realistic** `--min-hold-bars 3` (cùng start/end/watchlist).
- **Đọc 5 KPI:** PF, hold1_rate (nếu T+2.5 root cause → ~0), median_hold ↑, exit_reason breakdown (MARKET_DD ↓), tail5, sell_v4_exits (có thể ↑). Nếu PF ↓ mạnh + tail xấu → exit speed là edge, không phải artifact. Nếu min_hold_bars=3 cải thiện PF materially → soft sell/gate/MARKET_DD delay có thể không cần. *(Đã chạy: structural correction thành công; PF ~ unchanged → xem kết luận ở mục VN T+2.5 trên.)*

## Next step: exit_reason breakdown + PF by exit_reason (VN realistic, min_hold_bars=3)

- In exit_reason breakdown (count / %); in **PF theo từng exit_reason**. So subset PF. Ledger: run `--no-gate --min-hold-bars 3`. *(Đã chạy: STOCK_DD PF 1.50, MARKET_DD ~0.96, SELL_V4 0.38 → SELL_V4 là nơi đốt alpha.)*

## no_SELL_V4 experiment (pre-registered)

- **Define:** disable_sell_v4 = True: tắt MA-trailing exit (SELL_V4); **giữ** STOCK_DD, MARKET_DD, **UglyBar**. UglyBar nằm trong module SELL_V4 nhưng được tách: `sell_ugly_only` = exits chỉ do ugly bar (use_fire10&ugly10 | use_fire20&ugly20 | use_fire50&(ugly50|ugly_break50)). Khi --no-sell-v4: sell_final = sell_mkt_dd | sell_stk_dd | sell_ugly_only; exit_reason UGLY_BAR cho ugly exits. **UglyBar vẫn active**, không bị loại.
- **Chạy A/B:** Cùng min_hold_bars=3, cùng start/end/watchlist. Baseline VN: `--no-gate --min-hold-bars 3`. no_sell_v4: `--no-gate --min-hold-bars 3 --no-sell-v4`.
- **Paste format:**
  - baseline_vn: trades=810, PF=0.957, tail5=X%, avg_hold=X, sell_v4_exits=167, market_dd_exits=201, stock_dd_exits=440
  - no_sell_v4: trades=N, PF=X, tail5=X%, avg_hold=X, sell_v4_exits=0, market_dd_exits=N, stock_dd_exits=N
  - (kpi_from_ledger in thêm market_dd_exits, stock_dd_exits, ugly_bar_exits)
- **If X → do Y:** PF &gt; 1 → **KEEP no_SELL_V4**. PF ~ 1 → entry cần refine. PF &lt; baseline → SELL_V4 vẫn có role containment (rollback no_SELL_V4).
- **Fork:** Nếu loại SELL_V4 mà PF &gt; 1 → PP entry có edge, MA exit phá nó. Nếu PF vẫn &lt; 1 → PP entry không có edge ở VN.

**no_SELL_V4 experiment — kết luận (sau khi chạy):** PF aggregate **không đổi** (0.957 → 0.957). SELL_V4 bị loại hoàn toàn, exits chuyển sang MARKET_DD/STOCK_DD nhưng expectancy không cải thiện. **→ SELL_V4 không phải root cause.** Đã loại trừ: liquidity, exit speed, SELL_V4 design, label shift, gate. **Sau forward return test:** median f10 &gt; 0 → **EDGE_EXISTS**; framing cập nhật thành "thin edge not captured" (entry có edge nhưng mỏng; exit/fee/tail giải thích PF &lt; 1). Xem mục Forward return test và f10 vs realized gap.

## Forward return test (pre-registered)

- **Mục đích:** Đo PP entry có continuation edge trên VN không, độc lập exit logic. Dùng **đúng entry dates từ ledger** (không generate lại signals).
- **Spec:** Với mỗi PP entry (entry_date, symbol): baseline = close tại entry bar; forward return f5/f10/f20 = (close[t+k]/close[t]) - 1. Output: median và mean f5/f10/f20, % trades có f10 &gt; 0.
- **Quy tắc đọc (pre-registered):** median f10 ≤ 0 → PP entry không có continuation edge; exit tweak vô nghĩa. median f10 &gt; 0 → entry có edge; vấn đề có thể ở exit (nhưng đã stress test exit nhiều).
- **Chạy:** `python -m pp_backtest.forward_return_analysis --ledger ... --use-fetch` (OHLCV từ API như backtest).
- **Kết quả (810 trades):** median f10 = +0.42% &gt; 0 → **EDGE_EXISTS**. PP entry có continuation edge; vấn đề không nằm ở entry signal thuần. f20 &gt; f10 (median +0.98%) → edge cần runway; exit có thể thoát quá sớm.

**Framing sau forward return ("thin edge not captured"):** Entry có edge nhưng mỏng (0.42% median f10). Backtest PF &lt; 1 do: (A) exit timing cắt edge, (B) tail risk, (C) fee/slippage. Không optimize exit thêm; bước tiếp là f10 vs realized gap + tail.

## f10 vs realized gap (pre-registered)

- **Mục đích:** So sánh f10 (forward 10-bar return từ entry) với realized return (entry→exit). Xác định exit có cắt mất edge không, fee có ăn hết edge không, tail có được exit giới hạn không.
- **Metrics:** pct_realized_lt_f10, median_gap (f10 − realized), tail5_realized, tail5_f10, fee_adj_f10_median (f10 − fee round-trip).
- **Decision rules (pre-registered):** pct_realized_lt_f10 &gt; 60% → EXIT_TIMING; median_gap &lt; fee_round_trip → FEE_EROSION; tail5_realized &gt; tail5_f10 → EXIT_SAVING_TAIL.
- **Chạy:** `python -m pp_backtest.realized_vs_f10 --ledger pp_backtest/pp_trade_ledger_baseline.csv --use-fetch --fee-bps 30`
- **Kết quả mẫu (804 trades):** pct_realized_lt_f10 57%, median_gap +1.10%, fee_adj_f10_median −0.18%, tail5_realized −7.74%, tail5_f10 −10.88% → diagnoses: EXIT_SAVING_TAIL (exit giới hạn tail tốt hơn hold đến f10). 57% &lt; 60% nên không kết luận EXIT_TIMING; fee sau trừ 0.6% làm median f10 âm → fee erosion đáng kể.

## Regime filter MA200 (pre-registered — Option A only)

- **Mục đích:** Kiểm định PP continuation edge có regime-dependent không. Một rule duy nhất: trade chỉ khi VN30 close &gt; MA200. Không grid search MA50/100/150/200; không tối ưu threshold/slope/breadth.
- **Rule:** Regime_ON = (VN30 close &gt; MA200). Entry chỉ khi Regime_ON == True. Implement: `--regime-ma200` trong `pp_backtest.run`.
- **Chạy:** Full sample: `python -m pp_backtest.run --no-gate --regime-ma200`. Hold-out 2023–2026: `python -m pp_backtest.run --no-gate --regime-ma200 --start 2023-01-01 --end 2026-02-21`. So với baseline cùng period (không regime filter).
- **Decision rule (pre-registered):** PF_holdout &gt; baseline_holdout + 0.05 → regime filter có edge. PF_holdout ~ baseline → no regime alpha. PF_holdout &lt; baseline → regime filter harmful.
- **Lưu ý:** Nếu MA200 filter cũng fail hold-out → continuation breakout không còn mechanical edge ở VN hiện tại; cân nhắc regime filter khác hoặc strategy khác (mean reversion / breakout volatility).
- **Kết quả:** Hold-out PF regime_ma200 = 0.751 &lt; baseline 0.874 → regime filter harmful; no regime alpha từ MA200.

## Timeframe framework (pre-registered for VN)

- **2000–2006:** Không dùng (sơ khai, noise cao). **2007–2011:** Tham khảo cẩn thận (bubble/crash, liquidity khác). **2012–2017:** Extended in-sample (VN30 từ 02/2012). **2018–2022:** In-sample hiện tại. **2023–2026:** Hold-out.
- **Trước liquidity regime test:** Chạy baseline_2012_2022 và baseline_2018_2022. Nếu PF gần nhau → pool 2012–2022; nếu khác nhiều → giữ 2018 in-sample, 2012–2017 là slice riêng. Chi tiết: `docs/RESEARCH_NOTE_TIMEFRAME.md`.

## Liquidity regime test (pre-registered)

- **Mục đích:** Test edge khi filter theo liquidity (30d vol &gt; 126d vol VN30), không MA200. Spec + validation: `pp_backtest/liquidity_regime.py`. Implement: thêm `--regime-liquidity` vào run.py (cùng pattern MA200), công thức volume pre-registered.
- **Decision rule:** Hold-out PF &gt; 0.924 → liquidity regime có edge; &lt;= 0.924 → no alpha. **Thứ tự:** (1) validate `python -m pp_backtest.liquidity_regime`; (2) optional baseline_2012_2022 vs 2018_2022; (3) full sample + hold-out với --regime-liquidity.

## Next experiment (2): MARKET_DD delay k=2 bars (chỉ sau breakdown)

- **Rationale:** Nếu sau min_hold=3 vẫn cần can thiệp regime exit thì mới test. Delay k=2 có thể chỉ replicate reality (T+2.5).
- **Pre-registered:** `delay_market_dd_exit = 2` bars. Không tune 1/2/3/4/5.
- **Điều kiện:** A/B isolate, no gate. Chỉ delay 2–3 bars; không đổi threshold; không convert trim-only vội.
- **Rủi ro:** Tail / MDD — đo tail5 và max_drawdown trong A/B.

## Test còn thiếu: delay-exit A/B (MARKET_DD overlap)

- **Mục tiêu:** What-if hold 3–5 days cho trades MARKET_DD overlap.
- **Cách làm:** Giả lập exit tại bar k=3 hoặc 5 sau exit_signal_date; so median ret, tail loss.
- **Kết luận:** Median cải thiện + tail không nổ → trim-only đáng; tail xấu đi → entry/regime là gốc. Liên quan nhưng tách với experiment MARKET_DD delay k=2.

---

## Anomaly quan trọng: hold_cal_days = 1

- **Median = 1** ở nhiều nhóm = entry hôm nay, exit ngày hôm sau. Thường do: PP entry quá sát resistance, data VN gap, exit trigger intraday, hoặc implementation (close vs open). **Trước khi soften SELL_V4:** phải phân tích nhóm hold_cal_days = 1. Nếu mostly small losses → entry quality problem; big losses → risk management working; mixed → noise regime.
- Script in: `python -m pp_backtest.exit_diagnosis` → cuối output có block **“hold_cal_days == 1”**: `ret.describe()` và `ret by exit_reason (count, mean, median)`.
- **Kết quả mẫu (884 trades):** hold_cal_days==1 có 459 trades; ret mean -0.53%, median -0.71%. Theo exit_reason: MARKET_DD 151 (mean -0.89%, median -1.0%), SELL_V4 13 (mean -1.96%, median -1.38%), STOCK_DD 295 (mean -0.28%, median -0.4%). → Thiên lỗ, mixed; cần đối chiếu thêm với entry quality.

---

## Thứ tự test

1. **Test 3 — reason_set overlap** (đã có): `python -m pp_backtest.exit_diagnosis` — in overlap + **stratified hold_cal_days.describe()**.
2. **Test 1 — hold_cal_days** theo stratum: SELL_V4 single, SELL_V4 multi, MARKET_DD single, MARKET_DD overlap, STOCK_DD (script in trong exit_diagnosis).
3. **Test 2 — MFE/MAE 20 bars** cho từng nhóm: `python -m pp_backtest.exit_mfe_mae [--bars 20]` — in MFE/MAE avg & **median** (median quan trọng hơn avg), và **time_to_MFE / time_to_MAE** (bar 1..20) per stratum. So sánh median MFE vs median MAE; so time_to_MAE vs time_to_MFE để xem path (MAE trước hay MFE trước).
4. **Step 3:** Chỉ sau khi thấy behavior difference mới quyết định: soften SELL_V4 / change priority / hay gate entry.

---

## Flow chuẩn (đã cập nhật theo decision tree final)

- **Step 0:** Freeze entry (PP) tạm thời.
- **Next:** min_hold_bars=3 (baseline_vn_realistic, bar-based); sau đó mới MARKET_DD delay nếu cần.
- **Đã xong:** Gate(50) — no material ROI. SOFT_SELL — rollback. Baseline hiện tại = US-style liquidity.
- **Làm sau:** MARKET_DD overlap delay-exit test nếu cần; trim-only chỉ khi PF > 1 + tail check.
- **Step 4:** Exit diagnosis xong → expand universe theo **characteristics có edge**.

---

## Aggregate MDD -95%

Bỏ MDD này ra khỏi decision logic (không phải portfolio simulation thật).

---

## PP_GIL_V4.2 — Red-flag verification & lock (2026-02)

**Config frozen:** `config_hash=6c8cc91da73e`, `commit=664c46a`, `symbols=14`, `start=2023-01-01`, `end=2026-02-21`, `fee_bps=15`, `slip_bps=5`, `min_hold_bars=0` (VN realistic: use `--min-hold-bars 3` when deploying).

### Red-flag resolution

1. **Liquidity hold-out 0.970 vs 1.192**  
   Cùng config (2023-01-01 → 2026-02-21, 14 tickers, no min_hold_bars): Liquidity-only = **186 trades, PF 0.97**. Số 1.192/125 là từ **Exp3** (Liquidity + MA50 + Demand thrust), không phải Exp1. → Inconsistency do nhầm experiment; đã xác nhận bằng run có `[run]` in đủ start/end/config_hash.

2. **Exp1 vs Exp3 giống nhau (125, 1.192)**  
   Demand thrust gate **có tác dụng**: `filtered_by_demand_thrust: 74`. Exp1 (Liquidity only) = 186 trades, PF 0.97; Exp3 = 125 trades, PF 1.192. Cần log `filtered_by_*` mỗi run (đã thêm trong `run.py` / `backtest.py`).

3. **median_hold_days ~2.0 vs min_hold_bars=3**  
   Ledger: `hold_cal_days` = calendar days (entry_date → exit_date); `hold_trading_bars` = trading days. KPI: median_hold_bars từ `hold_trading_bars`. Với `min_hold_bars=0` (default) median_hold_bars=1, median_hold_days=2 là nhất quán. Khi chạy `--min-hold-bars 3`, KPI phải in `min_hold_bars` từ config và median_hold_bars ≥ 3.

### Verified 4-experiment table (hold-out 2023–2026)

| Experiment | trades | PF (KPI) | filtered_by_liquidity | filtered_by_ma50 | filtered_by_demand_thrust | filtered_by_tightness |
|------------|--------|----------|------------------------|-----------------|---------------------------|----------------------|
| Exp1 Liquidity only | 186 | 0.97 | 216 | — | — | — |
| Exp2 + MA50 | 171 | 1.01 | 216 | 17 | — | — |
| Exp3 + Demand thrust | 125 | 1.19 | 216 | 17 | 74 | — |
| Exp4 + Tightness | 106 | **1.29** | 216 | 17 | 74 | 22 |

**Lock candidate:** PP_GIL_V4.2 = Exp4 (Liquidity + MA50 + Demand thrust + Tightness).

---

### Robustness & final test (Exp4, PP_GIL_V4.2)

**Step A — Fee robustness (hold-out 2023–2026, min_hold_bars=0):**

| RT cost | fee_bps | slip_bps | trades | PF | tail5 |
|---------|---------|----------|--------|-----|------|
| 20 bps | 15 | 5 | 106 | 1.29 | -6.45% |
| 30 bps | 25 | 5 | 106 | 1.16 | -6.64% |
| 40 bps | 35 | 5 | 106 | 1.05 | -6.83% |

→ Edge survives 30 bps (PF > 1.05) và gần ngưỡng ở 40 bps.

**Step B — VN realism (min_hold_bars=3, RT 30 bps, 2023–2026):**

- trades=104, **PF=0.97**, tail5=-9.10%, median_hold_bars=3.0 ✓  
- **Kết luận:** Với T+2.5 (min_hold=3) + cost 30 bps, edge **không** survive (PF < 1.0).

**Step C — Final untouched test (2025-01-01 → 2026-02-21, 1 lần duy nhất):**

- Config: Exp4 + min_hold_bars=3, fee 25, slip 5.  
- trades=**28**, **PF=0.17**, tail5=-10.15%, median_hold_bars=3.0.  
- trades < 40 (noise), PF << 1.0.

**Decision rule final:**

- PF_final > 1.05 với RT 30 bps + min_hold=3 → deployable candidate.  
- PF_final 1.00–1.05 → micro pilot, discretionary overlay.  
- **PF_final < 1.00** → edge không survive cost + realism → **không deploy cơ học**.

→ **Kết luận:** PP_GIL_V4.2 lock đúng cấu hình research; với cost thực tế (30 bps) và VN T+2.5 (min_hold_bars=3), edge không đạt ngưỡng deploy. Không pilot cơ học; nếu muốn thử thì chỉ micro size + CPP/avoid-extended (phase 2) sau khi có thêm data.

---

### Exp4 — Định nghĩa 4 gates và tại sao fail với cost thực tế

Exp4 = PP_GIL_V4 baseline + **4 gates xếp chồng** (chỉ entry khi cả 4 đều pass). Thứ tự áp dụng:

| # | Gate | Định nghĩa kỹ thuật | Logic (sách / research) |
|---|------|---------------------|--------------------------|
| **1** | **Liquidity regime** | VN30: 30-day rolling volume > 126-day rolling volume | Chỉ trade khi thanh khoản mở rộng — "fuel" cho continuation. Gate duy nhất pass hold-out một mình (Liquidity-only PF ~0.97). |
| **2** | **Above MA50** | close > MA50 (cổ phiếu) | Gil: trên MA50 = under institutional support; dưới MA50 = no man's land, bounce thường là mean reversion. Loại PP trong downtrend / recovery yếu. |
| **3** | **Demand thrust** | close > close[-1] **và** close ≥ high − 0.3×(high−low) | Close trong **top 30%** biên độ ngày → demand thật cuối phiên, không phải doji/weak close. PP = effort + demand. |
| **4** | **Tightness** | ≥ 2 trong 5 phiên trước có volume < MA20(volume) | "Quiet period" trước breakout — supply đã cạn. Volume cao liên tục = còn supply → breakout dễ fade. |

**Gross edge có thật nhưng mỏng:**  
PF ~1.29 (14 symbols, hold-out 2023–2026, 20 bps, min_hold=0) cho thấy edge gross tồn tại. **Nếu giao dịch không phí** (hoặc phí rất thấp) thì edge vẫn có; nhưng:

- **30 bps RT + min_hold=3** (14 symbols) → PF ~0.97 (edge bị cost xóa).
- **30 bps RT + min_hold=3, 80 symbols** → PF ~0.77 (broad universe không cứu được).

**Tại sao 4 gates vẫn fail với cost thực tế:**  
Median gross edge mỗi trade chỉ ~0.5–0.8%. Với 30 bps round-trip + T+2.5 (hold tối thiểu 3 bar), mỗi trade phải "trả" phí đủ lâu; continuation VN thường decay nhanh sau bar 2–3 → **mismatch** giữa strategy (continuation) và đặc tính thị trường (short bursts). Edge tồn tại nhưng **không đủ dày** để deploy cơ học.

**Kết luận một câu:** Exp4 là bản "sạch nhất" và book-faithful nhất của PP_GIL_V4; gross edge có, nhưng quá mỏng so với cost structure VN. Deploy được cần: cost thấp hơn thị trường, hoặc entry selectivity cao hơn (trade ít, conviction cao), hoặc strategy có gross edge dày hơn (ví dụ Low-Vol Retest / U&R).

---

## Delay arming (exit_armed_after) — pre-registered

**Evidence:** Cùng entry Exp4 + cost + hold-out, fixed 10-bar exit → PF 0.97 → 1.22; median_hold_bars=10; SELL_V4/MARKET_DD/STOCK_DD = 0. ⇒ Alpha ở entry; exit hiện tại cắt trend sớm.

**Kết luận đúng mức:** Entry Exp4 có alpha ở horizon ~10 bars. Exit stack đang risk control quá sớm → triệt lợi nhuận trung vị. **Không** bỏ DD/SELL_V4; cần **delay arming**: Phase 1 (bars 1..N-1) chỉ UglyBar (+ hard stop nếu thêm sau); Phase 2 (từ bar N) bật full SELL_V4 + DD.

**Tail risk:** Fixed 10-bar → tail5 = -13.04%. Nhiệm vụ: exit giữ PF ~1.2 nhưng cải thiện tail5 (ít xấu hơn -13%).

### Lệnh

- **Oracle (fixed exit):** `python -m pp_backtest.run --exit-fixed-bars 10` (cùng gate/Exp4 nếu dùng gate).
- **Delay arming:** `python -m pp_backtest.run --exit-armed-after N`  
  - Bars 1..N-1: chỉ thoát bởi **UglyBar** (sell_ugly_only).  
  - Từ bar N: full stack (SELL_V4, MARKET_DD, STOCK_DD, UglyBar).
- **Test ladder (pre-registered, không grid):** N = 5, 10, 15. So với: full exit (0), fixed 10 (oracle).  
  **Decision:** Nếu arm_after=10 đạt PF ≥ 1.15 và tail5 cải thiện rõ (> -13%) → chọn.

### 4 dòng experiment (pre-registered)

| # | Mô tả | Lệnh |
|---|--------|------|
| 1 | Exp4 + full exit (baseline) | `python -m pp_backtest.run` (cùng start/end/watchlist) |
| 2 | Exp4 + fixed 10 bars (oracle) | `python -m pp_backtest.run --exit-fixed-bars 10` |
| 3 | Exp4 + armed-after 10, Phase1 chỉ UglyBar (no DD) | `python -m pp_backtest.run --exit-armed-after 10` |
| 4 | (Sau khi 3 ổn) armed-after 10 + full DD + SELL_V4 | Cùng lệnh 3 — Phase 2 đã bật full stack |

**Metrics bắt buộc:** PF, tail5, max_drawdown, avg_ret/trade, win_rate, avg_win, avg_loss, median_hold_bars. CSV có cột `tail5`, `median_hold_bars`; aggregate in sau run: `[aggregate] tail5=... median_hold_bars=...`. Chi tiết ledger: `python -m pp_backtest.kpi_from_ledger pp_backtest/pp_trade_ledger.csv`.

---

### 5 audit checks (bắt buộc trước khi tin PF)

| Check | Nội dung | Status |
|-------|----------|--------|
| **A** | UglyBar chỉ dùng dữ liệu bar hiện tại (O,H,L,C,V) + ATR14, MA50(vol) — không lookahead | ✅ signals.py: ugly_bar từ c,h,l,v, c.shift(1), a14, sma(v,50); không .shift(-1) |
| **B** | Phase 1 exit phải tuân min_hold_bars (UglyBar ở bar 1–2 với min_hold=3 → không exit) | ✅ backtest: `exit_now = phase1_exit and (min_hold <= 0 or bars_held >= min_hold)` |
| **C** | Phase switching đúng mốc N: bars_held 1-based, Phase 1 = 1..N-1, Phase 2 = bar N+ | ✅ backtest: bars_held = i - entry_i + 1; Phase 1 khi bars_held < N |
| **D** | Phase 2 exit priority: UglyBar (tail) thắng SELL_V4/DD khi ghi ledger | ✅ _first_true_reason: UGLY_BAR > SELL_V4 > MARKET_DD > STOCK_DD |
| **E** | tail5 thống nhất: per-trade return **net fee/slip**, aggregate = 1 tail5 toàn ledger | ✅ ret = (exit_px/entry_px)-1 với px đã trừ fee/slip; tail5 = nanpercentile(all_ledger["ret"], 5) |

---

### Quy tắc chọn N (pre-registered, mechanical — không overfit)

Dùng **validation window 2023–2024** (không dùng từ “holdout” khi chọn N để tránh adaptive overfit). Chọn **N nhỏ nhất** trong {5, 10, 15} thỏa **đồng thời** 3 điều kiện trên **validation (2023–2024)**:

1. **PF_validation(N) ≥ 1.15** — giữ alpha.
2. **tail5_validation(N) ≥ max(tail5_fixed10 + 3%, -10%)** — cải thiện tail so với oracle fixed 10 (tail5_fixed10 ≈ -13.04%); floor -10%.
3. **median_hold_bars(N) ≥ 7** — đủ “runway” để capture edge ~10 bar.

Nếu không có N nào thỏa → xem Case A / Case B bên dưới. Không tune N ngoài {5,10,15}.

---

### Dự đoán trước (để biết đang test cái gì)

Với kết quả đã có: fixed 10 bars PF≈1.22, tail5≈-13%; full exit PF≈0.97. Kỳ vọng ladder:

| N  | Kỳ vọng |
|----|--------|
| 5  | tail5 tốt hơn, PF có thể chưa lên đủ (exit vẫn bật sớm). |
| 10 | sweet spot — match horizon ~10 bar. |
| 15 | PF có thể cao hơn chút, tail5 xấu hơn (ít cắt tail). |

Nếu N=10 không thắng N=5 về PF đủ rõ → Phase 2 exits vẫn “đè” → vào Case A (remove/soften DD).

---

### Cách đọc kết quả ladder

- **PF vs oracle:** Baseline full exit PF≈0.97, fixed 10 PF≈1.22. Armed-after mục tiêu tiệm cận 1.2 nhưng tail tốt hơn.
- **tail5 & max_drawdown:** Fixed 10 tail5 = -13.04%. Armed-after phải kéo tail5 lên (ít âm hơn), MDD giảm.
- **median_hold_bars:** Nếu vẫn ~2–3 với N=10 → Phase 2 vẫn thoát sớm, chưa “buy time”. Nếu ~8–12 với N=10 → đúng thesis “give it room”.

---

### Nếu ladder không cho kết quả đẹp (next steps, pre-registered)

**Case A: PF vẫn ~1.0 dù N=10/15**  
→ Phase 2 exits vẫn đánh sập expectancy. Hướng xử lý (chọn 1, không tune lặt vặt):

- Remove DD nhưng giữ SELL_V4 (hoặc ngược lại) sau khi armed — DD market/stock có thể quá nhạy VN (whipsaw).
- Làm DD “soft” sau N: ví dụ chỉ exit DD nếu 2 phiên liên tiếp hoặc DD_count vượt ngưỡng + close weakness (lock rule trước, không backfit).

**Case B: PF gần oracle nhưng tail vẫn xấu**  
→ UglyBar-only chưa đủ tail stop trong VN. Thêm **1** hard stop duy nhất trong Phase 1 (pre-registered):

- `close < MA50` **hoặc** `loss > X%` (chọn **một**, không cả hai).
- X% lock trước theo thị trường VN (ví dụ 7–8%), không backfit.

---

### Checklist chạy (tránh config drift)

Mỗi run in `[run]` đủ:

- **config_hash**, **commit**
- **start / end**, **symbols** (count + tickers)
- **fee_bps**, **slip_bps**, **min_hold_bars**
- **entry_gates** (liquidity, +ma50, +demand_thrust, +tightness khi dùng Exp4)
- **exit_mode** = `full` | `fixed_10` | `armed_5` | `armed_10` | `armed_15`

Sau mỗi run copy **một bảng gọn** (aggregate từ ledger hoặc từ CSV):

| Run | trades | PF | tail5 | max_drawdown | median_hold_bars | avg_ret | win_rate | avg_win | avg_loss |
|-----|--------|-----|-------|--------------|------------------|---------|----------|---------|----------|
| baseline (full) | 48 | 0.39 | -6.34% | -50.12% | 1.0 | -1.32% | 29.17% | 2.87% | -3.04% |
| fixed_10 | 42 | 0.57 | -13.21% | -63.05% | 10.0 | -1.74% | 47.62% | 4.79% | -7.69% |
| armed_5 | 45 | 0.43 | -8.64% | -60.44% | 5.0 | -1.57% | 33.33% | 3.62% | -4.17% |
| armed_10 | 43 | 0.43 | -13.16% | -71.14% | 10.0 | -2.43% | 37.21% | 4.85% | -6.75% |
| armed_15 | 40 | 0.47 | -15.38% | -75.52% | 15.0 | -2.58% | 32.50% | 7.10% | -7.24% |

**Validation 2023–2024 (Exp4, 13 symbols sau skip TCX):** Không có N nào thỏa rule (PF_validation ≥ 1.15, tail5 ≥ -10%, median_hold_bars ≥ 7) — toàn bộ PF < 1. → **Case A:** Phase 2 exits vẫn đè expectancy trên window này; hoặc 2023–2024 là regime yếu cho setup. **Bước tiếp:** (1) Final test 2025–2026 vẫn chạy 1 lần với N=10 (match horizon) để xem out-of-sample; (2) hoặc test remove/soften DD (Case A) rồi chạy lại ladder.

---

### Final untouched test window (dứt điểm)

1. **Validation (2023–2024):** Chạy ladder N=5/10/15 với **start=2023-01-01 end=2024-12-31** (cùng watchlist, fee, slip, min_hold_bars, Exp4 gates). Chọn N theo quy tắc (PF_validation ≥ 1.15, tail5_validation ≥ max(tail5_fixed10+3%, -10%), median_hold_bars ≥ 7).
   - Lệnh mẫu (Exp4 = liquidity+ma50+demand_thrust+tightness, gate ON):  
     `python -m pp_backtest.run --start 2023-01-01 --end 2024-12-31` (baseline)  
     `python -m pp_backtest.run --start 2023-01-01 --end 2024-12-31 --exit-fixed-bars 10`  
     `python -m pp_backtest.run --start 2023-01-01 --end 2024-12-31 --exit-armed-after 5`  
     idem `--exit-armed-after 10`, `--exit-armed-after 15`
2. **Final (đúng 1 lần):** Chạy **một lần** với N đã chọn: **start=2025-01-01 end=2026-02-21** (cùng watchlist + gates).  
   - `python -m pp_backtest.run --start 2025-01-01 --end 2026-02-21 --exit-armed-after <N>`
3. **Decision:** Final pass → deploy candidate. Fail → không deploy cơ học (xem “Ladder đẹp nhưng final fail” bên dưới).

---

### Định nghĩa “tail chấp nhận được” (lock, mechanical)

**Đã chọn Option 1 (simple), lock:**

- **tail5_final ≥ -10%**
- **max_drawdown_final ≥ -25%** (ngưỡng MDD chịu được; -25% lock trước, không backfit)

Final pass = PF_final ≥ 1.05 **và** tail5_final ≥ -10% **và** max_drawdown_final ≥ -25%. (Có thể bổ sung Option 2 sau nếu muốn relative: tail5_final ≥ tail5_full_exit + 2% — nhưng hiện tại lock Option 1.)

---

### Ladder đẹp nhưng final fail — diễn giải đúng

Đừng coi là “strategy hỏng”. Đó là outcome hợp lệ:

- Edge **non-stationary** theo regime (2025–2026 khác 2023–2024).
- Liquidity/entry filter bắt đúng 2023–2024 nhưng trượt 2025–2026.
- Tail events **cluster** ở 2025 (structural shocks).

**Hướng đúng (pre-registered):**

- **Walk-forward:** validation window trượt (ví dụ 2024–2025 chọn N, final 2026) — chỉ khi đã lock quy trình.
- **Case B:** Thêm 1 hard stop Phase 1 (close < MA50 **hoặc** loss > X%, X lock trước) — pre-register rồi mới test