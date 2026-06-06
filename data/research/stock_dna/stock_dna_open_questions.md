# Stock DNA Open Questions
Date: 2026-06-06

## Data quality
- [ ] Are VIN return values distorting line obedience scores even after flagging?
- [ ] Does ta_ohlcv_panel.parquet contain corporate-action-adjusted close? If not, long-term SMA100/SMA150 may be biased.
- [ ] ADV20 filter of 5bn VND — is this appropriate for all years in the backtest (liquidity conditions changed)?

## Method
- [ ] Are 4 candidate lines (EMA20, EMA50, SMA100, SMA150) sufficient, or does EMA100/EMA200 matter for some stocks?
- [ ] Should "touch" require low to breach the line (not just approach), or is the current 1-2% tolerance correct?
- [ ] Walk-forward uses minimum 3 years of history before first OOS year — is this enough for SMA150?

## Regime
- [ ] Are breadth thresholds (>=60% BULL_BROAD, etc.) appropriate for VN market structure vs mature markets?
- [ ] Should VNINDEX price level (above EMA100) be a separate regime dimension?

## Overlay (V1 / V4)
- [ ] V1 T2 support gate: 3% tolerance for "near support" — too wide? Too narrow?
- [ ] V4 danger line: 1.2x ADV20 volume confirm — is this the right threshold?
- [ ] Is the shuffled-null benchmark passing? (see stock_dna_null_benchmark.json)

## Production path
- [ ] V1/V4 are RESEARCH_ANNOTATION_ONLY. When should we consider PAPER_SHADOW_CANDIDATE?
- [ ] Would ranking only (V5) be a safer first production integration than V1/V4?

## Recommended next step
1. Review stock_dna_symbol_profiles.csv — check top-scored symbols for face validity.
2. Monitor operator notes for 2-4 weeks on live scan output.
3. If OOS lift > 5pp consistently, consider PAPER_SHADOW_CANDIDATE review.
