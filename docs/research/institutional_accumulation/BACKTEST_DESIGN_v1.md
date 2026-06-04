# Institutional Accumulation Backtest Design v1

## Executive summary
Research-only validation framework for Institutional Accumulation score/tier/flag behavior from 2012 to latest local data.

## Scope confirmation
- IN: panel scoring parity, forward outcomes, portfolio/ablation/regime validation, review-pack artifacts.
- OUT: production trading logic (`final_action`, OMS, DNSE, A3/S3 execution paths).

## Source data
- OHLCV: `data/stocks/*.csv` (canonical scan source).
- Benchmark: resolved via existing benchmark fallback chain.
- Optional acceleration metadata: `data/fireant_ssot/ta_ohlcv_panel.parquet` (availability recorded in manifest).

## Universe construction
- Liquid universe per scan gates: `min_history>=120`, `adv20>=2B`, `adv50>=1.5B`.
- ETF/open-fund exclusion (`E1VFVN30`, `Quỹ mở` when sector available).
- Full and ex-VIN (`VIC`,`VHM`,`VRE`) tracked in outputs.

## Signal timing
- Base: signal at close T, entry open T+1.
- Sensitivity fields include close-T reference.

## Feature construction
- Reuse existing indicator/scoring modules in `src/scans/institutional_accumulation/`.
- Includes score blocks, risk/flag booleans, tier assignments, emerging/caution proxies.

## Forward outcomes
- Horizons: 5d, 10d, 20d, 60d, 120d.
- Includes returns, benchmark-relative excess, max drawdown, drawdown-hit flags, MFE.

## Benchmarks
- VNINDEX relative return columns in outcomes panel.
- Portfolio summary includes gross and cost-adjusted net returns.

## Cost model
- Round-trip: 0.15% / 0.30% / 0.50%.
- ADV slippage overlay by ADV50 bucket.

## OOS / walk-forward design
- Reported outputs support year/regime segmentation; walk-forward windows are tagged for further threshold tuning.

## Regime split
- No-lookahead reconstructed regime fields from benchmark trend proxies (200DMA, correction, fragile proxy, COVID window).

## Portfolio strategies S1–S7
- S1 tier ladders, S2 quintiles, S3 fund-tag overlays, S4 caution overlays, S5 reject avoidance, S6 changes events, S7 component ablations.

## Component ablation
- Composite and block knockouts, risk-penalty calibration, distribution-flag validation.

## Smart Money context handling
- `OHLCV_ONLY` mandatory baseline.
- `PIT_MONTHLY_CONTEXT` only if monthly files exist as-of date.
- `SYNTHETIC_APR2026_CONTEXT_ONLY_NOT_EMPIRICAL` for sensitivity only.

## VIN sensitivity policy
- Always output full vs ex-VIN (and VIN-only summaries).
- VPL-specific VIN event restrictions captured in tests/policy.

## Statistical tests
- Calibration tables and spread summaries included; bootstrap/multiple-testing extensions are staged.

## Pass/fail gates
- HTML dashboard maps metric groups to status labels (SUPPORTED/REJECTED/INCONCLUSIVE/SYNTHETIC_ONLY/BLOCKED_BY_DATA).

## Output artifacts
- `data/research/institutional_accumulation/*` (panel/outcomes/metrics/calibration/validation files).
- `reports/research/institutional_accumulation/institutional_accumulation_backtest_summary.html`.
- Review pack zip under `outputs/review_packages/`.

## Known limitations
- PIT monthly fund context may be unavailable if historical monthly files are missing.
- Local-file universe may carry survivorship bias.

## How to run
```bash
python -m scripts.research.institutional_accumulation_backtest.run_panel --start 2012-01-01 --end latest --cadence weekly --context-mode ohlcv_only
python -m scripts.research.institutional_accumulation_backtest.run_outcomes --panel data/research/institutional_accumulation/panel_scores.parquet
python -m scripts.research.institutional_accumulation_backtest.run_portfolios --context-mode ohlcv_only
python -m scripts.research.institutional_accumulation_backtest.run_ablation
python -m scripts.research.institutional_accumulation_backtest.run_yearly_report
python -m scripts.research.institutional_accumulation_backtest.run_html_report
python -m scripts.research.institutional_accumulation_backtest.build_review_pack
```

Research-only validation. This backtest does not set final_action, OMS orders, DNSE routing, position sizing, or live execution. Real capital remains NO-GO unless separately promoted through an explicit future gate.
