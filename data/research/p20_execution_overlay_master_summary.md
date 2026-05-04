# p20 Execution Overlay Master Summary

## Executive conclusion
Execution/risk overlays did not produce production-grade OOS improvement. Baseline p20 remains the benchmark. Next step is paper-trading baseline p20 with discretionary chart confirmation, or extend data history.

## QA summary
- rows: 223975, symbols: 513, dates: 735
- harness audit verdict: PASS

## Baseline metrics
- n=6679, hit_rate=0.1897, avg_ret=0.0003, avg_mdd=-0.0676

## Experiment results
- entry_timing: verdict=WATCH; reason=Only E0 baseline executable without OHLC.
- exit_rules: verdict=WATCH; reason=Only X0 fixed horizon executable without OHLC.
- regime_exposure: verdict=WATCH; reason=Risk overlay pass criteria not met.
- sizing: verdict=WATCH; reason=Only S0/S3 executable without OHLC; ATR variants skipped.
- confirmation: verdict=WATCH; reason=No confirmation rules executable without OHLC.

## Overfit risk assessment
- No diagnostic-only evidence is treated as final OOS proof.
- Final recommendations are based on episode-level monthly OOS comparisons.

## Production recommendation
- Production score: baseline p20.
- Execution/exit/confirmation overlays need OHLC-enriched panel for full test.
- Risk overlay to monitor weekly: regime exposure map and sizing turnover drift.