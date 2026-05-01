# Inputs còn thiếu — danh sách để Claude web săn nguồn & plug vào automation

Bộ máy weekly report cần các ô dữ liệu dưới đây. **Đã có sẵn trong repo**: Global (FRED), Market VN (FireAnt), **Vietnam liquidity (SBV)**. Còn thiếu = chưa có fetcher hoặc chưa săn được nguồn.

---

## 1. Vietnam liquidity — đã có nguồn và đã implement

**Nguồn:** SBV (scrape HTML). **Fetcher:** `scripts/fetch_vietnam_liquidity.py`. **Chi tiết URL + cách parse:** `docs/SBV_LIQUIDITY_SOURCES.md`. **Skill:** `.cursor/skills/vn_sbv_liquidity/skill.md`.

| # | Tên | Nguồn SBV | Ghi chú |
|---|-----|-----------|--------|
| 1 | omo_net | sbv.gov.vn/.../nghiep-vu-thi-truong-mo | Trang chỉ phiên mới nhất; net = Mua − Bán (tỷ đồng). |
| 2 | interbank_on | sbv.gov.vn/lãi-suất1 | Hàng "Qua đêm" → cột lãi suất (%). |
| 3 | credit_growth_yoy | sbv.gov.vn/.../du-no-tin-dung-doi-voi-nen-kt-dttktt | Hàng TỔNG CỘNG → Tốc độ tăng; SBV báo YTD. |
| 4 | fx_usd_vnd | sbv.gov.vn/tỷ-giá | Hàng "1 Đô la Mỹ" → tỷ giá trung tâm. |

**Cách dùng:** `python scripts/update_manual_inputs.py --asof YYYY-MM-DD --force-vn-liquidity` để merge SBV vào `manual_inputs.json` → `vietnam`.

---

## 2. Global — đã có, chỉ cần API key

| Ô | Nguồn trong repo | Cần gì |
|---|------------------|--------|
| ust_2y, ust_10y, dxy, cpi_yoy, nfp | FRED qua `scripts/fetch_global.py` | Biến môi trường `FRED_API_KEY`. Không cần săn thêm. |

---

## 3. Market VN — đã có

| Ô | Nguồn trong repo |
|---|------------------|
| vnindex_level, vn30_level | FireAnt (`scripts/fetch_vietnam_market.py`, `src/intake/auto_inputs_fireant.py`) |
| distribution_days_rolling_20 | FireAnt historical (`scripts/compute_distribution_days.py`) |

Không cần săn thêm.

---

## 4. Tuần trước (WoW) — manual_inputs_prev

Để có WoW (bond, FX, Vietnam liquidity, market), hệ thống đọc `data/raw/manual_inputs_prev.json` (cùng schema với `manual_inputs.json`, nhưng asof_date = tuần trước).

- **Cách hiện tại:** Roll (copy `manual_inputs.json` → `manual_inputs_prev.json`) sau mỗi lần chạy — không cần nguồn mới.
- **Nếu muốn “fetch tuần trước”:** Cần nguồn **historical** cho từng chỉ số (FRED đã hỗ trợ ngày; FireAnt có historical; Vietnam 4 ô trên cần trang/API có số theo ngày hoặc theo tuần). Claude web có thể săn: “SBV OMO theo ngày”, “lãi suất liên ngân hàng lịch sử”, “tăng trưởng tín dụng theo tháng”, “tỷ giá USD VND lịch sử”.

---

## 5. Prompt ngắn gửi Claude web (săn nguồn Vietnam)

Copy block dưới cho Claude web:

```
Tôi cần săn nguồn dữ liệu công bố (trang web hoặc API) cho 4 chỉ số Việt Nam sau, để tự động hóa (scrape/API) và ghi vào file JSON hàng tuần:

1. OMO net (giao dịch thị trường mở ròng của NHNN/SBV) — số liệu theo ngày hoặc tuần, đơn vị rõ (triệu/tỷ VND).
2. Lãi suất liên ngân hàng qua đêm (VND overnight interbank rate) — %.
3. Tăng trưởng dư nợ tín dụng YoY (credit growth year-on-year) — %.
4. Tỷ giá USD/VND (chính thức hoặc bán) — số.

Hãy tìm: (a) Trang chính thức SBV/NHNN hoặc ngân hàng lớn công bố các chỉ số này. (b) Nếu có API công bố (SBV, VCB, hoặc bên thứ ba đáng tin) thì ghi rõ endpoint và cách lấy. (c) Tần suất cập nhật (ngày/tuần/tháng). (d) Format (HTML table, CSV, JSON, PDF) để tôi viết code lấy.
```

---

## 6. Tóm tắt “còn thiếu” để plug vào automation

| Hạng mục | Trạng thái | Ghi chú |
|----------|------------|--------|
| **Vietnam liquidity** | Đã implement | SBV scrape: `scripts/fetch_vietnam_liquidity.py`; merge bằng `update_manual_inputs.py --force-vn-liquidity`. Xem `docs/SBV_LIQUIDITY_SOURCES.md`, skill `vn_sbv_liquidity`. |
| **Tuần trước (WoW)** | Tùy chọn | Roll (copy manual_inputs → manual_inputs_prev) hoặc fetch historical. |
| Global, Market VN | Đã đủ | FRED + FireAnt; chỉ cần FRED_API_KEY và chạy ingestion. |

File này giữ **danh sách từng ô** và tham chiếu nguồn/script; Vietnam 4 ô đã được plug vào automation.
