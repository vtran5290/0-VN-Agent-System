# p20 Return Leakage Context Audit

- Baseline p20 remains benchmark from prior strict episode-level OOS tests.
- Complex alpha recalibrations (v2/v2.2/v2.3) failed production-grade PASS.
- RS overlays failed as ranking add-ons: always-on RS, event-based RS, RS+range+slope all FAIL.
- Current objective shifts from alpha replacement to realized-return leakage diagnosis on top of baseline p20.
- Data limitation: `super_alpha_panel_from_2023.csv` may not include full OHLC path fields for every symbol-date, so OHLCV cache fetch is required.

Do not redo alpha recalibration. Current task is to identify whether realized return can be improved through trade execution, exit, holding horizon, sizing, or exposure control on top of baseline p20.