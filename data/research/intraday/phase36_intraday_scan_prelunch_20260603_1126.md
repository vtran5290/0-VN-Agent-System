# Intraday preview scan (pre-lunch)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-06-03T11:26:09.127906+07:00 |
| Mode | pre-lunch |
| Session | MORNING_CONTINUOUS |
| Active setups | 101 |
| Manual-review candidates | 50 |
| Scan status | OK |
| Quote coverage | 100.0% |
| Quoted / scan / missing quote | 101 / 101 / 0 |
| `auto_order_allowed` | **False** (always) |

## A. Data integrity

- **source:** FireAnt (`historical_quotes_partial_daily`)
- **capability available:** True
- **equity panel EOD max date:** 2026-06-02
- **scan panel as-of (with intraday bars):** 2026-06-03
- **quotes fetched:** 101 / 101
- **intraday_quote_coverage_pct:** 100.0%
- **quoted_symbols_count:** 101
- **scan_symbols_count:** 101
- **missing_quote_count:** 0
- **holdings_path:** `data\trading\holdings.txt` (13 symbols)
- **stale quote symbols:** none
- **missing quotes:** none

## A2. VNINDEX intraday overlay

- **overlay applied:** True
- **VNINDEX quote quality:** OK
- **EOD VNINDEX as-of:** 2026-06-02 close=1826.47
- **EOD regime_bull (last EOD bar):** False
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1810.33
- **Intraday regime_bull:** False

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 25.4%
- **pct_cloud_bull_s3:** 26.9%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** False

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `SKIP_VNINDEX_BEAR`=51, `TP1_PARTIAL`=1, `TRAIL_EXIT`=49

### would_be `TP1_PARTIAL` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VHM      |        145.9 |           0.301 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TRAIL_EXIT` (49)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.1  |           2.881 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| TCH      |        15    |           2.72  | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCG      |        19.7  |           2.716 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| ILS      |        25.3  |           0.978 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCB      |        61.7  |           0.958 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| HCM      |        27.4  |           0.954 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| SHI      |        14.1  |           0.953 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| LPB      |        51.1  |           0.947 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| BID      |        41.95 |           0.946 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| GVR      |        34.7  |           0.932 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| TDP      |        28.6  |           0.929 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| NTP      |        59.3  |           0.928 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| ORS      |        13    |           0.927 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSB      |        14.4  |           0.91  | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| DRI      |        14.4  |           0.899 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHC      |        58    |           0.895 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VPL      |        88.8  |           0.887 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VPB      |        26.45 |           0.869 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| TCB      |        31.8  |           0.86  | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| PVS      |        37.9  |           0.846 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `SKIP_VNINDEX_BEAR` (51)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| KSV      |       158    |           2.987 | defense        | False         | PREVIEW_ONLY             | OK                      |
| VEA      |        34.5  |           0.998 | defense        | False         | PREVIEW_ONLY             | OK                      |
| GSP      |        11.25 |           0.992 | defense        | False         | PREVIEW_ONLY             | OK                      |
| VGI      |        92.9  |           0.991 | defense        | False         | PREVIEW_ONLY             | OK                      |
| CTR      |        89.2  |           0.983 | defense        | False         | PREVIEW_ONLY             | OK                      |
| KOS      |        38.4  |           0.982 | defense        | False         | PREVIEW_ONLY             | OK                      |
| VTO      |        12.1  |           0.981 | defense        | False         | PREVIEW_ONLY             | OK                      |
| SAB      |        47.75 |           0.956 | defense        | False         | PREVIEW_ONLY             | OK                      |
| TRC      |        75.9  |           0.954 | defense        | False         | PREVIEW_ONLY             | OK                      |
| PSI      |         8.8  |           0.9   | defense        | False         | PREVIEW_ONLY             | OK                      |
| OIL      |        14.6  |           0.866 | defense        | False         | PREVIEW_ONLY             | OK                      |
| ACB      |        25.6  |           0.682 | defense        | False         | PREVIEW_ONLY             | OK                      |
| FUEVN100 |        26.92 |           0.46  | defense        | False         | PREVIEW_ONLY             | OK                      |
| BIC      |        24.65 |           0.332 | defense        | False         | PREVIEW_ONLY             | OK                      |
| APS      |         6.9  |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| ASM      |         5.97 |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| BIG      |         6.5  |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| BSR      |        28    |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| BWE      |        43.2  |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| CII      |        16.65 |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **101**; action changed IF_CLOSE_NOW: **2**

| symbol   | would_be_final_action   | final_action     | eod_final_action   |
|:---------|:------------------------|:-----------------|:-------------------|
| KOS      | SKIP_VNINDEX_BEAR       | INTRADAY_PREVIEW | TRAIL_EXIT         |
| SAB      | SKIP_VNINDEX_BEAR       | INTRADAY_PREVIEW | TRAIL_EXIT         |

## C. S3 paper-shadow preview

- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.
- `PAPER_S3_SHADOW` count: **0**

## D. Volume projection

- Projected volume is **not** used for official ADV50.
## E. Operator actions

1. Confirm EOD scan after market close.
2. Use this file only for **pre-lunch / pre-ATC planning**.
3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.

### Top manual-review (by `a3_rank_score`)

| symbol   | would_be_final_action   |   a3_rank_score |   close_kVND | intraday_action_status   |
|:---------|:------------------------|----------------:|-------------:|:-------------------------|
| EIB      | TRAIL_EXIT              |           2.881 |        21.1  | MANUAL_REVIEW_REQUIRED   |
| TCH      | TRAIL_EXIT              |           2.72  |        15    | MANUAL_REVIEW_REQUIRED   |
| VCG      | TRAIL_EXIT              |           2.716 |        19.7  | MANUAL_REVIEW_REQUIRED   |
| ILS      | TRAIL_EXIT              |           0.978 |        25.3  | MANUAL_REVIEW_REQUIRED   |
| VCB      | TRAIL_EXIT              |           0.958 |        61.7  | MANUAL_REVIEW_REQUIRED   |
| HCM      | TRAIL_EXIT              |           0.954 |        27.4  | MANUAL_REVIEW_REQUIRED   |
| SHI      | TRAIL_EXIT              |           0.953 |        14.1  | MANUAL_REVIEW_REQUIRED   |
| LPB      | TRAIL_EXIT              |           0.947 |        51.1  | MANUAL_REVIEW_REQUIRED   |
| BID      | TRAIL_EXIT              |           0.946 |        41.95 | MANUAL_REVIEW_REQUIRED   |
| GVR      | TRAIL_EXIT              |           0.932 |        34.7  | MANUAL_REVIEW_REQUIRED   |
| TDP      | TRAIL_EXIT              |           0.929 |        28.6  | MANUAL_REVIEW_REQUIRED   |
| NTP      | TRAIL_EXIT              |           0.928 |        59.3  | MANUAL_REVIEW_REQUIRED   |
| ORS      | TRAIL_EXIT              |           0.927 |        13    | MANUAL_REVIEW_REQUIRED   |
| MSB      | TRAIL_EXIT              |           0.91  |        14.4  | MANUAL_REVIEW_REQUIRED   |
| DRI      | TRAIL_EXIT              |           0.899 |        14.4  | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 10 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
