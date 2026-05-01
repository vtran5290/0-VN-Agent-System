# Mark's Brain — Export for Building a "Wyckoff Brain" (Same Structure)

**Purpose:** Give this document to Gemini (or another LLM) to generate a **detailed prompt/spec** that builds a **Wyckoff Brain** in the same format as Mark's Brain: pipeline doc + config YAML + engine layers (filters → setups → triggers → risk → exits).

---

## Part 1 — Mark's Brain: Conceptual Doc (Reference)

### Source: `minervini_backtest/docs/MARK_BRAIN.md`

# MARK_BRAIN — Stock selection + timing theo Mark Minervini (bản để code/backtest)

Mục tiêu file này:

- Đóng gói "Brain của Mark" ở mức **đủ cụ thể để lập trình / backtest**, nhưng **không phải clone 100% sách**.
- Nhắc lại: **Mark không phải "breakout system thuần kỹ thuật"**. Ông là **stock selection system + timing execution**:
  - FA + leadership (chọn đúng cổ phiếu)
  - Trend Template (đúng giai đoạn uptrend)
  - VCP/pivot (chọn điểm bấm nút)
  - Risk sizing / concentration (không tự sát)

File này dùng làm **tài liệu tham chiếu** khi thiết kế các Phase 2+ (FA-cohort, SEPA-style backtest), tránh bị lệch sang tối ưu trigger thuần kỹ thuật.

---

## 1. SEPA pipeline (ranking / stock selection)

Theo cả hai sách, "não" của Mark xoay quanh việc **lọc dần dần universe** cho đến khi chỉ còn vài mã "superperformer candidates".

Ở mức có thể code/backtest, pipeline có thể tóm gọn thành 4 tầng:

- **(1) Trend Template / Stage 2 uptrend**
  - Chỉ xét các mã:
    - Giá nằm trên một số đường trung bình chính (50/150/200 ngày) với thứ tự "đúng".
    - 200-day MA có độ dốc dương (đã tăng được một thời gian, không phải mới quay lên 1–2 ngày).
    - Giá đang nằm tương đối gần đỉnh 52-week (không phải mới hồi từ đáy).
    - Relative Strength cao so với thị trường/nhóm ngành.
  - Ý tưởng: chỉ chơi **Stage 2 uptrend mạnh**, không bắt đáy.

- **(2) Fundamental "High Growth Cohort" filter**
  - Mục tiêu: loại bỏ **~95% cổ phiếu "bình thường"**, chỉ giữ lại nhóm có "superperformance DNA".
  - Các trục chính (có thể mã hóa được):
    - **Earnings power:** tăng trưởng EPS (YoY/ QoQ) cao và có **dấu hiệu tăng tốc**, không chỉ một quý đơn lẻ.
    - **Sales growth:** doanh thu tăng mạnh và/hoặc tăng tốc.
    - **Margins:** biên lợi nhuận (gộp / hoạt động) giữ vững hoặc mở rộng so với cùng kỳ.
    - **Return metrics:** ROE/ROIC ở mức "cao" trong ngành.
    - **Balance sheet:** nợ không quá nặng (debt discipline).
  - Đây là nơi SEPA "đánh dấu" các mã có xác suất trở thành **future superperformers**.

- **(3) Leadership & supply–demand profile**
  - Trong nhóm FA-pass, Mark vẫn ưu tiên:
    - **Industry / sector leadership:** top performer trong nhóm ngành.
    - **Price leadership / RS:** nằm trong nhóm dẫn đầu về hiệu suất giá.
    - **Supply / float / accumulation:** số lượng cổ phiếu lưu hành không quá lớn, có dấu hiệu dòng tiền tổ chức tích lũy (tight ranges + volume pattern).
  - Mức này phần lớn mang tính "ranking" hơn là rule cứng → trong backtest có thể xấp xỉ bằng:
    - RS ranking trong universe.
    - Ngưỡng float / vốn hóa / turnover tối thiểu và tối đa.

- **(4) Manual review / prioritization**
  - Trong thực tế, Mark dùng:
    - Catalyst (sản phẩm mới, câu chuyện đặc biệt…).
    - Chất lượng báo cáo, guidance, estimate revisions.
    - Rủi ro thanh khoản, độ "thin" của giá.
  - Tầng này rất khó tái tạo trong backtest → với engine hiện tại có thể **bỏ qua / xấp xỉ** bằng các ngưỡng đơn giản (liquidity, vốn hóa, RS).

**Điểm chốt:**  
Trong "não" của Mark, **Stock Selection (SEPA) là lõi**. Breakout chỉ là cách **kích hoạt** mua khi đã chọn xong "đúng cổ phiếu".

---

## 2. VCP / Pivot — "cửa bấm nút"

Sau khi đã có danh sách cổ phiếu đạt:

- Stage 2 uptrend (Trend Template)
- FA + leadership (high-growth / leaders)

Mark mới dùng **Volatility Contraction Pattern (VCP)** và **pivot** để quyết định **chính xác khi nào** bấm nút.

Các đặc trưng chính có thể mã hóa:

- **Volatility co lại từ trái sang phải**
  - Mẫu hình giá có **2–6 "contraction"** rõ rệt, mỗi nhịp dao động **nhỏ hơn** nhịp trước đó.
  - Biên độ các nhịp giảm dần (ví dụ 18% → 12% → 6%), thể hiện việc **cung dần cạn**, người bán ít hẳn đi.

- **Volume "towel wrung dry"**
  - Trong các nhịp co, volume **khô hẳn** (dưới trung bình) → supply cạn.
  - Khi breakout qua pivot, volume **tăng vọt** so với trung bình (thrust) → dòng tiền mới vào.

- **Pivot buy point**
  - Một "điểm xoay" trong mẫu hình, thường là:
    - Đỉnh của nhịp co cuối.
    - Hoặc điểm mà nếu giá vượt qua, toàn bộ base trước đó bị "phá" theo hướng bullish.
  - Entry = **buy khi giá vượt pivot**, thường với:
    - price action mạnh (gần high của ngày).
    - volume lớn hơn bình thường.

Trong backtest:

- VCP/pivot có thể được xấp xỉ bằng:
  - Các proxy như **tight-range window + volume filter** (như engine đã làm cho M9/M10).
  - Thêm các điều kiện "co biên độ" (ATR giảm dần, range giảm dần).
- Tuy nhiên, **nếu universe không được FA-filter trước**, thì VCP/pivot **không thể tự cứu** chất lượng cổ phiếu.

**Điểm chốt:**  
VCP/pivot **không phải** edge độc lập. Nó là **"cửa bấm nút"** cho **cohort đã được SEPA lọc sẵn**.

---

## 3. Risk sizing & concentration

Mark nhấn rất mạnh vào **risk management**, không thua lỗ quá sâu trên từng lệnh và trên toàn portfolio.

Các nguyên tắc định lượng (ở mức có thể backtest):

- **Risk per trade:** thường trong khoảng **1–2% vốn** trên mỗi ý tưởng (tùy khẩu vị).  
  - Ví dụ tài khoản 100 đơn vị vốn:
    - Risk 1% = 1 đơn vị / trade.
    - Risk 2% = 2 đơn vị / trade.
  - Position size = risk_amount / (entry_price – stop_price).

- **Cut loss nhanh, không để lỗ "phình to"**
  - Stop thường đặt trong vùng **7–10%** dưới giá mua (tùy cấu trúc base và volatility).
  - Ý tưởng: **giữ lỗ nhỏ, để thắng lớn**, không để một vài lệnh xóa hết chuỗi thắng.

- **Concentration vs diversification**
  - Mark chấp nhận **vị thế lớn** (20–25% tài khoản) ở "best names".
  - Không cần quá nhiều mã; vài superperformers đủ tạo khác biệt.
  - Tuy nhiên, tránh:
    - Overconcentration vào các tên chất lượng thấp.
    - "Di-worsification" (chia nhỏ quá mức vào tên trung bình).

---

## Part 2 — Engine Structure (Mark's Brain)

### Source: `minervini_backtest/README.md` (condensed)

**Pipeline:** Universe → **Filter** → **Setup** → **Trigger** → **Risk** → **Exit** → Sizing.

| Layer   | Role | Mark examples |
|--------|------|----------------|
| Filter | Reduce universe to "stage" / regime | TT_Strict, TT_Lite (MA50>MA200, slope, price vs 52w high) |
| Setup  | Pattern that must be present before entry | VCP (volatility contraction), 3-week tight |
| Trigger| Exact entry condition | Breakout (high of base), Retest (close back above pivot within N bars) |
| Risk   | Stop, position size | stop_pct, atr_k, risk_pct (R-multiple) |
| Exit   | When to close | hard_stop, trend_break_ma, fail_fast_days, time_stop_days, take_partial_r, trail_ma |

**Config shape (YAML):** one file per "version" (e.g. M1, M4). Fields: name, description, tt, ma200_slope_bars, setup, lookback_base, vol_mult, close_strength, stop_pct, atr_k, risk_pct, exits (hard_stop, trend_break_ma, fail_fast_days, time_stop_days, take_partial_r, trail_ma), fee_bps, slippage_bps, min_hold_bars, and trigger-specific (e.g. use_retest, retest_max_bars, max_undercut_pct).

---

## Part 3 — Example Config (M4)

### Source: `minervini_backtest/configs/M4.yaml`

```yaml
# M4 — VCP + Retest Entry (2-step, reduce false breakout)
name: M4
description: "TT_Strict or Lite + VCP; Breakout then buy on retest within 1-5 bars; Stop under retest low; Fail-fast + MA50 break"

tt: lite
ma200_slope_bars: 20

setup: vcp

lookback_base: 40
vol_mult: 1.5
close_strength: true

stop_pct: 0.05
atr_k: 2.0
risk_pct: 0.006

exits:
  hard_stop: true
  trend_break_ma: 50
  fail_fast_days: 3
  time_stop_days: 0
  take_partial_r: null
  trail_ma: null
  climax_proxy: false

fee_bps: 20
slippage_bps: 5
min_hold_bars: 0

# 2-step: only enter when retest succeeds
use_retest: true
retest_max_bars: 5
max_undercut_pct: 0.02
```

---

## Part 4 — Signal Description (for Chart / AFL)

Mark's Brain is also exported as a **signal description** (layman + step-by-step logic) for AmiBroker AFL or similar:

- **Layman:** Uptrend (MA50, MA200, slope) → VCP (ATR contraction, volume dry-up) → Breakout (pivot = HH40, volume thrust, strong close) → Retest within 5 bars (low ≥ pivot×0.98, close > pivot) → Buy; exits: hard stop, fail-fast 3d, trend break MA50.
- **Step-by-step:** Gate 1 (TT Lite), Gate 2 (VCP proxy), Gate 3 (Breakout), Gate 4 (Retest), then exit rules with parameters (stop_pct, fail_fast_days, trend_break_ma).

---

## Part 5 — What to Ask Gemini (Wyckoff Brain)

**Request to paste into Gemini:**

---

Using the **Mark's Brain** export above as the **exact template**, produce a **Wyckoff Brain** spec that can be implemented in the same codebase structure (filters → setups → triggers → risk → exits, YAML configs, bar-by-bar engine).

Include:

1. **Conceptual doc (like MARK_BRAIN.md):**
   - Wyckoff's core idea in 3–5 sections (e.g. Accumulation / Distribution phases, Springs / Upthrusts, Sign of Strength / Sign of Weakness, volume context, cause and effect).
   - What corresponds to "stock selection" vs "timing" in Wyckoff terms.
   - Clear **pipeline layers** that map to: Filter (e.g. phase / structure), Setup (e.g. accumulation pattern), Trigger (e.g. spring breakout, SOS), Risk, Exit.
   - Risk and concentration principles in Wyckoff style (if any).

2. **Engine structure table:** Same columns as Mark (Filter, Setup, Trigger, Risk, Exit) with Wyckoff-specific names and short descriptions.

3. **At least one full YAML config example** (e.g. W1 or W4) with the same schema style as M4: name, description, filter params, setup params, trigger params (e.g. spring_confirm_bars, sos_volume_mult), risk (stop_pct, atr_k, risk_pct), exits, fee_bps, slippage_bps, min_hold_bars.

4. **Signal description for chart/AFL:** One "layman" paragraph and one "step-by-step logic" list (gates) so a Wyckoff Brain can be coded in AmiBroker or similar, mirroring the M4 signal description format.

5. **VN adaptation note:** One short paragraph on what might need to change for Vietnam (liquidity, regime, data) when implementing Wyckoff Brain, analogous to the Phase 2 / FA-first note in Mark's Brain.

Output as a single markdown file that can be dropped into `docs/WYCKOFF_BRAIN.md` and used to add `configs/W1.yaml` (and optionally W2, W3, W4) and code in the same engine (filters/setups/triggers/risk/exits).

---

End of export.
