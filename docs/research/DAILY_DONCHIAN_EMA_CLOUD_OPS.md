# Daily Donchian + EMA Cloud — Ops Runbook

Chat **daily** dùng file này làm SSOT cho agent: mỗi ngày giao dịch xuất **3 bảng gần trigger** + cuối phiên **danh sách có tín hiệu bán** (theo **Chandelier HOẶC EMA10 confirmed**, giống `TOP_ExitEither` trong AFL).

---

## 1) Tham chiếu (SSOT)

| Thành phần | File |
|-------------|------|
| AFL chart (định nghĩa marker + exit) | `data/research/afl charts/SMC_Donchian_EMA_Cloud_fixed_full.afl` |
| Spec research (Donchian + buffer + cloud) | `data/research/donchian_cloud_exits/Donch-EMAcloud_signal_spec_full.md` |
| OHLCV cache (batch screen) | `data/research/cache/fireant_ohlcv/<SYMBOL>.csv` |
| Universe gợi ý (đã lọc thanh khoản research) | symbols xuất hiện trong `data/research/ema_cloud/donchian_signals_full.csv` |
| VNINDEX (regime) | `minervini_backtest/data/raw/VNINDEX.csv` hoặc nguồn bạn trade; **align cùng phiên với cổ phiếu** |

**Lưu ý universe:** Bạn đã xác nhận universe **đã lọc sẵn ADV50 ≥ 2 tỷ/ngày** — khi đối chiếu AFL, toggle `DC_UseADV` không đổi membership; chỉ khác **màu marker** Orange vs Aqua.

---

## 2) Tham số mặc định (khớp AFL section 10 + 13)

| Tham số | Giá trị mặc định (AFL) |
|---------|-------------------------|
| Fast / Slow EMA | 10 / 50 |
| Donchian length | 20 |
| Breakout buffer | 0,30% → hệ số `1 + 0,003` |
| ATR Chandelier | 14 |
| CH k | 3,0 |
| CH kích hoạt | +10% từ **giá vào** |
| MAE min hold | 10 bar sau **entry bar** |
| MAE | 2 close dưới EMA10 (close thứ 2 **thấp hơn** close vi phạm đầu); reset nếu close lên lại ≥ EMA10 |
| Sell backtest mode (live logic bạn chọn) | **Either Chandelier or EMA10** → `Sell = CH_Exit OR MAE_Exit` |

---

## 3) Định nghĩa marker (khớp section 10 AFL)

Trên bar index `t` (causal, không nhìn tương lai):

```text
DC_donchianHigh  = HHV(H, 20) tại bar trước, tức max(high[t-20 .. t-1])  // Ref(HHV(H,20), -1)
DC_breakoutLevel = DC_donchianHigh * (1 + Buffer%/100)

DC_CloseAboveBO = C > DC_breakoutLevel
DC_BullCloud    = EMA(C,10) > EMA(C,50)
DC_AboveFast    = C > EMA(C,10)

DC_NoADVBuy = DC_CloseAboveBO AND DC_BullCloud AND DC_AboveFast
DC_RawBuy    = DC_NoADVBuy AND DC_ADVOK        // với universe đã lọc ADV: RawBuy ≈ NoADVBuy

DC_Buy: state machine — chỉ bật khi RawBuy và đang flat (một lệnh tại một thời điểm theo loop AFL)
```

**Ánh xạ màu / hình (AFL):**

| Marker | Điều kiện (theo AFL) |
|--------|----------------------|
| **Blue square** | `DC_CloseAboveBO` |
| **Orange △** (khi bật `DC_ShowNoADV`) | `DC_NoADVBuy` |
| **Aqua △** | `DC_RawBuy` |
| **Green ↑** | `DC_Buy` (đã qua state flat + RawBuy) |

---

## 4) Ba bảng “gần final buy” (khoảng cách tới trigger)

**Đường trigger** (cùng `DC_breakoutLevel` / research):  
`trigger = max(high[t-20 .. t-1]) * (1 + buffer%)`

**Điều kiện lọc “ứng viên” (đồng bộ chart + universe bạn):**

- `BullCloud` + `AboveFast` (tức đang trong setup bullish theo AFL; với bull cloud thì tương đương giá trên cả hai EMA).
- Khoảng cách: `dist_pct = 100 * (close / trigger - 1)`.
- Chỉ giữ mã có `|dist_pct| ≤ 10%`.

**Chia 3 bảng:**

| Bảng | Khoảng \|dist_pct\| |
|------|----------------------|
| **Level 1** | `< 3%` |
| **Level 2** | `≥ 3%` và `< 7%` |
| **Level 3** | `≥ 7%` và `≤ 10%` |

**Cột gợi ý mỗi dòng:** `symbol` · `close` · `trigger` · `dist_pct` · `Blue` · `Aqua/RawBuy` · `Green/DC_Buy` (nếu mô phỏng được state) · ghi chú ngắn (vd “đã breakout”, “dưới trigger”).

---

## 5) Regime — **quan trọng cho exit Chandelier / MAE**

Trong AFL, state cho **Chandelier** và **EMA exit** dùng:

```text
TOP_EntrySignal = PROD_Buy   // khi CH_DebugMode = No (mặc định)

PROD_Buy = DC_Buy AND RG_RegimeON
RG_RegimeON = VNINDEX_C > EMA(VNINDEX_C, 50)
```

**Hệ quả daily ops:**

- Nếu **Regime OFF** trên bar có `DC_Buy`, **AFL không coi đó là entry** cho `CH_*` / `MAE_*` (trừ khi bật `CH_DebugMode`).
- Agent daily khi báo “có bán Chandelier/EMA không” phải **mô phỏng entry theo `PROD_Buy`**, không chỉ `DC_RawBuy`, trừ khi bạn explicitly yêu cầu chế độ debug.

Ghi rõ mỗi ngày trong output: **Regime ON/OFF** + nguồn VNINDEX.

---

## 6) Cuối phiên — “mã nào có tín hiệu bán” (Chandelier **hoặc** EMA)

### 6.1 Giả định bắt buộc

Để biết **CH_Exit** / **MAE_Exit**, cần **chuỗi entry** giống AFL:

1. Duyệt theo thời gian; tại mỗi bar, nếu `TOP_EntrySignal` và đang **flat** → mở trade tại **`Open[t+1]`**, ghi `entry_bar = t+1`, `entry_px = Open[t+1]`.
2. Chỉ một trade đồng thời (giống loop AFL đơn giản).
3. Khi một trong hai exit bật → đóng trade tại **`Open[t+1]`** của bar exit (khớp `SellPrice = Open` trong AFL).

### 6.2 Chandelier (mặc định k=3, activate +10%)

Trong trade, mỗi bar `i ≥ entry_bar`:

- `HC = max(HC, Close[i])`
- Khi `Close[i] >= entry_px * (1 + activate_pct/100)` → bật trailing.
- Khi đã active: `trail = HC - k * ATR(14)[i]`
- Nếu `Close[i] < trail` → **`CH_Exit = 1`** (thoát phiên sau tại open).

**Gần cuối phiên — báo cáo gợi ý:**

| Nhóm | Ý nghĩa |
|------|---------|
| **A — Exit hôm nay** | Bar cuối đủ dữ liệu có `CH_Exit == 1` (hoặc `MAE_Exit == 1`) |
| **B — Cảnh báo CH** | Trailing **đã active** và `Close` gần `trail` (vd khoảng cách ≤ X×ATR — agent chọn X cố định, ghi trong log) |
| **C — Cảnh báo MAE** | Đủ `MinHoldBars`, đang violation bar đầu hoặc chờ confirm bar 2 |

### 6.3 EMA10 confirmed exit

Sau `entry_bar`, đếm `hold = i - entry_bar`:

- Khi `hold >= MAE_MinHoldBars` và `Close < EMA(C,10)`:
  - Bar đầu vi phạm: lưu `viol_close`
  - Bar sau: nếu vẫn dưới EMA10 **và** `Close < viol_close` → **`MAE_Exit = 1`**
- Nếu `Close >= EMA10` → reset violation.

### 6.4 Kết hợp (live bạn chọn)

- **`TOP_ExitEither = CH_Exit OR MAE_Exit`**
- Cuối ngày: liệt kê mã có **Either** true; nếu cả hai true cùng bar, ghi rõ (hiếm nhưng có thể).

---

## 7) Template output — copy cho agent mỗi ngày

Dán block dưới vào chat (agent điền số / tickers).

```markdown
## Daily Donchian + EMA — <YYYY-MM-DD>

**FACTS**
- Data source: FireAnt cache / … (ghi rõ)
- Last bar date: …
- VNINDEX regime (close > EMA50): ON / OFF
- Entry for CH/MAE simulation: PROD_Buy (DC_Buy AND regime) — Yes/No theo default AFL

### Level 1 (|dist| < 3%)
| Symbol | Close | Trigger | dist% | Blue | RawBuy | DC_Buy | Notes |
|--------|------:|----------:|------:|:----:|:------:|:------:|-------|
| … | … | … | … | … | … | … | … |

### Level 2 (3% ≤ |dist| < 7%)
| Symbol | Close | Trigger | dist% | Blue | RawBuy | DC_Buy | Notes |
|--------|------:|----------:|------:|:----:|:------:|:------:|-------|
| … | … | … | … | … | … | … | … |

### Level 3 (7% ≤ |dist| ≤ 10%)
| Symbol | Close | Trigger | dist% | Blue | RawBuy | DC_Buy | Notes |
|--------|------:|----------:|------:|:----:|:------:|:------:|-------|
| … | … | … | … | … | … | … | … |

### Sell watch (Chandelier OR EMA10) — end of session
| Symbol | In trade? | CH active? | Close vs trail | CH_Exit today? | MAE phase | MAE_Exit today? | Either exit? |
|--------|:---------:|:------------:|----------------|:----------------:|-----------|:---------------:|:--------------:|
| … | … | … | … | … | … | … | … |

### INTERPRETATION (ngắn)
- …
```

---

## 8) Hạn chế / toàn vẹn dữ liệu

- Cache OHLCV có thể **chậm 1 phiên** so với AmiBroker live — luôn ghi `last_bar`.
- `DC_Buy` / `DC_Sell` (63 bar) trên chart là **state machine đơn giản**; portfolio thực có thể khác (nhiều lệnh, sizing) — daily list là **mô phỏng rule**, không phải sao kê broker.
- Nếu divergence giữa AFL và Python: ưu tiên **đối chiếu 2–3 mã** (EMA seed, đơn vị volume) trước khi đổi rule.

---

## 9) Cursor / agent

- **Chat daily:** dùng đúng thread này; mỗi phiên paste template mục 7 + yêu cầu “chạy theo runbook”.
- Khi đổi AFL params (buffer, k, activate, min hold): sửa **mục 2** của file này cho khớp, rồi mới chạy lại.

---

## 10) Ba slot — lệnh gọn (token)

Chạy từ **repo root**. Output **một dòng**: `SLOT` `DATE` `REG` `BUY|L1` `L2` `L3` `RB` `G` `NK` `SELL|E`

| Key | Ý nghĩa |
|-----|---------|
| `RB` | RawBuy (close > trigger + bull + trên EMA10) |
| `G` | Pulse **DC_Buy** (vào lệnh mới theo state 63 bar) |
| `NK` | RawBuy hôm nay nhưng **không** pulse G (thường do đang trong cửa sổ 63 bar từ tín hiệu trước) |
| `SELL|E` | Exit **Chandelier HOẶC MAE10** (một vị thế; hit cái nào trước cũng đóng) trên bar cuối cache |

**PowerShell 7 (`pwsh`) — nếu đã cài:**

```powershell
pwsh -NoProfile -File scripts/research/daily_slots.ps1 AM_OPEN
pwsh -NoProfile -File scripts/research/daily_slots.ps1 AM_MID
pwsh -NoProfile -File scripts/research/daily_slots.ps1 PM_CLOSE
```

**Windows PowerShell 5.1** (khi `pwsh` không có trên PATH — cùng file `.ps1`):

```powershell
powershell -NoProfile -File scripts/research/daily_slots.ps1 PM_CLOSE
```

**Node trực tiếp:**

- `daily_slots.ps1` gọi kèm **`--pretty`**: dòng compact + khối liệt kê mã theo nhóm (dễ đọc).
- Chỉ một dòng (parse/ghi log): bỏ `--pretty`.

```text
node scripts/research/daily_donchian_ema_slot_scan.mjs --slot=AM_OPEN --pretty
node scripts/research/daily_donchian_ema_slot_scan.mjs --slot=AM_MID --pretty
node scripts/research/daily_donchian_ema_slot_scan.mjs --slot=PM_CLOSE --pretty
```

**Prompt 1 dòng trong chat (copy từ):** `.cursor/prompts/daily-donchian-scan.md`

**Minimal mode:** gõ `Minimal Mode on` trong chat nếu muốn agent chỉ trả log ngắn (xem rule `.cursor/minimal_mode`).
