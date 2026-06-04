# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-29T13:34:34.642231+07:00 |
| Mode | pre-lunch |
| Session | AFTERNOON_CONTINUOUS |
| Active setups | 103 |
| Manual-review candidates | 47 |
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
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1870.0
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 28.4%
- **pct_cloud_bull_s3:** 28.7%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=2, `NO_T2_BREADTH`=11, `TP1_PARTIAL`=2, `TRAIL_EXIT`=44, `WATCH_ONLY`=39

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| GSP      |         11.3 |           0.989 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VEA      |         34.9 |           0.94  | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| AAV      |          7.6 |           0.819 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHM      |        157.9 |           0.341 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TRAIL_EXIT` (44)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| KSV      |       156    |           2.922 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| EIB      |        21.4  |           2.914 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCG      |        20.5  |           2.816 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| TCH      |        15.35 |           2.744 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCB      |        62.5  |           0.994 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| SAB      |        47.25 |           0.989 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| DRI      |        14.1  |           0.982 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HCM      |        27.75 |           0.975 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VRE      |        32.1  |           0.945 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHC      |        58.9  |           0.933 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| ORS      |        13.1  |           0.932 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HNM      |         7.7  |           0.929 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| PVS      |        38.9  |           0.929 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| TDP      |        28.8  |           0.929 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| GVR      |        34.8  |           0.927 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| SHI      |        14.05 |           0.92  | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSN      |        75.6  |           0.917 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| KOS      |        37.55 |           0.913 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VPL      |        92.9  |           0.884 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| DGW      |        41.05 |           0.869 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **103**; action changed IF_CLOSE_NOW: **10**

| symbol   | would_be_final_action        | final_action     | eod_final_action   |
|:---------|:-----------------------------|:-----------------|:-------------------|
| GSP      | NEW_T1_MANUAL_REVIEW_BREADTH | INTRADAY_PREVIEW | TRAIL_EXIT         |
| KSV      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |
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
| KSV      | TRAIL_EXIT                   |           2.922 |       156    | MANUAL_REVIEW_REQUIRED   |
| EIB      | TRAIL_EXIT                   |           2.914 |        21.4  | MANUAL_REVIEW_REQUIRED   |
| VCG      | TRAIL_EXIT                   |           2.816 |        20.5  | MANUAL_REVIEW_REQUIRED   |
| TCH      | TRAIL_EXIT                   |           2.744 |        15.35 | MANUAL_REVIEW_REQUIRED   |
| VCB      | TRAIL_EXIT                   |           0.994 |        62.5  | MANUAL_REVIEW_REQUIRED   |
| GSP      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.989 |        11.3  | MANUAL_REVIEW_REQUIRED   |
| SAB      | TRAIL_EXIT                   |           0.989 |        47.25 | MANUAL_REVIEW_REQUIRED   |
| DRI      | TRAIL_EXIT                   |           0.982 |        14.1  | MANUAL_REVIEW_REQUIRED   |
| HCM      | TRAIL_EXIT                   |           0.975 |        27.75 | MANUAL_REVIEW_REQUIRED   |
| VRE      | TRAIL_EXIT                   |           0.945 |        32.1  | MANUAL_REVIEW_REQUIRED   |
| VEA      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.94  |        34.9  | MANUAL_REVIEW_REQUIRED   |
| VHC      | TRAIL_EXIT                   |           0.933 |        58.9  | MANUAL_REVIEW_REQUIRED   |
| ORS      | TRAIL_EXIT                   |           0.932 |        13.1  | MANUAL_REVIEW_REQUIRED   |
| HNM      | TRAIL_EXIT                   |           0.929 |         7.7  | MANUAL_REVIEW_REQUIRED   |
| PVS      | TRAIL_EXIT                   |           0.929 |        38.9  | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 10 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
