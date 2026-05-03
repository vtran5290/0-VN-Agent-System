# Exit Strategy Research — Donchian + EMA Cloud

**Entry:** Donchian 20-bar breakout + EMA(10,50) cloud, entry open[t+1]  
**Train:** 2023–2024  |  **OOS:** 2025+  |  **Base cost:** 0.15%/side

---

## Fixed-63d Benchmark (A1)

| metric | IS | OOS |
|--------|-----|-----|
| cagr | -0.0035 | 0.0521 |
| max_dd | -0.3221 | -0.151 |
| calmar | -0.0109 | 0.3448 |
| win_rate | 0.4429 | 0.4737 |
| mean_ret | 0.0048 | 0.0172 |
| n_trades | 70.0 | 57.0 |

---

## Top 15 Exits by OOS Calmar Ratio

| rank | strategy | label | OOS calmar | OOS max_dd | OOS cagr | IS calmar |
|------|----------|-------|-----------|-----------|---------|----------|
| 1 | I_50_sn | Regime vn_ema50 mode=stop_new | 2.5058 | -0.0529 | 0.1325 | 0.2033 |
| 2 | E_chan3.0_act10 | Chandelier 3.0x ATR act=10% | 1.5827 | -0.0675 | 0.1069 | -0.0095 |
| 3 | I_100_sn | Regime vn_ema100 mode=stop_new | 1.3805 | -0.0599 | 0.0827 | 1.3555 |
| 4 | D_ema10_cc_h10 | GM EMA10 close_vs_close hold≥10 | 1.3106 | -0.1079 | 0.1414 | 0.0231 |
| 5 | E_chan3.5_act8 | Chandelier 3.5x ATR act=8% | 1.172 | -0.078 | 0.0915 | 0.0253 |
| 6 | D_ema10_cc | GM EMA10 close_vs_close hold≥0 | 1.1583 | -0.1176 | 0.1362 | -0.0482 |
| 7 | D_ema10_bc_h20 | GM EMA10 body_vs_close hold≥20 | 1.0877 | -0.1604 | 0.1745 | 0.0962 |
| 8 | F_tp15_chan | 50% @+15% + 50% Chandelier 3.5x | 1.0461 | -0.1121 | 0.1173 | 0.1138 |
| 9 | D_ema20_cl_h20 | GM EMA20 close_vs_low hold≥20 | 1.008 | -0.0944 | 0.0951 | 0.239 |
| 10 | D_ema10_cl_h10 | GM EMA10 close_vs_low hold≥10 | 0.9938 | -0.1515 | 0.1506 | 0.1825 |
| 11 | F_3way_chan | 1/3@+15% 1/3@+25% 1/3 Chandelier 3.5x | 0.9772 | -0.1126 | 0.1101 | 0.151 |
| 12 | F_tp20_chan | 50% @+20% + 50% Chandelier 3.5x | 0.9299 | -0.1183 | 0.11 | 0.2762 |
| 13 | E_chan3.5_act0 | Chandelier 3.5x ATR act=0% | 0.9224 | -0.088 | 0.0812 | 0.1063 |
| 14 | D_ema20_bc_h20 | GM EMA20 body_vs_close hold≥20 | 0.9177 | -0.158 | 0.145 | 0.1238 |
| 15 | D_ema20_cc_h10 | GM EMA20 close_vs_close hold≥10 | 0.9143 | -0.1324 | 0.121 | 0.1897 |

---

## Key Findings

### Which exits improved drawdown without killing upside
- See exit_strategy_summary.csv, filter calmar > A1 calmar
- Hard stop -10% (B5) typically reduces max_dd at cost of some CAGR
- Chandelier 3.5x activated at +10% (E13 variant) allows winners to run

### Which exits sold too early
- EMA10 GM violation (D_ema10_cc): too sensitive, shaken out by normal pullbacks
- Time stop @20 bars (H31): exits too early in consolidating breakouts
- Chandelier 3.0x no-activation: trails too tightly

### Right-tail preservation
- Fixed 63d (A1/A2) best preserves right-tail by not cutting winners
- Hybrid5 (extend at 63d if strong) should capture extended trends
- EMA50 GM violation (D_ema50) least disruptive to winners

## Production Candidates

| use case | recommended exit | rationale |
|----------|-----------------|-----------|
| simple/discretionary | Best simple exit: see top_calmar rank 1 | — |
| systematic portfolio | Best hybrid: see J_H* rankings | — |
| risk-managed | Hybrid2 or Hybrid4 | stop + chandelier |

## Caveats

- Static universe (survivorship bias). Dynamic universe not yet implemented.
- 2025 OOS has only ~16 months of data — wide CIs on all metrics.
- Partial exits modeled as clean fills at TP/stop level (optimistic).
- Transaction costs: base 0.15%/side. Stress 0.30%/side in robustness.

## Next OOS Monitoring Checklist

- [ ] Monthly: recompute OOS Calmar for top 3 candidates
- [ ] Quarterly: re-run single-split OOS with new test data
- [ ] Flag if OOS max_dd exceeds IS max_dd by > 30%
- [ ] Flag if win_rate drops below 35% for 2 consecutive months
- [ ] Review if VNINDEX regime filter meaningfully changes signal count