# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-26T16:49:17.512186+07:00 |
| Mode | pre-atc |
| Session | CLOSED |
| Active setups | 101 |
| Manual-review candidates | 0 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 101 / 101 / 0 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-26
- **scan panel as-of (with intraday bars):** 2026-05-26
- **quotes fetched:** 101 / 101
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 101
- **scan_symbols_count:** 101
- **missing_quote_count:** 0
- **holdings_path:** `data\trading\holdings.txt` (11 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-26 close=1884.18
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1884.18
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 30.7%
- **pct_cloud_bull_s3:** 29.5%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=2, `NO_T2_BREADTH`=15, `TP1_PARTIAL`=2, `TRAIL_EXIT`=41, `WATCH_ONLY`=36

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| CTR      |         90.5 |           0.897 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCB      |         64.4 |           0.822 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| AAV      |          7.4 |           0.942 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHM      |        153.8 |           0.455 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TRAIL_EXIT` (41)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.55 |           2.93  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TCH      |        16    |           2.875 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCG      |        20.75 |           2.822 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VRE      |        32.7  |           0.993 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VTO      |        12    |           0.992 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MSN      |        77    |           0.985 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HDB      |        26.5  |           0.979 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HCM      |        27.8  |           0.967 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHC      |        59.5  |           0.955 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| KOS      |        38    |           0.951 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DRI      |        13.9  |           0.95  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HNM      |         7.5  |           0.949 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| ORS      |        13.2  |           0.949 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GVR      |        35.15 |           0.945 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GSP      |        11.15 |           0.939 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| SHI      |        14.1  |           0.914 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| NRC      |         6.2  |           0.91  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DGW      |        41.45 |           0.887 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HUT      |        15.5  |           0.882 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TDP      |        28.55 |           0.871 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **101**; action changed IF_CLOSE_NOW: **1**

| symbol   | would_be_final_action   | final_action     | eod_final_action   |
|:---------|:------------------------|:-----------------|:-------------------|
| AAV      | TP1_PARTIAL             | INTRADAY_PREVIEW | TRAIL_EXIT         |

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
