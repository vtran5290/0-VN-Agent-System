# Portfolio Optimization Research — Batch Review Request

**Date:** 2026-05-16  
**Repo:** VN Agent System — Vietnam equities EMA-cloud strategy  
**Reviewer requested by:** VTran  

---

## Context: What this system is

Vietnam equities trading system. Three strategies running on daily OHLCV data for ~272 symbols (2012–2026):

| Label | Signal | Universe | Exit |
|-------|--------|----------|------|
| **A3 PRIMARY** | EMA 20/100 cloud turn (cloud_only_entry) | ex-VIN3 (excl VIC/VHM/VRE/VPL) | TP1=+18%, trail=2.5×ATR, max_hold=250 bars |
| **S3 SHADOW** | EMA 21/55 cloud turn (cloud_only_entry) | Full universe | TP1=+18%, trail=3.5×ATR, max_hold=250 bars |
| **C_GK** | Gaussian-Kernel channel + G07 regime gate | Full universe | Trail only (no TP1) |

`cloud_only_entry` = cloud turns bullish (fast > slow) after ≥3 bearish bars, price above fast EMA.  
Entry at next bar open (T+1 close used). Cost = 0.4% round-trip.  
Vietnamese T+3 settlement → min_sell_lock_bars=5.

---

## What this batch did

Full portfolio optimization research across 4 phases on 272 symbols, 33,813 total trades (2012–2026):

### Phase 0 — Baseline (equal-weight, max 20 positions)
| Strategy | CAGR | MaxDD | Sharpe | MAR | N_Trades | HitRate |
|----------|------|-------|--------|-----|----------|---------|
| A3 | 13.61% | -26.51% | 1.18 | 0.51 | 12,909 | 67.10% |
| S3 | 11.91% | -27.36% | 1.04 | 0.44 | 17,324 | 65.32% |
| COMBINED | 9.47% | -33.77% | 0.90 | 0.28 | 33,813 | 62.89% |

### Phase 1 — Sizing (114 experiments across A3 and S3)

Grid: equal-weight (7 position_pct × 5 max_pos), rank-based (linear/top_heavy/sqrt), inv-ATR, risk-per-trade (4 risk_pct × 4 stop_modes), bucket/Kelly stubs.

**Top findings:**

| Config | CAGR | MaxDD | Sharpe | MAR | Note |
|--------|------|-------|--------|-----|------|
| Equal pos=20 (baseline) | 13.61% | -26.51% | 1.18 | 0.51 | — |
| Equal pos=15 | 14.10% | -26.18% | 1.15 | 0.54 | Marginal improvement |
| **Linear rank (ema_dist)** | **20.40%** | -35.82% | **1.21** | **0.57** | Best practical |
| Top-heavy rank | 13.89% | -27.00% | 1.20 | 0.51 | ≈ baseline |
| Inv-ATR | 12.68% | -26.75% | 1.12 | 0.47 | Worse |
| Risk-per-trade rp=1.5%, fixed 7% | 59.80% | -72.79% | 1.22 | 0.82 | MAR winner, but -73% DD is impractical |

Linear rank-based sizes positions by ema_dist percentile rank within each entry batch. Higher ema_dist = larger weight.

### Phase 2 — Scale-in (16 configs: 2T and 3T, time/pullback/strength triggers)

All scale-ins simulate blended entry price across tranches, with the same exit logic applied from blended entry.

**Full results (all 16 configs):**

| Config | Trigger | CAGR | MaxDD | Sharpe | MAR | AvgTranches | MissedT |
|--------|---------|------|-------|--------|-----|-------------|---------|
| A3 2T_5050_T2 | time+2 | 11.08% | -28.36% | 1.06 | 0.39 | 1.84 | 2,062 |
| A3 2T_5050_T3 | time+3 | 11.92% | -27.41% | 1.10 | 0.43 | 1.81 | 2,496 |
| A3 2T_6040_T2 | time+2 | 11.20% | -28.11% | 1.06 | 0.40 | 1.84 | 2,062 |
| A3 2T_7030_T3 | time+3 | 12.16% | -28.72% | 1.14 | 0.42 | 1.81 | 2,496 |
| **A3 2T_5050_pullback** | **pullback −2%** | **15.66%** | **-23.68%** | **1.39** | **0.66** | 1.65 | 4,487 |
| A3 2T_5050_strength | strength +2% | 10.96% | -25.36% | 1.05 | 0.43 | 1.69 | 4,033 |
| A3 3T_403030_T2 | time+2 (3T) | 10.84% | -30.38% | 1.02 | 0.36 | 2.66 | 2,233 |
| A3 3T_503020_T2 | time+2 (3T) | 11.02% | -26.50% | 1.04 | 0.42 | 2.66 | 2,233 |
| S3 2T_5050_T2 | time+2 | 11.06% | -23.79% | 0.98 | 0.47 | 1.84 | 2,789 |
| S3 2T_5050_T3 | time+3 | 11.28% | -27.72% | 1.10 | 0.41 | 1.80 | 3,376 |
| S3 2T_6040_T2 | time+2 | 11.21% | -27.44% | 1.00 | 0.41 | 1.84 | 2,789 |
| S3 2T_7030_T3 | time+3 | 12.65% | -29.07% | 1.19 | 0.44 | 1.80 | 3,376 |
| **S3 2T_5050_pullback** | **pullback −2%** | **15.56%** | **-21.50%** | **1.24** | **0.72** | 1.64 | 6,230 |
| S3 2T_5050_strength | strength +2% | 9.54% | -34.26% | 0.91 | 0.28 | 1.69 | 5,438 |
| S3 3T_403030_T2 | time+2 (3T) | 10.56% | -31.51% | 0.94 | 0.34 | 2.66 | 3,104 |
| S3 3T_503020_T2 | time+2 (3T) | 10.33% | -26.64% | 1.06 | 0.39 | 2.66 | 3,104 |

**Pullback trigger definition:** Add second tranche when close pulls back to ≤ signal_close × 0.98 within next 20 bars, AND close > slow_EMA × 0.97. Exit uses blended entry price.

### Phase 3 — Convergence (45 combos: 3 windows × 5 modes × 3 multipliers)

All convergence experiments filter A3 trades and optionally boost ema_dist rank by conviction multiplier.

**Modes:**
- C0: no filter (full A3 ledger, 12,909 trades)
- C1: A3+S3 same day on same symbol
- C2: A3+S3 within N days on same symbol  
- C3: A3+GK within N days on same symbol
- C4: A3+S3+GK all within N days on same symbol

**Multipliers:** M0=none, M1=1.25×/1.5× (2-conv/3-conv), M2=1.5×/2.0×

**Key findings:**

| Config | Mode | Window | N_Trades | Coverage | CAGR | Sharpe | MAR |
|--------|------|--------|----------|----------|------|--------|-----|
| C0 baseline | No filter | — | 12,909 | 100% | 13.61% | 1.18 | 0.51 |
| **C3_M0_w5** | **A3+GK** | **5d** | **1,619** | **12.5%** | **14.60%** | **1.31** | **0.53** |
| C3_M1_w5 | A3+GK | 5d | 1,619 | 12.5% | 14.60% | 1.31 | 0.53 |
| C3_M0_w10 | A3+GK | 10d | 2,638 | 20.4% | 13.35% | 1.12 | 0.43 |
| C2_M2_w3 | A3+S3 | 3d | 6,184 | 47.9% | 12.82% | 1.07 | 0.45 |
| C1_M0 | Same day | — | 3,265 | 25.3% | 7.96% | 0.81 | 0.21 |

**Critical findings:**
1. A3+S3 convergence **HURTS** performance: C1 MAR=0.21 (vs 0.51 baseline). Same-day A3+S3 overlap is anti-correlated with quality.
2. A3+GK within 5 days (C3_w5) is the only filter that adds value — +10% Sharpe improvement, 12.5% of trades selected.
3. Multipliers have no effect when all filtered trades share the same convergence level.

### Phase 5 — Walk-Forward OOS (monthly folds, 125 folds 2016-2026)

Method: Pre-built trade ledger sliced into monthly folds by entry_date. Per-fold mean_net and hit_rate reported (equity-curve slicing was abandoned — inappropriate for 50-250 bar holds).

| Metric | Value |
|--------|-------|
| Positive-return folds | 82 / 125 (65.6%) |
| Mean net return per fold | 4.86% |
| Mean hit rate per fold | 63.86% |
| Fold stability | -1.819 |

65.6% positive folds ≈ in-sample hit rate (67.1% for A3) — confirms signal quality is consistent across time.

---

## Files in this package

| File | Description |
|------|-------------|
| `TOP_FINDINGS.md` | Auto-generated findings summary |
| `sizing_summary.csv` | 114 sizing experiments (all methods) |
| `scalein_summary.csv` | 16 scale-in experiments |
| `convergence_summary.csv` | 45 convergence experiments |
| `walk_forward_results.csv` | 125 monthly OOS folds |
| `trade_ledger_sample500.csv` | 500-row sample of 33,813-trade ledger |
| `equity_A3.csv` | A3 baseline daily equity curve |
| `equity_S3.csv` | S3 baseline daily equity curve |
| `portfolio_optimization_research.py` | Full research implementation |

---

## Review Questions

### 1. Pullback scale-in validity
The pullback trigger adds a second tranche when price retraces ≥2% from signal_close within 20 bars. The blended entry is then used for the exit sim (TP1 reprices to blended_ep × 1.18). A3 MAR improves from 0.51 → 0.66, S3 from 0.44 → 0.72, AND drawdown improves.

- Is the "missed tranche" count (4,487 for A3, 6,230 for S3) a concern? These are trades where no pullback occurred within 20 bars — they ran with tranche 1 only.
- Is the blended-entry-to-exit simulation correct? (same exit function, entry price = weighted average of actual close prices)
- Could selection bias explain part of the improvement? (stocks that pull back are different from stocks that don't)

### 2. A3+S3 convergence is anti-correlated
C1 (same-day A3+S3) shows MAR=0.21 vs 0.51 baseline. A3 fires on EMA 20/100 cloud turn (ex-VIN3), S3 fires on EMA 21/55 cloud turn (full universe). They share similar signal logic but different periods.

- Why would simultaneous signals be worse? Is this a data artifact (small N for C1 = 3,265 trades)?
- Or is there a structural reason — e.g., stocks with simultaneous cloud turns on both timeframes are overextended?
- Does C2 (within 3 days, 47.9% coverage) being slightly worse than baseline confirm this, or is it noise?

### 3. Linear rank-based sizing (+50% CAGR, +36% MaxDD)
B_A3_linear: CAGR=20.40%, MaxDD=-35.82%, MAR=0.57. Baseline: CAGR=13.61%, MaxDD=-26.51%, MAR=0.51.

- The CAGR boost is large (+50%) but MaxDD increases by +35%. Is MAR=0.57 vs 0.51 the right comparison metric for this tradeoff, or should we use Calmar or Sortino?
- Linear weighting assigns weight ∝ ema_dist rank within each entry batch (higher ema_dist = more weight). Is there a look-ahead concern? ema_dist at entry is computed from same-day close, entered at next-day open.
- Combining linear sizing with pullback scale-in was NOT tested. What would you expect?

### 4. Walk-forward fold stability score
Stability = 1 - std(fold_returns) / mean(fold_returns) = 1 - σ/μ = -1.819. This is negative because σ > μ (high variance of monthly average net returns). 

- Is this an expected result for a monthly slice of a multi-month holding strategy? 
- What would be the correct OOS validation framework for strategies with 50-250 bar holds?

### 5. Risk-per-trade sizing practical use
rp=0.015, fixed 7% stop gives CAGR=59.80%, MaxDD=-72.79%, MAR=0.82. This dominates all other methods by MAR but with catastrophic DD.

- At what MaxDD level does risk-per-trade become operationally feasible? -40%? -50%?
- Could risk-per-trade + GK regime gate (only trade when VNINDEX > EMA100 AND EMA20 > EMA50) significantly reduce the drawdown while preserving the CAGR boost?
- The stop distance is 7% (fixed). Is this realistic for Vietnam stocks with ATR/price often 2-5%?

### 6. C3 convergence (A3+GK within 5d) — is 12.5% coverage operationally useful?
C3_w5 selects 1,619 out of 12,909 A3 trades. In practice: the daily scan outputs ~5-15 near-entry symbols per day for A3. C3 would filter this to ~1-2 symbols per day that also have a GK signal within 5 days.

- Is a 1-2 symbol/day filtered list operationally better than the 5-15 symbol/day unfiltered list?
- The improvement is modest (MAR 0.51→0.53, Sharpe 1.18→1.31). Is the filtering complexity worth it?

---

## What was NOT done (pending)

- Bucket sizing (Phase 1E): requires walk-forward training window to estimate bucket thresholds from historical hit-rate × avg-gain. Stubbed in the CSV with NaN metrics.
- Kelly sizing (Phase 1F): same stub.
- Combining the best approaches (linear sizing + pullback scale-in + C3 filter): these were tested independently, not combined.
- Cost sensitivity analysis (low=0.2%, high=0.6% scenarios): only base=0.4% was run.
- Sub-period analysis by regime: did pullback scale-in help equally in bull/bear VNINDEX regimes?

---

*End of REVIEW_PROMPT.md*
