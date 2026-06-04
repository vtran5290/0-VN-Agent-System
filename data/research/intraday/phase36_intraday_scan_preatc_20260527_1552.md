# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-27T15:52:14.208026+07:00 |
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
- **equity panel EOD max date:** 2026-05-27
- **scan panel as-of (with intraday bars):** 2026-05-27
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
- **EOD VNINDEX as-of:** 2026-05-27 close=1874.43
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1874.43
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 29.5%
- **pct_cloud_bull_s3:** 29.8%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=5, `NEW_T1_MANUAL_REVIEW_BREADTH`=2, `NO_T2_BREADTH`=17, `TP1_PARTIAL`=2, `TRAIL_EXIT`=39, `WATCH_ONLY`=36

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| CTR      |         90   |           0.932 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VEA      |         35.2 |           0.884 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| AAV      |          7.1 |           0.872 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHM      |        147.4 |           0.351 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TRAIL_EXIT` (39)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.95 |           2.981 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCG      |        20.8  |           2.849 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TCH      |        15.75 |           2.817 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HNM      |         7.6  |           0.987 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HDB      |        26.7  |           0.986 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DRI      |        14.1  |           0.981 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GSP      |        11.2  |           0.964 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MSN      |        76.5  |           0.957 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| ORS      |        13.15 |           0.936 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| KOS      |        37.8  |           0.932 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MWG      |        80    |           0.931 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VPL      |        91.7  |           0.93  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DGW      |        41.7  |           0.924 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| SHI      |        14.1  |           0.922 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HCM      |        27.5  |           0.921 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HUT      |        15.6  |           0.921 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TDP      |        28.8  |           0.921 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GVR      |        34.8  |           0.905 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHC      |        58.3  |           0.869 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| PVS      |        38.5  |           0.861 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **101**; action changed IF_CLOSE_NOW: **1**

| symbol   | would_be_final_action   | final_action     | eod_final_action   |
|:---------|:------------------------|:-----------------|:-------------------|
| AAV      | TP1_PARTIAL             | INTRADAY_PREVIEW | TRAIL_EXIT         |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **55**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

## F. Risk warnings

- **Holdings overlap:** 8 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
