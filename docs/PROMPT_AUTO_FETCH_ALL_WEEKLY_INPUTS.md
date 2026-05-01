# Prompt: Auto-fetch tất cả input cho Weekly Report (không dùng manual input)

**Mục tiêu:** Hệ thống VN Agent System hiện đọc dữ liệu từ `data/raw/manual_inputs.json` và `data/raw/manual_inputs_prev.json`. Tôi muốn **không còn phải điền tay bất kỳ file nào**. Bạn (Claude web / update skill) cần implement hoặc bổ sung các bước **tự động lấy dữ liệu** và **ghi đúng format** vào các file đó (hoặc vào file thay thế mà pipeline đọc được), sao cho chạy `python -m scripts.run_full_weekly_cycle` là đủ để có báo cáo tuần đầy đủ.

---

## 1. Cấu trúc file đích (contract)

Pipeline đọc hai file chính:

### 1.1. `data/raw/manual_inputs.json` (tuần hiện tại)

```json
{
  "asof_date": "YYYY-MM-DD",
  "global": {
    "fed_tone": "unknown",
    "ust_2y": 3.42,
    "ust_10y": 4.02,
    "dxy": 117.9917,
    "cpi_yoy": null,
    "nfp": 158627.0
  },
  "vietnam": {
    "omo_net": 171395,
    "interbank_on": 8.5,
    "credit_growth_yoy": 15,
    "fx_usd_vnd": 23864
  },
  "market": {
    "vnindex_level": 1696.24,
    "vn30_level": 1853.6,
    "distribution_days_rolling_20": 8,
    "dist_proxy_symbol": "VN30"
  },
  "overrides": {
    "global_liquidity": "tight",
    "vn_liquidity": "easing"
  }
}
```

- **asof_date:** Ngày báo cáo (thường là thứ Sáu hoặc ngày giao dịch gần nhất). Cần **tự động**: lấy “last trading day” hoặc “today” (YYYY-MM-DD).
- **global.ust_2y, ust_10y:** Lãi suất trái phiếu Mỹ 2Y, 10Y (%); nguồn: **FRED** (DGS2, DGS10). Repo đã có `scripts/fetch_global.py` dùng FRED; cần **FRED_API_KEY** trong env.
- **global.dxy:** Chỉ số USD (ví dụ DTWEXBGS trên FRED, hoặc Yahoo DXY). Đã có trong `fetch_global.py`.
- **global.cpi_yoy:** CPI Mỹ YoY (%). FRED có; `fetch_global.py` đã gọi `_fred_cpi_yoy`.
- **global.nfp:** Non-farm payrolls (số việc làm). FRED; `fetch_global.py` đã gọi `_fred_nfp`.
- **vietnam.omo_net:** OMO net (triệu VND hoặc đơn vị SBV). **Chưa có fetcher** — cần scrape SBV hoặc nguồn công bố.
- **vietnam.interbank_on:** Lãi suất liên ngân hàng qua đêm (%). **Chưa có fetcher** — SBV hoặc nguồn thị trường.
- **vietnam.credit_growth_yoy:** Tăng trưởng tín dụng YoY (%). **Chưa có fetcher** — SBV / NHNN.
- **vietnam.fx_usd_vnd:** Tỷ giá USD/VND (số, ví dụ 23864). **Chưa có fetcher** — SBV hoặc Vietcombank/ngân hàng.
- **market.vnindex_level, vn30_level:** Giá đóng cửa VN-Index, VN30. Đã có: **FireAnt** qua `scripts/fetch_vietnam_market.py` và `src/intake/auto_inputs_fireant.py`.
- **market.distribution_days_rolling_20:** Số phiên phân phối (rolling 20). Đã có: **FireAnt historical** qua `scripts/compute_distribution_days.py`.
- **market.dist_proxy_symbol:** Cố định `"VN30"`.
- **overrides:** Có thể để mặc định (e.g. `global_liquidity`, `vn_liquidity`) hoặc infer từ dữ liệu nếu có logic.

### 1.2. `data/raw/manual_inputs_prev.json` (tuần trước — cho WoW)

Cùng schema như trên, nhưng **asof_date** và tất cả số liệu là **tuần trước** (hoặc ngày giao dịch cuối tuần trước). Dùng để tính “What changed (WoW)” cho bond, FX, Vietnam liquidity, market.

- **Cách 1:** Mỗi tuần sau khi chạy xong, copy `manual_inputs.json` → `manual_inputs_prev.json` (đã có `src/intake/roll_week.py`).
- **Cách 2:** Tự động fetch **historical** cho cùng các chỉ số: FRED cho ngày tuần trước, FireAnt historical cho VN30/VNINDEX tuần trước, SBV (nếu có API) cho VN liquidity tuần trước, rồi ghi thẳng vào `manual_inputs_prev.json`.

---

## 2. Danh sách từng ô dữ liệu — nguồn và trạng thái

| Ô dữ liệu | File + path | Nguồn nên dùng | Đã có trong repo? | Ghi chú |
|-----------|------------|----------------|-------------------|--------|
| asof_date | manual_inputs.json (root) | Last trading day hoặc today | Có (trong update_manual_inputs) | Tự set theo ngày chạy hoặc quy ước (vd: thứ 6). |
| ust_2y | global.ust_2y | FRED DGS2 | Có (fetch_global.py) | Cần FRED_API_KEY. |
| ust_10y | global.ust_10y | FRED DGS10 | Có (fetch_global.py) | Cần FRED_API_KEY. |
| dxy | global.dxy | FRED DTWEXBGS hoặc Yahoo DXY | Có (fetch_global.py) | |
| cpi_yoy | global.cpi_yoy | FRED (CPI YoY) | Có (fetch_global.py) | |
| nfp | global.nfp | FRED (NFP) | Có (fetch_global.py) | |
| omo_net | vietnam.omo_net | SBV / NHNN | **Chưa** | Cần implement fetcher (web scrape hoặc API nếu có). |
| interbank_on | vietnam.interbank_on | SBV / thị trường tiền tệ | **Chưa** | Cần implement fetcher. |
| credit_growth_yoy | vietnam.credit_growth_yoy | SBV / NHNN | **Chưa** | Cần implement fetcher. |
| fx_usd_vnd | vietnam.fx_usd_vnd | SBV / VCB / trang tỷ giá | **Chưa** | Cần implement fetcher. |
| vnindex_level | market.vnindex_level | FireAnt | Có (fetch_vietnam_market, auto_inputs_fireant) | |
| vn30_level | market.vn30_level | FireAnt | Có (fetch_vietnam_market, auto_inputs_fireant) | |
| distribution_days_rolling_20 | market.distribution_days_rolling_20 | FireAnt historical VN30 | Có (compute_distribution_days.py) | |
| dist_proxy_symbol | market.dist_proxy_symbol | Cố định "VN30" | Có | |
| **Toàn bộ manual_inputs_prev** | manual_inputs_prev.json | Cùng các nguồn trên, cho ngày tuần trước | Một phần (roll_week copy) | Hoặc fetch historical FRED + FireAnt + SBV cho ngày tuần trước. |

---

## 3. Việc cần làm (checklist cho Claude web / update skill)

1. **Đảm bảo “current week” được fill hoàn toàn tự động**
   - Gọi (hoặc tích hợp) `scripts/update_manual_inputs.py` với `asof` = last trading day / today. Script này đã merge:
     - `scripts/fetch_global.py` → global (ust_2y, ust_10y, dxy, cpi_yoy, nfp)
     - `scripts/fetch_vietnam_market.py` → market (vnindex_level, vn30_level)
     - `scripts/compute_distribution_days.py` → market (distribution_days_rolling_20, dist_proxy_symbol)
   - **Thiếu:** Vietnam liquidity (omo_net, interbank_on, credit_growth_yoy, fx_usd_vnd). Cần:
     - Implement fetcher (Python): scrape SBV hoặc nguồn công bố (OMO, lãi suất liên ngân hàng, tăng trưởng tín dụng, tỷ giá). Output format: dict `vietnam` đúng key như trên.
     - Merge vào `manual_inputs.json` (ghi đè hoặc merge vào key `vietnam`) khi chạy ingestion, **không** cần người dùng mở file điền tay.

2. **asof_date**
   - Không để người dùng sửa file để đổi ngày. Trong bước “ingestion” (trước khi chạy weekly report): set `asof_date` = ngày chạy hoặc “last trading day” (logic trong code), rồi ghi vào `manual_inputs.json`.

3. **manual_inputs_prev.json (WoW)**
   - **Option A:** Mỗi lần chạy xong full weekly, gọi `roll_week` (copy `manual_inputs.json` → `manual_inputs_prev.json`) để tuần sau có WoW.
   - **Option B:** Implement “fetch prior week”: với ngày tuần trước, gọi FRED (historical), FireAnt (historical), và fetcher Vietnam liquidity (nếu có API theo ngày), ghi kết quả vào `manual_inputs_prev.json`. Khi đó không cần roll_week.

4. **Loại bỏ mọi chỗ “manual” trong message cho user**
   - Trong report (HTML/MD), trong warnings, trong open_questions: không còn nhắc “cập nhật manual_inputs” hay “điền manual_inputs_prev”. Thay bằng: “Dữ liệu WoW sẽ có sau khi chạy ingestion + roll (hoặc fetch prior week).”

5. **Env / config**
   - Document rõ: `FRED_API_KEY` cần cho global. Nếu thiếu, global có thể null — không coi đó là “manual”, mà là “chưa cấu hình API”.
   - Nếu SBV fetcher cần API key hoặc cookie, ghi vào README/env example.

---

## 4. Thứ tự chạy mong muốn (không manual)

1. **Ingestion (mỗi tuần, trước hoặc trong “full cycle”):**
   - Set `asof_date` (auto).
   - Fetch global (FRED) → merge vào `manual_inputs.json`.
   - Fetch Vietnam market (FireAnt) + distribution days → merge vào `manual_inputs.json`.
   - Fetch Vietnam liquidity (SBV / nguồn mới) → merge vào `manual_inputs.json`.
   - (Tùy chọn) Fetch hoặc roll để có `manual_inputs_prev.json`.

2. **Weekly report:**
   - `python -m src.report.weekly --render` (đọc `manual_inputs.json`, `manual_inputs_prev.json`).

3. **Normalize + render:**
   - `python -m scripts.ingest.run_weekly_update` (đã gọi weekly ở bước 2 nếu không --skip-weekly).
   - `python -m scripts.reporting.render_weekly_report`.

4. **Một lệnh duy nhất:** `python -m scripts.run_full_weekly_cycle` sẽ chạy toàn bộ; không file manual nào cần mở để điền.

---

## 5. Định dạng và đường dẫn cố định

- **Current week:** `data/raw/manual_inputs.json`
- **Prior week (WoW):** `data/raw/manual_inputs_prev.json`
- **Schema:** Đúng như ví dụ JSON ở mục 1; số có thể `null` nếu nguồn lỗi hoặc chưa cấu hình; pipeline đã xử lý null (hiển thị "—", warning).

---

## 6. Tóm tắt “còn thiếu” để không còn manual

| Hạng mục | Trạng thái | Hành động |
|----------|------------|-----------|
| Global (UST 2Y/10Y, DXY, CPI YoY, NFP) | Đã có (FRED) | Chỉ cần set FRED_API_KEY và gọi update_manual_inputs (hoặc tương đương) trong pipeline. |
| Market VN (VNINDEX, VN30, dist days) | Đã có (FireAnt) | Đã trong update_manual_inputs / auto_inputs_fireant. |
| asof_date | Một phần | Tự set trong ingestion (last trading day / today), không đọc từ tay. |
| Vietnam liquidity (OMO, interbank, credit growth, FX) | **Chưa có** | **Implement fetcher** (SBV hoặc nguồn thay thế), merge vào `manual_inputs.json`. |
| manual_inputs_prev (WoW) | Chỉ có roll (copy) | Dùng roll sau mỗi lần chạy, hoặc implement fetch historical cho tuần trước. |
| Copy / message “manual” trong UI | Đang còn | Xóa hoặc đổi thành “tự động sau khi chạy ingestion”. |

---

Bạn hãy implement các fetcher còn thiếu (đặc biệt Vietnam liquidity), tích hợp vào bước ingestion, đảm bảo `manual_inputs.json` và `manual_inputs_prev.json` luôn được ghi bởi code (không cần người dùng mở file), và cập nhật mọi chỗ nhắc “manual input” trong report/docs thành “auto after ingestion”.
