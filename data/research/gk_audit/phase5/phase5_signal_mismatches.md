# Phase 5 — AFL / Python Signal Reconciliation Checklist

This file exports the Python-side signal computation for C06.
Compare against AmiBroker AFL chart manually.

## Reconciliation Checklist

For each ticker below, verify against AFL chart:

| Field | Check |
|-------|-------|
| GK_Buy date | Does AFL BUY arrow match Python `gk_buy=True` date? |
| GK_Sell date | Does AFL SELL arrow match Python `gk_sell=True` date? |
| VolExp filter | Is `volexp >= 1.2` same as AFL VolExp gate? |
| ADV50 filter | Is `adv50_lag >= 2.0 bn` same as AFL ADV50 gate? |
| VNINDEX EMA50 | Is `vnx_above_e50` same as AFL regime check? |
| Time stop | Does AFL exit at bar 20 if flat/neg match Python `tstop_would_fire`? |
| Size factor | Is half-size (0.5) when regime OFF matching AFL? |

## Common Mismatch Sources

1. **EMA seed**: Python and AFL may differ in EMA initialization if lookback window differs.
   - Python: EMA starts seeding from first non-NaN price.
   - AFL: may use first bar as seed. Check EMA values at period start.

2. **ATR seed**: Wilder ATR uses SMA seed for first `n` bars.
   - Same logic in both; should match if warmup data covers 100+ bars.

3. **ADV50 calculation**: Python uses lagged ADV50 (bars i-50 to i-1).
   - AFL must use same lagging convention (prior 50 bars, not including today).

4. **Price unit**: Python reads raw VND from parquet.
   - AFL must use Thousand VND with same multiplier correction.

5. **Execution timing**: Python entry = next open after signal bar.
   - AFL must buy at next open (no lookahead).

6. **Corporate action**: VIC/VHM/VRE prices may differ if AFL uses adjusted data.

## Tickers Traced

### VRE
- GK Buy signals:  ['2023-07-13', '2024-01-04', '2024-08-26', '2025-10-07', '2026-01-07', '2026-04-16']
- GK Sell signals: ['2023-06-01', '2023-09-19', '2024-04-16', '2025-09-22', '2025-11-07', '2026-02-03']
- TStop fire dates:['2023-09-18', '2023-09-19', '2023-09-20', '2023-09-21', '2023-09-22', '2023-09-25', '2023-09-26', '2023-09-27', '2023-09-28', '2023-09-29']

### VGI
- GK Buy signals:  ['2023-04-13', '2023-10-13', '2024-02-27', '2024-10-11', '2025-06-10', '2025-11-10', '2026-01-12']
- GK Sell signals: ['2023-08-21', '2023-12-18', '2024-07-22', '2025-01-15', '2025-09-30', '2025-12-26', '2026-03-06']
- TStop fire dates:['2023-05-17', '2023-05-18', '2023-05-19', '2023-05-22', '2023-05-23', '2023-05-24', '2023-05-25', '2023-05-26', '2023-05-29', '2023-05-30']

### VIC
- GK Buy signals:  ['2023-08-01', '2023-12-05', '2024-04-15', '2026-04-15']
- GK Sell signals: ['2023-05-08', '2023-09-15', '2024-01-31', '2026-01-28']
- TStop fire dates:['2023-09-14', '2023-09-15', '2023-09-18', '2023-09-19', '2023-09-20', '2023-09-21', '2023-09-22', '2023-09-25', '2023-09-26', '2023-09-27']

### FPT
- GK Buy signals:  ['2023-01-30', '2023-08-25', '2024-04-25', '2024-12-06', '2025-06-11', '2025-10-29']
- GK Sell signals: ['2023-07-06', '2023-10-26', '2024-07-25', '2025-02-10', '2025-08-25', '2026-02-25']
- TStop fire dates:['2023-10-05', '2023-10-06', '2023-10-09', '2023-10-10', '2023-10-11', '2023-10-12', '2023-10-13', '2023-10-16', '2023-10-17', '2023-10-18']

### HPG
- GK Buy signals:  ['2023-01-30', '2023-12-07', '2024-05-08', '2024-10-01', '2025-06-17', '2026-02-25']
- GK Sell signals: ['2023-08-23', '2024-01-31', '2024-07-24', '2025-04-04', '2025-10-16']
- TStop fire dates:['2024-01-05', '2024-01-08', '2024-01-09', '2024-01-10', '2024-01-11', '2024-01-12', '2024-01-15', '2024-01-16', '2024-01-17', '2024-01-18']

### TCH
- GK Buy signals:  ['2023-01-31', '2024-03-21', '2025-02-05', '2025-05-27', '2026-03-25']
- GK Sell signals: ['2023-10-03', '2024-07-22', '2025-04-09', '2025-09-19']
- TStop fire dates:['2024-04-19', '2024-04-22', '2024-04-23', '2024-04-24', '2024-04-25', '2024-04-26', '2024-05-02', '2024-05-03', '2024-05-06', '2024-05-07']

### NVL
- GK Buy signals:  ['2023-04-12', '2023-11-22', '2024-08-22', '2025-02-21', '2025-04-24', '2026-03-17']
- GK Sell signals: ['2023-02-14', '2023-09-19', '2024-03-12', '2025-01-14', '2025-04-08', '2025-08-25']
- TStop fire dates:['2023-05-15', '2023-05-16', '2023-05-17', '2023-05-18', '2023-05-19', '2023-05-22', '2023-05-23', '2023-05-24', '2023-05-25', '2023-05-26']

### winner_L40
- GK Buy signals:  ['2023-02-03', '2023-07-14', '2023-11-13', '2024-04-15', '2025-05-21', '2025-08-29', '2026-04-29']
- GK Sell signals: ['2023-01-30', '2023-05-08', '2023-09-05', '2024-01-31', '2024-12-20', '2025-08-06', '2025-12-01']
- TStop fire dates:[]

### loser_ACV
- GK Buy signals:  ['2023-07-13', '2024-01-26', '2024-04-15', '2024-10-14', '2025-05-21', '2026-01-12']
- GK Sell signals: ['2023-04-10', '2023-08-29', '2024-01-31', '2024-07-19', '2025-02-12', '2025-10-01', '2026-03-20']
- TStop fire dates:['2023-08-10', '2023-08-11', '2023-08-14', '2023-08-15', '2023-08-16', '2023-08-17', '2023-08-18', '2023-08-21', '2023-08-22', '2023-08-23']
