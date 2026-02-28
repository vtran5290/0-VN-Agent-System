# M4 Signal — Mô tả cho AmiBroker AFL

**Mục đích:** Dùng làm spec để tạo tín hiệu (buy/sell) trên AFL chart trong AmiBroker, theo logic backtest **M4** của VN Agent (Minervini-style, retest entry).

---

## 1) Model hiệu quả nhất (so far trong project)

- **Tên:** **M4** — VCP + Breakout + **Retest** (2-step entry).
- **Lý do:** Gate attribution (G5 = retest) cho thấy **retest** tạo bước nhảy lớn nhất cho expectancy_r và profit factor so với breakout-only; thesis T2 của framework: “edge chủ yếu từ retest trong thị trường VN hay break-fail”.

---

## 2) Cơ chế (layman)

1. **Xu hướng:** Giá trên MA50, MA50 > MA200, MA200 đang dốc lên (uptrend).
2. **Co lại (VCP):** Biến động và volume co lại — ATR ngắn < ATR trung < ATR dài, và volume 5 ngày < volume 20 ngày.
3. **Breakout:** Giá đóng cửa vượt đỉnh 40 phiên (HH40), volume > 1.5× VolSMA(20), và nến đóng ở phần trên của range (strong close: close ≥ high − 0.25×range).
4. **Retest (bước 2):** Không mua ngay khi breakout. Chờ trong **tối đa 5 phiên** sau ngày breakout:
   - Giá có thể kéo về gần vùng breakout (pivot) nhưng **không được “đâm thủng” quá 2% dưới pivot** (low ≥ pivot × 0.98).
   - Khi có **một phiên mà đóng cửa lại trên pivot** → **tín hiệu mua** (entry ngày sau tại open).
5. **Cắt lỗ / thoát:** Cắt lỗ cứng (stop), thoát sớm nếu thua 3 phiên liên tiếp (fail-fast), thoát khi giá cắt xuống MA50 (trend break).

**Tóm một câu:** Chỉ mua khi cổ phiếu đang uptrend, vừa co lại (VCP), breakout đỉnh 40 phiên với volume, rồi **kéo về test lại vùng đỉnh mà không phá vỡ** — mua khi giá đóng cửa trở lại trên vùng đó trong 5 phiên.

---

## 3) Mô tả từng bước cho AFL (logic tín hiệu)

### Chuẩn bị dữ liệu / indicator

- **MA50, MA200** (close).
- **MA200 slope:** MA200 hiện tại > MA200 20 bar trước.
- **ATR(5), ATR(10), ATR(20)** và **ATR%** = ATR/Close (cho VCP).
- **VolSMA(5), VolSMA(20).**
- **HH40:** Highest High của 40 bar trước (không tính bar hiện tại) — đây là **pivot** cho breakout/retest.

### Gate 1 — Trend Template (TT Lite)

- `Close > MA50`
- `MA50 > MA200`
- `MA200 > Ref(MA200, -20)` (MA200 dốc lên).

### Gate 2 — VCP proxy

- **Contraction stack:** `ATR%_5 < ATR%_10` AND `ATR%_10 < ATR%_20`.
- **Volume dry-up:** `VolSMA(5) < VolSMA(20)`.

### Gate 3 — Breakout (ngày T)

- `Close > HH40` (close vượt đỉnh 40 bar).
- `Volume > 1.5 * VolSMA(20)`.
- **Strong close:** `Close >= High - 0.25 * (High - Low)` (nến đóng ở 3/4 trên của range).

→ Nếu **Gate1 AND Gate2 AND Gate3** đều đúng ở bar T → **breakout** xảy ra tại T. Ghi nhớ **pivot = HH40 tại T** (hoặc high của vùng breakout tương đương).

### Gate 4 — Retest (trong 5 bar sau breakout)

- Xét từ bar T+1 đến T+5:
  - Với mỗi bar j:
    - `Low >= pivot * 0.98` (không undercut quá 2%).
    - `Close > pivot`.
  - **Tín hiệu BUY:** Ngày **đầu tiên** (trong 5 bar) mà cả hai điều kiện trên thỏa → **signal = 1** tại bar đó. Entry thực tế = open của **bar kế tiếp** (giống backtest).

### Tham số M4 (để map vào AFL)

| Tham số           | Giá trị | Ý nghĩa AFL |
|-------------------|---------|-------------|
| lookback_base     | 40      | HH40 (pivot) |
| vol_mult          | 1.5     | Volume > 1.5× VolSMA20 |
| retest_max_bars   | 5       | Chỉ xét retest trong 5 bar sau breakout |
| max_undercut_pct  | 0.02    | Low ≥ pivot × (1 − 0.02) = pivot × 0.98 |
| strong close      | top 25% | Close ≥ High − 0.25×(High−Low) |

### Exit (để vẽ hoặc backtest trong AmiBroker)

- **Hard stop:** ví dụ 5% dưới entry (config M4: stop_pct 0.05).
- **Fail-fast:** thoát nếu 3 phiên liên tiếp lỗ (so với entry).
- **Trend break:** thoát khi Close < MA50.

---

## 4) Một phiên bản pseudo-AFL (chỉ ý tưởng, chưa chạy)

```afl
// --- Indicators ---
MA50  = MA(C, 50);
MA200 = MA(C, 200);
MA200Up = MA200 > Ref(MA200, -20);
HH40  = HHV(H, 40);   // AmiBroker: 40 bars including current; for pivot use Ref(HHV(H,40),1) at breakout bar
VolSMA20 = MA(V, 20);
VolSMA5  = MA(V, 5);
ATR5  = ATR(5);  ATR10 = ATR(10);  ATR20 = ATR(20);
ATRp5 = ATR5/C;  ATRp10 = ATR10/C; ATRp20 = ATR20/C;

// TT Lite
TT = C > MA50 AND MA50 > MA200 AND MA200Up;

// VCP
Contraction = ATRp5 < ATRp10 AND ATRp10 < ATRp20;
DryUp = VolSMA5 < VolSMA20;
VCP = Contraction AND DryUp;

// Pivot = HH40 of previous 40 bars (excl. current) → Ref(HHV(H,40),1)
Pivot = Ref(HHV(H, 40), 1);
StrongClose = C >= H - 0.25 * (H - L);
Breakout = C > Pivot AND V > 1.5 * VolSMA20 AND StrongClose AND TT AND VCP;

// Retest: within 5 bars after breakout, Low >= Pivot*0.98 and Close > Pivot
// (Implementation: mark bar of breakout, then in next 5 bars check condition; first bar that satisfies = Buy signal bar)
```

Trên chart AFL bạn sẽ cần:

- **Buy signal bar** = bar mà retest thành công (lần đầu trong 5 bar sau breakout: Low ≥ pivot×0.98 và Close > pivot), với pivot = HH40 tại **ngày breakout** (không phải ngày hiện tại).
- **Entry** = Open của bar kế tiếp sau signal bar (nếu backtest giống engine).

---

## 5) Lưu ý khi implement AFL

- **Pivot cố định cho retest:** Pivot là HH40 **tại ngày breakout**, không cập nhật mỗi bar. Trong AFL cần lưu/lookup pivot của bar breakout khi kiểm tra retest (có thể dùng biến static hoặc loop ngược tìm bar breakout rồi lấy HH40 tại đó).
- **Một breakout → một cơ hội retest:** Sau khi retest thành công (hoặc quá 5 bar), reset; breakout mới lại bắt đầu chu kỳ retest mới.
- **Strong close:** Range = High−Low; nếu range = 0 thì coi như thỏa (tránh chia 0).

File này đủ để bạn chuyển thành AFL đầy đủ (vẽ mũi tên mua, hoặc dùng làm điều kiện trong Backtest của AmiBroker). Nếu bạn gửi đoạn AFL hiện tại, có thể chỉnh từng dòng cho khớp M4.
