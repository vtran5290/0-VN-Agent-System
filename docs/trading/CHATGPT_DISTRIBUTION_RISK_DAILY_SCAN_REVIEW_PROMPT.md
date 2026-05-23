# ChatGPT Review Prompt — Distribution Risk Lens v1.2 + Daily Scan + Cloud Daily Report

**Paste this entire file into ChatGPT and attach:** `distribution_risk_daily_scan_chatgpt_20260520.zip`

No prior chat context required.

---

## Your role

You are an **independent QA / research reviewer** for a Vietnam equities operator stack. Validate:

1. **Distribution Risk Lens v1.2** — methodology, VIN/ex-VIN dual view, probability tables, warning states
2. **Integration** — `daily_scan.md`, `cloud-daily-report`, auto-refresh, no trading-logic leakage
3. **EOD pipeline as-of 2026-05-20** — data freshness, consistency across outputs
4. **Analyst notes** — session recovery + MA context vs historical buckets (sanity-check only)

**Do not** recommend changing `final_action`, A3/S3 rules, OMS, order routing, or live capital deployment.

---

## Patch / delivery summary (FACTS)

| Item | Value |
|------|--------|
| **Method version** | `distribution_risk_lens_v1.2` |
| **As-of date** | 2026-05-20 |
| **Primary index view** | `ex_vin_proxy` (labelled proxy — NOT native ex-VIN index) |
| **VNINDEX raw warning** | `DISTRIBUTION_CLUSTER` (dist 10/25/50 = 3/4/9) |
| **ex-VIN proxy warning** | `CAUTION` (dist 10/25/50 = 2/3/7) |
| **VIN distortion flag** | `true` |
| **Phase36 scan** | 101 symbols; A3 breadth **31.4%** (defense) |
| **Portfolio NAV (local SSOT)** | 4,397,660,045 VND; 10 holdings; portfolio as-of **2026-05-19** |
| **Tests cited at build** | **80 passed** (distribution + cloud report + portfolio_state) |
| **Cloud report status** | `NEEDS_REVIEW` (ex-VIN proxy stale: last 2026-05-19 vs requested 2026-05-20) |
| **Manual-review T1 (scan SSOT)** | TRC, OIL, DXS, VGI, BID — `counts.manual_review_t1 = 5` |

**Safety invariant (must appear in all reports):**

> Distribution Risk Lens is **market context only** and does **not** change `final_action`.

---

## Data source discipline (mandatory in your review)

When citing market data:

- **source** = FireAnt (REST) for OHLCV refresh; VNINDEX also from repo CSV/parquet merge
- **method** = REST API + derived ex-VIN proxy decomposition
- **symbols** = VNINDEX native; ex-VIN proxy; VIN basket VIC/VHM/VRE (VPL excluded if &lt;252 bars)
- **date range** = 2012-01-01 → 2026-05-20 (data start flagged 2012-01-03)
- **proxy** = ex-VIN is **derived**, not exchange index — never present as native
- **limitations** = cap-weight VNINDEX may be VIN-skewed 2025–2026; lens horizons are **5, 10, 25, 75, 100d** (not 20/50/150 native)

---

## Files in this package

| Path in zip | Role |
|-------------|------|
| `REVIEW_PROMPT.md` | This file |
| `README.txt` | How to use zip |
| `ANALYST_CONTEXT_20260520.md` | Operator Q&A: expected returns, session/MA analogues |
| `docs/CLOUD_DAILY_REPORT_GUIDE.md` | Operator runbook |
| `docs/VIN_EMA_CLOUD_BASELINE.md` | Dual universe + VIN contamination rules |
| `src/market/distribution_risk_lens/` | Lens core (definitions → pipeline) |
| `src/trading/reports/cloud_daily_report.py` | Cloud report builder |
| `src/trading/reports/distribution_risk_card.py` | Section G card + refresh helper |
| `scripts/reporting/daily_scan_report.py` | `daily_scan.md` / `.json` |
| `scripts/scan_ssot.py` | Compatibility shim (imports `scripts.ingest.scan_ssot`) |
| `scripts/ingest/scan_ssot.py` | Canonical scan SSOT resolver |
| `scripts/daily_scan_report.py` | CLI wrapper |
| `scripts/research/run_distribution_risk_lens.py` | CLI runner |
| `scripts/maintenance/refresh_eod_20260519.py` | EOD refresh pattern (extended to 20/5) |
| `tests/test_distribution_*.py` | Lens + cloud integration tests |
| `outputs/distribution_risk_latest.json` | Latest lens snapshot |
| `outputs/distribution_days_probability_table.csv` | Bucket mean/median fwd returns |
| `outputs/distribution_days_forward_returns_2024plus.csv` | Per-day features + fwd outcomes (2024+ subset; full 2012 file not in zip) |
| `outputs/analyst_historical_buckets_20260520.csv` | Reproducibility summary for ANALYST_CONTEXT filter buckets |
| `outputs/daily_scan.md` | Consolidated operator scan |
| `outputs/daily_scan.json` | Machine-readable scan |
| `outputs/cloud_daily_report_latest.md` | Cloud report markdown |
| `outputs/cloud_daily_report_latest.json` | Cloud report payload |
| `outputs/phase36_daily_scan_latest.csv` | Scan SSOT |
| `outputs/phase36_daily_scan_20260520.csv` | Dated snapshot |
| `outputs/VNINDEX_recent_5d.csv` | Last 5 VNINDEX rows + MA distances |

---

## Round 2 patches (verify in this review)

| ID | Fix |
|----|-----|
| P0-1 | Per-view `last_data_date` / `is_stale_for_as_of`; freshness table; `PRIMARY_VIEW_STALE` → NEEDS_REVIEW |
| P0-2 | S3 shadow no longer demotes `NEW_T1_MANUAL_REVIEW_BREADTH`; cloud counts/list = 5 symbols |
| P1-1 | No "Prepare next-open order" — manual-review checklist wording only |
| P1-2 | ex-VIN `note` + "NOT a native exchange index" in rendered reports |
| P1-3 | Canonical `scripts/reporting/daily_scan_report.py` imports `scripts.scan_ssot`; zip includes `scripts/ingest/scan_ssot.py` |
| P1-4 | `ANALYST_CONTEXT_20260520.md` matches `VNINDEX_recent_5d.csv` (full-history EMA, not tail-only) |
| P2 | Zip lists `forward_returns_2024plus` + `analyst_historical_buckets` (not full 2012 CSV) |

---

## Review focus — 8 checks

### Check 1 — Research-only boundary

Confirm nowhere in lens card, `daily_scan.md`, or cloud report:

- Overrides `final_action`
- Issues buy/sell orders
- Writes `portfolio_state.json` trading decisions

Lens must be labelled **context / research**.

### Check 2 — ex-VIN proxy disclosure

Verify `distribution_risk_latest.json` and report sections state:

- `is_proxy: true` for ex-VIN
- `NOT true ex-VIN index` note present
- Primary view = `ex_vin_proxy` while raw may disagree

### Check 3 — P1 fixes (v1.2)

| Fix | Expected |
|-----|----------|
| VIN group volume | If basket volume missing → dist counts **null**, warning **UNKNOWN** (not false NORMAL) |
| Correction prob | `p_correction_10pct_75d` uses **−10%** threshold (not −5%) |
| Horizon base rates | `snapshot_probabilities()` uses horizon-specific base rates |
| Raw vs ex-VIN spread | Date-aligned closes in `pipeline.py` |

Flag any code path that still mixes horizons or uses wrong drawdown threshold.

### Check 4 — Warning state + freshness (2026-05-20)

From `distribution_risk_latest.json`:

- Raw: `DISTRIBUTION_CLUSTER` with dist 3/4/9
- ex-VIN: `CAUTION` with dist 2/3/7
- `raw_vs_ex_vin_warning_disagreement: true`
- `vin_distortion_warning: true`
- `ex_vin_proxy.last_data_date` = **2026-05-19** vs `requested_as_of_date` = **2026-05-20** → `is_stale_for_as_of: true`
- `report_status` = **NEEDS_REVIEW**; `PRIMARY_VIEW_STALE` in load_warnings

Cross-check freshness table in `daily_scan.md` and cloud report; probabilities must be caveated, not implied fully as-of 20/5 for ex-VIN.

### Check 5 — Probability table vs snapshot JSON

For **ex_vin_proxy**, bucket **dist_count_25d = 3**, compare:

- `p_ret_neg_10d`, `p_ret_neg_25d`, `mean_fwd_ret` in CSV vs JSON `probabilities` / `lift_vs_base`
- Sample size and confidence labels reasonable (n≈600, HIGH)

### Check 6 — Cloud daily report integration

- `cloud-daily-report --mode eod` refreshes lens before build (or documents refresh path)
- Section G / JSON field `distribution_risk_lens` present
- `distribution_risk_lens_version` = v1.2

### Check 7 — Daily scan + scan SSOT alignment

- `daily_scan.md` header as-of **2026-05-20**
- SSOT path = `phase36_daily_scan_latest.csv` (or dated 20260520 copy)
- Portfolio block cites `portfolio_state.json` / derived positions; NAV not inferred from prices alone
- Breadth defense + T2 blocked language consistent with Phase36 rules

### Check 7b — Cloud manual-review list (P0-2)

From `cloud_daily_report_latest.json`:

- `counts.manual_review_t1` = **5**
- `new_entry_symbols` = **["TRC","OIL","DXS","VGI","BID"]** (rank DESC)
- MD must **not** say "2 manual-review"; must list all 5 in Group 1
- No phrase "Prepare next-open order" in EOD report

### Check 8 — Analyst context sanity (2026-05-20 session)

Read `ANALYST_CONTEXT_20260520.md`. Verify:

- VNINDEX 20/5: wide range, vol 1.46× MA20, close_loc ≈ 0.90, **not** a distribution day; prior day **was** dist
- Above EMA10/20/50 but only **+0.36%** above EMA10
- Historical bucket claims trace to `outputs/analyst_historical_buckets_20260520.csv` and/or `distribution_days_forward_returns_2024plus.csv`
- `ANALYST_CONTEXT_20260520.md` agrees with `outputs/VNINDEX_recent_5d.csv` on 2026-05-20 (full-history EMA method)
- No overclaim that “good recovery” is a separate lens bucket (it is **analogue analysis**, not v1.2 feature)

---

## Key numbers to verify (canonical for this package)

### Lens snapshot (ex-VIN primary, dist_25d=3)

| Metric | Value |
|--------|-------|
| p_ret_neg_10d | ~32.9% (base ~40.1%) |
| p_ret_neg_25d | ~32.8% |
| mean_fwd 10d (bucket table) | ~+1.1% |
| mean_fwd 25d | ~+2.0% |
| mean_fwd 100d | ~+6.2% |
| p_correction_5pct_25d | ~36.1% |
| p_correction_10pct_75d | ~39.0% |

### VNINDEX raw (dist_10d ≥ 3)

| Horizon | mean_fwd (approx) | p_ret_neg |
|---------|-------------------|-----------|
| 10d | +0.5% | ~42.6% |
| 25d | +1.1% | ~39.1% |
| 100d | +3.8% | ~37.3% |

### Phase36 / portfolio

| Metric | Value |
|--------|-------|
| NAV VND | 4,397,660,045 |
| Holdings | STB, MSB, BID, VCB, CTG, HCM, TCX, VIX, DXG, PDR |
| A3 breadth | 31.4% |
| Regime | bull (per scan) |

---

## Commands (operator regenerate)

```powershell
# EOD refresh (extend end date as needed)
.venv\Scripts\python.exe scripts\maintenance\refresh_eod_20260519.py

# Distribution lens
.venv\Scripts\python.exe -m src.trading.cli distribution-risk --as-of 2026-05-20

# Phase36 scan + daily scan report
.venv\Scripts\python.exe pp_backtest\portfolio_optimization_final_steps.py --step scan
.venv\Scripts\python.exe scripts\reporting\daily_scan_report.py

# Cloud daily report
.venv\Scripts\python.exe -m src.trading.cli cloud-daily-report --mode eod

# Tests
.venv\Scripts\python.exe -m pytest tests\test_distribution_days.py tests\test_distribution_risk_lens.py tests\test_cloud_daily_report_distribution_risk.py tests\test_cloud_daily_report.py tests\test_portfolio_state.py -q
```

---

## Response format

```
## PASS / FAIL / NEEDS_REVISION

### Check 1 — Research-only boundary: [PASS|FAIL]
Finding: ...

### Check 2 — ex-VIN proxy disclosure: [PASS|FAIL]
Finding: ...

### Check 3 — P1 v1.2 fixes: [PASS|FAIL]
Finding: ...

### Check 4 — Warning consistency 2026-05-20: [PASS|FAIL]
Finding: ...

### Check 5 — Probability table vs JSON: [PASS|FAIL]
Finding: ...

### Check 6 — Cloud daily report integration: [PASS|FAIL]
Finding: ...

### Check 7 — Daily scan + SSOT: [PASS|FAIL]
Finding: ...

### Check 8 — Analyst context sanity: [PASS|FAIL]
Finding: ...

### FACTS vs INTERPRETATION separation: [PASS|FAIL]
Finding: ...

### Remaining issues (if any):
1. [file]: [issue] — severity P0|P1|P2

### Optional improvements (research-only, no trading logic):
1. ...

### Overall verdict:
[one paragraph]

### CURSOR_IMPLEMENTATION_PROMPT
(Only if NEEDS_REVISION — concise patch list for Cursor; no strategy changes)
```

---

## Hard constraints for your recommendations

- No changes to A3 T1/T2, breadth gates, TP/trail, or `final_action` semantics
- No live broker / DNSE / OMS recommendations
- Any new horizon (20d/50d/150d) = **research extension**, not production trading input
- Prefer **ex-VIN + breadth** for broad-market conclusions; caveat VNINDEX raw when `vin_distortion_warning`

---

*Package built for external review — VN Agent System.*
