# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-18T11:48:16.377162+07:00 |
| Mode | pre-atc |
| Session | LUNCH_BREAK |
| Active setups | 94 |
| Manual-review candidates | 0 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-15
- **scan panel as-of (with intraday bars):** 2026-05-18
- **quotes fetched:** 3 / 2
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-15 close=1921.6
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1920.76
- **Intraday regime_bull:** True
- **WARNING:** VNINDEX regime flag **changed** vs EOD — review SKIP_VNINDEX_BEAR / NEW_T1 gates.

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel
- **pct_cloud_bull_a3:** 32.2%
- **pct_cloud_bull_s3:** 31.3%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=4, `NO_T2_BREADTH`=18, `TP1_PARTIAL`=2, `TRAIL_EXIT`=32, `WATCH_ONLY`=38

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| TCO      |         15.5 |           2.829 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHM      |        158   |           0.168 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TRAIL_EXIT` (32)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.85 |           2.913 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCG      |        21.6  |           2.885 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HHS      |        13    |           0.999 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VGI      |        89.2  |           0.973 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MSN      |        77.5  |           0.969 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MZG      |        12.9  |           0.961 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| NVL      |        17.3  |           0.96  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HUT      |        15.9  |           0.933 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MCH      |       133    |           0.932 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| PPC      |         9.81 |           0.929 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VHC      |        60    |           0.917 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| MWG      |        82    |           0.89  | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| DGW      |        42.4  |           0.882 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HNM      |         7.5  |           0.863 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| REE      |        60.3  |           0.859 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| NRC      |         6.2  |           0.834 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| PAC      |        22.05 |           0.824 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| LPB      |        51.5  |           0.815 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| KBC      |        32.05 |           0.804 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| HDG      |        24.75 |           0.758 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **94**; action changed IF_CLOSE_NOW: **1**

| symbol   | would_be_final_action   | final_action     | eod_final_action             |
|:---------|:------------------------|:-----------------|:-----------------------------|
| VPB      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |

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

- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
