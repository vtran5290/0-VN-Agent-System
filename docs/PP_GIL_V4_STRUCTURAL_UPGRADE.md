# PP_GIL_V4.2 — Structural Upgrade (Book-Aligned)

Design from Gil/Kacher books (Trade Like an O'Neil Disciple 2010; In The Trading Cockpit 2012) vs current PP_GIL_V4. No parameter tuning; structural gates only.

**Interpretation vs book:** Book 2 discusses close strength and leadership but does not prescribe numeric rules (e.g. “30% of range” or “85% of 52-week high”). Such numbers are **reasonable adaptations** for backtest, not direct quotes. Leadership/RS in the book is about character and relative strength, not a single hard threshold.

---

## I. What Is Consistent (Keep)

- **Volume signature:** vol > max(down_vol last 10 bars) — core PP definition.
- **MA support:** MA10/20/50 touch + slope gate.
- **UglyBar exit override:** change of character; keep as-is.
- **Market/Stock distribution days:** CANSLIM-style risk management; keep.

---

## II. Structural Gaps (Books vs Current Code)

| Gap | Current | Books | Consequence in VN |
|-----|---------|-------|--------------------|
| **Up day** | close >= close[-1] | Effort + demand thrust; close near high | Doji/flat days admitted → noise, thin edge |
| **Tightness** | None | PP from tight base / consolidation; VDU | Many “formula-valid” pivots from loose action → bull traps |
| **MA50** | MA10/20 touch allowed below MA50 | Leaders typically above MA50; MA50 = structural line | Low-quality bounces below MA50 → fee erosion |

Exits (SELL_V4, MARKET_DD, STOCK_DD) are **not** the main issue; evidence shows they preserve tail. Problem is **entry quality**.

**Book 2 points not in table (add to design context):**  
- **CPP (Continuation Pocket Pivot):** PP in an **already-established uptrend**, not initial breakout. This distinction matters for VN — continuation setups vs first breakout have different success rates.  
- **Avoiding extended stocks:** Book 2 stresses not buying when the stock is too extended from its base. We do not yet encode “extended” as a gate; it is a candidate for a later, pre-registered rule (e.g. distance from base or from MA50).  
- **Leadership / RS:** Book 2 emphasizes relative strength and leadership character, not a numeric cutoff. Any future “e.g. close ≥ 85% of 52-week high” would be an **adaptation** for testing, not a direct book spec.

---

## III. Pre-Registered Structural Gates (No Grid Search)

**1. Regime gate (already implemented)**  
- MA200: entry only when VN30 close > MA200.  
- Liquidity: entry only when VN30 30d vol > 126d vol.  
- Result: MA200 failed hold-out; liquidity passed (PF hold-out > 0.924).

**2. Above MA50 (structural)**  
- Rule: `close > MA50` (stock-level) on entry bar.  
- One binary gate; no threshold tuning.

**3. Demand thrust (quality)**  
- Strengthen “up day”:  
  - `close > close[-1]` (strictly up), and  
  - `close >= high - 0.3 * (high - low)` (close in **upper 30% of daily range** — *our interpretation*; Book 2 mentions close strength but does not prescribe 30%).  
- Removes doji/flat “fake PP”; single definition, locked.

**4. Tightness (context)**  
- One option, locked:  
  - **Option A (VDU):** In the **last 5 bars before** the pivot bar, at least **2 bars** have `volume < MA20(volume)`.  
- No range-based variant in this spec (Option B kept for doc only; implement only A).

---

## IV. Clean Experiment Order

Run **one gate at a time**; full sample + hold-out 2023–2026 each time. Baseline hold-out PF = 0.874. **Regime that passed hold-out is Liquidity** (PF 0.970 > 0.924), not MA200 (MA200 hold-out PF 0.751). So the sequence continues from **Liquidity**, not from MA200.

| Step | Experiment | Status / decision rule |
|------|------------|-------------------------|
| 1 | Regime: MA200 | Done. Hold-out PF 0.751 < 0.874 → MA200 harmful; do not use. |
| 2 | Regime: Liquidity | Done. Hold-out PF 0.970 > 0.924 → **liquidity has edge; lock as regime gate.** |
| 3 | **Liquidity + Above MA50** | **Next step.** PF_holdout > 0.924 → keep MA50; else drop. |
| 4 | + Demand thrust | PF_holdout vs step 3; meaningful gain → keep. |
| 5 | + Tightness (VDU) | PF_holdout vs step 4; meaningful gain → keep. |

Do **not** restart from MA200 (e.g. “MA200 + MA50”); the regime that earned lock-in is Liquidity. If after step 5 PF_holdout still ~1.0 or below baseline → conclude mechanical PP not viable net of fees in VN post-2022.

---

## V. Implementation (Flags Only)

- **--above-ma50:** entry only if stock `close > MA50`.  
- **--demand-thrust:** entry only if `close > close[-1]` and `close >= high - 0.3*(high-low)`.  
- **--tightness:** entry only if at least 2 of last 5 bars have `volume < MA20(volume)`.  

Baseline (no flags) unchanged. Exits unchanged. No new numeric parameters; structural rules only.

---

## VI. If X Then Y

- **Liquidity + MA50 improves hold-out** → lock both; add Demand thrust next.  
- **Liquidity + MA50 no improvement** → try Demand thrust alone on baseline or liquidity.  
- **All gates applied, PF_holdout still ~1.0** → stop; conclude PP mechanical edge not viable in VN under current structure.
