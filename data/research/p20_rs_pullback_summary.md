# p20 + RS Pullback OOS Summary

- source = FireAnt
- method = REST API for VNINDEX and symbol close enrichment
- symbol universe from panel = 513 symbols
- date range = 2023-01-01 to 2026-04-30
- values_native_or_proxy = native stock close and native VNINDEX close

## Interpretation guardrail
- Diagnostic ideas are tested only through episode-level OOS folds.
- No variant is PASS unless strict criteria are met.

- Best hit-rate uplift variant: B0_baseline_p20 (0.00 pp), verdict=FAIL