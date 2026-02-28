# Smart Money Dashboard — Layer 3.5 (Institutional Positioning)

**Mục tiêu:** Biến fund reports (VEIL, VOF, PYN, open-end, ETF) thành **1 lớp Institutional Positioning** đứng giữa Sector Bias và Technical, feed thẳng vào **Regime / Position Engine**.

Kiến trúc được thiết kế để:

- **Facts-first:** chỉ đọc dữ liệu có thật trong reports / JSON.
- **No hallucination:** nếu thiếu số → `null` + ghi rõ trong `missing_data`.
- **Single Source of Truth:** toàn bộ positioning / consensus nằm trong `data/smart_money/`.

---

## 1. Vị trí layer trong hệ thống

Flow sau khi thêm Layer 3.5:

- **Macro Regime (liquidity, policy)**
- **Sector Bias (top–down)**
- **Layer 3.5 — Institutional Positioning (Smart Money Dashboard)**
- **Technical Setup**
- **Execution (sell/trim)**
- **Audit / Decision Log**

Layer 3.5 trả về:

- **Crowded trade** (single name + sector).
- **Under-owned sectors / buckets.**
- **Risk-on level (cash regime của smart money).**
- **Policy-alignment score** (ví dụ Resolution 79 / FTSE upgrade).
- **Gợi ý bias** cho Position Engine (over/under-weight theo nhóm).

---

## 2. File & thư mục chính

- `docs/SMART_MONEY_DASHBOARD.md` — tài liệu này (spec layer).
- `agents/smart_money_dashboard.md` — prompt cho Smart Money Agent (LLM).
- `src/smart_money/`:
  - `io.py` — I/O helpers cho `data/smart_money/*`.
  - `consensus.py` — build consensus + crowding metrics từ per-fund JSON.
  - `scoring.py` — tính `crowding_score`, `risk_on_score`, `policy_alignment_score`, `regime_bias`.
  - `run_monthly.py` — CLI: đọc JSON theo tháng, ghi consensus file.
- `data/smart_money/`:
  - `raw/` — (tùy chọn) lưu PDF/ZIP hoặc pointer.
  - `extracted/` — JSON per-fund, per-month.
  - `monthly/` — consensus JSON mỗi tháng, feed vào engine.

**Nguyên tắc:**  
PDF / factsheet được xử lý bởi LLM ở ngoài Cursor → output JSON chuẩn → copy vào repo.  
Cursor chỉ đọc **JSON**, không parse PDF trực tiếp.

---

## 3. JSON schema — Single Source of Truth

### 3.1 Per-fund extracted JSON

Vị trí: `data/smart_money/extracted/<fund>_<YYYY-MM>.json`

```json
{
  "fund_name": "string",
  "fund_code": "string|null",
  "report_month": "YYYY-MM",
  "as_of_date": "YYYY-MM-DD|null",
  "equity_weight": 0.0,
  "cash_weight": 0.0,
  "top_holdings": [
    { "rank": 1, "ticker": "MBB", "weight": 8.7, "source_section": "Top Holdings" }
  ],
  "sector_weights": [
    { "sector": "Banks", "weight": 38.0, "source_section": "Sector Allocation" }
  ],
  "manager_themes": [
    { "theme_tag": "Resolution79", "polarity": "Positive", "evidence": "..." }
  ],
  "missing_data": ["cash_weight", "sector_weights"],
  "confidence": { "holdings": 0.9, "themes": 0.7 }
}
```

**Rules:**

- Không bịa ticker, weight, date. Nếu không có số → `null` + thêm vào `missing_data`.
- `manager_themes` chỉ chứa **policy / macro / earnings themes** trích từ commentary, không tự suy diễn.

### 3.2 Monthly consensus JSON

Vị trí: `data/smart_money/monthly/smart_money_<YYYY-MM>.json`

```json
{
  "month": "YYYY-MM",
  "fund_universe": {
    "n_funds": 0,
    "funds": ["VEIL", "VOF", "PYN", "VEOF", "VDEF", "VESAF", "VMEEF"]
  },
  "ticker_consensus": [
    {
      "ticker": "MBB",
      "n_top5": 0,
      "n_top10": 0,
      "funds_top10": ["VEOF", "VEIL"],
      "avg_weight_top10": 0.0
    }
  ],
  "sector_consensus": [
    {
      "sector": "Banks",
      "avg_weight": 0.0,
      "median_weight": 0.0,
      "dispersion": 0.0
    }
  ],
  "scores": {
    "crowding_score": 0,
    "risk_on_score": 0,
    "policy_alignment_score": 0
  },
  "regime_bias": "Bullish",
  "policy_tags_strength": {
    "Resolution79": 0,
    "FTSEUpgrade": 0,
    "SBVLiquidity": 0,
    "CreditGrowth": 0
  },
  "flags": [
    { "type": "SectorCrowding", "detail": "Banks avg>30%" }
  ],
  "deltas": {
    "vs_prev_month": {
      "ownership_momentum": [{ "ticker": "MBB", "delta_n_top10": 0 }],
      "median_cash_change": 0.0
    }
  },
  "diagnostics": {
    "missing_funds": [],
    "notes": []
  }
}
```

---

## 4. Scoring & logic v1

### 4.1 Crowding score (`crowding_score`, 0–10)

- **Single-name crowding** (dựa trên `n_top10 / n_funds`):
  - ≥ 70% → +4 điểm.
  - 50–69% → +3 điểm.
  - 30–49% → +2 điểm.
- **Sector crowding** (dựa trên `avg_weight`):
  - ≥ 35% → +4 điểm.
  - 30–34% → +3 điểm.
  - 25–29% → +2 điểm.
- **Clamp** tổng điểm về [0, 10].  
  Nếu thiếu dữ liệu (quá ít fund hoặc thiếu sector/holdings) → score gần 0 và ghi chú trong `diagnostics.notes`.

### 4.2 Risk-on score (`risk_on_score`, 0–10)

- Dùng **median `cash_weight`** toàn universe:
  - ≤ 2% → +5 điểm (Max risk-on).
  - 2–5% → +4 điểm.
  - 5–10% → +3 điểm.
  - 10–20% → +1 điểm.
  - > 20% hoặc thiếu dữ liệu → 0 điểm.
- Có thể cộng thêm 1–2 điểm nhẹ nếu sector beta cao (Banks, Brokers, Real Estate) đang chiếm tỷ trọng lớn; phiên bản này giữ MVP: chỉ dùng cash.

### 4.3 Policy-alignment score (`policy_alignment_score`, 0–10)

- Đếm số fund có **theme_tag** policy (ví dụ `"Resolution79"`, `"FTSEUpgrade"`, `"SBVLiquidity"`, `"CreditGrowth"`).
- Với mỗi tag:
  - `tag_score = 10 * (n_funds_with_positive_tag / n_funds_total)` (clamp 0–10).
  - Ghi vào `policy_tags_strength[tag]`.
- `policy_alignment_score` = **trung bình** các `tag_score` khác 0.  
  Nếu không fund nào nhắc đến policy tag → score = 0.

### 4.4 Regime bias (Smart Money)

- Dựa trên `crowding_score` và `risk_on_score`:
  - **Bullish:** `risk_on_score ≥ 7` và `crowding_score ≤ 6`.
  - **Extended:** `risk_on_score ≥ 7` và `crowding_score ≥ 7`.
  - **Fragile:** `risk_on_score ≤ 3` và `crowding_score ≥ 7`.
  - Ngược lại → dùng label đơn giản nhất gần nhất (ví dụ `Extended` nếu cả hai ở mid-high); logic chi tiết nằm trong `src/smart_money/scoring.py`.

---

## 5. CLI / Runbook — Smart Money layer

### 5.1 Chuẩn bị dữ liệu (ngoài Cursor)

Mỗi tháng:

- Gom tất cả fund reports (VEIL, VOF, PYN, VEOF, VDEF, VESAF, ETF, …).
- Dùng LLM (ChatGPT) để **parse** theo schema 3.1:
  - Một file JSON per-fund: `<fund>_<YYYY-MM>.json`.
  - Đảm bảo:
    - Không bịa số.
    - `missing_data` liệt kê các field không lấy được.
    - `confidence` ∈ [0, 1].

Sau đó:

- Copy các file JSON vào: `data/smart_money/extracted/`.

### 5.2 Chạy consensus engine (trong repo)

Module: `src/smart_money/run_monthly.py`

- Input:
  - `--month YYYY-MM` (bắt buộc).
  - `--prev-month YYYY-MM` (tùy chọn, để tính deltas).
- Hành vi:
  - Đọc tất cả file `data/smart_money/extracted/*_<month>.json`.
  - Build:
    - `fund_universe`.
    - `ticker_consensus`.
    - `sector_consensus`.
    - `scores` + `regime_bias`.
    - `flags`.
    - `deltas.vs_prev_month.ownership_momentum`.
  - Ghi output:
    - `data/smart_money/monthly/smart_money_<month>.json`.

Ví dụ:

```bash
python -m src.smart_money.run_monthly --month 2026-02 --prev-month 2026-01
```

---

## 6. Hook với Position Engine / Decision Layer

**Nguyên tắc:** Smart Money layer **cố vấn** cho Regime/Allocation, không override cứng trừ khi bạn chủ động bật.

Các điểm hook gợi ý:

- Weekly report (`src/report/weekly.py`):
  - Đọc `data/smart_money/monthly/smart_money_<YYYY-MM>.json` theo `asof_date`.
  - Thêm 1 subsection: **Smart Money Positioning**:
    - Mega consensus stocks.
    - Sector crowding.
    - Cash regime (risk-on level).
    - Policy-alignment (nếu > 0).
- Allocation engine (`src/alloc/engine.py` hoặc module mới):
  - Đọc `crowding_score`, `risk_on_score`, `regime_bias`.
  - Tùy chọn: adjust `gross_exposure` band (ví dụ clamp upper band khi `Extended` + crowding cao).
- Decision log (`decision_log/<date>.json`):
  - Thêm snapshot Smart Money: scores, flags chính → phục vụ audit sau này.

Phiên bản này chỉ tạo **layer + engine + schema**.  
Hook cụ thể vào gross_cap / bucket allocation có thể thêm ở phiên bản sau, khi bạn đã chạy vài tháng để **calibrate**. 

