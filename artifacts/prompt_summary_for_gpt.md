# Prompt: Tóm tắt kết quả validation để update GPT

Copy toàn bộ nội dung dưới đây (từ "Bối cảnh" đến hết "Yêu cầu") và paste vào ChatGPT, kèm theo file/table kết quả nếu bạn đã chạy xong và có `artifacts/validation_results.md` hoặc log đầy đủ.

---

## Bối cảnh

Tôi đang chạy một hệ thống backtest portfolio cho thị trường chứng khoán Việt Nam (VN), theo hướng dẫn trước đó của bạn:

- **Chiến lược:** Pocket Pivot (Gil/Kacher) + EMA21/MA50 làm cổng xu hướng; vào khi EMA21 cắt lên MA50 và có tín hiệu PP tuần; thoát khi vi phạm EMA21/MA50 hoặc EMA21 cắt xuống MA50.
- **Universe:** Cổ phiếu có ADTV ≥ 4 tỷ VND (danh sách tĩnh từ user), ~219 mã.
- **Portfolio engine:** Một engine duy nhất, overlapping positions; VND làm đơn vị (NAV ban đầu 1 tỷ); phí 15 bps mỗi chiều; thoát tại open tuần kế tiếp khi có tín hiệu thoát; equity = cash + mark-to-market.
- **Regime:** Chỉ vào lệnh khi `regime_ftd == True`, chặn khi `no_new_positions == True` (VN30 FTD / book mode).
- **Risk:** risk_per_trade 0.5% NAV, max_heat 4%, max 8 vị thế, max 10% NAV/symbol, liquidity cap 5% ADTV20.
- **Ranking vào lệnh (mặc định):** Ưu tiên RS cao hơn → tightness_3w thấp → ext_vs_ma10 thấp → ADTV20 cao.

Không thêm FA, không grid optimization; chỉ validation robustness và capacity.

---

## Các bước đã chạy

### 1) Out-of-sample era validation (cùng config, ranking mặc định)

Chạy 4 khoảng thời gian:

| Era         | CAGR   | MDD     | MAR | n_trades | final_equity (VND) | avg_heat | avg_gross_exposure | skipped_ineligible | skipped_regime_off | skipped_no_new_positions | skipped_max_positions | skipped_liquidity |
|------------|--------|---------|-----|----------|--------------------|----------|--------------------|--------------------|--------------------|--------------------------|-----------------------|-------------------|
| 2012-2017  | 12.06% | -10.96% | 1.10 | 63       | 1,975,855,251      | 0.0216   | 0.3889              | 2118                | 1587               | 781                       | 714                   | 0                 |
| 2022-2024  | 7.19%  | -9.35%  | 0.77 | 39       | 1,230,846,863      | 0.0181   | 0.3610              | 426                 | 1026               | 533                       | 1513                  | 0                 |
| 2025-2026Q1| 0.71%  | -3.45%  | 0.21 | 6        | 1,007,943,620      | 0.0056   | 0.1078              | 20                  | 55                 | 149                       | 172                   | 0                 |
| full_sample | 11.42% | -22.22% | 0.51 | 219      | 4,596,901,089      | 0.0230   | 0.4502              | 4334                | 5568               | 2266                      | 5920                  | 0                 |

*(Nếu bạn có bảng khác từ `validation_results.md` hoặc log mới hơn, hãy thay thế bảng trên bằng bảng đó.)*

### 2) Ranking ablation (2018-01-01 đến 2021-12-31)

Cùng data 2018-2021, 5 cách xếp hạng candidate vào lệnh:

- **current ranking** (RS → tightness_3w → ext_vs_ma10 → ADTV20)
- **ADTV20 descending only**
- **tightness_3w ascending only**
- **ext_vs_ma10 ascending only**
- **random (seed=42)**

*(Dán vào đây bảng kết quả section 2 từ `artifacts/validation_results.md` hoặc console nếu đã chạy xong.)*

### 3) Capacity test (2018-2021, ranking mặc định)

Cùng data 2018-2021, 3 mức NAV ban đầu: 1 tỷ, 5 tỷ, 10 tỷ VND.

*(Dán vào đây bảng kết quả section 3 từ `artifacts/validation_results.md` hoặc console nếu đã chạy xong.)*

---

## Kết quả 2018-2021 (baseline từ lần chạy trước)

Một lần chạy riêng 2018-2021 với config trên đã cho: CAGR 22.03%, MDD -12.25%, MAR 1.80, n_trades 43, final_equity 2,211,810,510 VND, avg_heat 0.0187, avg_gross_exposure 0.4384; skipped_regime_off 1799, skipped_no_new_positions 456, skipped_max_positions 2122, skipped_ineligible 1278, skipped_liquidity 0.

---

## Yêu cầu

Hãy tóm tắt ngắn gọn:

1. **OOS:** Nhận xét về tính nhất quán của CAGR/MDD/MAR qua các era và full sample; era nào yếu/ổn/mạnh.
2. **Ranking ablation:** So sánh 5 cách ranking – ranking mặc định có tốt hơn rõ rệt không, hay đơn giản (ví dụ ADTV20 only) đã đủ.
3. **Capacity:** 1 vs 5 vs 10 tỷ VND – skipped_liquidity và các chỉ số có thay đổi đáng kể không; có gợi ý về scale NAV tối đa.
4. **Kết luận:** Strategy có đủ robust qua các era và scale không; bước nên làm tiếp (ví dụ: walk-forward, filter thêm, hay giữ nguyên và paper trade).

Output: một bản tóm tắt có cấu trúc (bullet hoặc section ngắn), dùng được để update context cho GPT và quyết định bước tiếp theo.
