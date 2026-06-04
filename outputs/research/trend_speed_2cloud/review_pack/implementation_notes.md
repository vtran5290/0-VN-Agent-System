# Implementation notes — v2 cleanup

## P0-1 Pine speed reset — FIXED (Option A)
- Cross bar: `speed[i] = 2 × (RMA(close,10) − RMA(open,10))`
- Non-cross: `speed[i] = speed[i−1] + co[i]`
- Test: `test_pine_speed_cross_bar_is_double_co` + full-series match to `compute_speed_series_pine_equiv`

## P0-2 Exact T2 re-simulation — DONE
- `simulate_a3_trade_exact()` evaluates breadth + TSA gate at **T2 fill bar**
- Blocked T2 → `blended_net_return = t1_net` (no scaling)
- Per-variant CSVs: `a3_trades_C0_baseline.csv` … `a3_trades_C6_*.csv`
- Fields: `t1_net`, `t2_net`, `t2_blocked_by_tsa`, `t2_fill_bar`, `t2_gate_feature_value`, etc.

## P0-3 Validation
- Stage13 blended match (ex breadth-blocked T2): max_abs_diff = 0.0 (n=158)
- v1 approx C3 MAR **0.116 was not reproducible** — exact C3 MAR **0.075**, ΔMAR **−0.024 vs C0**

## P1-1 Ranking
- `HAS_EXISTING_A3_RANK = False` — no `a3_rank_score` on OHLCV panel
- Modes run: `fifo`, `tsa_composite_only` only
- Skipped: `existing_rank_only`, `existing_rank_then_tsa_tiebreak`
- Decile files per rank column: `tsa_rank_deciles_a3_{rank_col}.csv`

## P1-2 Exit overlay
- **Removed** from v2 conclusions (`exit_overlay_results_a3.csv` = NOT_RUN_INCONCLUSIVE)

## v1 → v2 headline change
| Metric | v1 (approx T2) | v2 (exact T2) |
|--------|----------------|---------------|
| A3 baseline MAR | 0.094 | 0.098 |
| C3 T2 MAR | 0.116 (+0.023) | 0.075 (−0.024) |
| Best entry A5 MAR | 0.116 | 0.127 |
