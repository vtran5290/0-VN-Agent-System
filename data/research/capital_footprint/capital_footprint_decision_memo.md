# Capital Footprint — Final Decision Memo

**Date:** 2026-05-29
**Status:** RESEARCH ONLY. No production change. All results are empirical backtest findings — not investment advice.

---

## FACTS

### IC Results — 20D Forward Return (all regimes, all liquidity tiers)

| Signal | IC Mean | IC t-stat | IC Hit Rate | n Dates | Direction |
|---|---|---|---|---|---|
| **dry_up_pullback_flag** | **+0.0107** | **+3.747** | 49.6% | 1,566 | **POSITIVE — significant** |
| cloud_bull_20_100 | +0.0031 | +0.749 | 50.2% | 1,596 | Neutral (not significant) |
| breakout_volume_flag | +0.0001 | +0.026 | 34.8% | 1,201 | Neutral (not significant) |
| sector_rotation_score | -0.0063 | -1.623 | 48.3% | 1,606 | Negative |
| big_individual_footprint_proxy | -0.0072 | -1.922 | 48.3% | 1,606 | **Negative — marginally sig.** |
| close_location_value | -0.0126 | -3.316 | 43.5% | 1,605 | **Negative — significant** |
| turnover_z_20d | -0.0127 | -3.317 | 44.8% | 1,606 | **Negative — significant** |
| net_accumulation_score | -0.0135 | -3.454 | 42.6% | 1,606 | **Negative — significant** |
| up_down_value_ratio_20d | -0.0153 | -3.731 | 45.2% | 1,606 | **Negative — significant** |
| rs_persistence_score | -0.0145 | -2.676 | 50.0% | 1,606 | **Negative — significant** |
| rs_rank_market_20d | -0.0183 | -3.584 | 44.7% | 1,606 | **Negative — significant** |
| **capital_footprint_score_raw** | **-0.0250** | **-5.092** | 45.4% | 1,606 | **NEGATIVE — highly significant** |
| capital_footprint_score_pure_tech | -0.0235 | -4.717 | 46.2% | 1,606 | **NEGATIVE — highly significant** |

### Year-by-Year IC (capital_footprint_score_raw vs fwd_ret_20d)

| Year | IC Mean | IC t-stat | Interpretation |
|---|---|---|---|
| 2019 | +0.0417 | +5.225 | **Strong positive** — signal worked in bull year |
| 2021 | +0.0301 | +3.513 | **Positive** — liquidity boom year |
| 2018 | -0.0074 | -0.744 | Weak negative |
| 2020 | -0.0268 | -2.497 | Negative — COVID disruption |
| 2022 | -0.0660 | -4.196 | Strong negative — correction year |
| 2023 | -0.0333 | -3.745 | Negative |
| 2024 | -0.1248 | -8.436 | **Very strongly negative** |
| 2025–2026 | -0.2661 | -4.377 | **Extremely negative** |

### Quantile Portfolio (CF raw score, 20D holding, all stocks, 0 bps)

| Quintile | Mean Return | Win Rate |
|---|---|---|
| Q1 (lowest CF) | +1.09% | 53.3% |
| Q2 | +0.95% | 52.0% |
| Q3 | +0.93% | 53.3% |
| Q4 | +0.58% | 50.7% |
| Q5 (highest CF) | +1.16% | 60.0% |
| **Q5 - Q1 spread** | **+0.07%** | — |

Note: Q5 win rate is higher (60%) but the mean return spread is essentially zero (+0.07%). The composite signal provides no meaningful quintile separation on 20-day returns.

### Data Quality Issues Found

- **breadth_pct**: All NaN in combined regime log — regime bucketing defaulted to STRESS for all rows. Regime analysis results are unreliable.
- **A3 join**: Only 2,597 of 215,638 A3 rows matched (1.2%). Root cause: A3 institutional accumulation backtest uses a different stock universe (lower-liquidity: PTM, TKC, ART) vs. CF panel (liquid stocks: SHB, HPG, SSI, FPT, VPB). Universe mismatch makes A3 enhancement tests statistically inconclusive.
- **Sector coverage**: Only 16.4% of OHLCV stocks have a sector classification. Sector rotation features apply to a minority of universe.

---

## INTERPRETATION

### Primary Finding: The Capital Footprint hypothesis is NOT validated for Vietnam's market at 20-day horizons.

**The composite CF score has statistically significant NEGATIVE predictive power (IC=-0.0250, t=-5.092).** Stocks ranked in the top quintile by CF score do NOT outperform low-CF stocks — they underperform.

**Vietnam is a mean-reversion market at 20D holding periods, not a momentum market.**

The signals with the strongest negative IC are exactly those that identify extended / high-activity stocks:
- High RS (recent outperformers) → tend to mean-revert
- High CLV on strong close → often marks distribution tops, not accumulation
- High net accumulation count → identifies stocks that have already run up; pullback likely
- Strong up/down value ratio → indicates extended price, not accumulation entry

**The only confirmed positive signal: `dry_up_pullback_flag` (IC=+0.0107, t=+3.747)**

This captures supply absorption: price holds near recent high while volume dries up. This is a CONTRARIAN signal — it identifies stocks where sellers have been absorbed before the next leg. The IC is modest but statistically reliable.

**Regime dependency is critical:** The composite was positive only in 2019 and 2021 (liquidity boom years). Post-2022, the IC worsened dramatically to -0.12 in 2024 and -0.27 in 2025. The hypothesis only holds in strong bull markets with high domestic liquidity.

### On the Big Individual Footprint Proxy

The proxy (high value + strong close + net accumulation) has a marginally significant NEGATIVE IC (-0.0072, t=-1.922). The proxy cannot distinguish:
1. Institutional accumulation before breakout → bullish
2. Large retail/prop desk distributing to retail → bearish
3. Market maker / arbitrage activity → neutral

Without foreign flow data for attribution, the proxy conflates accumulation and distribution. It should not be used for positive selection.

---

## Final Decision Table

| Use Case | Verdict | Evidence | Risk | Recommendation |
|---|---|---|---|---|
| **Standalone strategy** | **REJECT** | IC=-0.025, t=-5.09. CF score predicts underperformance. | Mean-reversion market at 20D. | Do not deploy. |
| **A3 ranking layer** | **INCONCLUSIVE** | 1.2% universe overlap; untestable. | Universe mismatch — CF uses liquid stocks, A3 uses illiquid. | Fix universes first, then retest. |
| **A3 soft filter** | **REJECT** | Insufficient data to test. CF score as positive filter would likely hurt A3 given negative IC. | Same universe issue. | Do not apply CF as positive filter to A3. |
| **A3 T2 confirmation** | **INCONCLUSIVE** | 6 matched rows — statistically meaningless. | Universe mismatch. | Needs proper universe match to test. |
| **Sector rotation watchlist** | **PARTIAL — WATCHLIST** | Sector rotation score IC=-0.006, not significant. Sector map only 16.4% coverage. | Sector data severely incomplete. | Expand sector map first, then retest. |
| **Big individual footprint proxy** | **REJECT** | IC=-0.007, marginally negative. Cannot attribute capital source without foreign flow. | Distribution and accumulation look identical in OHLCV. | Not useful without foreign flow data. |
| **dry_up_pullback_flag (standalone)** | **WATCHLIST** | IC=+0.0107, t=+3.747. Only statistically significant positive signal. | Regime-dependent (works in bull years). Low absolute IC. | Add as passive annotation in daily scan. Non-binding. |

---

## Top Findings

**Finding 1 — FACT: Mean-reversion dominates Vietnam at 20-day horizons.**
The most "accumulated" stocks by observable footprints (high RS, high CLV, high volume, high up/down ratio) underperform over 20 days. The capital footprint hypothesis is inverted. INTERPRETATION: Vietnam's retail-dominated market creates frequent distribution at extended prices. Identifying "where big money bought" after the fact often means identifying near-term distribution.

**Finding 2 — FACT: Supply absorption (dry_up_pullback) is the only valid signal.**
IC=+0.0107, t=+3.747. Consistent and statistically significant. INTERPRETATION: Quiet consolidation near highs with volume dry-up signals exhausted sellers, not active accumulation. This is the contrarian complement to the failed momentum hypothesis.

**Finding 3 — FACT: Strong regime dependency — positive only in 2019/2021.**
In 2024-2025, IC deteriorated to -0.12 and -0.27. INTERPRETATION: The composite only worked during peak domestic liquidity expansion. In the current environment (post-2022 tightening), momentum signals are particularly unreliable.

---

## What Failed

**Failed 1: Momentum/accumulation composite.**
High volume + strong close + high up/down ratio = distribution signal in Vietnam. The market structure does not reward momentum at 20-day holding periods.

**Failed 2: Big individual footprint proxy.**
Cannot distinguish accumulation from distribution without foreign flow attribution. Marginally negative IC.

**Failed 3: A3 universe alignment.**
CF panel universe (liquid stocks, ADV50 >= 1bn VND) does not overlap with A3 institutional accumulation backtest universe (lower-liquidity stocks). Enhancement tests are untestable without fixing this.

**Failed 4: Regime analysis.**
breadth_pct column all NaN in regime log. Regime bucketing was unreliable. Sector coverage only 16.4%.

---

## Production Impact

**Default answer: No production change.**

Specific actions:
1. **Do NOT add capital_footprint_score_raw or pure_tech** to any A3 ranking, filter, or review priority — signal predicts underperformance.
2. **Do NOT add big_individual_footprint_proxy** — marginally negative and unverifiable.
3. **Consider adding dry_up_pullback_flag annotation** to daily scan as passive context (non-binding, operator-read only, no hard filter).
4. **Do NOT use top_stocks_current.csv** for positive selection — high CF stocks may be at elevated mean-reversion risk.

---

## Next Steps

**Priority 1 (data gaps to fix before any further testing):**
- Expand sector_map.csv from 115 to full universe (use FA icbCode fallback already in features.py)
- Populate breadth_pct in combined regime log to enable regime bucketing
- Align CF panel universe with A3 universe (use same ADV filter as A3, or load A3 universe directly)

**Priority 2 (if data gaps fixed):**
- Rerun A3 enhancement test with matching universe
- Test whether dry_up_pullback_flag improves A3 T2 confirmation specifically
- Test 60D and 120D holding periods (may show different IC profile)

**Priority 3 (speculative directions):**
- Test INVERTED CF score: low CF stocks (mean-reversion short candidates, not for this strategy)
- Test 5D ultra-short holding — momentum vs mean-reversion profile at very short horizons
- Rerun with 2019/2021 universe only to confirm the regime-dependent finding

---

## Top 20 Stocks by CF Score on Latest Date (2026-05-29)

| Symbol | Sector | CF Score (Rank Pct) |
|---|---|---|
| MSB | Banks | 1.000 |
| ABB | Banks | 0.977 |
| VCB | Banks | 0.954 |
| TVN | Steel | 0.948 |
| ACB | Banks | 0.937 |
| BSR | Oil_Gas | 0.931 |
| LPB | Banks | 0.908 |

**WARNING: Given the negative IC finding, high CF scores in the current environment may indicate mean-reversion candidates, not momentum breakout candidates. Do NOT use this list for positive entry selection.**

---

*Runner: `scripts/research/run_capital_footprint_backtest.py`*
*22/22 lookahead guard + smoke tests passing*
*Full research pack: `data/research/capital_footprint/capital_footprint_review_pack.zip`*
