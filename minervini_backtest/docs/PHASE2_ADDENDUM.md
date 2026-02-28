# Phase 2 FA Cohort — Addendum (Facts-Only)

## Survivorship check (watchlist universe)

| Metric | Value |
|--------|--------|
| total_symbols | 85 |
| symbols_present_pre2017 (first FA row ≤ 2016-12-31) | 84 |
| symbols_first_seen_2017_2018 | 1 |
| symbols_first_seen_post2019 | 0 |

**Caveat:** Universe is watchlist_80 as of 2024; survivorship bias likely present. Results represent upper bound.

## Decision metrics (FA_only vs Hybrid, VNINDEX, 8/10/13w)

| strategy | horizon | median_yearly_alpha | sharpe | trade_count |
|----------|---------|---------------------|--------|-------------|
| FA_only | 8 | 0.0355 | 0.399 | 175 |
| FA_only | 10 | 0.0255 | 0.385 | 175 |
| FA_only | 13 | 0.0602 | 0.410 | 175 |
| Hybrid | 8 | 0.0635 | 0.432 | 144 |
| Hybrid | 10 | 0.0410 | 0.392 | 144 |
| Hybrid | 13 | 0.0720 | 0.428 | 144 |

**Conclusion:** Hybrid improves median alpha and Sharpe vs FA-only with fewer trades; proceed with FA-first architecture.

---

## Phase 2 locked (freeze)

- **Phase 2 v1 locked:** timing = **breakout_20d**, **signal_window = 30** trading days. Default for all Phase 2 comparisons.
- **Phase 2 v1.1 candidate:** timing = **ma**, variant = **ma5_gt_ma10_gt_ma20**, window = 30. Candidate replacement for breakout; no scope creep.
- **Why window30:** window15 reduces trades (~33 fewer) but 10w alpha drops (delta -0.0166); window30 preserves selection+timing edge. window15 remains available as a capacity knob (lower turnover) but is not the default.
- **Survivorship caveat:** Universe is watchlist_80 as of 2024; survivorship bias likely present. Results represent upper bound.
- **Output paths:** Baseline (FA_only + Hybrid) writes to `window{N}/decision_metrics.csv`. Hybrid-only runs write to `window{N}/hybrid_{variant}/decision_metrics.csv` so the baseline is never overwritten.

---

## Phase 2 – Final Timing Decision (E1 head-to-head)

- **v1 locked:** Hybrid **breakout_20d** + window 30 (primary; keep as benchmark).
- **v1.1 co-locked:** Hybrid **ma5_gt_ma10_gt_ma20** + window 30 (alternative; promoted by rule).
- **Rule used:** MA promoted if it wins ≥2/3 horizons on median_yearly_alpha and Sharpe not worse by >0.02. **Result:** MA won 10w and 13w alpha; Sharpe higher at all three horizons → pass.
- **Interpretation:** Breakout better at 8w; MA stacked better at 10–13w. FA gate is the main engine; timing is refinement. Two valid timing engines; no need to replace breakout.

---

## Vietnam Growth Leadership Model (architecture)

- **Layer 1 – FA growth acceleration:** Cohort selection (Mark-tight + earnings accel). Primary edge.
- **Layer 2 – Trend confirmation:** breakout_20d (primary) or ma5_gt_ma10_gt_ma20 (co-locked). Incremental; only inside FA cohort.
- **Layer 3 – (future)** Regime / risk cap.
- **Insight:** This is not “Minervini for VN.” It is a different structure: FA-first, timing-second. MA stacked / breakout on full universe without FA gate would likely lose edge.

**Next research directions (when continuing in Cursor):** 16–20w horizons (sweet spot?), blend breakout ∪ MA stacked, regime interaction.

---

## Phase 2 – E6 OR Performance Test (Final)

**Setup (no change to gate or signals):**

- Universe: FA Mark-tight + earnings acceleration
- Window: 30
- Bench: VNINDEX
- Horizons: 8 / 10 / 13 / 16 / 20
- Engines:
  - Hybrid breakout_20d
  - Hybrid ma5_gt_ma10_gt_ma20
- OR definition: union of trades (tolerance_days = 3)

**Decision rule (pre-defined):**

- OR must improve median_yearly_alpha in ≥3 horizons
- Sharpe not worse than best(single) by > 0.02 in any horizon
- Trade count increase ≤ 25%

**E6 Results (facts)**

Median yearly alpha (OR vs best single):

| Horizon | Breakout | MA | OR | OR vs Best |
|---------|----------|-----|-----|------------|
| 8w | 0.0635 | 0.0511 | 0.0457 | Lower |
| 10w | 0.0410 | 0.0462 | 0.0140 | Lower |
| 13w | 0.0720 | 0.0861 | 0.0187 | Lower |
| 16w | 0.0601 | 0.0660 | 0.0494 | Lower |
| 20w | 0.0888 | 0.0846 | 0.0756 | Lower |

- OR did not improve alpha in any horizon.
- Sharpe deteriorated > 0.02 in 4/5 horizons.
- Trade count increased 34–53% vs best single (rule max = 25%).

**Verdict**

**NO_OR**

Reason:

- Alpha dilution
- Sharpe degradation
- Turnover expansion beyond predefined threshold

---

## Phase 2 Architecture (Finalized)

- **Layer 1:** FA growth acceleration (edge source)
- **Layer 2:** Two co-locked timing engines inside FA cohort
  - breakout_20d (v1 locked)
  - ma5_gt_ma10_gt_ma20 (v1.1 co-locked)
- **No OR union.**

---

## Optional Next Step (Clean Extension)

**E7 – Allocation Split (Portfolio Level)**

Instead of OR union:

- Run Breakout portfolio (A)
- Run MA portfolio (B)
- Combine equity curves with fixed weight (e.g., 50/50 or 60/40)

Evaluate:

- Combined Sharpe
- Max drawdown
- Stability vs single engines

This preserves signal purity while testing diversification at portfolio level.
