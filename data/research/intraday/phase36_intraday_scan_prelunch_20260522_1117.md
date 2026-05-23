# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-22T11:17:03.733648+07:00 |
| Mode | pre-lunch |
| Session | MORNING_CONTINUOUS |
| Active setups | 103 |
| Manual-review candidates | 3 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 10 / 103 / 96 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-21
- **scan panel as-of (with intraday bars):** 2026-05-22
- **quotes fetched:** 10 / 10
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 10
- **scan_symbols_count:** 103
- **missing_quote_count:** 96
- **holdings_path:** `data\trading\holdings.txt` (9 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-21 close=1896.89
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1859.07
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 31.1%
- **pct_cloud_bull_s3:** 32.5%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=6, `NEW_T1_MANUAL_REVIEW_BREADTH`=7, `NO_T2_BREADTH`=13, `TP1_PARTIAL`=1, `TRAIL_EXIT`=39, `WATCH_ONLY`=37

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (7)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| TRC      |        74.9  |           0.979 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| BID      |        42.85 |           0.953 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| NTP      |        61.2  |           0.951 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DXS      |         8.08 |           0.898 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| OIL      |        15.6  |           0.875 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VGI      |        96    |           0.809 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VCB      |        63.6  |           0.352 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TP1_PARTIAL` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VHM      |        159.8 |           0.222 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

### would_be `TRAIL_EXIT` (39)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.4  |           2.862 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VCG      |        20.8  |           2.784 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| TCH      |        15.6  |           2.689 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VRE      |        32.8  |           0.99  | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DRI      |        14    |           0.968 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HCM      |        28.15 |           0.966 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| GSP      |        11.25 |           0.966 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NRC      |         6.3  |           0.959 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VTO      |        11.9  |           0.955 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| GVR      |        36.2  |           0.939 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MSN      |        76.2  |           0.923 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HUT      |        15.7  |           0.911 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| SHI      |        14.15 |           0.905 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| ORS      |        13.1  |           0.889 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VHC      |        58.8  |           0.881 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DGW      |        41.7  |           0.87  | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HNM      |         7.4  |           0.859 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MWG      |        79.5  |           0.844 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HDB      |        25.85 |           0.835 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| KBC      |        31.6  |           0.824 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **103**; action changed IF_CLOSE_NOW: **1**

| symbol   | would_be_final_action   | final_action     | eod_final_action   |
|:---------|:------------------------|:-----------------|:-------------------|
| HCM      | TRAIL_EXIT              | INTRADAY_PREVIEW | NO_T2_BREADTH      |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **60**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action        |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:-----------------------------|----------------:|-------------:|:-------------------------|
| HCM      | TRAIL_EXIT                   |           0.966 |        28.15 | MANUAL_REVIEW_REQUIRED   |
| BID      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.953 |        42.85 | MANUAL_REVIEW_REQUIRED   |
| VCB      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.352 |        63.6  | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 7 held symbols in scan; 3 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
