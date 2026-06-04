# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-25T10:28:49.015240+07:00 |
| Mode | pre-atc |
| Session | MORNING_CONTINUOUS |
| Active setups | 102 |
| Manual-review candidates | 47 |
| Scan status | OK |
| Quote coverage | 98.0% |
| Quoted / scan / missing quote | 100 / 102 / 2 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-22
- **scan panel as-of (with intraday bars):** 2026-05-25
- **quotes fetched:** 100 / 102
- **intraday_quote_coverage_pct:** 98.0%
- **quoted_symbols_count:** 100
- **scan_symbols_count:** 102
- **missing_quote_count:** 2
- **holdings_path:** `data\trading\holdings.txt` (11 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-22 close=1877.13
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1884.98
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 30.7%
- **pct_cloud_bull_s3:** 30.2%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=6, `NO_T2_BREADTH`=12, `TP1_PARTIAL`=1, `TRAIL_EXIT`=42, `WATCH_ONLY`=36

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (6)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| NTP      |        61.1  |           0.964 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| BID      |        42.85 |           0.959 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCB      |        63.2  |           0.894 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VGI      |        94.8  |           0.894 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| DXS      |         8.18 |           0.86  | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| CTR      |        91.4  |           0.332 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TP1_PARTIAL` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VHM      |        155.5 |           0.384 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TRAIL_EXIT` (42)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.8  |           2.974 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCG      |        21    |           2.86  | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| TCH      |        15.9  |           2.824 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| KOS      |        38.3  |           0.984 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VRE      |        32.75 |           0.984 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| DRI      |        14    |           0.974 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| GSP      |        11.25 |           0.972 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VTO      |        11.9  |           0.965 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHC      |        59.5  |           0.954 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSN      |        76.3  |           0.944 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| ORS      |        13.15 |           0.923 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| SHI      |        14.1  |           0.905 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| GVR      |        34.95 |           0.902 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HUT      |        15.6  |           0.901 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| NRC      |         6.2  |           0.901 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HDB      |        26.05 |           0.898 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HCM      |        28.65 |           0.894 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HNM      |         7.4  |           0.872 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MWG      |        79.2  |           0.855 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| KBC      |        31.4  |           0.828 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **102**; action changed IF_CLOSE_NOW: **2**

| symbol   | would_be_final_action   | final_action     | eod_final_action   |
|:---------|:------------------------|:-----------------|:-------------------|
| KOS      | TRAIL_EXIT              | INTRADAY_PREVIEW | NO_T2_BREADTH      |
| CDC      | TRAIL_EXIT              | INTRADAY_PREVIEW | HOLD_T1_ONLY       |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **56**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action        |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:-----------------------------|----------------:|-------------:|:-------------------------|
| EIB      | TRAIL_EXIT                   |           2.974 |        21.8  | MANUAL_REVIEW_REQUIRED   |
| VCG      | TRAIL_EXIT                   |           2.86  |        21    | MANUAL_REVIEW_REQUIRED   |
| TCH      | TRAIL_EXIT                   |           2.824 |        15.9  | MANUAL_REVIEW_REQUIRED   |
| VRE      | TRAIL_EXIT                   |           0.984 |        32.75 | MANUAL_REVIEW_REQUIRED   |
| KOS      | TRAIL_EXIT                   |           0.984 |        38.3  | MANUAL_REVIEW_REQUIRED   |
| DRI      | TRAIL_EXIT                   |           0.974 |        14    | MANUAL_REVIEW_REQUIRED   |
| GSP      | TRAIL_EXIT                   |           0.972 |        11.25 | MANUAL_REVIEW_REQUIRED   |
| VTO      | TRAIL_EXIT                   |           0.965 |        11.9  | MANUAL_REVIEW_REQUIRED   |
| NTP      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.964 |        61.1  | MANUAL_REVIEW_REQUIRED   |
| BID      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.959 |        42.85 | MANUAL_REVIEW_REQUIRED   |
| VHC      | TRAIL_EXIT                   |           0.954 |        59.5  | MANUAL_REVIEW_REQUIRED   |
| MSN      | TRAIL_EXIT                   |           0.944 |        76.3  | MANUAL_REVIEW_REQUIRED   |
| ORS      | TRAIL_EXIT                   |           0.923 |        13.15 | MANUAL_REVIEW_REQUIRED   |
| SHI      | TRAIL_EXIT                   |           0.905 |        14.1  | MANUAL_REVIEW_REQUIRED   |
| GVR      | TRAIL_EXIT                   |           0.902 |        34.95 | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 8 held symbols in scan; 2 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
