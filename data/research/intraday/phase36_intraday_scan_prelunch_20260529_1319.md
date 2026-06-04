# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-29T13:19:58.385380+07:00 |
| Mode | pre-lunch |
| Session | AFTERNOON_CONTINUOUS |
| Active setups | 103 |
| Manual-review candidates | 46 |
| Scan status | OK |
| Quote coverage | 99.0% |
| Quoted / scan / missing quote | 102 / 103 / 1 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-28
- **scan panel as-of (with intraday bars):** 2026-05-29
- **quotes fetched:** 102 / 103
- **intraday_quote_coverage_pct:** 99.0%
- **quoted_symbols_count:** 102
- **scan_symbols_count:** 103
- **missing_quote_count:** 1
- **holdings_path:** `data\trading\holdings.txt` (13 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-28 close=1863.67
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1862.67
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 28.4%
- **pct_cloud_bull_s3:** 28.7%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=2, `NO_T2_BREADTH`=12, `TP1_PARTIAL`=2, `TRAIL_EXIT`=43, `WATCH_ONLY`=39

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| GSP      |         11.3 |           0.989 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VEA      |         34.9 |           0.94  | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| AAV      |          7.6 |           0.819 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHM      |        156.1 |           0.393 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TRAIL_EXIT` (43)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.4  |           2.914 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCG      |        20.5  |           2.816 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| TCH      |        15.25 |           2.716 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCB      |        62.4  |           0.999 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| DRI      |        14    |           0.987 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| SAB      |        47.2  |           0.984 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HCM      |        27.65 |           0.959 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHC      |        59    |           0.942 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| ORS      |        13.1  |           0.932 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HNM      |         7.7  |           0.929 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| PVS      |        38.9  |           0.929 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| TDP      |        28.8  |           0.929 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VRE      |        31.95 |           0.924 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| SHI      |        14.05 |           0.92  | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| GVR      |        34.7  |           0.914 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| KOS      |        37.55 |           0.913 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VPL      |        92.4  |           0.908 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSN      |        75.4  |           0.905 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HDB      |        25.8  |           0.872 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| DGW      |        41.05 |           0.869 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **103**; action changed IF_CLOSE_NOW: **9**

| symbol   | would_be_final_action        | final_action     | eod_final_action   |
|:---------|:-----------------------------|:-----------------|:-------------------|
| GSP      | NEW_T1_MANUAL_REVIEW_BREADTH | INTRADAY_PREVIEW | TRAIL_EXIT         |
| VCB      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |
| SAB      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |
| TCB      | HOLD_T1_ONLY                 | INTRADAY_PREVIEW | TRAIL_EXIT         |
| LPB      | HOLD_T1_ONLY                 | INTRADAY_PREVIEW | NO_T2_BREADTH      |
| AAV      | TP1_PARTIAL                  | INTRADAY_PREVIEW | TRAIL_EXIT         |
| NAB      | TRAIL_EXIT                   | INTRADAY_PREVIEW | HOLD_T1_ONLY       |
| MSB      | NO_T2_BREADTH                | INTRADAY_PREVIEW | TP1_PARTIAL        |
| QNS      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **52**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action        |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:-----------------------------|----------------:|-------------:|:-------------------------|
| EIB      | TRAIL_EXIT                   |           2.914 |        21.4  | MANUAL_REVIEW_REQUIRED   |
| VCG      | TRAIL_EXIT                   |           2.816 |        20.5  | MANUAL_REVIEW_REQUIRED   |
| TCH      | TRAIL_EXIT                   |           2.716 |        15.25 | MANUAL_REVIEW_REQUIRED   |
| VCB      | TRAIL_EXIT                   |           0.999 |        62.4  | MANUAL_REVIEW_REQUIRED   |
| GSP      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.989 |        11.3  | MANUAL_REVIEW_REQUIRED   |
| DRI      | TRAIL_EXIT                   |           0.987 |        14    | MANUAL_REVIEW_REQUIRED   |
| SAB      | TRAIL_EXIT                   |           0.984 |        47.2  | MANUAL_REVIEW_REQUIRED   |
| HCM      | TRAIL_EXIT                   |           0.959 |        27.65 | MANUAL_REVIEW_REQUIRED   |
| VHC      | TRAIL_EXIT                   |           0.942 |        59    | MANUAL_REVIEW_REQUIRED   |
| VEA      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.94  |        34.9  | MANUAL_REVIEW_REQUIRED   |
| ORS      | TRAIL_EXIT                   |           0.932 |        13.1  | MANUAL_REVIEW_REQUIRED   |
| HNM      | TRAIL_EXIT                   |           0.929 |         7.7  | MANUAL_REVIEW_REQUIRED   |
| PVS      | TRAIL_EXIT                   |           0.929 |        38.9  | MANUAL_REVIEW_REQUIRED   |
| VRE      | TRAIL_EXIT                   |           0.924 |        31.95 | MANUAL_REVIEW_REQUIRED   |
| SHI      | TRAIL_EXIT                   |           0.92  |        14.05 | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 10 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
