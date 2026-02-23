# Research Note — Timeframe Framework (VN Backtest)

**Lock into research design before any further experiments.**

---

## 1. Timeframe framework for VN backtest

| Period      | Use for                    | Reason |
|------------|----------------------------|--------|
| **2000–2006** | **Do NOT use**           | Quá sơ khai, noise cực cao, không representative. |
| **2007–2011** | Tham khảo cẩn thận       | Bubble + crash cycle, liquidity structure khác hoàn toàn. |
| **2012–2017** | Extended in-sample       | VN30 ra đời (02/2012), cấu trúc ổn định hơn, thêm ~6 năm data. |
| **2018–2022** | In-sample (current)      | Modern regime, institutional participation, methodology hiện tại. |
| **2023–2026** | Hold-out (current)       | Out-of-sample validation. |

---

## 2. When did the index become “professional”?

- **Sau 2006–2007:** Giai đoạn bùng nổ đầu tiên; trước 2006 thị trường rất sơ khai, thanh khoản thấp.
- **Từ 2012:** VN30 chính thức ra đời (02/2012), sàng lọc vốn hóa và thanh khoản lớn; dữ liệu ổn định hơn về cấu trúc dòng tiền.
- **Từ 2018 đến nay:** Quy mô vốn hóa lớn, hệ thống giao dịch cải thiện, tham gia tổ chức tăng; chất lượng index tốt nhất cho backtest thuật toán / dòng tiền.

---

## 3. Should we extend in-sample to 2012?

**Có**, nhưng theo cách đã pre-register:

- Mở rộng in-sample từ 2018 về 2012 thêm ~300–400 trades (ước tính), tổng ~1.100–1.200 trades → giảm standard error của PF.
- **Lưu ý:** 2012–2017 có market microstructure khác 2018+ (fee, T+settlement, liquidity). Cần chạy **hai analysis riêng** trước khi pool:
  - **baseline_2012_2022:** trades=N, PF=X (in-sample mở rộng)
  - **baseline_2018_2022:** trades=N, PF=X (in-sample hiện tại)

**Recommendation:**

- Nếu hai con số **gần nhau** → pooling 2012–2022 hợp lý; thêm data có giá trị.
- Nếu **khác nhau nhiều** → giữ 2018 làm in-sample chính; dùng 2012–2017 như separate validation slice, không pool.

---

## 4. Order of tests (before liquidity regime)

1. Chạy **baseline_2012_2022** và **baseline_2018_2022** (cùng watchlist, --no-gate).
2. So PF và số trades; quyết định có pool 2012–2022 hay không.
3. Sau đó mới chạy **liquidity regime test** (full sample + hold-out 2023–2026) theo spec trong `pp_backtest/liquidity_regime.py`.

---

*Section này có thể copy vào Research Note (.docx) như một mục riêng (e.g. “Timeframe framework & in-sample extension”).*
