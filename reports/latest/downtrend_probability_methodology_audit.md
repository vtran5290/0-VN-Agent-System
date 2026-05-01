# Downtrend Probability Methodology Audit

## Current code path / entry points
- Legacy event study: `scripts/research/vnindex_8ndd_event_study.py`
- Legacy current analog classification: `scripts/research/vnindex_current_case_classification.py`
- V2 runner added: `scripts/run_vnindex_downtrend_v2.py`
- FireAnt loader: `src/intake/fireant_historical.py`
- Breadth snapshot source: `data/research/industry_wave_probability_l3_tune_d_latest.csv`

## Current feature list (V2, mode=T10)
- `close_vs_ma20`, `close_vs_ma50`, `ma50_slope_10d`, `ma20_slope_5d`, `above_ma50`
- `d5_pre,d10_pre (for T+ modes only)`

## Target labels
- Backward-compatible: `outcome_A`, `outcome_B` (MA50 breach proxy), `outcome_B_strict`, `outcome_C`
- New: `pullback_20d`, `trend_break_20d`, `confirmed_downtrend_20d`

## Timestamp / leakage risk findings
- Legacy risk: post-event deterioration metrics can leak if mixed in T0 inference.
- V2 fix: strict mode separation (`T0`, `T5`, `T10`); T0 excludes all post-event features.
- Forward outcomes measured after prediction timestamp (`pred_i+1` to `pred_i+20`).

## Denominator / sample-size issues
- MA50 unavailable rows are excluded from valid target denominators.
- Raw analog probabilities include Wilson CI and explicit small-sample warnings.

## Calibration status
- Legacy 20% was raw analog frequency (not calibrated probability).
- V2 now reports raw, Wilson CI, and shrinkage-adjusted stabilized estimate.
- Calibration evidence stored in walk-forward reports.

## What changed in this patch
- Added V2 script with:
  - leakage-safe inference modes
  - expanded targets
  - uncertainty bands
  - shrinkage estimator
  - walk-forward validation + calibration outputs
  - sensitivity tests
  - production markdown report
