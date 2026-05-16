# Step 0: Ledger Schema Audit

As of: 2026-05-16

## Ledger Status

### A3_pos15
- Path: `data\research\portfolio_optimization\phase2\phase2_baseline_trade_ledgers\A3_pos15.csv`
- Rows: 12,909
- Date range: 2012-06-11 to 2026-05-15
- adv50 median: 6.465 B VND
- adv50 unit check: OK
- Required cols: symbol, strategy, entry_date, exit_date, net_return, gross_return, hold_bars
- Missing required: t1_frac, total_frac
- Preferred missing: has_gk, add_path
- Issues: required_col_t1_frac; required_col_total_frac

### A3_pos20
- Path: `data\research\portfolio_optimization\phase2\phase2_baseline_trade_ledgers\A3_pos20.csv`
- Rows: 12,909
- Date range: 2012-06-11 to 2026-05-15
- adv50 median: 6.465 B VND
- adv50 unit check: OK
- Required cols: symbol, strategy, entry_date, exit_date, net_return, gross_return, hold_bars
- Missing required: t1_frac, total_frac
- Preferred missing: has_gk, add_path
- Issues: required_col_t1_frac; required_col_total_frac

### S3_pos15
- Path: `data\research\portfolio_optimization\phase2\phase2_baseline_trade_ledgers\S3_pos15.csv`
- Rows: 17,324
- Date range: 2012-04-06 to 2026-05-15
- adv50 median: 6.627 B VND
- adv50 unit check: OK
- Required cols: symbol, strategy, entry_date, exit_date, net_return, gross_return, hold_bars
- Missing required: t1_frac, total_frac
- Preferred missing: has_gk, add_path
- Issues: required_col_t1_frac; required_col_total_frac

### S3_pos20
- Path: `data\research\portfolio_optimization\phase2\phase2_baseline_trade_ledgers\S3_pos20.csv`
- Rows: 17,324
- Date range: 2012-04-06 to 2026-05-15
- adv50 median: 6.627 B VND
- adv50 unit check: OK
- Required cols: symbol, strategy, entry_date, exit_date, net_return, gross_return, hold_bars
- Missing required: t1_frac, total_frac
- Preferred missing: has_gk, add_path
- Issues: required_col_t1_frac; required_col_total_frac

### DP_A3_pb_only
- Path: `data\research\portfolio_optimization\phase25\phase25a_dp_trade_ledger.csv`
- Rows: 9,030
- Date range: 2012-08-21 to 2026-05-15
- adv50 median: nan B VND
- adv50 unit check: NO_COL
- Required cols: symbol, strategy, entry_date, exit_date, net_return, gross_return, hold_bars, t1_frac, total_frac
- Missing required: none
- Preferred missing: adv50_value, has_gk, ema_dist_at_entry
- Issues: none

### PTS_A3_pb4w30
- Path: `data\research\portfolio_optimization\phase3\phase3_pts_trade_ledger.csv`
- Rows: 9,030
- Date range: 2012-08-21 to 2026-05-15
- adv50 median: nan B VND
- adv50 unit check: NO_COL
- Required cols: symbol, strategy, entry_date, exit_date, net_return, gross_return, hold_bars, t1_frac, total_frac
- Missing required: none
- Preferred missing: adv50_value, has_gk, ema_dist_at_entry
- Issues: none

## Summary

- 2/6 ledgers have no issues
- Ledgers needing adv50 tag: DP_A3_pb_only, PTS_A3_pb4w30

## Action Required

- DP_A3_pb_only and PTS_A3_pb4w30: adv50_value absent → must _tag_adv50() before equity sim
- All new S3 ledgers from Step 1 must go through _tag_adv50() before capacity analysis
