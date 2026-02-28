# MARK_BRAIN — Stock selection + timing theo Mark Minervini (bản để code/backtest)

Mục tiêu file này:

- Đóng gói “Brain của Mark” ở mức **đủ cụ thể để lập trình / backtest**, nhưng **không phải clone 100% sách**.
- Nhắc lại: **Mark không phải “breakout system thuần kỹ thuật”**. Ông là **stock selection system + timing execution**:
  - FA + leadership (chọn đúng cổ phiếu)
  - Trend Template (đúng giai đoạn uptrend)
  - VCP/pivot (chọn điểm bấm nút)
  - Risk sizing / concentration (không tự sát)

File này dùng làm **tài liệu tham chiếu** khi thiết kế các Phase 2+ (FA-cohort, SEPA-style backtest), tránh bị lệch sang tối ưu trigger thuần kỹ thuật.

---

## 1. SEPA pipeline (ranking / stock selection)

Theo cả hai sách, “não” của Mark xoay quanh việc **lọc dần dần universe** cho đến khi chỉ còn vài mã “superperformer candidates”.

Ở mức có thể code/backtest, pipeline có thể tóm gọn thành 4 tầng:

- **(1) Trend Template / Stage 2 uptrend**
  - Chỉ xét các mã:
    - Giá nằm trên một số đường trung bình chính (50/150/200 ngày) với thứ tự “đúng”.
    - 200-day MA có độ dốc dương (đã tăng được một thời gian, không phải mới quay lên 1–2 ngày).
    - Giá đang nằm tương đối gần đỉnh 52-week (không phải mới hồi từ đáy).
    - Relative Strength cao so với thị trường/nhóm ngành.
  - Ý tưởng: chỉ chơi **Stage 2 uptrend mạnh**, không bắt đáy.

- **(2) Fundamental “High Growth Cohort” filter**
  - Mục tiêu: loại bỏ **~95% cổ phiếu “bình thường”**, chỉ giữ lại nhóm có “superperformance DNA”.
  - Các trục chính (có thể mã hóa được):
    - **Earnings power:** tăng trưởng EPS (YoY/ QoQ) cao và có **dấu hiệu tăng tốc**, không chỉ một quý đơn lẻ.
    - **Sales growth:** doanh thu tăng mạnh và/hoặc tăng tốc.
    - **Margins:** biên lợi nhuận (gộp / hoạt động) giữ vững hoặc mở rộng so với cùng kỳ.
    - **Return metrics:** ROE/ROIC ở mức “cao” trong ngành.
    - **Balance sheet:** nợ không quá nặng (debt discipline).
  - Đây là nơi SEPA “đánh dấu” các mã có xác suất trở thành **future superperformers**.

- **(3) Leadership & supply–demand profile**
  - Trong nhóm FA-pass, Mark vẫn ưu tiên:
    - **Industry / sector leadership:** top performer trong nhóm ngành.
    - **Price leadership / RS:** nằm trong nhóm dẫn đầu về hiệu suất giá.
    - **Supply / float / accumulation:** số lượng cổ phiếu lưu hành không quá lớn, có dấu hiệu dòng tiền tổ chức tích lũy (tight ranges + volume pattern).
  - Mức này phần lớn mang tính “ranking” hơn là rule cứng → trong backtest có thể xấp xỉ bằng:
    - RS ranking trong universe.
    - Ngưỡng float / vốn hóa / turnover tối thiểu và tối đa.

- **(4) Manual review / prioritization**
  - Trong thực tế, Mark dùng:
    - Catalyst (sản phẩm mới, câu chuyện đặc biệt…).
    - Chất lượng báo cáo, guidance, estimate revisions.
    - Rủi ro thanh khoản, độ “thin” của giá.
  - Tầng này rất khó tái tạo trong backtest → với engine hiện tại có thể **bỏ qua / xấp xỉ** bằng các ngưỡng đơn giản (liquidity, vốn hóa, RS).

**Điểm chốt:**  
Trong “não” của Mark, **Stock Selection (SEPA) là lõi**. Breakout chỉ là cách **kích hoạt** mua khi đã chọn xong “đúng cổ phiếu”.

---

## 2. VCP / Pivot — “cửa bấm nút”

Sau khi đã có danh sách cổ phiếu đạt:

- Stage 2 uptrend (Trend Template)
- FA + leadership (high-growth / leaders)

Mark mới dùng **Volatility Contraction Pattern (VCP)** và **pivot** để quyết định **chính xác khi nào** bấm nút.

Các đặc trưng chính có thể mã hóa:

- **Volatility co lại từ trái sang phải**
  - Mẫu hình giá có **2–6 “contraction”** rõ rệt, mỗi nhịp dao động **nhỏ hơn** nhịp trước đó.
  - Biên độ các nhịp giảm dần (ví dụ 18% → 12% → 6%), thể hiện việc **cung dần cạn**, người bán ít hẳn đi.

- **Volume “towel wrung dry”**
  - Trong các nhịp co, volume **khô hẳn** (dưới trung bình) → supply cạn.
  - Khi breakout qua pivot, volume **tăng vọt** so với trung bình (thrust) → dòng tiền mới vào.

- **Pivot buy point**
  - Một “điểm xoay” trong mẫu hình, thường là:
    - Đỉnh của nhịp co cuối.
    - Hoặc điểm mà nếu giá vượt qua, toàn bộ base trước đó bị “phá” theo hướng bullish.
  - Entry = **buy khi giá vượt pivot**, thường với:
    - price action mạnh (gần high của ngày).
    - volume lớn hơn bình thường.

Trong backtest:

- VCP/pivot có thể được xấp xỉ bằng:
  - Các proxy như **tight-range window + volume filter** (như engine đã làm cho M9/M10).
  - Thêm các điều kiện “co biên độ” (ATR giảm dần, range giảm dần).
- Tuy nhiên, **nếu universe không được FA-filter trước**, thì VCP/pivot **không thể tự cứu** chất lượng cổ phiếu.

**Điểm chốt:**  
VCP/pivot **không phải** edge độc lập. Nó là **“cửa bấm nút”** cho **cohort đã được SEPA lọc sẵn**.

---

## 3. Risk sizing & concentration

Mark nhấn rất mạnh vào **risk management**, không thua lỗ quá sâu trên từng lệnh và trên toàn portfolio.

Các nguyên tắc định lượng (ở mức có thể backtest):

- **Risk per trade:** thường trong khoảng **1–2% vốn** trên mỗi ý tưởng (tùy khẩu vị).  
  - Ví dụ tài khoản 100 đơn vị vốn:
    - Risk 1% = 1 đơn vị / trade.
    - Risk 2% = 2 đơn vị / trade.
  - Position size = risk_amount / (entry_price – stop_price).

- **Cut loss nhanh, không để lỗ “phình to”**
  - Stop thường đặt trong vùng **7–10%** dưới giá mua (tùy cấu trúc base và volatility).
  - Ý tưởng: **giữ lỗ nhỏ, để thắng lớn**, không để một vài lệnh xóa hết chuỗi thắng.

- **Concentration vs diversification**
  - Mark chấp nhận **vị thế lớn** (20–25% tài khoản) ở “best names”.
  - Không cần quá nhiều mã; vài superperformers đủ tạo khác biệt.
  - Tuy nhiên, tránh:
    - Overconcentration vào các tên chất lượng thấp.
    - “Di-worsification” (chia nhỏ quá mức vào tên trung bình).

Trong bối cảnh lab hiện tại (PP C2 m0 / Minervini engine):

- Các rule về **risk_pct**, **K slots**, **kill-switch** có thể được thiết kế sao cho:
  - Per-trade risk không vượt quá ~1–2% equity.
  - Tổng exposure và drawdown được kiểm soát ngay cả khi win rate thấp.

---

## 4. Ý nghĩa cho lab VN Agent System

1. **Backtest Minervini phase 1** trước đây chủ yếu test:
   - Trend Template + breakout / retest / pullback / U&R  
   - **Không có** SEPA FA-filter ở giữa → thực chất là “technical breakout engine” trên universe trung bình.

2. **Nếu muốn “test Mark thật sự” ở Phase 2**:
   - Cần thêm tầng **FA-cohort filter** (earnings / sales / margin / ROE / debt / leadership).
   - Chỉ sau đó mới có ý nghĩa quay lại VCP/pivot để tăng độ chính xác entry.

3. **Kết nối với quyết định hiện tại:**
   - Mechanical Minervini **đang ở trạng thái CLOSED** cho deploy (theo Postmortem).
   - “Full Mark” (SEPA + VCP + risk) chỉ nên được xem là **Phase 2 research** nếu:
     - FA-cohort study cho thấy trong VN **tồn tại** nhóm cổ phiếu có “superperformance DNA” thật sự.

File này **không đổi quyết định deploy hiện tại**, chỉ làm rõ “Brain của Mark” để sau này nếu mở Phase 2 thì không phải reverse engineer lại từ sách.

---

## 5. VN adaptation (Phase 2 empirical result)

**Primary edge is FA cohort selection; technical timing adds incremental value only inside FA cohort.**

- Breakout-only (universe-wide) is **unstable** in Vietnam across regimes.
- FA Mark-tight + earnings-accel cohort (2015–2024) vs VNINDEX **PASS**; hybrid (FA + 20d breakout within 30 days) improves median alpha and Sharpe vs FA-only with fewer trades.
- **Conclusion:** FA-first, timing second. Breakout/VCP/PP should live **inside** the FA cohort, not as standalone engine.

