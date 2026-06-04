# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-29T15:41:44.839854+07:00 |
| Mode | pre-lunch |
| Session | CLOSED |
| Active setups | 103 |
| Manual-review candidates | 0 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 103 / 103 / 0 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-28
- **scan panel as-of (with intraday bars):** 2026-05-29
- **quotes fetched:** 103 / 103
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 103
- **scan_symbols_count:** 103
- **missing_quote_count:** 0
- **holdings_path:** `data\trading\holdings.txt` (13 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-28 close=1863.67
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1863.49
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 28.4%
- **pct_cloud_bull_s3:** 28.7%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=4, `NEW_T1_MANUAL_REVIEW_BREADTH`=2, `NO_T2_BREADTH`=11, `TP1_PARTIAL`=3, `TRAIL_EXIT`=44, `WATCH_ONLY`=39

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| GSP      |         11.3 |           0.989 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VEA      |         34.8 |           0.953 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TP1_PARTIAL` (3)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| AAV      |          7.3 |           0.997 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MSB      |         15.3 |           0.569 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHM      |        156   |           0.396 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TRAIL_EXIT` (44)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.3  |           2.893 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCG      |        20.05 |           2.72  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TCH      |        15.05 |           2.66  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DRI      |        14.1  |           0.982 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| LPB      |        52    |           0.981 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCB      |        62    |           0.97  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| KOS      |        38    |           0.967 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VRE      |        32.25 |           0.966 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| SAB      |        46.95 |           0.96  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| GVR      |        34.9  |           0.941 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| PVS      |        39    |           0.941 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| SHI      |        14.1  |           0.936 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HNM      |         7.7  |           0.929 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HCM      |        27.45 |           0.926 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HUT      |        16.1  |           0.919 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHC      |        58.7  |           0.918 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| TDP      |        28.6  |           0.904 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| ORS      |        13    |           0.898 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HDB      |        25.9  |           0.889 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MSN      |        74.7  |           0.865 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **103**; action changed IF_CLOSE_NOW: **10**

| symbol   | would_be_final_action        | final_action     | eod_final_action   |
|:---------|:-----------------------------|:-----------------|:-------------------|
| GSP      | NEW_T1_MANUAL_REVIEW_BREADTH | INTRADAY_PREVIEW | TRAIL_EXIT         |
| AAV      | TP1_PARTIAL                  | INTRADAY_PREVIEW | TRAIL_EXIT         |
| LPB      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |
| VCB      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |
| TCB      | HOLD_T1_ONLY                 | INTRADAY_PREVIEW | TRAIL_EXIT         |
| SAB      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |
| VPL      | NO_T2_BREADTH                | INTRADAY_PREVIEW | TRAIL_EXIT         |
| NAB      | TRAIL_EXIT                   | INTRADAY_PREVIEW | HOLD_T1_ONLY       |
| PHP      | TRAIL_EXIT                   | INTRADAY_PREVIEW | NO_T2_BREADTH      |
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

## F. Risk warnings

- **Holdings overlap:** 10 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
