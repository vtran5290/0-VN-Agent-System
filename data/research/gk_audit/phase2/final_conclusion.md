# Phase 2 Research — Final Conclusion

Run date: 2026-05-03

---

## A. FACTS

### Task 1 — True Concentration Rerun

| Arm | Scenario | ExclN | Trades | CAGR | MaxDD | MAR |
|-----|----------|-------|--------|------|-------|-----|
| A2 | baseline | 0 | 111 | 17.4% | -33.4% | 0.52 |
| A2 | top1_trade | 1 | 106 | 16.1% | -40.3% | 0.40 |
| A2 | top3_trade | 3 | 109 | 7.1% | -40.0% | 0.18 |
| A2 | top5_trade | 5 | 112 | 3.1% | -42.6% | 0.07 |
| A2 | top1_ticker | 1 | 112 | 8.8% | -33.4% | 0.26 |
| A2 | top3_ticker | 3 | 107 | 7.4% | -40.3% | 0.18 |
| A2 | top5_ticker | 5 | 109 | 5.5% | -40.0% | 0.14 |
| A2 | ca_all | 15 | 111 | 14.2% | -34.0% | 0.42 |
| A3 | baseline | 0 | 126 | 9.8% | -40.1% | 0.24 |
| A3 | top1_trade | 1 | 126 | 10.9% | -40.1% | 0.27 |
| A3 | top3_trade | 3 | 126 | 5.6% | -44.3% | 0.13 |
| A3 | top5_trade | 5 | 126 | -0.8% | -48.8% | 0.02 |
| A3 | top1_ticker | 1 | 126 | 10.9% | -40.1% | 0.27 |
| A3 | top3_ticker | 3 | 126 | 5.3% | -39.5% | 0.14 |
| A3 | top5_ticker | 5 | 126 | -0.8% | -48.8% | 0.02 |
| A3 | ca_all | 15 | 125 | 3.6% | -47.4% | 0.08 |
| H4 | baseline | 0 | 85 | 8.9% | -44.5% | 0.20 |
| H4 | top1_trade | 1 | 86 | 3.1% | -44.5% | 0.07 |
| H4 | top3_trade | 3 | 88 | -2.2% | -43.0% | 0.05 |
| H4 | top5_trade | 5 | 90 | -4.9% | -45.6% | 0.11 |
| H4 | top1_ticker | 1 | 86 | 3.1% | -44.5% | 0.07 |
| H4 | top3_ticker | 3 | 88 | -2.2% | -43.0% | 0.05 |
| H4 | top5_ticker | 5 | 90 | -4.9% | -45.6% | 0.11 |
| H4 | ca_all | 15 | 82 | 4.3% | -44.7% | 0.10 |
| H5d | baseline | 0 | 131 | 9.4% | -39.0% | 0.24 |
| H5d | top1_trade | 1 | 134 | 2.4% | -39.0% | 0.06 |
| H5d | top3_trade | 3 | 136 | -0.9% | -40.3% | 0.02 |
| H5d | top5_trade | 5 | 139 | -5.1% | -41.4% | 0.12 |
| H5d | top1_ticker | 1 | 134 | 2.4% | -39.0% | 0.06 |
| H5d | top3_ticker | 3 | 136 | -0.9% | -40.3% | 0.02 |
| H5d | top5_ticker | 5 | 139 | -5.1% | -41.4% | 0.12 |
| H5d | ca_all | 15 | 132 | 3.2% | -39.2% | 0.08 |

### Task 2 — Exposure-Adjusted Benchmarks

| Arm | AvgExp | Beta | Corr | StratCAGR | AdjVNXCAGR | ExcessCAGR | ActiveMaxDD |
|-----|--------|------|------|-----------|-----------|-----------|------------|
| A2 | 91% | 0.72 | 0.49 | 17.4% | n/a | n/a | -30.1% |
| H4 | 99% | 0.98 | 0.62 | 8.9% | n/a | n/a | -41.8% |
| H5d | 99% | 0.88 | 0.58 | 9.4% | n/a | n/a | -40.8% |
| A3 | 93% | 1.02 | 0.59 | 9.8% | n/a | n/a | -41.8% |

### Task 3 — GK_Fast + EMA Filters

| Arm | Label | Trades | CAGR | MaxDD | MAR | Sharpe |
|-----|-------|--------|------|-------|-----|--------|
| F1 | GKFast+Close>EMA50 | 107 | 10.4% | -40.3% | 0.26 | 0.34 |
| F2 | GKFast+Close>EMA100 | 109 | 15.1% | -44.1% | 0.34 | 0.48 |
| F3 | GKFast+Close>EMA150 | 115 | 11.7% | -46.1% | 0.25 | 0.39 |
| F4 | GKFast+EMA150slope | 115 | 11.7% | -46.1% | 0.25 | 0.39 |
| F5 | GKFast+Close>EMA150+slope | 115 | 11.7% | -46.1% | 0.25 | 0.39 |
| F6 | GKFast+Close>EMA150+slope+RS3M | 112 | 15.3% | -42.7% | 0.36 | 0.55 |

### Task 4 — GK_Fast Parameter Grid

| Arm | Label | Trades | CAGR | MaxDD | MAR |
|-----|-------|--------|------|-------|-----|
| G09 | L100_M2.0_C2 | 111 | 17.4% | -33.4% | 0.52 |
| G11 | L100_M2.2_C2 | 102 | 14.4% | -40.3% | 0.36 |
| G01 | L80_M1.8_C2 | 127 | 9.5% | -37.1% | 0.26 |
| G08 | L100_M1.8_C3 | 110 | 8.6% | -35.4% | 0.24 |
| G07 | L100_M1.8_C2 | 121 | 8.7% | -38.0% | 0.23 |
| G02 | L80_M1.8_C3 | 115 | 6.6% | -35.1% | 0.19 |
| G12 | L100_M2.2_C3 | 97 | 5.3% | -36.1% | 0.15 |
| G15 | L120_M2.0_C2 | 106 | 5.4% | -42.2% | 0.13 |
| G18 | L120_M2.2_C3 | 92 | -6.6% | -55.0% | 0.12 |
| G17 | L120_M2.2_C2 | 100 | -6.6% | -57.5% | 0.12 |

### Task 5 — DC Ranking Variants

| Arm | Label | Trades | CAGR | MaxDD | MAR |
|-----|-------|--------|------|-------|-----|
| R_vole_GKOr | DC+volexp+GKOrigSell | 83 | 16.1% | -51.6% | 0.31 |
| R_vole_GKFa | DC+volexp+GKFastSell | 119 | 12.4% | -39.8% | 0.31 |
| R_rs6m_Fixe | DC+rs6m+Fixed63 | 126 | 9.7% | -34.0% | 0.29 |
| R_comp_Fixe | DC+composite+Fixed63 | 126 | 10.0% | -36.1% | 0.28 |
| R_vole_Fixe | DC+volexp+Fixed63 | 126 | 7.4% | -34.8% | 0.21 |
| R_near_GKOr | DC+near52wk+GKOrigSell | 87 | 8.9% | -49.6% | 0.18 |
| R_rs3m_GKOr | DC+rs3m+GKOrigSell | 86 | 8.6% | -47.8% | 0.18 |
| R_near_Fixe | DC+near52wk+Fixed63 | 126 | 7.3% | -43.9% | 0.17 |
| R_rs6m_GKFa | DC+rs6m+GKFastSell | 120 | 7.5% | -45.6% | 0.17 |
| R_rs6m_GKOr | DC+rs6m+GKOrigSell | 86 | 8.3% | -51.9% | 0.16 |

### Task 6 — DC + GK_FAST Exit Arms

| Arm | Label | Trades | CAGR | MaxDD | MAR |
|-----|-------|--------|------|-------|-----|
| P6a | DC+cloud+GKFast_SELL | 123 | 11.5% | -45.7% | 0.25 |
| P6b | DC+cloud+GKFast_Lower_D1 | 170 | -0.1% | -46.6% | 0.00 |
| P6c | DC+cloud+GKFast_Lower_D4 | 204 | -6.9% | -43.8% | 0.16 |

### Task 7 — Data Quality

Top-20 trades checked: 20 total, 0 flagged for review.

---

## B. INTERPRETATION

1. **Concentration robustness**: If CAGR collapses >50% when top-3 tickers excluded, the strategy
   is a handful-of-winners story, not a systematic edge.

2. **Exposure-adjusted alpha**: Excess CAGR vs exposure-weighted VNINDEX is the cleanest alpha
   measure. Negative excess CAGR = strategy underperforms passive VNX exposure.

3. **EMA filters**: Adding Close>EMA150 + slope should reduce false breakouts in downtrends.
   If it reduces trades by >40% with <10% CAGR improvement, the filter is too tight.

4. **Best grid combo**: L100_M2.0_C2 — CAGR 17.4% MAR 0.52.

5. **Best ranking**: DC+volexp+GKOrigSell — CAGR 16.1% MAR 0.31.

---

## C. DECISION

- If any EMA-filter arm beats A2 (GK_Fast baseline) by MAR with ≥20 trades/year → adopt filter.
- If concentration reruns show CAGR drops >60% ex-top3-tickers → do NOT scale until universe expanded.
- If best grid combo is not L100_M2.0 (current default) → update AFL default params.
- If DC+GK_FAST_SELL (P6a) beats DC+GK_ORIG_SELL (H4) → use GK_FAST for all DC exits.

---

## D. BEST CURRENT AFL DEFAULT

Based on Phase 1 + Phase 2 results:
- Entry: GK_Fast (L100, Mult2.0, ATR14, Conf2)
- EMA filter: TBD from Task 3 results
- Exit: GK_SELL (same param set as entry)
- Universe filter: ADV50 > 2B VND/day
- Portfolio: max 10 positions, equal slot, 35bps friction/side

---

## E. TOP 3 NEXT RESEARCH ITEMS

1. **Adjusted price data**: Obtain adjusted OHLCV to resolve the VIC/L40 unadjusted-price concern.
   Re-run A2, H4, H5d on clean data to confirm whether 2025 gains persist.

2. **Sector/regime overlay**: Add VNINDEX trend filter (e.g., VNINDEX > EMA200) to gate all entries.
   This is the most commonly cited improvement in Vietnam trend-following research.

3. **Longer test period**: Extend parquet cache back to 2018 to get a full bear-market test
   (2018 drawdown -30%, 2022 drawdown -30%). Current 2023-2026 is a recovering/bull period only.

---

## F. KILL CRITERIA

Abandon GK_Fast as primary entry signal if ANY of:
- Phase 2 concentration rerun shows CAGR < 5% ex-top-5-tickers for A2
- Exposure-adjusted excess CAGR (vs adj VNINDEX) < 2% for A2
- Best EMA-filter arm has MAR < 0.3 (lower than DC+Fixed63 baseline)
- Walk-forward fold 2 (2025 test) test_CAGR < -10% for A2 (already: -5% in Phase 1 WF, marginal)

Abandon DC breakout as universe entry if:
- CAGR ex-top-5-tickers < 3% for all DC arms (H4, P6a)
- No ranking variant beats ADV50 by >2% CAGR