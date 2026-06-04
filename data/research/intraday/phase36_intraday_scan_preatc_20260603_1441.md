# Intraday preview scan (pre-atc)

> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.

## 0. Executive summary

| Field | Value |
|-------|-------|
| Generated | 2026-06-03T14:41:48.987102+07:00 |
| Mode | pre-atc |
| Session | PRE_ATC |
| Active setups | 101 |
| Manual-review candidates | 49 |
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
- **Intraday VNINDEX close (IF_CLOSE_NOW):** 1818.68
- **Intraday regime_bull:** False

## A3. Macro (live panel breadth)

- **breadth_source:** live_panel_full_intraday
- **pct_cloud_bull_a3:** 26.1%
- **pct_cloud_bull_s3:** 27.2%
- **breadth_zone:** defense
- **regime_bull (post-VNINDEX overlay):** False

## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)

**Counts:** `SKIP_VNINDEX_BEAR`=52, `TP1_PARTIAL`=1, `TRAIL_EXIT`=48

### would_be `TP1_PARTIAL` (1)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| VHM      |        148.7 |           0.385 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TRAIL_EXIT` (48)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| EIB      |        21.15 |           2.892 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| TCH      |        15.1  |           2.748 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCG      |        19.7  |           2.716 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCB      |        61.9  |           0.972 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| SHI      |        14.1  |           0.953 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| BID      |        41.85 |           0.935 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| HCM      |        27.25 |           0.929 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| TDP      |        28.6  |           0.929 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| GVR      |        34.65 |           0.925 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| ILS      |        25    |           0.924 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| ORS      |        12.95 |           0.91  | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHC      |        58.1  |           0.902 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VPL      |        89.1  |           0.901 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| PVS      |        38.2  |           0.88  | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSB      |        14.5  |           0.878 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| VPB      |        26.5  |           0.877 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| MWG      |        77.8  |           0.874 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| DRI      |        14.5  |           0.867 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| NRC      |         6    |           0.861 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSN      |        73.8  |           0.854 | defense        | False         | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `SKIP_VNINDEX_BEAR` (52)

| symbol   |   close_kVND |   a3_rank_score | breadth_zone   | regime_bull   | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:---------------|:--------------|:-------------------------|:------------------------|
| KSV      |       159.8  |           2.962 | defense        | False         | PREVIEW_ONLY             | OK                      |
| VEA      |        34.5  |           0.998 | defense        | False         | PREVIEW_ONLY             | OK                      |
| TRC      |        75    |           0.993 | defense        | False         | PREVIEW_ONLY             | OK                      |
| CTR      |        89.2  |           0.983 | defense        | False         | PREVIEW_ONLY             | OK                      |
| KOS      |        38.4  |           0.982 | defense        | False         | PREVIEW_ONLY             | OK                      |
| SAB      |        47.55 |           0.975 | defense        | False         | PREVIEW_ONLY             | OK                      |
| VGI      |        93.6  |           0.975 | defense        | False         | PREVIEW_ONLY             | OK                      |
| GSP      |        11.2  |           0.972 | defense        | False         | PREVIEW_ONLY             | OK                      |
| VTO      |        12.15 |           0.962 | defense        | False         | PREVIEW_ONLY             | OK                      |
| PSI      |         8.7  |           0.953 | defense        | False         | PREVIEW_ONLY             | OK                      |
| NTP      |        59.6  |           0.951 | defense        | False         | PREVIEW_ONLY             | OK                      |
| OIL      |        14.7  |           0.896 | defense        | False         | PREVIEW_ONLY             | OK                      |
| ACB      |        25.95 |           0.617 | defense        | False         | PREVIEW_ONLY             | OK                      |
| FUEVN100 |        26.85 |           0.472 | defense        | False         | PREVIEW_ONLY             | OK                      |
| BIC      |        24.65 |           0.332 | defense        | False         | PREVIEW_ONLY             | OK                      |
| APS      |         6.8  |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| ASM      |         5.98 |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| BIG      |         6.4  |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| BSR      |        27.95 |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |
| BWE      |        43.15 |         nan     | defense        | False         | PREVIEW_ONLY             | OK                      |

## B2. Delta vs last EOD scan (if any)

- Symbols in both: **101**; action changed IF_CLOSE_NOW: **3**

| symbol   | would_be_final_action   | final_action     | eod_final_action   |
|:---------|:------------------------|:-----------------|:-------------------|
| KOS      | SKIP_VNINDEX_BEAR       | INTRADAY_PREVIEW | TRAIL_EXIT         |
| SAB      | SKIP_VNINDEX_BEAR       | INTRADAY_PREVIEW | TRAIL_EXIT         |
| NTP      | SKIP_VNINDEX_BEAR       | INTRADAY_PREVIEW | TRAIL_EXIT         |

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
| EIB      | TRAIL_EXIT              |           2.892 |        21.15 | MANUAL_REVIEW_REQUIRED   |
| TCH      | TRAIL_EXIT              |           2.748 |        15.1  | MANUAL_REVIEW_REQUIRED   |
| VCG      | TRAIL_EXIT              |           2.716 |        19.7  | MANUAL_REVIEW_REQUIRED   |
| VCB      | TRAIL_EXIT              |           0.972 |        61.9  | MANUAL_REVIEW_REQUIRED   |
| SHI      | TRAIL_EXIT              |           0.953 |        14.1  | MANUAL_REVIEW_REQUIRED   |
| BID      | TRAIL_EXIT              |           0.935 |        41.85 | MANUAL_REVIEW_REQUIRED   |
| HCM      | TRAIL_EXIT              |           0.929 |        27.25 | MANUAL_REVIEW_REQUIRED   |
| TDP      | TRAIL_EXIT              |           0.929 |        28.6  | MANUAL_REVIEW_REQUIRED   |
| GVR      | TRAIL_EXIT              |           0.925 |        34.65 | MANUAL_REVIEW_REQUIRED   |
| ILS      | TRAIL_EXIT              |           0.924 |        25    | MANUAL_REVIEW_REQUIRED   |
| ORS      | TRAIL_EXIT              |           0.91  |        12.95 | MANUAL_REVIEW_REQUIRED   |
| VHC      | TRAIL_EXIT              |           0.902 |        58.1  | MANUAL_REVIEW_REQUIRED   |
| VPL      | TRAIL_EXIT              |           0.901 |        89.1  | MANUAL_REVIEW_REQUIRED   |
| PVS      | TRAIL_EXIT              |           0.88  |        38.2  | MANUAL_REVIEW_REQUIRED   |
| MSB      | TRAIL_EXIT              |           0.878 |        14.5  | MANUAL_REVIEW_REQUIRED   |
## F. Risk warnings

- **Holdings overlap:** 10 held symbols in scan; 0 would_be new T1 on holdings.
- Intraday quotes may lag exchange tape (partial daily bar).
- Do not confuse `would_be_final_action` with `final_action`.
- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.
