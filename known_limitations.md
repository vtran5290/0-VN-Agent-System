# Known limitations

- Effective first scan date is 2017-05-19 (requested start was 2012-01-01), constrained by source-data coverage and minimum-history filters.
- PIT monthly context is unavailable for full historical chain in current snapshot.
- Local-file universe can include survivorship/coverage bias.
- Synthetic Apr-2026 context remains sensitivity-only and not empirical fund evidence.

## Critical finding — score decile inversion

The composite institutional accumulation score is not currently validated as a buy-ranking signal.

In the current OHLCV-only backtest, the highest score decile does not show robust forward outperformance. In some calibration views, the highest decile has worse forward outcome probability than mid-range deciles.

This means the score should remain research-only and must not be used as a production buy signal, sizing input, OMS input, or final_action input.

P1 should investigate whether the issue comes from:

- score component scaling,
- risk penalty interaction,
- money-flow features rewarding exhaustion rather than accumulation,
- regime dependence,
- liquidity/sample effects,
- or tier threshold design.

## Portfolio simulation caveat

The current portfolio summary is a research diagnostic, not a fully investable portfolio simulation.

Some portfolio metrics compound overlapping 20-day forward returns from weekly scan dates, and CAGR annualization is not yet calibrated to a non-overlapping portfolio equity curve.

Therefore:

- use portfolio outputs for directional diagnostics only,
- do not quote absolute CAGR/gross_return/max_drawdown as investable performance,
- P1 must rebuild portfolio simulation with non-overlapping holdings, proper rebalance accounting, and correct annualization.

## Effective sample period limitation

Although the requested backtest start is 2012-01-01 and the first generated scan date is 2017-05-19, usable forward-return coverage is materially stronger from 2022 onward. Some earlier years, especially 2019–2021, contain many NaN forward outcomes due to source-data coverage.

Therefore, current conclusions should be treated as mainly supported by the 2022–2026 sample, not a full 2012–2026 cycle.
