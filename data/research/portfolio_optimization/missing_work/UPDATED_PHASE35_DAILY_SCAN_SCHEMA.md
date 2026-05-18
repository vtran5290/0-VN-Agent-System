# Phase35 Daily Scan Schema (SSOT)

**Command:** `python pp_backtest/portfolio_optimization_final_steps.py --step scan`

**Outputs:**
- `phase35_daily_scan_sample.csv` (primary)
- `phase34_daily_scan_sample.csv` (alias)
- `phase35_daily_scan_schema.csv` (field dictionary)

## Production vs research

| Track | Classification | Live orders | DNSE |
|-------|----------------|-------------|------|
| A3 DP-first | `A3_PRODUCTION` | `final_action` only | When approved |
| S3 max60 shadow | `PAPER_TRADE_SHADOW` | **Never** | **Never** |
| S3 GK5+top100 monitor | `s3_research_monitor_action` | **Never** | **Never** |
| S3 max250 | `REJECTED_CONFIG` | **Never** | **Never** |

## A3 `final_action` (real-capital SSOT)

`NEW_T1`, `NEW_T1_MANUAL_REVIEW_BREADTH`, `WAIT_PB`, `ADD_T2`, `HOLD_T1_ONLY`, `NO_T2_BREADTH`, `TP1_PARTIAL`, `TRAIL_EXIT`, `MAX_HOLD_EXIT`, `SKIP_LIQUIDITY`, `SKIP_VNINDEX_BEAR`, `WATCH_ONLY`

- **Only VNINDEX bear** hard-blocks new A3 T1.
- Breadth **does not** hard-block T1; `<35%` → `NEW_T1_MANUAL_REVIEW_BREADTH`.
- Breadth `<40%` blocks T2 only.

## S3 shadow fields (paper only)

| Field | Active shadow value |
|-------|---------------------|
| `s3_shadow_classification` | `PAPER_TRADE_SHADOW` |
| `s3_max_hold` | `60` |
| `s3_max_hold_60_flag` | `True` |
| `s3_tp1_pct` | `0.18` |
| `s3_trail_atr` | `3.5` |
| `s3_shadow_action` | `PAPER_S3_SHADOW` |
| `s3_no_real_order_flag` | `True` (all rows) |

## S3 research monitor (parallel paper research)

When S3 max60 active **and** `s3_gk5` **and** `s3_top100_adv`:

- `s3_gk5_top100_monitor` = `True`
- `s3_research_monitor_action` = `PAPER_S3_RESEARCH_MONITOR`
- `s3_research_monitor_reason` = `GK5_MAX60_TOP100_MONITOR`

Does **not** change A3 `final_action` or position size.

## A3 priority boost (ranking only)

- `a3_s3_lead_5d` = `True` if S3 fired **1–5 bars before** A3 (not same bar).
- `a3_priority_boost_from_s3` = same boolean.
- Used for **sort/rank** on same-day candidates; never gates A3.

## Liquidity

- `close_kVND` × `volume` × 1000 → ADV50 VND (or panel `value` column).
- `adv50_B_VND`, `max_10pct_M`, `liq_warn_T1`, `liq_warn_full` required before sizing.

Full column list: see `phase35_daily_scan_schema.csv`.
