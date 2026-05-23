# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-22T16:31:33.282549+07:00 |
| Mode | pre-atc |
| Session | CLOSED |
| Active setups | 102 |
| Manual-review candidates | 0 |
| Scan status | OK |
| Quote coverage | 99.0% |
| Quoted / scan / missing quote | 101 / 102 / 1 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-22
- **scan panel as-of (with intraday bars):** 2026-05-22
- **quotes fetched:** 101 / 102
- **intraday_quote_coverage_pct:** 99.0%
- **quoted_symbols_count:** 101
- **scan_symbols_count:** 102
- **missing_quote_count:** 1
- **holdings_path:** `data\trading\holdings.txt` (9 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-22 close=1877.13
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1877.13
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 31.1%
- **pct_cloud_bull_s3:** 31.0%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=6, `NEW_T1_MANUAL_REVIEW_BREADTH`=6, `NO_T2_BREADTH`=13, `TP1_PARTIAL`=1, `TRAIL_EXIT`=40, `WATCH_ONLY`=36

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (6)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| NTP      |        60.6  |           1     | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| BID      |        43    |           0.936 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VGI      |        94.2  |           0.915 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DXS      |         8.08 |           0.908 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCB      |        63.5  |           0.359 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| CTR      |        93    |           0.223 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TP1_PARTIAL` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VHM      |        153.8 |           0.428 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TRAIL_EXIT` (40)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VCG      |        21    |           2.846 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| EIB      |        21.2  |           2.834 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TCH      |        15.65 |           2.731 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| PVS      |        39.9  |           0.982 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DRI      |        14    |           0.971 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GSP      |        11.25 |           0.969 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VTO      |        11.85 |           0.941 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GVR      |        35.3  |           0.941 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| ORS      |        13.2  |           0.933 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| SHI      |        14.2  |           0.93  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MSN      |        76    |           0.918 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HCM      |        28.5  |           0.909 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHC      |        59    |           0.907 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HUT      |        15.6  |           0.891 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| NRC      |         6.2  |           0.891 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HNM      |         7.4  |           0.872 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VRE      |        31.7  |           0.857 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MWG      |        79.4  |           0.853 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HDB      |        25.85 |           0.85  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DGW      |        41.25 |           0.834 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **102**; action changed IF_CLOSE_NOW: **0**

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **58**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

## F. Risk warnings

- **Holdings overlap:** 7 held symbols in scan; 2 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
