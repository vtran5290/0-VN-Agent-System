# Phase 1 Revised — Review Package
**Date:** 2026-05-16
**Repo:** VN Agent System — Vietnam equities EMA-cloud strategy
**Reviewer requested by:** VTran

---

## Context: What this system is

Vietnam equities trading system. Three strategies running on daily OHLCV data for ~272 symbols (2012–2026):

| Label | Signal | Universe | Exit |
|-------|--------|----------|------|
| **A3 PRIMARY** | EMA 20/100 cloud turn (`cloud_only_entry`) | ex-VIN3 (excl VIC/VHM/VRE/VPL) | TP1=+18%, trail=2.5×ATR, max_hold=250 bars |
| **S3 SHADOW** | EMA 21/55 cloud turn (`cloud_only_entry`) | Full universe | TP1=+18%, trail=3.5×ATR, max_hold=250 bars |
| **C_GK** | Gaussian-Kernel channel + G07 regime gate | Full universe | Trail only, ~24-bar mean hold |

`cloud_only_entry` = cloud turns bullish (fast > slow) after ≥3 bearish bars, price above fast EMA.
Entry at next bar open (T+1 close used). Cost = 0.4% round-trip.
Vietnamese T+3 settlement → min_sell_lock_bars=5.

**Baseline (corrected engine, equal-weight, 20 positions):**

| Strategy | CAGR | MaxDD | Sharpe | MAR | N_Trades | HitRate |
|----------|------|-------|--------|-----|----------|---------|
| A3 | 13.61% | -26.51% | 1.18 | 0.51 | 12,909 | 67.10% |
| S3 | 11.91% | -27.36% | 1.04 | 0.44 | 17,324 | 65.32% |

---

## What changed vs the prior review package

**Two bugs were fixed from the earlier optimization session:**
1. `max_position_pct` was decorative in equal-weight (never enforced). Fixed.
2. Linear rank weights were not batch-normalized → implicit leverage up to 1.4×. Fixed.

**One finding invalidated:**
- Risk-per-trade CAGR=59.80% (prior): stop was used to SIZE positions but never EXECUTED. Now actual stop execution with T+5 sell-lock is simulated.

All Phase 1 results below are from the corrected engine.

---

## Phase 1B — Pullback Scale-in Robustness

### Setup
Second tranche triggered when close pulls back ≥ `depth`% from signal_close within `window` bars, AND quality filter passes (default: `close > slow_EMA × 0.97`). Blended entry price used for all exits.

Core grid: 5 depths (1–5%) × 5 windows (5–30 bars) × 2 strategies = 50 configs.
Plus quality variants and split variants at d=2%, w=20.

### Top results by MAR

| Config | Strategy | Depth | Window | PB% | Mean Net All | Mean Net PB | Mean Net No-PB | Blended Benefit | CAGR | MaxDD | Sharpe | MAR |
|--------|----------|-------|--------|-----|-------------|-------------|----------------|-----------------|------|-------|--------|-----|
| d4_w30_slow097 | A3 | 4% | 30b | 51.0% | 7.31% | 4.81% | 9.91% | +0.87% | 13.83% | -23.84% | 1.35 | **0.58** |
| d4_w20_slow097 | A3 | 4% | 20b | 45.3% | 7.23% | 4.74% | 9.29% | +0.79% | 13.60% | -23.97% | 1.33 | **0.57** |
| d5_w20_slow097 | S3 | 5% | 20b | 33.7% | 7.11% | 3.38% | 9.00% | +0.82% | 12.34% | -22.71% | 1.20 | **0.54** |
| d2_w20_slow097 | A3 | 2% | 20b | 66.0% | 7.20% | 5.26% | 10.95% | +0.75% | 13.63% | -26.07% | 1.31 | 0.52 |

Baseline A3 MAR = 0.51. Best improvement: +0.07 MAR (d=4%, w=30).

### Pullback vs No-Pullback trade quality (at d=2%, w=20, slow_097)

| Strategy | Group | N | Mean Net | Mean T1-only | Blended Benefit | Hit Rate | Mean MAE | Mean Hold |
|----------|-------|---|----------|-------------|-----------------|----------|----------|-----------|
| A3 | All trades | 9,030 | 7.20% | 6.44% | +0.75% | 71.8% | -15.4% | 133 bars |
| A3 | Pullback occurred | 5,964 | 5.26% | 4.12% | +1.14% | 67.2% | -18.3% | 146 bars |
| A3 | No pullback | 3,066 | 10.95% | 10.95% | 0.00% | 80.6% | -9.7% | 106 bars |
| S3 | All trades | 11,819 | 7.19% | 6.29% | +0.90% | 69.9% | -16.4% | 145 bars |
| S3 | Pullback occurred | 7,725 | 4.65% | 3.28% | +1.37% | 65.1% | -19.7% | 158 bars |
| S3 | No pullback | 4,094 | 11.97% | 11.97% | 0.00% | 78.9% | -10.3% | 121 bars |

**Critical finding:** No-pullback trades have mean_net ≈ 2× that of pullback trades (10.95% vs 5.26% for A3). The blended-entry benefit (+0.75–1.14%) is real but small relative to the quality gap. Pullback trades have higher MAE (-18.3% vs -9.7%) and longer holds (146 vs 106 bars).

---

## Phase 1C — Rank Sizing (corrected normalization)

### Setup
Equal-weight corrected: `base_w = min(1/max_positions, max_position_pct)`, enforced.
Rank modes: linear (weight ∝ ema_dist rank), top_heavy (weight ∝ rank_pct²), sqrt (weight ∝ √rank_pct).
All batch weights normalized so sum ≤ max_total_exposure before per-position cap.

Grid: 3 rank modes × 4 pos (10/15/20/30) × 5 pct caps (5/7.5/10/15/20%) × 2 exposure (70/100%) = 120 configs per strategy.
Plus drawdown guard variants.

### Top results by MAR

| Config | Strategy | Mode | Pos | PctCap | Exp | CAGR | MaxDD | Sharpe | MAR | Class |
|--------|----------|------|-----|--------|-----|------|-------|--------|-----|-------|
| LINEAR_A3_pos15_pct10 | A3 | linear | 15 | 10% | 100% | 14.27% | -25.47% | 1.15 | **0.56** | PRODUCTION |
| TOP_HEAVY_A3_pos15_pct10 | A3 | top_heavy | 15 | 10% | 100% | 14.24% | -25.57% | 1.15 | **0.56** | PRODUCTION |
| SQRT_A3_pos15_pct10 | A3 | sqrt | 15 | 10% | 100% | 14.24% | -25.57% | 1.15 | **0.56** | PRODUCTION |
| LINEAR_A3_pos15_pct7 | A3 | linear | 15 | 7.5% | 100% | 14.18% | -25.46% | 1.15 | **0.56** | PRODUCTION |
| LINEAR_A3_pos20_pct10 | A3 | linear | 20 | 10% | 100% | 13.57% | -25.97% | 1.20 | 0.52 | PRODUCTION |

**Key finding:** The three rank modes (linear, top_heavy, sqrt) produce nearly identical results at the same pos count. The driver is `max_positions=15` (base_w=6.7%) not the rank mode. Prior session's CAGR=20.40% (linear) was entirely from implicit leverage (×1.4), not from the rank weighting logic.

### Drawdown Guard

| Config | Strategy | Mode | Guard | CAGR | MaxDD | Sharpe | MAR | n_dd_blocked |
|--------|----------|------|-------|------|-------|--------|-----|-------------|
| DDG_A3_equal_no_guard | A3 | equal | none | 13.61% | -26.51% | 1.18 | 0.51 | 0 |
| DDG_A3_linear_no_guard | A3 | linear | none | 13.57% | -25.98% | 1.20 | 0.52 | 0 |
| DDG_A3_equal_guard_firm | A3 | equal | firm | **4.90%** | **-20.22%** | **0.70** | **0.24** | 0 |
| DDG_A3_equal_guard_mild | A3 | equal | mild | 4.78% | -22.58% | 0.67 | 0.21 | 0 |
| DDG_A3_equal_guard_strict | A3 | equal | strict | 4.04% | -19.73% | 0.65 | 0.20 | 0 |
| DDG_S3_equal_no_guard | S3 | equal | none | 11.91% | -27.36% | 1.04 | 0.44 | 0 |
| DDG_S3_equal_guard_mild | S3 | equal | mild | 8.24% | -29.03% | 0.96 | 0.28 | 0 |

Guard levels:
- mild: 0.5× at -10%, 0.25× at -15%, 0.0× at -20%
- firm: 0.25× at -10%, 0.0× at -15%
- strict: 0.0× at -5%

**Critical finding:** DD guard reduces CAGR from 13.6% to 4.8% (A3, firm). The guard is dramatically overcorrecting. MAR drops from 0.51 to 0.24 — the guard *worsens* risk-adjusted returns because it blocks re-entry during the recovery phase, missing the subsequent rallies.

---

## Phase 1D — Risk-Per-Trade with Actual Stop Execution

### Setup
Position weight = `min(risk_pct / stop_dist, max_position_pct)`. Stop is now actually executed with T+5 sell-lock. Stop modes tested:

| Mode | Description |
|------|-------------|
| fixed_5/7/10/15pct | Fixed distance from entry price |
| atr_25/35 | 2.5×ATR or 3.5×ATR at entry |
| hybrid_7_25 | Fixed 7% initial, widens to 2.5×ATR after T+5 |
| hybrid_10_30 | Fixed 10% initial, widens to 3.0×ATR after T+5 |

Risk %: 0.25%, 0.50%, 1.00%, 1.50%, 2.00%, 2.50%, 3.00%.
Total: 7 × 10 = 70 configs per strategy, 140 total.

### Production candidates (MaxDD > -30%)
51 out of 140 configs. All best candidates are S3, not A3.

| Config | Strategy | Risk% | Stop | CAGR | MaxDD | Sharpe | MAR |
|--------|----------|-------|------|------|-------|--------|-----|
| RPT_S3_rp5_hybrid_10_30 | S3 | 0.50% | hybrid_10_30 | 8.69% | -21.51% | 0.88 | **0.40** |
| RPT_S3_rp5_hybrid_7_25 | S3 | 0.50% | hybrid_7_25 | 8.75% | -21.73% | 0.82 | **0.40** |
| RPT_S3_rp5_atr_35 | S3 | 0.50% | atr_35 | 7.64% | -19.19% | 0.79 | **0.40** |
| RPT_S3_rp2_hybrid_7_25 | S3 | 0.25% | hybrid_7_25 | 5.28% | -13.78% | 0.84 | 0.38 |
| RPT_S3_rp2_hybrid_10_30 | S3 | 0.25% | hybrid_10_30 | 4.32% | -11.34% | 0.87 | 0.38 |

Best MAR = 0.40 (vs baseline 0.44 for S3 equal-weight). RPT with real stops is **worse** than equal-weight by MAR.

---

## Phase 1E — A3+GK Convergence (corrected)

### Setup
GK (Gaussian-Kernel channel) signals computed per symbol. A3 trades tagged as `has_gk=True` if a GK buy signal occurred within N days of the A3 signal date. Three experiments per window (3/5/10 days):
- `A3+GK`: only trades where GK fired (filter)
- `A3_no_GK`: complement (GK did not fire)
- `size_125x`: all A3 trades, GK-confirmed trades get 1.25× size boost

### A3+GK results

| Config | Window | Subset | N_Trades | Coverage | Mean Net | CAGR | MaxDD | MAR | Class |
|--------|--------|--------|----------|----------|----------|------|-------|-----|-------|
| A3+GK w10 | 10d | GK fired | 3,755 | 29.1% | 7.75% | 12.85% | -23.85% | **0.54** | PROD |
| A3+GK w5 | 5d | GK fired | 2,302 | 17.8% | 6.85% | 12.13% | -24.88% | **0.49** | PROD |
| size_125x w3 | 3d | All (1.25× for GK) | 12,909 | 100% | 6.59% | 13.30% | -27.51% | **0.48** | PROD |
| A3_no_GK w3 | 3d | GK did NOT fire | 11,220 | 86.9% | 6.52% | 12.37% | -27.84% | **0.44** | PROD |
| A3+GK w3 | 3d | GK fired | 1,689 | 13.1% | 7.04% | 10.69% | -28.50% | 0.37 | PROD |

**Key finding:** A3+GK (10d window) selects 29.1% of A3 trades with higher mean_net (7.75% vs 6.59% baseline) AND lower MaxDD (-23.85% vs -26.51%). This is the only filter that simultaneously improves both CAGR quality and DD. The size-boost approach (125×) is inferior — it adds exposure to all trades, diluting the benefit.

### S3+GK results

| Config | Window | Subset | Coverage | Mean Net | CAGR | MaxDD | MAR | Class |
|--------|--------|--------|----------|----------|------|-------|-----|-------|
| S3_no_GK w3 | 3d | No GK | 84.2% | 6.18% | 10.18% | -25.64% | **0.40** | PROD |
| S3+GK w10 | 10d | GK fired | 34.7% | 7.63% | 10.99% | -31.28% | 0.35 | SHADOW |
| S3+GK w5 | 5d | GK fired | 21.5% | 7.38% | 8.83% | -26.41% | 0.33 | PROD |

S3+GK does NOT improve MAR vs baseline (S3 baseline MAR=0.44). GK is calibrated on a longer timeframe (100-bar ZL-EMA) that aligns better with A3's 100-bar slow EMA than S3's 55-bar slow EMA.

---

## Annual Decomposition (A3 baseline)

| Year | N_Trades | Mean Net | Hit Rate | TP Trail% | Mean Hold |
|------|----------|----------|----------|-----------|-----------|
| 2013 | 838 | +18.05% | 85.9% | 80.2% | 124 bars |
| 2020 | 1,337 | +22.43% | 93.9% | 89.7% | 111 bars |
| 2021 | 788 | +13.05% | 80.2% | 78.2% | 114 bars |
| 2025 | 1,322 | +13.19% | 78.9% | 74.1% | 118 bars |
| 2016 | 660 | +8.31% | 70.2% | 59.1% | 169 bars |
| 2017 | 848 | +8.28% | 69.6% | 64.6% | 144 bars |
| 2014 | 572 | +5.01% | 64.3% | 58.2% | 152 bars |
| 2023 | 1,234 | +4.63% | 65.1% | 61.1% | 155 bars |
| 2024 | 1,425 | +6.04% | 63.2% | 53.7% | 180 bars |
| **2018** | 865 | **-2.98%** | 52.4% | 47.2% | 181 bars |
| **2019** | 943 | **-1.57%** | 51.2% | 42.7% | 187 bars |
| **2022** | 705 | **-19.15%** | 36.2% | 29.1% | 200 bars |
| 2026 (partial) | 512 | -4.03% | 35.7% | 18.6% | 44 bars |

**Clear regime sensitivity:** Bad years (2018, 2019, 2022) have: hit_rate 36–52%, TP trail rate 29–47%, mean hold near max (181–200 bars). Good years (2013, 2020, 2021) have: hit_rate 80–94%, mean hold 111–124 bars. The strategy is essentially a trend-following strategy that breaks down in choppy/bear markets.

---

## Review Questions

### 1. Pullback selection bias — is this a feature or a bug?

No-pullback trades have mean_net=10.95% vs pullback_trades=5.26% for A3. The blended_benefit is only +0.75%. This means:

- Adding a pullback tranche to a no-pullback trade CANNOT make it as good as an original no-pullback trade
- The MAR improvement (0.51→0.58 at d=4%, w=30) comes from the **portfolio composition** changing (fewer high-quality no-pullback runs in the portfolio), not from better entry prices
- Is the MAR improvement real at all? Isn't this just reducing exposure to volatile signals while concentrating in slower-to-develop setups?
- Could the same MAR improvement be achieved by simply filtering to signals where a 4% pullback occurred (regardless of using it as a tranche trigger)?

### 2. Rank sizing — rank mode doesn't matter after normalization

After the leverage bug is fixed, linear/top_heavy/sqrt rank modes are nearly identical at the same `max_positions`. The real driver is pos=15 (base_w=6.67%) vs pos=20 (5%). Is there any theoretical argument why rank-weighting should add value over uniform sizing once the leverage artifact is removed? Or is this just a position-count grid in disguise?

The uncapped prior result (20.40% CAGR) was leveraged. Corrected result (14.27%) is only +0.66% over baseline (13.61%). Is that meaningful or within noise given the 14-year backtest?

### 3. DD Guard destroys value — is the design wrong?

A3 with mild guard (-10% = 0.5×, -15% = 0.25×, -20% = block): CAGR drops from 13.6% to 4.8%, MAR from 0.51 to 0.21.

The `n_dd_blocked=0` in all configs means the guard triggers but blocks `n_filled` (accepted trades are halved or quartered in size), not actual trades. The recovery effect is what's being missed.

- Is the guard calibrated too aggressively for a strategy with a -27% baseline MaxDD?
- A -10% portfolio DD triggers the first guard level. Given that portfolio DD regularly exceeds -10% in any non-trivial bear market, the guard is essentially always on during bad years.
- Would a guard that only activates at deeper levels (e.g., -15%, -20%, -25%) preserve more value while still providing protection?
- Should the guard be asymmetric — size reduction at DD, but faster recovery when equity recovers past a trigger?

### 4. RPT with real stops is WORSE than equal-weight — what changed?

Prior session (invalid): RPT CAGR=59.80%, MAR=0.82.
This session (real stops): Best RPT MAR=0.40 (S3) vs baseline S3 MAR=0.44.

RPT sizing formula: `weight = risk_pct / stop_dist`. With rp=0.5% and hybrid_10_30 stop (initial 10% fixed), weight = 0.5%/10% = 5% — same as equal-weight at pos=20. The position size is nearly identical to baseline but exits are now cut at the stop (forced loss realization vs the original trail/TP which sometimes recovered). 

- Is the failure of RPT explained entirely by the Vietnam market dynamic: EMA-cloud entries have 27% MAE on average, routinely breaching fixed-distance stops before recovering to TP?
- What's the mean MAE for A3/S3 trades? (Available in the pullback quality table: -15.4% and -16.4% respectively). A fixed 7% stop would be hit by virtually every losing trade AND many eventual winners.
- Is there a stop distance that's wide enough to not over-fire AND provides meaningful risk control for this strategy?

### 5. A3+GK filter — is 29% coverage operationally useful?

A3+GK (10d window): 3,755 trades selected from 12,909. In production: daily scan outputs 5-15 near-entry symbols for A3. With GK filter, this becomes ~1-4 symbols/day.

MAR improves 0.51→0.54 with simultaneously better MaxDD (-26.51% → -23.85%). This is the cleanest improvement in the batch — both return AND risk metrics improve.

- The improvement is +0.03 MAR over 14 years. Is that statistically significant given that A3 has ~850 trades/year and the GK-filtered subset is ~266 trades/year?
- GK is a trend-confirmation signal calibrated to the same timeframe as A3 (100-bar EMA). Does the GK filter add orthogonal information, or is it just selecting the same "strong trend" subset that A3 already overweights?
- The `size_125x` approach (full coverage, GK confirmed gets 1.25× weight) gives MAR=0.48, worse than the filter approach (0.54). Why does filtering beat size-boosting when coverage is the same denominator?

### 6. Year decomposition — strategy has fat tails in regime sensitivity

2022 A3: mean_net=-19.15%, hit_rate=36.2%. That single year contributes disproportionately to MaxDD.
2013 + 2020 A3: mean_net ≈ +18–22%, hit_rate 85–94%. These two years alone drive most of the CAGR.

- Given that ~3 out of 14 years drive most of the CAGR and 3 other years are deeply negative, is the baseline CAGR=13.61% a reliable expectation or a small-sample artifact dominated by 2013 and 2020?
- The VNINDEX regime gate (EMA20 > EMA50 and close > EMA50) would have flagged bear periods in 2018, 2019, 2022. Would gating ALL entries (not just sizing) on the regime have avoided the -19% mean_net year of 2022?
- Is the A3 strategy viable as a standalone strategy, or does it require explicit bear-regime defense?

---

## Files in this package

| File | Rows | Description |
|------|------|-------------|
| `PHASE1_REVIEW_PROMPT.md` | — | This document |
| `scalein_pullback_robustness.csv` | 66 | 5×5 depth/window grid + quality/split variants, A3+S3 |
| `pullback_vs_no_pullback_trade_quality.csv` | 6 | Selection bias diagnostic |
| `pullback_scalein_by_year.csv` | 30 | Annual breakdown for pullback experiments |
| `rank_sizing_with_caps.csv` | 224 | Corrected rank sizing grid, all modes |
| `rank_sizing_drawdown_guard.csv` | 16 | DD guard variants (A3+S3, equal+linear) |
| `risk_per_trade_feasibility.csv` | 140 | RPT with actual stop execution (70 A3 + 70 S3) |
| `convergence_A3GK_overlay.csv` | 9 | A3+GK filter/size experiments |
| `convergence_S3GK_overlay.csv` | 6 | S3+GK filter/size experiments |
| `convergence_diagnostics_A3S3.csv` | 36 | A3+S3 same-day diagnostic breakdown |
| `component_by_year.csv` | 45 | Year-by-year metrics for A3, S3, GK |
| `component_by_regime.csv` | 5 | Regime (VNINDEX gate) breakdown |
| `PHASE1_REVISED_TOP_FINDINGS.md` | — | Auto-generated summary |

---

## What was NOT done (future phases)

- Phase 1F: Entry timing / no-chase filters (signal entry only if within N days of cloud turn)
- Phase 1G: Conditional exits by entry quality (different trail multiplier for GK-confirmed vs not)
- Phase 1H: Sector-level exposure caps (sector_map.csv not yet built)
- Combining the best results: pullback (d=4%, w=30) + A3+GK filter + pos=15 tested **independently**, not combined
- Cost sensitivity analysis (0.2% / 0.4% / 0.6% scenarios)
- Out-of-sample validation of Phase 1 winners (walk-forward folds by method)

---

*End of PHASE1_REVIEW_PROMPT.md*
