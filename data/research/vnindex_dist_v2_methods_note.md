# VNINDEX distribution v2 — methods note

## Purpose

Descriptive event-study statistics for VNINDEX and a **non-tradable synthetic ex-VIN** level (VIC, VHM, VRE; VPL excluded per `docs/research/VIN_EMA_CLOUD_BASELINE.md`). **Not** a calibrated predictive model.

## Distribution day (fixed)

`close <= prior_close * (1 - 0.002)` AND `volume > prior_volume`; valid only when volumes strictly positive.

## Regime forks

- **strict_le1_***: trailing `L` trading days with at most **1** distribution day (same `L` as the current window).
- **matched_density_*** (**hypothesis fork**): trailing `L` with at most the **observed** count of distribution days in the current window (separate threshold for full vs ex-VIN series). This matches today’s density by construction and is **not** the original low-distribution hypothesis.

## Data / reproducibility

- `source_used`: `csv_only` or `csv+fireant` (heuristic: VNINDEX extended past CSV, or any Vin CSV ended before `--end` implying fetch path in `build_ex_vin_series`).
- `--offline` fails fast if CSVs do not reach `--end`.
- Outputs record `actual_last_bar_date` and `actual_L_trading_days`.

## Random baselines

1. **IID** (`random_baseline_iid`): `mc_reps` draws of `n` eligible indices with replacement.
2. **Spacing-matched** (`random_baseline_spacing_matched`): `spacing_mc_reps` draws; each draw is a random **sparse** set of `n` indices from the eligible pool with the same **min_anchor_spacing** in trading-day index space as regime anchors; same horizon survival as the pool definition.
3. **Year-histogram-matched** (`random_baseline_year_histogram_matched`): `year_block_mc_reps` draws; each draw samples the same count of anchors per **calendar year** as the conditional anchor set, uniformly from pool dates in that year (without replacement within the year).

## Decision table (`vnindex_dist_v2_decision_table.csv`)

Heuristic `conclusion` enum (uses **spacing-matched** median and p-value): `strong_short_term_edge` (horizons 25–50d only), `weak_or_inconclusive`, `no_edge_vs_baseline`. Not investment advice.

## Breadth (optional)

If `config/watchlist.txt` (or `--breadth-watchlist`) exists and `--skip-breadth` is not set: for **matched_density_full_dist** anchors, report % above EMA50, median 20d forward return across loaded names, and 1d advance fraction — for full watchlist and ex-VIN subset (drop VIC/VHM/VRE).

## OOS

If `--oos-start` is set, `oos` blocks restrict to anchors on/after that date; regime labels still use only past prices by construction (trailing window).

## Run

`python scripts/research/run_vnindex_dist_v2.py --end YYYY-MM-DD --start-window YYYY-MM-DD [--offline] [--oos-start ...] [--spacing-mc-reps 5000] [--year-block-mc-reps 5000] [--skip-breadth]`

