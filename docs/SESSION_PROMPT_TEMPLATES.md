# Session prompt templates — paste vào đầu chat mới

Dùng **sau khi** paste nội dung `docs/RESEARCH_STATE.md` (hoặc @ file đó). Dưới đây là request cụ thể theo thesis.

---

## Template: 2012–2019 extension (robustness appendix)

```
RESEARCH_STATE — paste vào đầu chat
Sau đó thêm request cụ thể:

Context: Đang nghiên cứu Minervini mechanical system trên VN equities. Đã test walk-forward 2020–2022 (train) / 2023 (val) / 2024 (holdout) — kết quả: train mạnh, val/holdout âm. Root cause xác định là persistence mismatch, không phải breadth hay regime level. Hệ thống đã CLOSED cho mechanical deploy.

Task: Extend backtest data về 2012–2019 như một robustness appendix — không dùng để justify deploy, chỉ để xem edge có tồn tại trong các chu kỳ VN bình thường hơn không.

Constraints cần giữ:
- Liquidity filter chặt theo từng năm (ADTV threshold động, không fixed)
- Treat 2012–2019 là separate robustness check, không merge vào WF chính
- Walk-forward mới nếu làm: train 2012–2018, val 2019–2021, holdout 2022–2024
- Fee 30bps, min_hold=3 giữ nguyên

Câu hỏi cụ thể: [bạn điền — ví dụ: "Build data pipeline cho 2012–2019" hoặc "Chạy M0R trên extended data"]

Không làm: Không reopen Minervini deploy candidate. Không build MHC composite. Không optimize entry trên extended data.
```

---

Thêm template khác (persistence study, O'Neil overlay, …) vào file này khi cần.
