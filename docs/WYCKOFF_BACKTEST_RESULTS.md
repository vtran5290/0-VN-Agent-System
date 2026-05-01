# Wyckoff Brain — VN Backtest Results (cập nhật)

**Universe:** 40–80 mã từ `minervini_backtest/data/raw/` / `config/watchlist_80.txt` (cổ phiếu VN).  
**Chỉnh theo tư duy Wyckoff:** ST (Secondary Test), Spring, Cause & Effect, trend filter (TT Lite), tight base, ultra-dry volume, SOS/JAC xuyên kháng cự.

---

## 1. Giả định backtest (đã implement)

| Hạng mục | Cách làm |
|----------|----------|
| **TR** | SC = volume cao nhất 50 bar, spread ≥ 2× ATR, nến có bóng dưới dài; AR = rally > 5% từ đáy SC trong 20 bar. TR = (SC_low, AR_high). |
| **ST** | Giá quay về vùng SC, volume **thấp hơn** SC → cung đã giảm. Có cột `wyckoff_st_done`, config `require_st: true` nếu muốn bắt buộc. |
| **Spring** | Đáy < TR_low, volume < 0.65–0.7× SC_vol, hồi phục (close > TR_low) trong 5 bar. |
| **JAC** | Close > TR_high, volume ≥ 1.2× SMA20, spread ≥ 1.5× ATR. |
| **LPS** | Sau JAC, lần pullback đầu về vùng AR, volume ≤ 35–50% SMA20. |
| **Entry** | Mặc định VN: chỉ LPS. Biến thể: JAC hoặc LPS (`trigger_jac_ok: true`). |
| **Trend filter** | `wyckoff_trend_filter: true` → vẫn dùng TT Lite (Close > MA50, MA50 > MA200) trước khi cho vào Wyckoff. |
| **Tight base** | `wyckoff_base_tight`: trong 8–12 bar gần nhất của nền, closes phải co hẹp (`max-min` / mean close thấp, stdev close thấp). |
| **Ultra-dry volume** | `wyckoff_ultra_dry_days`: số phiên trong nền có volume ≤ 45–50% SMA20. Dùng để test “supply has dried up”. |
| **SOS / Creek jump** | `wyckoff_sos_ready`: ít nhất 1–2 up-bar có spread rộng + volume cao trong 10–12 bar gần nhất; JAC có thể yêu cầu close vượt AR thêm 0.1–0.4% và close near high. |
| **Stop** | Min(entry − ATR×k, entry×(1−stop_pct), TR_low×0.99). |
| **Exits** | Hard stop, trend break MA50, fail_fast 3 ngày, climax proxy. |

---

## 2. Kết quả so sánh (40–60 mã)

| Config | Mã | Trades | Win% | Expectancy | PF | Expectancy_R | CAGR | Ghi chú |
|--------|-----|--------|------|------------|-----|--------------|------|---------|
| W2_wyckoff_pure | 40 | 55 | 18.2% | -0.0175 | 0.13 | -0.15 | -7.7% | ST+Spring, LPS only, TR chặt — quá ít lệnh, thua |
| W2_cause_effect | 40 | 44 | 25% | -0.012 | 0.22 | -0.12 | -4.3% | min_tr 50, max_tr 15% — vẫn âm |
| W2_tight_absorption | 40 | 47 | 27.7% | -0.0077 | 0.39 | -0.07 | -3.0% | TR 15%, Spring — âm |
| W2_spring_and_loose | 40 | 164 | 22% | -0.0099 | 0.50 | -0.10 | -13.7% | Loose SC + Spring — âm |
| W2_st_only | 40 | 101 | 25.7% | -0.0089 | 0.51 | -0.10 | -8.1% | Chỉ ST, LPS only — âm |
| **W2_loose_sc** | 40 | 248 | 24.6% | **+0.0048** | **1.24** | **+0.005** | -3.2% | SC 2.5×, JAC/LPS, stop 4%, fail_fast 3 |
| **W2_loose_sc_trend** | 40 | 125 | 21.6% | **+0.0131** | **1.60** | **+0.038** | **+2.3%** | + TT Lite (uptrend) |
| **W2_loose_sc_trend** | **60** | **184** | **20.7%** | **+0.0243** | **2.23** | **+0.14** | **+17.3%** | Cùng config, 60 mã — tốt nhất |
| W2_loose_sc_trend_spring | 60 | 122 | 19.7% | +0.0067 | 1.37 | +0.024 | +1.3% | Thêm require_spring — vẫn dương nhưng thấp hơn |
| W2_loose_sc_trail | 40 | 251 | 25.5% | -0.0068 | 0.64 | -0.07 | -15.3% | Partial 1.5R + trail MA20 — cắt lời sớm, tệ hơn |

### 2b. Test thêm theo ý tưởng “nền siết + vol cạn + kéo qua kháng cự” (80 mã)

| Config | Trades | Win% | Expectancy | PF | Expectancy_R | CAGR | Đọc theo Wyckoff |
|--------|--------|------|------------|-----|--------------|------|------------------|
| W2_loose_sc_trend | 255 | 23.5% | +0.0001 | 1.00 | +0.029 | -4.6% | Baseline trên 80 mã: gần hòa vốn |
| W2_tight_dry_sos1 | 5 | 0.0% | -0.0138 | n/a | -0.157 | -0.8% | Siết quá tay: trade gần như biến mất |
| W2_tight_dry_sos2 | 1 | 0.0% | -0.0088 | n/a | -0.115 | -66.1% | Cực đoan hơn: hầu như không có setup |
| W2_tight_dry_lps | 5 | 0.0% | -0.0120 | n/a | -0.145 | -0.6% | Tight base + LPS only quá hiếm |
| W2_creek_jump | 132 | 23.5% | +0.0024 | 1.09 | +0.027 | -2.1% | Cần 2 SOS + JAC mạnh: tốt hơn baseline nhưng chưa rõ rệt |
| W2_tight_moderate | 58 | 25.9% | +0.0050 | 1.36 | +0.129 | +1.3% | Nền tương đối chặt + 1 phiên ultra-dry, không siết quá mức |
| **W2_dry_jump** | **150** | **22.7%** | **+0.0059** | **1.29** | **+0.048** | **+2.1%** | **Có 1 phiên ultra-dry trong nền + 1 SOS bar + JAC mạnh hơn** |
| W2_tight_jump | 59 | 28.8% | +0.0056 | 1.37 | +0.084 | +1.4% | Tight base vừa phải + 1 SOS bar + strong JAC |

---

## 3. Kết luận

- **Chỉ Wyckoff thuần (ST + Spring, LPS only, TR chặt)** trên VN cho ít lệnh và **expectancy âm**.
- **SC lỏng (2.5× vol) + JAC or LPS + stop chặt (4%) + fail_fast 3** cho **expectancy dương** (W2_loose_sc).
- **Thêm trend filter (TT Lite: giá > MA50, MA50 > MA200)** cải thiện rõ: **W2_loose_sc_trend** — trên 60 mã: **expectancy +2.43%**, **PF 2.23**, **CAGR +17.3%**, expectancy_r +0.14.
- Require Spring trong bối cảnh loose SC + trend vẫn dương nhưng thấp hơn (CAGR +1.3%).
- Partial + trail (W2_loose_sc_trail) làm tệ hơn — cắt lời quá sớm.
- Khi thêm **tight base / ultra-dry / creek jump** thì điểm mấu chốt là: **không được siết quá tay**. Cực chặt (`tight_dry_sos1/2`, `tight_dry_lps`) làm số trade gần như bằng 0.
- Thứ hoạt động tốt hơn là **“supply has dried up” ở mức vừa phải**:
  - `W2_tight_moderate`: nền tương đối chặt + 1 phiên ultra-dry → expectancy dương.
  - `W2_dry_jump`: **ít nhất 1 phiên ultra-dry trong nền + ít nhất 1 SOS bar + JAC mạnh hơn** → là config tốt nhất trong nhóm filter mới trên 80 mã.
- Kết luận thực chiến kiểu Wyckoff cho VN: **nền không cần quá textbook-tight**, nhưng nên có **1 cụm cạn cung** rồi mới chấp nhận cú **SOS/JAC đủ spread + volume + close near high**.

---

## 4. Config đề xuất cho VN (sau khi tweak theo Wyckoff)

**Config tốt nhất theo mẫu 60 mã:** `W2_loose_sc_trend`  
**Config tốt nhất trong batch 80 mã với filter mới:** `W2_dry_jump`

- **SC:** `sc_vol_mult: 2.5`, `sc_spread_atr_mult: 1.8` (đủ TR theo Wyckoff nhưng không quá gắt).
- **Trend:** `wyckoff_trend_filter: true` — chỉ vào khi đã có uptrend (MA50 > MA200, Close > MA50).
- **Trigger:** `trigger_jac_ok: true` (JAC hoặc LPS).
- **Cause:** `min_tr_duration: 20`, `max_tr_volatility: 0.25`.
- **Risk:** `stop_pct: 0.04`, `fail_fast_days: 3`.
- **Không** require_spring, **không** partial/trail trong test tốt nhất.

Batch 80 mã, filter mới tốt nhất:

- **Supply drying:** `require_ultra_dry_days: 1`, `ultra_dry_vol_ratio: 0.5`.
- **Creek attack:** `require_sos: true`, `min_sos_bars: 1`, `sos_vol_mult: 1.15`, `sos_spread_atr_mult: 1.05`.
- **JAC mạnh hơn baseline:** `jac_vol_mult: 1.35`, `jac_breakout_pct: 0.002`, `jac_close_pos_min: 0.72`.
- **Không** bắt buộc tight base; tight base chỉ nên dùng ở mức vừa phải (`W2_tight_moderate`, `W2_tight_jump`), không quá cực đoan.

File config:

- `minervini_backtest/configs/W2_loose_sc_trend.yaml`
- `minervini_backtest/configs/W2_dry_jump.yaml`

---

## 5. Cách chạy

```bash
cd minervini_backtest
python run.py --config W2_loose_sc_trend [--symbols A B C ...] [--out outputs/result.csv]
python run.py --config W2_dry_jump [--symbols A B C ...] [--out outputs/result.csv]
```

---

## 6. Files liên quan

- Engine: `src/wyckoff.py` (state machine, ST/Spring/JAC/LPS, tight base, ultra-dry days, SOS readiness), `engine.py` (nhánh Wyckoff, `require_st`, `require_spring`, `wyckoff_trend_filter`, `require_tight_base`, `require_ultra_dry_days`, `require_sos`).
- Config: `configs/W2_loose_sc_trend.yaml`, `W2_dry_jump.yaml`, `W2_tight_moderate.yaml`, `W2_tight_jump.yaml`, ...
- Kết quả mẫu: `outputs/w_trend_60.csv`, `outputs/w80_dry_jump.csv`, `outputs/w80_tight_jump.csv`.
