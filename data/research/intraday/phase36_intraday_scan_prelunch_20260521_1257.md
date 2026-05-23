# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-05-21T12:57:08.094094+07:00 |
| Mode | pre-lunch |
| Session | LUNCH_BREAK |
| Active setups | 101 |
| Manual-review candidates | 0 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 10 / 101 / 94 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-05-20
- **scan panel as-of (with intraday bars):** 2026-05-21
- **quotes fetched:** 10 / 10
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 10
- **scan_symbols_count:** 101
- **missing_quote_count:** 94
- **holdings_path:** `data\trading\holdings.txt` (9 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-05-20 close=1913.23
- **EOD regime_bull (last EOD bar):** True
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1898.51
- **Intraday regime_bull:** True

## A3. Macro (live panel breadth)

- **breadth_source:** mixed_intraday_eod_panel
- **pct_cloud_bull_a3:** 31.8%
- **pct_cloud_bull_s3:** 32.1%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** True

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `HOLD_T1_ONLY`=6, `NEW_T1_MANUAL_REVIEW_BREADTH`=6, `NO_T2_BREADTH`=19, `TP1_PARTIAL`=1, `TRAIL_EXIT`=35, `WATCH_ONLY`=34

### would_be `NEW_T1_MANUAL_REVIEW_BREADTH` (6)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| TRC      |        75.2  |           0.957 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| OIL      |        15.7  |           0.829 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DXS      |         8.22 |           0.798 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VGI      |        97.9  |           0.685 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| BID      |        44    |           0.314 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |
| VCB      |        65.7  |           0.171 | defense        | True          | OUT_OF_SESSION_NO_ACTION | OUT_OF_SESSION          |

### would_be `TP1_PARTIAL` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VHM      |        159.9 |           0.188 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

### would_be `TRAIL_EXIT` (35)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.4  |           2.849 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VCG      |        20.9  |           2.785 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| TCH      |        15.55 |           2.643 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DRI      |        14.1  |           1     | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| ORS      |        13.3  |           0.953 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VTO      |        11.85 |           0.929 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MCH      |       131    |           0.891 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VRE      |        33.5  |           0.882 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MSN      |        75.6  |           0.876 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NRC      |         6.2  |           0.876 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HUT      |        15.6  |           0.871 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HNM      |         7.4  |           0.844 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| VHC      |        58.2  |           0.82  | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| HDB      |        25.8  |           0.808 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| DGW      |        40.85 |           0.757 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| CRC      |         8.15 |           0.716 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| KBC      |        30.95 |           0.707 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| MWG      |        77.2  |           0.688 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| SMC      |        11.4  |           0.684 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |
| NVL      |        15.9  |           0.676 | defense        | True          | STALE_DATA_NO_ACTION     | MISSING_INTRADAY_QUOTE  |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **101**; action changed IF_CLOSE_NOW: **1**

| symbol   | would_be_final_action        | final_action     | eod_final_action   |
|:---------|:-----------------------------|:-----------------|:-------------------|
| VCB      | NEW_T1_MANUAL_REVIEW_BREADTH | INTRADAY_PREVIEW | WATCH_ONLY         |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **59**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

## F. Risk warnings

- **Holdings overlap:** 6 held symbols in scan; 1 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
