# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-19T11:17:24.854133+07:00 |
| Mode | pre-atc |
| Session | MORNING_CONTINUOUS |
| Active setups | 2 |
| Manual-review candidates | 1 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 3 / 2 / 0 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-18
- **scan panel as-of (with intraday bars):** 2026-05-19
- **quotes fetched:** 3 / 3
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 3
- **scan_symbols_count:** 2
- **missing_quote_count:** 0
- **holdings_path:** `data\trading\holdings.txt` (14 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-18 close=1927.94
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1924.08
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 31.8%
- **pct_cloud_bull_s3:** 31.3%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `NO_T2_BREADTH`=1, `TRAIL_EXIT`=1

### would_be `TRAIL_EXIT` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| HPG      |         26.5 |           0.367 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **2**; action changed IF_CLOSE_NOW: **0**

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **1**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action   |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:------------------------|----------------:|-------------:|:-------------------------|
| HPG      | TRAIL_EXIT              |           0.367 |         26.5 | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 1 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
