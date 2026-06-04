# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-26T14:07:12.581955+07:00 |
| Mode | pre-atc |
| Session | AFTERNOON_CONTINUOUS |
| Active setups | 101 |
| Manual-review candidates | 45 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 102 / 101 / 0 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-25
- **scan panel as-of (with intraday bars):** 2026-05-26
- **quotes fetched:** 102 / 102
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 102
- **scan_symbols_count:** 101
- **missing_quote_count:** 0
- **holdings_path:** `data\trading\holdings.txt` (11 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-25 close=1886.03
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1880.85
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 30.3%
- **pct_cloud_bull_s3:** 29.5%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=2, `NO_T2_BREADTH`=15, `TP1_PARTIAL`=2, `TRAIL_EXIT`=41, `WATCH_ONLY`=36

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| CTR      |         89.9 |           0.928 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCB      |         63.8 |           0.865 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| AAV      |          7.3 |           0.997 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHM      |        154.5 |           0.434 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TRAIL_EXIT` (41)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.6  |           2.941 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| TCH      |        15.8  |           2.819 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCG      |        20.7  |           2.812 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HDB      |        26.55 |           0.987 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHC      |        59.9  |           0.985 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSN      |        76.9  |           0.979 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VTO      |        12.05 |           0.974 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HCM      |        28.2  |           0.969 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| VRE      |        32.35 |           0.959 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HNM      |         7.5  |           0.949 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| GSP      |        11.15 |           0.939 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| ORS      |        13.15 |           0.931 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| KOS      |        37.8  |           0.927 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| DRI      |        13.8  |           0.917 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| SHI      |        14.1  |           0.914 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| HUT      |        15.5  |           0.882 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| GVR      |        34.65 |           0.881 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| PVS      |        38.6  |           0.858 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| MWG      |        78.9  |           0.854 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |
| TDP      |        28.4  |           0.848 | defense        | True          | MANUAL_REVIEW_REQUIRED   | OK                      |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **101**; action changed IF_CLOSE_NOW: **5**

| symbol   | would_be_final_action   | final_action     | eod_final_action             |
|:---------|:------------------------|:-----------------|:-----------------------------|
| AAV      | TP1_PARTIAL             | INTRADAY_PREVIEW | TRAIL_EXIT                   |
| VGI      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |
| NTP      | HOLD_T1_ONLY            | INTRADAY_PREVIEW | NO_T2_BREADTH                |
| BID      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |
| DXS      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **54**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action        |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:-----------------------------|----------------:|-------------:|:-------------------------|
| EIB      | TRAIL_EXIT                   |           2.941 |        21.6  | MANUAL_REVIEW_REQUIRED   |
| TCH      | TRAIL_EXIT                   |           2.819 |        15.8  | MANUAL_REVIEW_REQUIRED   |
| VCG      | TRAIL_EXIT                   |           2.812 |        20.7  | MANUAL_REVIEW_REQUIRED   |
| AAV      | TP1_PARTIAL                  |           0.997 |         7.3  | MANUAL_REVIEW_REQUIRED   |
| HDB      | TRAIL_EXIT                   |           0.987 |        26.55 | MANUAL_REVIEW_REQUIRED   |
| VHC      | TRAIL_EXIT                   |           0.985 |        59.9  | MANUAL_REVIEW_REQUIRED   |
| MSN      | TRAIL_EXIT                   |           0.979 |        76.9  | MANUAL_REVIEW_REQUIRED   |
| VTO      | TRAIL_EXIT                   |           0.974 |        12.05 | MANUAL_REVIEW_REQUIRED   |
| HCM      | TRAIL_EXIT                   |           0.969 |        28.2  | MANUAL_REVIEW_REQUIRED   |
| VRE      | TRAIL_EXIT                   |           0.959 |        32.35 | MANUAL_REVIEW_REQUIRED   |
| HNM      | TRAIL_EXIT                   |           0.949 |         7.5  | MANUAL_REVIEW_REQUIRED   |
| GSP      | TRAIL_EXIT                   |           0.939 |        11.15 | MANUAL_REVIEW_REQUIRED   |
| ORS      | TRAIL_EXIT                   |           0.931 |        13.15 | MANUAL_REVIEW_REQUIRED   |
| CTR      | NEW_T1_MANUAL_REVIEW_BREADTH |           0.928 |        89.9  | MANUAL_REVIEW_REQUIRED   |
| KOS      | TRAIL_EXIT                   |           0.927 |        37.8  | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 8 held symbols in scan; 1 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
