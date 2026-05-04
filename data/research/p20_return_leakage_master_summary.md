# p20 Return Leakage Master Summary

## Executive conclusion
Return-leakage tests did not produce production-grade OOS improvement. Baseline p20 remains the benchmark. Next step is paper-trading baseline p20 with discretionary chart confirmation or expanding data history.

## QA / coverage
- panel rows: 223975, symbols: 513, dates: 735
- OHLCV cache coverage: 1.0

## Baseline reconstruction
- corr vs panel fwd_ret20: 0.9999999999999998
- p95 abs diff: 0.003000000000000086

## Best by module
- entry_best: E3_tight_day_skip / verdict=WATCH
- exit_best: X1_profit_take_12pct / verdict=WATCH
- horizon_best: H50 / verdict=WATCH
- sizing_best: S1_inverse_ATR20 / verdict=FAIL
- exposure_best: EX2_top15_only / verdict=WATCH
- rs_execution_best: RSF2_size_down_weak_rs_in_pullback / verdict=FAIL