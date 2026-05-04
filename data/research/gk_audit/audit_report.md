# VN Quant Full Audit Report

Run date: 2026-05-03
Data period: 2023-01-01 – 2026-04-30

## Bugs Found and Fixed

### BUG-1: Exit-day return missing from equity curve (CRITICAL)
**Prior code**: positions deleted from `positions` dict BEFORE MTM on exit signal day.
This caused the final day's return (close[T-1]→close[T]) for each exiting position
to be excluded from the equity curve.  Impact: systematic upward bias in equity CAGR
when exits fire after down days (GK_SELL, hard stops).

**Fix**: Pending-exit queue.  Positions remain in `holdings` dict through MTM on signal day.
Exit proceeds (shares × open[T+1] × cost_x) reflected in `cash` on execution day T+1.
Equity is always: `cash + sum(shares_i × close_i)`.

### BUG-2: Stop triggered by Close price, not intraday Low (MODERATE)
**Prior code**: stop checked as `(close / entry_open - 1) <= -stop_pct`.
This misses intraday breaches where Low[t] < stop but Close[t] > stop.

**Fix**: Check `Low[t] <= stop_price`.  Conservative exit: `min(stop_price, Open[t+1])`.
For gap-down scenarios: exit at next open if it is lower than the stop level.

### BUG-3: Yearly returns from serial trade compounding (DISPLAY BUG)
**Prior code**: `np.prod(1 + trade_rets) - 1` per year.
This treats all trades in a year as serial (sequential), severely overstating returns
when trades are parallel (multiple positions simultaneously).

**Fix**: All yearly/monthly returns derived from daily portfolio equity curve.

### GK Parameter Mismatch (DOCUMENTATION)
Written report cited Len=100, ATRLen=14 as default.  Code used Len=200, ATRLen=21.
**Resolution**: Both parameter sets run separately as A1/H1 (Orig L200) and A2 (Fast L100).

### Remaining Limitation
Stop cap (min(stop_level, next_open)) is applied at execution time using the stored cap
from signal day.  If a gap-down opens BELOW the stop level, we exit at the open,
which is the conservative (worse) outcome — this is the correct behavior.

## Data Convention
- Source: FireAnt OHLCV parquet cache, 271 symbols, 2023-01-03 – 2026-04-29
- Price unit: VND (not thousands VND).  Confirmed by ADV50 magnitudes (~2–20 billion VND/day
  for liquid stocks at typical Vietnam price levels of 10,000–100,000 VND × vol 1M+ shares).
- OHLC: price-adjusted (assumed; no raw/adjusted flag in dataset).
- ADV50: lagged — mean(value[t-50:t])/1e9.  First valid bar = t=50.
- Excluded: VPL (structural distortion per project convention).

## Corporate Action Anomaly Check
Found 15 extreme-gap events (>40% overnight) or suspicious trades.
See `corporate_action_anomalies.csv`.

## Signal Count Summary

- **A1** GK_Orig+GK_SELL: raw=52799 adv_ok=103 selected=82 rejected=52717
- **A2** GK_Fast+GK_SELL: raw=48319 adv_ok=148 selected=111 rejected=48208
- **A3** DC+Fixed63: raw=736 adv_ok=736 selected=126 rejected=610
- **H1** GK_Orig+GK_SELL: raw=52799 adv_ok=103 selected=82 rejected=52717
- **H2** GK_Orig+cloud+GK_SELL: raw=56910 adv_ok=95 selected=84 rejected=56826
- **H3** DC+cloud+Fixed63: raw=736 adv_ok=736 selected=126 rejected=610
- **H4** DC+cloud+GK_SELL: raw=250 adv_ok=250 selected=85 rejected=165
- **H5a** DC+GK_Lower_D1(close): raw=356 adv_ok=356 selected=114 rejected=242
- **H5b** DC+GK_Lower_D2(intraday): raw=432 adv_ok=432 selected=129 rejected=303
- **H5d** DC+GK_Lower_D4(trail): raw=415 adv_ok=415 selected=131 rejected=284
- **H6** DC+GK_SELL+7%stop: raw=600 adv_ok=600 selected=172 rejected=428
- **H7** DC+GK_SELL+8%stop: raw=459 adv_ok=459 selected=148 rejected=311
- **H8** DC+GK_SELL+10%stop: raw=412 adv_ok=412 selected=129 rejected=283
- **H9** DC+GK_SELL+12%stop: raw=377 adv_ok=377 selected=117 rejected=260
- **H10** DC+TrailGKLow+GK_SELL: raw=415 adv_ok=415 selected=131 rejected=284
- **H11** DC+TrailGKLow+7%+GK_SELL: raw=705 adv_ok=705 selected=219 rejected=486
- **H12a** DC+ATR2.5x14+GK_SELL: raw=1403 adv_ok=1403 selected=406 rejected=997
- **H12b** DC+ATR3.0x14+GK_SELL: raw=1101 adv_ok=1101 selected=286 rejected=815
- **H12c** DC+ATR3.5x14+GK_SELL: raw=899 adv_ok=899 selected=224 rejected=675
- **H13** DC+Chandelier3.0+10%: raw=139 adv_ok=139 selected=27 rejected=112
- **H14** DC+EMA20exit: raw=1183 adv_ok=1183 selected=340 rejected=843
- **H15** DC+EMA10exit: raw=1930 adv_ok=1930 selected=507 rejected=1423
- **CS_low** DC+GK_SELL+7%_CostLow: raw=600 adv_ok=600 selected=172 rejected=428
- **CS_high** DC+GK_SELL+7%_CostHigh: raw=600 adv_ok=600 selected=172 rejected=428

## Summary: All Arms

| Arm | Label | Trades | Win% | CAGR | MaxDD | MAR | Sharpe |
|-----|-------|--------|------|------|-------|-----|--------|
| A1 | GK_Orig+GK_SELL | 82 | 41.5% | 5.3% | -46.6% | 0.11 | 0.20 |
| A2 | GK_Fast+GK_SELL | 111 | 44.1% | 17.4% | -33.4% | 0.52 | 0.65 |
| A3 | DC+Fixed63 | 126 | 48.4% | 9.8% | -40.1% | 0.24 | 0.31 |
| H1 | GK_Orig+GK_SELL | 82 | 41.5% | 5.3% | -46.6% | 0.11 | 0.20 |
| H2 | GK_Orig+cloud+GK_SELL | 84 | 42.9% | 12.0% | -40.8% | 0.29 | 0.41 |
| H3 | DC+cloud+Fixed63 | 126 | 48.4% | 9.8% | -40.1% | 0.24 | 0.31 |
| H4 | DC+cloud+GK_SELL | 85 | 36.5% | 8.9% | -44.5% | 0.20 | 0.31 |
| H5a | DC+GK_Lower_D1(close) | 114 | 36.0% | 8.2% | -42.1% | 0.19 | 0.30 |
| H5b | DC+GK_Lower_D2(intraday) | 129 | 31.8% | 3.5% | -46.6% | 0.07 | 0.12 |
| H5d | DC+GK_Lower_D4(trail) | 131 | 35.9% | 9.4% | -39.0% | 0.24 | 0.34 |
| H6 | DC+GK_SELL+7%stop | 172 | 26.7% | -1.5% | -49.3% | 0.03 | -0.05 |
| H7 | DC+GK_SELL+8%stop | 148 | 29.7% | -0.0% | -48.7% | 0.00 | -0.00 |
| H8 | DC+GK_SELL+10%stop | 129 | 29.5% | -0.2% | -47.9% | 0.00 | -0.01 |
| H9 | DC+GK_SELL+12%stop | 117 | 30.8% | -1.4% | -47.3% | 0.03 | -0.05 |
| H10 | DC+TrailGKLow+GK_SELL | 131 | 35.9% | 9.4% | -39.0% | 0.24 | 0.34 |
| H11 | DC+TrailGKLow+7%+GK_SELL | 219 | 22.8% | -7.4% | -50.7% | 0.15 | -0.27 |
| H12a | DC+ATR2.5x14+GK_SELL | 406 | 28.6% | -26.9% | -70.4% | 0.38 | -0.97 |
| H12b | DC+ATR3.0x14+GK_SELL | 286 | 30.4% | -15.8% | -53.2% | 0.30 | -0.56 |
| H12c | DC+ATR3.5x14+GK_SELL | 224 | 31.7% | -19.6% | -63.2% | 0.31 | -0.66 |
| H13 | DC+Chandelier3.0+10% | 27 | 70.4% | 8.5% | -26.7% | 0.32 | 0.48 |
| H14 | DC+EMA20exit | 340 | 30.6% | -3.5% | -47.5% | 0.07 | -0.12 |
| H15 | DC+EMA10exit | 507 | 29.2% | -12.3% | -53.1% | 0.23 | -0.44 |
| CS_low | DC+GK_SELL+7%_CostLow | 172 | 26.7% | 0.5% | -47.3% | 0.01 | 0.02 |
| CS_high | DC+GK_SELL+7%_CostHigh | 172 | 26.2% | -3.6% | -51.1% | 0.07 | -0.12 |

## Yearly Portfolio Returns (from equity curve — NOT serial compounding)

| Arm | 2023 | 2024 | 2025 | 2026 YTD |
|-----|------|------|------|----------|
| A1 | 50.6% | -18.1% | -4.9% | 1.4% |
| A2 | 18.4% | 7.8% | 36.6% | -1.0% |
| A3 | 36.1% | -10.8% | 44.6% | -18.1% |
| H1 | 50.6% | -18.1% | -4.9% | 1.4% |
| H2 | 56.3% | 0.0% | -3.1% | -4.3% |
| H3 | 36.1% | -10.8% | 44.6% | -18.1% |
| H4 | 20.2% | -13.0% | 68.5% | -23.4% |
| H5a | 19.9% | -14.5% | 66.4% | -22.9% |
| H5b | 11.4% | -17.1% | 79.6% | -29.9% |
| H5d | 22.1% | -14.5% | 79.2% | -25.3% |
| H6 | 19.2% | -16.2% | 40.2% | -29.6% |
| H7 | 11.3% | -13.2% | 45.9% | -26.6% |
| H8 | 17.7% | -19.6% | 47.9% | -27.8% |
| H9 | 19.5% | -16.9% | 39.2% | -30.0% |
| H10 | 22.1% | -14.5% | 79.2% | -25.3% |
| H11 | 14.8% | -23.2% | 31.8% | -32.2% |
| H12a | -9.5% | -42.2% | -1.2% | -27.8% |
| H12b | -4.2% | -28.2% | 14.8% | -25.2% |
| H12c | 7.8% | -26.7% | -5.9% | -31.9% |
| H13 | 20.7% | -7.6% | 21.5% | -2.4% |
| H14 | -2.6% | -21.8% | 41.6% | -16.9% |
| H15 | -10.4% | -25.0% | 25.5% | -21.0% |
| CS_low | 21.0% | -14.3% | 42.5% | -28.5% |
| CS_high | 17.5% | -18.1% | 38.0% | -30.7% |

## Concentration Analysis

| Arm | HHI | CAGR | ex-top1 | ex-top3 | ex-top5 | cap50% | cap75% |
|-----|-----|------|---------|---------|---------|--------|--------|
| A1 | 0.0495 | 5.3% | 5.6% | 0.9% | -2.4% | 4.8% | 7.7% |
| A2 | 0.0488 | 17.4% | 14.6% | 7.1% | 2.6% | 9.4% | 14.3% |
| A3 | 0.0362 | 9.8% | 10.6% | 4.4% | -0.5% | 5.9% | 10.9% |
| H1 | 0.0495 | 5.3% | 5.6% | 0.9% | -2.4% | 4.8% | 7.7% |
| H2 | 0.052 | 12.0% | 10.1% | 4.5% | 0.2% | 7.4% | 11.5% |
| H3 | 0.0362 | 9.8% | 10.6% | 4.4% | -0.5% | 5.9% | 10.9% |
| H4 | 0.0954 | 8.9% | 4.8% | -2.0% | -5.8% | 0.4% | 4.7% |
| H5a | 0.0695 | 8.2% | 5.8% | -1.2% | -5.3% | 0.5% | 5.5% |
| H5b | 0.0709 | 3.5% | 0.8% | -4.7% | -8.8% | -3.4% | 1.7% |
| H5d | 0.0628 | 9.4% | 6.9% | 1.0% | -3.3% | 1.9% | 7.8% |
| H6 | 0.0427 | -1.5% | -1.7% | -6.0% | -9.6% | -3.2% | 0.3% |
| H7 | 0.0467 | -0.0% | -0.7% | -5.1% | -8.7% | -2.2% | 1.4% |
| H8 | 0.0521 | -0.2% | -1.5% | -6.2% | -9.8% | -3.4% | 0.1% |
| H9 | 0.0545 | -1.4% | -2.3% | -6.4% | -9.8% | -3.3% | -0.3% |
| H10 | 0.0628 | 9.4% | 6.9% | 1.0% | -3.3% | 1.9% | 7.8% |
| H11 | 0.0401 | -7.4% | -5.8% | -11.5% | -15.2% | -9.6% | -5.5% |
| H12a | 0.0212 | -26.9% | -26.1% | -28.7% | -30.9% | -25.7% | -24.6% |
| H12b | 0.0286 | -15.8% | -16.2% | -19.5% | -22.2% | -16.6% | -14.4% |
| H12c | 0.0369 | -19.6% | -19.3% | -22.6% | -24.9% | -19.2% | -17.7% |
| H13 | 0.0924 | 8.5% | 5.6% | 1.4% | -2.0% | 5.4% | 7.8% |
| H14 | 0.0228 | -3.5% | -3.0% | -7.6% | -11.2% | -5.1% | -1.4% |
| H15 | 0.0164 | -12.3% | -11.8% | -15.8% | -18.4% | -12.3% | -10.2% |
| CS_low | 0.0422 | 0.5% | 0.4% | -4.1% | -7.8% | -1.4% | 2.4% |
| CS_high | 0.0433 | -3.6% | -3.7% | -7.9% | -11.4% | -5.1% | -1.7% |

## Final Conclusions

See `corrected_summary.csv` for full metric table.
See `yearly_portfolio_returns.csv` for year-by-year detail.
See `concentration_report.csv` for winner-concentration robustness.
See `entry_quality_comparison.csv` for episode-level forward-return analysis.
