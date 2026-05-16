# Implementation Notes

Date: 2026-05-16

## Data sources
- Panel: data/research/ema_cloud/ohlcv_panel_ext2012.parquet
- VNINDEX: data/fireant_ssot/ta_vnindex.parquet

## Phase mapping
- Phase 0: build_trade_ledger() — full signal sim with extended columns
- Phase 1: run_sizing_experiments() — equal-weight grid, rank-based, inv-ATR, risk-per-trade
- Phase 2: run_scalein_experiments() — 2T and 3T scale-in with multiple triggers
- Phase 3: run_convergence_experiments() — multi-strategy overlap filter + multipliers
- Phase 5: run_walk_forward() — monthly fold OOS validation

## Known stubs
- Bucket sizing (Phase 1E) and Kelly sizing (Phase 1F): require walk-forward training; return placeholder rows
- Walk-forward Kelly weight: fixed 0.05 placeholder; full implementation requires per-fold hit-rate / payoff estimation

## Cost scenarios
- base: 0.004 (0 bps)
- low:  0.002 (0 bps)
- high: 0.006 (1 bps)
