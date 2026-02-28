# Minervini Mechanical System – Postmortem

## 1. Objective

Build and test a fully mechanical implementation of Mark Minervini-style breakout and pullback systems on Vietnam equities using:

- TT filter (structural trend)
- VCP proxy / contraction stack
- Breakout triggers (HH, tight range)
- Retest logic
- U&R (Undercut & Rally)
- Realistic cost model (fee=30 bps round-trip)
- T+2.5 constraint (min_hold_bars=3)
- Walk-forward validation (Train 2020–2022, Validate 2023, Holdout 2024)

**Goal:** Identify a deployable mechanical system with:

- Expectancy_r > 0.10
- PF ≥ 1.05–1.10 under realism
- Stable performance across splits
- Sufficient trade density

## 2. Hypotheses Tested

- **H1 — Breakout continuation (G0 core)**  
  TT Lite + High breakout (HH 40) + volume filter; No retest (M0R).

- **H2 — Breakout + Retest (SEPA-style)**  
  TT + VCP + breakout + retest 1–7 bars (M4R).

- **H3 — Pullback re-entry**  
  TT + tight pullback + mini-pivot break (P1A / P1A_R).

- **H4 — Undercut & Rally (U&R)**  
  TT + pivot low undercut + close back above (P2A / P2B).

Each tested under: funnel density gate, walk-forward realism, regime overlay (M11) where applicable.

## 3. What Worked (In-Sample Only)

Across multiple variants, **train period (2020–2022)** showed strong results:

- Expectancy_r often 0.5–1.4
- PF frequently > 2–3
- Clear edge during high momentum years

This confirms: the logic is internally coherent, the engine implementation is correct, and the system can exploit strong trend regimes.

## 4. What Failed (Out-of-Sample)

Across all classes (Breakout, Retest, Pullback, U&R): **split instability**.

| Split        | Result              |
|-------------|---------------------|
| Train       | Strongly positive   |
| Validate 2023 | Negative          |
| Holdout 2024  | Negative or unstable |

**Observations:**

- Density was sufficient (e.g., M0R: 100 full-sample entries).
- Pre-split warmup implemented correctly.
- Realism override (fee=30, min_hold=3) applied correctly.
- **Regime gate (M11) did not fix instability.**
- U&R showed extreme train performance but failed across splits.

**Conclusion:** The systems exhibit regime dependency not captured by the current regime model, and/or rely on structural properties that did not persist in 2023–2024.

## 5. Root Cause Analysis

**1) Vietnam microstructure mismatch**

- Minervini-style systems assume: persistent breakout follow-through, strong post-break expansion, institutional trend continuation.
- Vietnam (2023–2024): lower persistence, faster mean reversion, more shakeout without continuation; T+2.5 friction increases decay cost.

**2) Cost + Hold Constraint Interaction**

- Breakout continuation often decays after 1–3 bars.
- With 30 bps cost and min_hold=3 bars, edge gets compressed significantly.

**3) Regime Model Insufficient**

- Regime gate tested: VN30 vol 30d > 126d OR close > MA200.
- This was too coarse to isolate momentum-favorable sub-periods.

## 6. Final Conclusion

**No** Minervini-style mechanical system tested:

- Passed split stability
- Maintained positive expectancy_r in both 2023 and 2024
- Survived realism constraints consistently

Therefore: **Minervini mechanical breakout/pullback/U&R systems are NOT deployable in current tested form.**

They may be: regime-conditional; suitable as discretionary overlays; or informational (quality scanner), not execution engines.

## Addendum: 2012–2026 Extension, Liquidity Gate, and MH Overlay

### Scope

Extend evaluation of Minervini mechanical variants (M0R, M4R, P2A, P2B) to 2012–2026 under:

- Fee = 30 bps, min_hold_bars = 3
- Liquidity gate via ADTV (VNĐ) with year-adjusted thresholds
- Walk-forward realism using existing 2020–2022 (train), 2023 (validate), 2024 (holdout) splits

### Liquidity Gate

- Entries over 2012–2026 (liquidity gate ON):

| Version | Entries |
|---------|---------|
| M0R     | 122     |
| M4R     | 19      |
| P2A     | 26      |
| P2B     | 23      |

- Liquidity gate did **not** materially reduce signal density in 2020–2024 and did **not** change the split profile.

**Conclusion:** liquidity realism does not explain the instability; mismatch is not driven by micro-cap / illiquid fills.

### Walk-Forward (Liquidity Gate ON)

Key splits for M0R:

| Split    | Trades | PF    | Expectancy_r |
|----------|--------|-------|--------------|
| Train    | 49–51  | ~3.5  | ~+1.16       |
| 2023 Val | 17     | 0.52  | -0.37        |
| 2024 Hol | 23     | 2.74  | +0.64        |

- M0R shows strong edge in expansion regimes (2020–22, 2024) and fails in 2023 (persistence collapse).
- P2A/P2B keep the pattern: strong train, negative validate/holdout → structurally unstable.
- M4R remains low-density and unstable.

**Conclusion:** M0R has a **regime-sensitive edge**; P2-class and M4R remain **non-deployable**.

### Market Health Overlay (NH-heavy v1)

- Overlay rule (universe B breadth + NH20%):
  - **OFF** if nh20_pct < 0.06 OR breadth_ma50 < 0.45
  - **ON**  if nh20_pct > 0.09 AND breadth_ma50 > 0.55
- Walk-forward comparison:

| Version | Split    | Expectancy_r |
|---------|----------|--------------|
| M0R     | 2023 Val | -0.3709      |
| M0R_MH  | 2023 Val | -0.3025      |
| M0R     | 2024 Hol | +0.6449      |
| M0R_MH  | 2024 Hol | +0.3780      |

- Overlay slightly improves 2023 (still strongly negative) and materially reduces 2024 edge.

**Conclusion:** NH-heavy overlay v1 **fails** the rescue criterion (does not fix 2023 without harming 2024). No threshold optimisation will be pursued.

Overall, 2012–2026 extension, liquidity realism, and MH overlay do **not** change the core conclusion: Minervini mechanical systems remain **research-only** and **not deployable** under the current gates.

## 7. What Would Revive This Track?

Minervini mechanical research should only be resumed if:

- A **persistence metric** is defined and shows the environment has changed (e.g. % breakouts still above entry after 10 bars; or avg forward 10-day return of NH20 stocks). Reopen only when this metric clearly separates “high persistence” vs “low persistence” regimes — not based on breadth/level filters alone.
- A refined regime model is developed (e.g. momentum persistence filter, breadth expansion filter).
- A materially different entry class is tested (e.g. shorter-horizon re-entry with tight stop).
- Cost environment changes significantly (unlikely).
- Market structure shifts toward strong trend persistence.

Otherwise, this track remains closed.

## 8. Current Positioning

- **Mechanical deployment focus** → PP_Gil C2 m0 (stress-tested, deployable).
- Mechanical systems must satisfy: split stability, realism robustness, stress survival.
- **Minervini engine** remains as: research infrastructure, discretionary scanning tool, experimental lab.

## 9. Decision Record

- **Status:** CLOSED (Mechanical Deploy Candidate)
- **Reopen condition (quantified):** Only when a **persistence metric** (e.g. % breakouts still above entry after 10 bars) shows clearly that the environment has shifted to a high-persistence regime. Do not reopen on breadth/level filters or “feel” alone.

This document prevents future re-optimization loops on the same hypothesis without structural change.

---

**Signals to monitor next week**

- Live PF of deployed PP system
- Regime health indicators
- Momentum persistence metrics (for future Minervini revival research)

**If X → Do Y**

- If PP edge degrades materially → research new class, not revert to Minervini mechanical.
- If future regime shows persistent multi-week breakout follow-through → revisit breakout class with new regime gate.

*End of Postmortem.*
