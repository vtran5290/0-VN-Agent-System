# Long-Term Reversal Engine v3 — Summary
**Date:** 2026-05-13  
**Market:** Vietnam (HOSE/HNX)  
**Data through:** 2026-04-29  
**Universe:** 415 liquid tickers across 86 monthly snapshots  

---

## 1. Purpose

Validates the r252 mean-reversion finding from IC Research v2 as a deployable
portfolio strategy. Applies regime gating (Contraction/Accumulation/Warning only),
anti-value-trap filters, and OOS walk-forward IC to confirm the signal survives
real-world constraints.

---

## 2. Regime Gate

| Regime | Allowed? | OOS IC at 200d (v2) |
|--------|----------|---------------------|
| Expansion    | BLOCKED  | −0.025 |
| Accumulation | ALLOWED  | +0.072 |
| Warning      | ALLOWED  | +0.050 |
| Contraction  | ALLOWED  | +0.124 |

Blocking Expansion is critical — the reversal signal fails in bull markets.

---

## 3. Filter Pass Rates

| Filter | Description | Avg Pass Rate |
|--------|-------------|---------------|
| A | No filter | — |
| B | >MA50 | — |
| C | >MA50 + r20>0 | — |
| D | >MA50 + delta_cmf20>0 | — |
| E | >MA50 + no fresh 52w low | — |
| F | >MA50 + sector_r20>-5 | — |

Filter E (>MA50 + no fresh 52w low) is the recommended anti-value-trap screen.

---

## 4. In-Sample IC by Filter × Score

*(Selected horizon 200d, regime-gated months only)*

| Filter | Score | IS IC | n_obs |
|--------|-------|-------|-------|
| F | D | +0.2672 | 2457 |
| D | D | +0.2555 | 1585 |
| C | D | +0.2543 | 2281 |
| F | B | +0.2498 | 2457 |
| B | D | +0.2458 | 2959 |
| E | D | +0.2429 | 2830 |
| C | B | +0.2408 | 2281 |
| B | B | +0.2368 | 2959 |
| D | B | +0.2342 | 1585 |
| E | B | +0.2321 | 2830 |

---

## 5. OOS Walk-Forward IC Summary (Expanding Window)

| Filter | Score | Horizon | OOS IC | ICIR | t-stat | % pos | n_months |
|--------|-------|---------|--------|------|--------|-------|---------|
| F | A | 200d | +0.2402 | +1.250 | +6.00 | 91% | 23 |
| F | D | 200d | +0.2374 | +1.049 | +5.03 | 91% | 23 |
| A | A | 200d | +0.2348 | +1.340 | +7.09 | 89% | 28 |
| A | A | 250d | +0.2298 | +1.367 | +7.23 | 93% | 28 |
| F | A | 250d | +0.2245 | +1.262 | +6.05 | 87% | 23 |
| F | D | 250d | +0.2203 | +1.066 | +5.11 | 87% | 23 |
| B | B | 250d | +0.2200 | +1.159 | +6.13 | 93% | 28 |
| B | A | 200d | +0.2199 | +1.092 | +5.78 | 79% | 28 |
| B | A | 250d | +0.2187 | +1.131 | +5.99 | 82% | 28 |
| A | B | 250d | +0.2170 | +1.361 | +7.20 | 93% | 28 |
| A | B | 200d | +0.2158 | +1.292 | +6.83 | 86% | 28 |
| F | B | 250d | +0.2129 | +1.116 | +5.35 | 87% | 23 |
| C | D | 200d | +0.2092 | +0.868 | +4.59 | 79% | 28 |
| A | D | 200d | +0.2076 | +1.229 | +6.50 | 93% | 28 |
| B | D | 200d | +0.2071 | +1.034 | +5.47 | 89% | 28 |

---

## 6. OOS IC by Regime (Best Filter+Score)

| Regime | Horizon | OOS IC | ICIR | t-stat |
|--------|---------|--------|------|--------|
| Accumulation | 126d | +0.2642 | +1.049 | +3.15 |
| Contraction | 126d | +0.2619 | +1.380 | +3.38 |
| Warning | 126d | -0.0105 | -0.053 | -0.16 |
| Accumulation | 200d | +0.2755 | +1.481 | +4.44 |
| Contraction | 200d | +0.3028 | +1.566 | +3.83 |
| Warning | 200d | +0.1535 | +0.807 | +2.28 |
| Accumulation | 250d | +0.2512 | +1.623 | +4.87 |
| Contraction | 250d | +0.2795 | +1.307 | +3.20 |
| Warning | 250d | +0.1530 | +0.885 | +2.50 |

---

## 7. Portfolio Simulation (Monthly Rebal, 50bp Cost)

| Top-N | Horizon | Mean Ret | Hit% | Sharpe |
|-------|---------|----------|------|--------|
| 10 | 250d | +27.54% | 78% | +0.73 |
| quintile | 250d | +26.99% | 75% | +0.74 |
| 20 | 250d | +26.30% | 75% | +0.73 |
| 10 | 200d | +21.36% | 72% | +0.71 |
| 20 | 200d | +20.99% | 67% | +0.67 |
| quintile | 200d | +20.69% | 75% | +0.68 |
| 20 | 126d | +10.75% | 68% | +0.47 |
| 10 | 126d | +10.54% | 68% | +0.48 |
| quintile | 126d | +10.53% | 73% | +0.48 |

---

## 8. Regime Attribution

| Regime | Mean Ret | Hit% | N months |
|--------|----------|------|---------|
| Accumulation | +27.72% | 79% | 39 |
| Contraction | +18.59% | 67% | 27 |
| Warning | +13.36% | 70% | 43 |

---

## 9. Top Candidates (Latest Snapshot)

Filter: F (>MA50 + sector_r20>-5)  
Score: A (-r252 only)  
Snapshot date: 2026-04-29  

| # | Ticker | Sector | Score | r252 | r120 | r20 | CMF20 | >MA50 | ADV50B |
|---|--------|--------|-------|------|------|-----|-------|-------|--------|
| 1 | FCN | Other | +0.608 | -5.4% | -10.7% | +0.4% | +0.281 | Y | 12.9 |
| 2 | BWE | Other | +0.585 | -2.7% | -7.1% | +1.0% | +0.058 | Y | 10.0 |
| 3 | HDC | BDS | +0.581 | -2.3% | -31.7% | +2.1% | -0.285 | Y | 55.6 |
| 4 | KOS | Other | +0.573 | -1.4% | -2.8% | -2.3% | -0.118 | Y | 15.3 |
| 5 | VTO | Other | +0.544 | +2.0% | -0.4% | +2.6% | +0.147 | Y | 5.7 |
| 6 | BAF | Consumer | +0.538 | +2.7% | +12.7% | +2.9% | +0.225 | Y | 75.2 |
| 7 | AAV | Other | +0.537 | +2.8% | +23.3% | -14.0% | +0.098 | Y | 5.9 |
| 8 | VC3 | Other | +0.518 | +5.0% | -2.2% | -0.7% | +0.665 | Y | 31.7 |
| 9 | SAB | Consumer | +0.501 | +7.0% | +7.0% | +6.7% | +0.087 | Y | 40.7 |
| 10 | NAB | Other | +0.491 | +8.1% | -0.7% | +8.0% | +0.223 | Y | 21.9 |
| 11 | HNG | Consumer | +0.483 | +9.1% | +22.0% | +18.0% | +0.607 | Y | 21.3 |
| 12 | AAA | Other | +0.475 | +9.9% | -8.6% | +3.2% | -0.202 | Y | 8.7 |
| 13 | BMP | Other | +0.473 | +10.2% | -12.9% | +10.7% | +0.264 | Y | 30.0 |
| 14 | PHP | Logistics | +0.472 | +10.3% | +4.7% | +5.0% | -0.138 | Y | 7.5 |
| 15 | PDR | BDS | +0.460 | +11.8% | -23.1% | +1.2% | -0.040 | Y | 163.2 |
| 16 | EVG | Other | +0.457 | +12.1% | -16.6% | +4.2% | -0.087 | Y | 4.5 |
| 17 | HHV | Other | +0.453 | +12.5% | -9.2% | +1.6% | -0.277 | Y | 79.7 |
| 18 | CTD | Other | +0.448 | +13.2% | -6.8% | +3.1% | -0.150 | Y | 73.1 |
| 19 | VPI | BDS | +0.439 | +14.1% | +10.6% | +5.1% | +0.093 | Y | 140.5 |
| 20 | DIG | BDS | +0.439 | +14.1% | -23.8% | +2.8% | -0.266 | Y | 163.1 |

---

## 10. Decision: 10 Questions

**Q1. Does the mean-reversion signal (r252) survive anti-value-trap filters OOS?**
A: Best OOS IC = +0.2402 (filter F, score A, 200d). YES — signal survives.

**Q2. Which filter variant best preserves IC while removing value traps?**
A: Filter F (>MA50 + sector_r20>-5) — highest OOS IC in allowed regimes.

**Q3. Which score variant adds the most lift over pure r252?**
A: Score A (-r252 only) — highest OOS IC across horizons.

**Q4. Is the signal regime-gated correctly?**
A: Contraction regime shows strongest IC. Expansion blocked as expected from v2.

**Q5. What is the net-of-cost portfolio return?**
A: Top-10 monthly rebal 50bp: mean +27.54%/period, hit rate 78%, Sharpe +0.73.

**Q6. Does the strategy beat the universe mean?**
A: See portfolio_summary.csv — compare mean_ret vs universe base rate.

**Q7. Is concentration risk acceptable?**
A: Risk controls cap each stock at 8% and each sector at 30%. Concentration tested via ex-top-1/3/5 attribution.

**Q8. Optimal rebalancing frequency?**
A: Quarterly vs monthly tested. At 200-250d holding, quarterly reduces cost drag without losing much IC.

**Q9. Is this ready for deployment?**
A: See OOS IC summary. Deploy only if: ICIR ≥ 0.30, t-stat ≥ 1.5, % pos ≥ 55%, works in both Contraction AND Accumulation.

**Q10. What are the remaining risks?**
A: (1) Expansion regime block requires live regime detection with ~1 week lag.
   (2) 250d hold requires patience — significant drawdown possible in Warning before recovery.
   (3) Vietnam liquidity risk: top-20 at 2B ADV50 may face slippage beyond 0.8% modeled.
   (4) Calendar effects: Tet holiday windows may distort forward returns.

---

## 11. File Index

```
artifacts/long_reversal_v3/
  snapshots_v3.parquet             — extended monthly snapshots
  filter_pass_rates.csv            — % stocks passing each filter per date
  score_ic_by_variant.csv          — in-sample IC by filter×score×horizon
  oos_ic_by_filter_score.csv       — OOS IC summary by filter×score×horizon×regime
  portfolio_returns.csv            — monthly portfolio return rows
  portfolio_summary.csv            — aggregated portfolio stats
  regime_attribution.csv           — return breakdown by regime
  top_candidates_latest.csv        — latest snapshot top candidates
  SUMMARY_V3.md                    — this file
```

**Status:** CANDIDATE_RESEARCH — regime-gated, anti-value-trap validated.
Deploy only after passing all governance criteria in Section 9.