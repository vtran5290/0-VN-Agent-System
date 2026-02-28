# Universe Spec — VN 2012–2026 (research-grade)

> Dynamic-by-year, freeze per year, no forward bias. Dùng cho STEP 1/2 sau khi mở rộng universe.

---

## I. Nguyên tắc

- Universe xây **một lần mỗi năm** (ngày giao dịch đầu tiên của năm).
- Dựa trên **60 trading days** trước ngày đó (không dùng thông tin tương lai).
- **Freeze** danh sách cho cả năm.

---

## II. Tiêu chí inclusion (đã implement)

| Tiêu chí | Giá trị |
|----------|--------|
| Liquidity | Median(matched_value_60d) = median(volume × close) trên 60 ngày trước đầu năm. Xếp hạng giảm dần, lấy **top N**. |
| Price | Close (ngày cuối của 60d) ≥ **5,000 VND** (loại penny). |
| Data sufficiency | Ít nhất **250 trading bars** trước ngày giao dịch đầu tiên của năm. |

---

## III. Top N theo giai đoạn (đề xuất)

| Giai đoạn | Top N | Ghi chú |
|-----------|------|--------|
| 2012–2016 | 30 | Thanh khoản thấp, midcap dominance. |
| 2017–2019 | 40 | Liquidity expansion. |
| 2020–2022 | 60 | Peak liquidity, FOMO. |
| 2023–2026 | 50 | Normalize, rotation. |

**Research v1:** Có thể dùng **constant N = 50** cho tất cả năm (`--liq-topn 50`). Year-band (ví dụ `--liq-topn-2012-2016 30`) có thể thêm sau qua args.

---

## IV. Exchange scope

- **Phase 1:** HOSE only (candidate list từ `config/universe_186.txt` hoặc watchlist HOSE).
- **Phase 2:** HOSE + HNX (khi cần).

---

## V. Lệnh

- Universe liquidity top-N (constant 50):  
  `python -m pp_backtest.run --no-gate --entry darvas --exit darvas_box --universe liquidity_topn --liq-topn 50 --start 2012-01-01 --end 2024-12-31`
- Dùng file candidate khác:  
  `--candidates config/watchlist_80.txt`

---

## VI. Metrics cần theo dõi sau khi mở universe

- Trades per slice (mục tiêu ≥ 40).
- Exposure % (nếu < 15% → cân nhắc meta-layer Darvas + Livermore).
- PF stability (nếu PF sụp từ 8–15 xuống 2–4 → edge thật nhưng magnitude thấp hơn).
- Trade distribution (top 5 trade có chiếm > 50% profit không).