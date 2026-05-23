# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-20T14:06:42.909629+07:00 |
| Mode | pre-atc |
| Session | AFTERNOON_CONTINUOUS |
| Active setups | 100 |
| Manual-review candidates | 1 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 10 / 100 / 93 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-19
- **scan panel as-of (with intraday bars):** 2026-05-20
- **quotes fetched:** 10 / 10
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 10
- **scan_symbols_count:** 100
- **missing_quote_count:** 93
- **holdings_path:** `data\trading\holdings.txt` (10 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-19 close=1912.93
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1901.65
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 31.8%
- **pct_cloud_bull_s3:** 32.5%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=6, `NEW_T1_MANUAL_REVIEW_BREADTH`=7, `NO_T2_BREADTH`=16, `TP1_PARTIAL`=1, `TRAIL_EXIT`=35, `WATCH_ONLY`=35

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (7)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| KOS      |         38.7 |           0.972 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NTP      |         61.1 |           0.958 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| GSP      |         11.5 |           0.929 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| TCB      |         32.6 |           0.897 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| OIL      |         15.6 |           0.843 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| TRC      |         75.1 |           0.459 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| BID      |         43.4 |           0.359 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TP1_PARTIAL` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VHM      |          157 |           0.249 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

### would_be `TRAIL_EXIT` (35)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.7  |           2.901 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| TCH      |        16.4  |           2.861 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VCG      |        21.1  |           2.809 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DRI      |        14.1  |           1     | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VTO      |        12.05 |           0.995 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HHS      |        13    |           0.989 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| SHI      |        14.4  |           0.983 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HDB      |        26.7  |           0.956 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MSN      |        76.5  |           0.921 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HUT      |        15.8  |           0.919 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MCH      |       131    |           0.88  | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NVL      |        16.7  |           0.878 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NRC      |         6.2  |           0.864 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DGW      |        41.9  |           0.855 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| GVR      |        36.55 |           0.855 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| LPB      |        51.6  |           0.848 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VHC      |        58.6  |           0.835 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HNM      |         7.4  |           0.828 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| KBC      |        31.65 |           0.783 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| SMC      |        11.7  |           0.775 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **99**; action changed IF_CLOSE_NOW: **2**

| symbol   | would_be_final_action        | final_action     | eod_final_action             |
|:---------|:-----------------------------|:-----------------|:-----------------------------|
| BID      | NEW_T1_MANUAL_REVIEW_BREADTH | INTRADAY_PREVIEW | WATCH_ONLY                   |
| CTG      | HOLD_T1_ONLY                 | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **59**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action        |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:-----------------------------|----------------:|-------------:|:-------------------------|
| BID      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.359 |         43.4 | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 7 held symbols in scan; 1 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
