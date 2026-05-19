# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-19T10:19:46.455081+07:00 |
| Mode | pre-lunch |
| Session | MORNING_CONTINUOUS |
| Active setups | 95 |
| Manual-review candidates | 1 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 14 / 95 / 85 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-18
- **scan panel as-of (with intraday bars):** 2026-05-19
- **quotes fetched:** 14 / 14
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 14
- **scan_symbols_count:** 95
- **missing_quote_count:** 85
- **holdings_path:** `data\trading\holdings.txt` (14 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-18 close=1927.94
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1924.77
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 32.2%
- **pct_cloud_bull_s3:** 31.7%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=4, `NO_T2_BREADTH`=19, `TP1_PARTIAL`=2, `TRAIL_EXIT`=30, `WATCH_ONLY`=35

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (4)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| KSV      |       163    |           2.834 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| SHI      |        14.75 |           0.898 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| BMP      |       154.5  |           0.891 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| QNS      |        48.8  |           0.351 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| TCO      |        15.55 |           2.831 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VHM      |       154    |           0.322 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

### would_be `TRAIL_EXIT` (30)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| TCH      |        16.65 |           2.921 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| EIB      |        21.7  |           2.891 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VCG      |        21.2  |           2.813 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NVL      |        17    |           0.958 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| PPC      |         9.79 |           0.927 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VRE      |        33.1  |           0.916 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MSN      |        76.5  |           0.913 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HUT      |        15.8  |           0.911 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MCH      |       132    |           0.905 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HHS      |        13.35 |           0.877 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HNM      |         7.5  |           0.875 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MZG      |        13.2  |           0.859 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DGW      |        42    |           0.852 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VHC      |        59    |           0.851 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NRC      |         6.2  |           0.85  | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| KBC      |        32.05 |           0.822 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| SMC      |        11.8  |           0.793 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MWG      |        79    |           0.738 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HDG      |        24.45 |           0.728 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| CRC      |         8.21 |           0.694 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **95**; action changed IF_CLOSE_NOW: **1**

| symbol   | would_be_final_action   | final_action     | eod_final_action             |
|:---------|:------------------------|:-----------------|:-----------------------------|
| PVS      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **50**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action   |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:------------------------|----------------:|-------------:|:-------------------------|
| NVL      | TRAIL_EXIT              |           0.958 |           17 | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 10 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
