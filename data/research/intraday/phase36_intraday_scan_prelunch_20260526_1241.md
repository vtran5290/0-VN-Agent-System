# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-26T12:41:33.096694+07:00 |
| Mode | pre-lunch |
| Session | LUNCH_BREAK |
| Active setups | 101 |
| Manual-review candidates | 0 |
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
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1880.89
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 30.3%
- **pct_cloud_bull_s3:** 29.5%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=2, `NO_T2_BREADTH`=16, `TP1_PARTIAL`=2, `TRAIL_EXIT`=40, `WATCH_ONLY`=36

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| CTR      |         90   |           0.923 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCB      |         63.9 |           0.858 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| AAV      |          7.3 |           0.997 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHM      |        156.4 |           0.378 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TRAIL_EXIT` (40)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.6  |           2.941 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCG      |        20.85 |           2.844 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TCH      |        15.85 |           2.833 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VRE      |        32.6  |           0.993 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHC      |        60    |           0.993 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VTO      |        11.95 |           0.989 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MSN      |        76.9  |           0.979 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HDB      |        26.45 |           0.97  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HCM      |        28.2  |           0.969 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HNM      |         7.5  |           0.949 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| KOS      |        37.9  |           0.939 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DRI      |        13.8  |           0.917 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| SHI      |        14.1  |           0.914 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| ORS      |        13.1  |           0.914 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HUT      |        15.6  |           0.91  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| NRC      |         6.2  |           0.91  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TDP      |        28.8  |           0.909 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GVR      |        34.45 |           0.856 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| SMC      |        11.6  |           0.84  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MWG      |        78.5  |           0.832 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **101**; action changed IF_CLOSE_NOW: **6**

| symbol   | would_be_final_action   | final_action     | eod_final_action             |
|:---------|:------------------------|:-----------------|:-----------------------------|
| AAV      | TP1_PARTIAL             | INTRADAY_PREVIEW | TRAIL_EXIT                   |
| GSP      | NO_T2_BREADTH           | INTRADAY_PREVIEW | TRAIL_EXIT                   |
| VGI      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |
| BID      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |
| NTP      | HOLD_T1_ONLY            | INTRADAY_PREVIEW | NO_T2_BREADTH                |
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

## F. Risk warnings

- **Holdings overlap:** 8 held symbols in scan; 1 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
