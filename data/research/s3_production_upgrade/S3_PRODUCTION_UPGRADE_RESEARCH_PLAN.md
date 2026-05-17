# S3 Production Upgrade — Research Plan

Date: 2026-05-17
Git commit: 1b99bcd

---

## 1. Data

- Panel: 741,563 rows × 8 columns
- Symbols: 272
- Date range: 2012-01-03 to 2026-05-15
- Source: data/research/ema_cloud/ohlcv_panel_ext2012.parquet

## 2. Universe

- A3 universe: "ex_vin3" — excludes VIC, VHM, VRE, VPL
- S3 universe: "full" — all symbols with ≥ 150 bars data
- VPL excluded until 252 bars accumulated (see VIN_EMA_CLOUD_BASELINE.md)

## 3. Price Unit Convention

- `close` is in kVND (thousands of VND)
- `volume` is shares
- `adv50_value_VND = close_kVND × volume × 1000` (corrected Phase 3.1)

## 4. Cost Assumptions

| Scenario | Cost per trade (round-trip) |
|----------|----------------------------|
| Base     | 0.4% (0.004)               |
| Stress   | 0.6% (0.006)               |

## 5. Liquidity Assumptions

| Portfolio size | Slots | ADV participation |
|---------------|-------|-------------------|
| 1B VND        | 20    | 10%               |
| 3B VND        | 20    | 10%               |
| 5B VND (base) | 20    | 10%               |
| 10B VND       | 20    | 10%               |

ADV participation cap = 10% of ADV50 per trade.

## 6. Settlement

- min_sell_lock_bars = 5 (Vietnam T+3, minimum 5 bars before selling)

## 7. Metrics

| Metric | Description |
|--------|-------------|
| CAGR | Compound annual growth rate |
| MaxDD | Maximum drawdown |
| MAR | CAGR / abs(MaxDD) — primary gate metric |
| Hit rate | % trades with net_return > 0 |
| TP1 rate | % trades that triggered TP1 exit |
| Avg hold | Average bars held |
| Trade count | Total trades in backtest period |
| Annual returns | Year-by-year equity return |

## 8. Gate Definitions

| Gate | Condition |
|------|-----------|
| PAPER_TRADE_SHADOW | MAR ≥ 0.30, no severe concentration, no data bugs |
| PRODUCTION_CANDIDATE | MAR ≥ A3 DP (0.416) or close with better diversification |
| Real-capital | Separate future gate: 3+ months paper trade, 30+ decisions |

## 9. Strict Rule

All outputs are written to:
  data/research/s3_production_upgrade/

A3/Phase34/Phase35 files in missing_work/ are NOT modified.

## 10. Current Accepted Truth

- A3 DP-first (EMA20/100, ex-VIN3): MAR = 0.416 — PRODUCTION_CANDIDATE
- S3 default max_hold=250: MAR ≈ -0.011 — REJECTED
- S3 max_hold=60: MAR ≈ 0.377 — PAPER_TRADE_SHADOW (confirmed)
- S3 top100 ADV: MAR ≈ 0.334 — PAPER_TRADE_SHADOW (confirmed)
- S3_GK5_max60_top100: MAR ≈ 0.449 — FUTURE_RETEST_REQUIRED (unverified)
- S3Lead5 (a3_s3_lead_5d): A3 with_s3 MAR delta = +0.083 vs without_s3
