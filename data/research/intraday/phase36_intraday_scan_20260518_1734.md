# Intraday preview scan (ad-hoc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-18T17:34:19.176041+07:00 |
| Mode | ad-hoc |
| Session | CLOSED |
| Active setups | 95 |
| Manual-review candidates | 0 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 14 / 95 / 85 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-15
- **scan panel as-of (with intraday bars):** 2026-05-18
- **quotes fetched:** 14 / 14
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 14
- **scan_symbols_count:** 95
- **missing_quote_count:** 85
- **holdings_path:** `data\trading\holdings.txt` (14 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-15 close=1921.6
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1927.94
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 32.2%
- **pct_cloud_bull_s3:** 31.7%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=4, `NEW_T1_MANUAL_REVIEW_BREADTH`=1, `NO_T2_BREADTH`=18, `TP1_PARTIAL`=2, `TRAIL_EXIT`=32, `WATCH_ONLY`=38

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| PVS      |         42.5 |           0.673 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| TCO      |         15.5 |           2.829 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VHM      |        158   |           0.168 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

### would_be `TRAIL_EXIT` (32)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.85 |           2.913 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VCG      |        21.6  |           2.885 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HHS      |        13    |           0.999 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NVL      |        17.15 |           0.997 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VGI      |        89.2  |           0.973 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MSN      |        77.5  |           0.969 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MZG      |        12.9  |           0.961 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HUT      |        15.9  |           0.933 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MCH      |       133    |           0.932 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| PPC      |         9.81 |           0.929 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VHC      |        60    |           0.917 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MWG      |        82    |           0.89  | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DGW      |        42.4  |           0.882 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HNM      |         7.5  |           0.863 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| REE      |        60.3  |           0.859 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NRC      |         6.2  |           0.834 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| PAC      |        22.05 |           0.824 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| LPB      |        51.5  |           0.815 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| KBC      |        32.05 |           0.804 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HDG      |        24.75 |           0.758 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **94**; action changed IF_CLOSE_NOW: **1**

| symbol   | would_be_final_action   | final_action     | eod_final_action             |
|:---------|:------------------------|:-----------------|:-----------------------------|
| VPB      | NO_T2_BREADTH           | INTRADAY_PREVIEW | NEW_T1_MANUAL_REVIEW_BREADTH |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **53**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

## F. Risk warnings

- **Holdings overlap:** 10 held symbols in scan; 1 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
