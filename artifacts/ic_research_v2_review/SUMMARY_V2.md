# IC Research V2 — Regime-Aware Validation Summary
**Date:** 2026-05-13  
**Market:** Vietnam (HOSE/HNX)  
**Status:** CANDIDATE_RESEARCH — not yet deployable

---

## 1. Data Audit Results

### Root Cause (Confirmed)
The raw OHLCV panel stores `value = close_thousands × volume` (NOT `close_VND × volume`).
The correct formula for ADV50: `close × 1000 × volume`, applied per bar, then rolling-50-mean.

| Metric | Finding |
|--------|---------|
| Total rows | 1,260,734 |
| Tickers | 1,564 |
| Rows where ratio = value / (close_VND × vol) ≈ 0.001 | **614,152 (49%)** |
| ADV50 error factor after ×1000 correction | **median 1.00× — correct** |
| ADV50 in old sector_stock_prob.csv (STB) | ~~56,130B~~ → **correct: 597B** |

**Fix applied in all v2 scripts:** `adv50_vnd = df["close"] × 1000 × df["volume"]` directly, bypassing the `value` column.

---

## 2. Sector Taxonomy

Canonical `data/master/sector_map.csv` created with:
- Consistent labels: `BDS` (not RE), `Securities` (not Securi), `VIN_Group` mapped under `BDS`
- Multi-theme support: VHM tagged `BDS;VIN_Group`, GVR tagged `Rubber;Industrial_Land`
- 109 tickers covered across 12 primary sectors

---

## 3. Factor IC — Date-Level Cross-Sectional Analysis

**Method:** Spearman IC computed per snapshot month (N=126 dates, 2018–2026).  
Metrics: mean IC, IC std, ICIR = mean/std, % months IC > 0, t-stat.

### 3a. Raw IC by Horizon

| Indicator | 25d IC | 50d IC | 100d IC | 150d IC | 200d IC | 250d IC | Dominant pattern |
|-----------|--------|--------|---------|---------|---------|---------|-----------------|
| **r252** | −0.024 | −0.046 | **−0.083*** | **−0.111*** | **−0.132*** | **−0.143*** | Strong mean-reversion, all horizons |
| r120 | −0.007 | −0.013 | −0.026 | −0.034 | **−0.054** | **−0.072*** | Medium-term reversal |
| dist_hi52 | −0.008 | −0.003 | −0.015 | −0.032 | **−0.052** | **−0.062*** | Near-high → mean-reverts |
| ma_align | −0.005 | 0.000 | −0.004 | −0.019 | **−0.030** | **−0.039*** | Trend-following fails long-term |
| r60 | −0.016 | **−0.024** | −0.019 | −0.026 | −0.028 | **−0.038** | Reversal at 50–250d |
| stage2 | +0.004 | −0.005 | −0.011 | −0.019 | **−0.026** | **−0.034** | Weak positive short-term, fades |
| dist_days | −0.012 | −0.016 | **−0.021** | −0.021 | −0.018 | **−0.021** | Consistent selling-pressure penalty |
| obv_slope | +0.002 | +0.011 | +0.002 | +0.007 | +0.004 | +0.006 | Weak positive across all (unique!) |
| cmf20 | −0.022 | −0.015 | −0.011 | −0.007 | −0.010 | −0.005 | Noisy, regime-dependent |
| bb_width | −0.008 | −0.011 | **−0.024** | −0.018 | −0.011 | −0.017 | Mixed, regime-sensitive |
| r5/r20 | −0.012/−0.018 | −0.019/−0.012 | −0.023/−0.014 | −0.017/−0.013 | −0.014/−0.015 | −0.005/−0.007 | Short-term reversal |
| vol_ratio | −0.011 | −0.006 | −0.012 | −0.008 | −0.006 | −0.001 | Mostly flat/noise |
| RSI14 | −0.014 | −0.011 | −0.010 | −0.007 | −0.007 | +0.002 | Weak, unreliable |

(\* t-stat magnitude > 2.0)

### 3b. Critical Finding: ALL Factors Negative in This Dataset
**Every indicator has negative mean IC at most horizons.** This is a structural finding:

> **Interpretation:** The pool of 485 liquid tickers over 2018–2026 includes the 2022 deep bear (-50% VNINDEX). In a mean-reverting, crash-dominated market, EVERY technical "buy" signal underperformed. This is not necessarily true in bull regimes — see regime breakdown below.

### 3c. Sector-Neutral IC vs Raw IC

Sector-neutral IC (demeaning within sector before computing IC) tracks closely with raw IC — most signals are not explained by sector rotation alone. The ratio SN_IC / raw_IC is typically 0.75–1.0, meaning ~75-100% of raw IC signal survives sector neutralization.

---

## 4. Regime-Conditioned IC

**Regime definition:**
- **Expansion:** VNINDEX > MA50 > MA200
- **Accumulation:** VNINDEX > MA50, MA50 ≤ MA200
- **Warning:** VNINDEX < MA50, MA50 > MA200
- **Contraction:** VNINDEX < MA50 < MA200

### Regime IC (raw, horizon 200d — best differentiation)

| Indicator | Expansion (n=44m) | Accumulation (n=12m) | Warning (n=20m) | Contraction (n=16m) |
|-----------|------------------|---------------------|----------------|---------------------|
| r252 | −0.076 | **−0.205** | −0.097 | **−0.228** |
| r120 | −0.038 | −0.040 | −0.034 | −0.107 |
| bb_width | −0.055 | **+0.046** | −0.063 | **+0.074** |
| cmf20 | +0.029 | +0.004 | −0.015 | −0.078 |
| vol_ratio | −0.033 | **+0.047** | +0.006 | −0.012 |
| stage2 | −0.003 | −0.037 | −0.011 | −0.071 |

**Key insight:**
- `r252` mean-reversion is **strongest in Contraction** (IC = −0.23) and **Accumulation** (−0.21): laggards recover hardest after bear market
- `bb_width` and `vol_ratio` flip to **positive** in Accumulation — expanding volume + volatility in recovery phase signals breakout
- `cmf20` is only positive during **Expansion** regime

---

## 5. Walk-Forward OOS Validation

**Method:** Train factor model on past data only (sign + top-5 selection). Score test-month stocks. Record OOS IC.

### 5a. OOS IC Summary

| Window | Horizon | N months | OOS IC mean | ICIR | t-stat | % pos |
|--------|---------|----------|-------------|------|--------|-------|
| Expanding | 25d | 92 | −0.048 | −0.26 | −2.5 | 45% |
| Expanding | 50d | 90 | −0.054 | −0.32 | −3.1 | 38% |
| Expanding | 100d | 83 | −0.018 | −0.11 | −1.0 | 52% |
| Expanding | 150d | 81 | −0.003 | −0.02 | −0.1 | 53% |
| **Expanding** | **200d** | **78** | **+0.037** | **+0.25** | **+2.2** | **60%** |
| **Expanding** | **250d** | **76** | **+0.049** | **+0.38** | **+3.3** | **66%** |
| Rolling-60 | 250d | 55 | +0.053 | +0.36 | +2.7 | 66% |
| Rolling-60 | 250d | 38 | **+0.064** | **+0.53** | **+3.3** | **68%** |

**Critical finding:** The only OOS IC that is positive, significant, and consistent is at **200–250d** horizon. At 25–100d, OOS IC is negative — the composite short-term signal actively hurts performance.

### 5b. Portfolio Net Returns (25d horizon, expanding, top-10)

| Cost level | Mean return | Median | Hit% |
|-----------|------------|--------|------|
| top10 −30bp | +1.04% | −0.46% | 46% |
| top10 −50bp | +0.84% | −0.66% | 45% |
| top10 −80bp | +0.54% | −0.96% | 43% |
| Universe mean | +2.04% | +2.06% | 58% |

**The top-10 portfolio underperforms the universe mean by ~1% per month.** Short-term factors fail OOS.

### 5c. OOS IC by Regime (Expanding Window)

| Regime | OOS IC 50d | OOS IC 100d | OOS IC 200d |
|--------|-----------|------------|------------|
| Expansion (n=44m) | −0.060 | −0.017 | **−0.025** |
| Accumulation (n=12m) | −0.071 | −0.082 | **+0.072** |
| Warning (n=20m) | −0.028 | −0.001 | **+0.050** |
| Contraction (n=16m) | −0.053 | +0.010 | **+0.124** |

**Finding:** OOS IC at 200d is positive in ALL non-Expansion regimes. In Contraction (bear market), the composite correctly identifies laggards that recover (+0.124 IC). This is the mean-reversion signal working OOS.

---

## 6. Candidate Factor Families

All marked **CANDIDATE_RESEARCH** — no deployment until criteria met (Section 7).

### A. Tactical 25–50d Breakout
**Factors:** bb_width expansion + r120 + stage2 + vol_ratio + MA reclaim  
**OOS IC:** **FAILS** — negative OOS IC at 25d (−0.048) and 50d (−0.054)  
**Regime:** Only works weakly in Contraction at 50d  
**Status:** ❌ DISCARDED — short-term factor does not survive OOS validation

### B. Medium Trend 50–100d
**Factors:** r60, r120, stage2, obv_slope, cmf20, sector RS  
**OOS IC:** Marginal at 100d (−0.018, t = −1.0, not significant)  
**Regime:** Works marginally in Expansion (IC = −0.017 at 100d), but inconsistent  
**Status:** ⚠️ RESEARCH-ONLY — no significant OOS IC

### C. Rotation Reversal 150–250d (Mean-Reversion)
**Factors:** negative r252, improving cmf20, vol_ratio, stage2  
**OOS IC:** **+0.037 to +0.064** (t = 2.2–3.3) at 200–250d  
**Regime:** Best in Contraction (+0.124) and Accumulation (+0.072) at 200d  
**Status:** ⚠️ CANDIDATE — passes IC threshold, does NOT yet pass full go/no-go (see Section 7)

---

## 7. Go / No-Go Decision

### Criteria (from governance rules)

| Criterion | Threshold | Strategy C (250d) | Pass? |
|-----------|-----------|------------------|-------|
| OOS ICIR (expanding) | ≥ 0.30 | +0.38 | ✅ |
| OOS IC t-stat | ≥ 1.5 | +3.3 | ✅ |
| % positive IC months | ≥ 55% | 66% | ✅ |
| Works in Expansion AND Accumulation | IC > 0 in both | Accumulation +0.072 ✅, Expansion −0.025 ❌ | ❌ |
| Sector-neutral IC ≥ 50% of raw IC | SN_IC / IC > 0.5 | ~0.8 | ✅ |
| Net of 50bp cost > 0% (portfolio) | > 0% mean | Not tested at 250d | ⚠️ |

**Overall: NO-GO for deployment today.**

The 250d reversal strategy passes 4 of 6 criteria but **fails the Expansion regime test** (IC negative during bull markets) and lacks portfolio net-of-cost validation at 250d horizon.

---

## 8. Factor Disposition

| Factor | IC Quality | OOS Result | Regime Profile | Verdict |
|--------|-----------|-----------|---------------|---------|
| r252 (inverted) | Strong | Significant | Works in bear/recovery, fails bull | **CANDIDATE** at 200–250d |
| r120 (inverted) | Moderate | Significant at 250d | Mixed | **RESEARCH-ONLY** |
| bb_width | Weak/mixed | Not significant | Regime-sensitive | **DISCARDED standalone** |
| stage2 | Weak | Negative OOS | Fails at 150d+ | **DISCARDED** |
| cmf20 | Weak | Not significant | Expansion only | **RESEARCH-ONLY** |
| obv_slope | Uniquely positive IC | t < 1 | Consistent small signal | **MONITOR** |
| vol_ratio | Regime-dependent | Pos. in Accumulation | Useful as regime filter | **RESEARCH-ONLY** |
| dist_days | Consistent negative | Consistent | Bear market amplifier | **RESEARCH-ONLY** |
| RSI14, r20, r5 | Weak | Negative OOS | Mean-reversion | **DISCARDED** |
| dist_hi52 | Moderate reversal | Significant 250d | Bull→recover | **CANDIDATE** at 250d |

---

## 9. Next Steps for Deployment

1. **Regime gate:** Only activate C (reversal) during non-Expansion regimes. Shut off in Expansion.
2. **Portfolio simulation at 250d:** Build overlapping monthly-entry portfolio, measure net-of-cost returns over full OOS period.
3. **Calibration:** Fit a logistic or Platt-scaling model to convert composite score → win-probability. Requires labeled data (win = fwd250 > +5%).
4. **Capacity check:** 250d holding means high turnover if rebalanced monthly. Consider quarterly rebalancing to reduce tx cost impact.
5. **Regime detection lag:** MA200 has 200-day lag. Test faster regime proxies (MA50 slope, VIX equivalent).

---

## 10. File Index

```
New v2 scripts (do not overwrite legacy):
  scripts/research/audit_ohlcv_units.py          — data integrity audit
  scripts/research/indicator_ic_by_date.py        — cross-sectional IC engine
  scripts/research/indicator_walkforward.py       — OOS walk-forward validation
  scripts/research/sector_stock_prob.py           — updated: renamed score, fixed ADV50

New data files:
  data/master/sector_map.csv                      — canonical sector taxonomy (109 tickers)
  data/research/unit_scaling_audit.csv            — per-symbol ADV50 error audit
  data/research/bad_ohlcv_rows.csv                — 614,152 rows with value unit issue
  data/research/data_quality_summary.md           — audit findings
  data/research/ic_by_date.csv                    — 9,792 rows: per-date IC
  data/research/ic_summary_by_factor_horizon.csv  — 102 rows: raw/excess/SN IC summary
  data/research/ic_by_regime.csv                  — 408 rows: IC by regime
  data/research/walkforward_ic.csv                — 1,302 rows: OOS IC per test month
  data/research/walkforward_portfolio_returns.csv — 1,146 rows: portfolio simulations
  data/research/walkforward_ic_summary.csv        — 18 rows: summary statistics
  data/research/walkforward_summary.md            — narrative walkforward findings
  data/research/sector_stock_prob_v2.csv          — updated scores (rotation_priority_score)

Legacy (do not delete — comparative baseline):
  data/research/indicator_backtest_single_factor.csv
  data/research/indicator_backtest_multifactor.csv
  data/research/indicator_snapshots.parquet
  data/research/sector_stock_prob.csv
```
