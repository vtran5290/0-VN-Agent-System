# Pre-Registration — Cortex Book 3: S4 — Darvas Box Breakout Filter
# Lane A (backtestable) | STATUS: DEFERRED pending VN-THIN empirical pre-check

**Date filed:** 2026-07-05
**Status:** DEFERRED — degeneracy pre-check complete (EXPRESSIBLE structurally); VN-THIN empirical pre-check required before gate parameters may be locked
**Belief:** S4 — "A stock is only actionable when it breaks into a confirmed new higher price range (box) on rising price action — wait for the confirmed break, don't anticipate it"
**Source:** Darvas, How I Made $2,000,000 in the Stock Market, Ch.4 (Box Theory)
**Cortex brain:** D:\V\.claude\brains\vn-trading-advisor\knowledge.md — belief S4
**Session context:** 2026-07-05 propagation session log — Decision 003

---

## Why this test is "Book 3" priority

Per Fable council (2026-07-04) and Phase 1–4 audit: S4 is in the Book 3 slot, after S1/S2 reach verdicts. This pre-registration documents the formal degeneracy pre-check (Opus artifact verdict, 2026-07-05) and locks the parameter design for when the VN-THIN pre-check passes.

---

## Degeneracy Pre-Check — Formal (Opus verdict, 2026-07-05)

### (a) Expressibility
**VERDICT: EXPRESSIBLE (structurally — no structural binding constraint found)**

The IV: whether an A3_RS signal day satisfies a "box breakout" criterion — specifically, that price has consolidated in a tight range for N prior trading days AND the current signal-day close exceeds the prior N-day maximum high.

Constraint check:
- **±7% daily price band:** Affects individual bar SIZE but NOT the multi-day box definition. A box top within 7% of current price is reachable in a single bar; a box top >7% away requires multi-bar accumulation. The filter (box breakout vs no breakout) STILL VARIES across stocks/periods — the band compresses bar size, not the IV.
- **Slot cap (1/20):** SIZING constraint. Does not prevent the box-breakout IV from varying.
- **ADV cap:** SIZING constraint. Does not prevent the box-breakout IV from varying.
- **C1 bear suppression:** Applies equally to baseline and candidate; the relative gate G1a removes this as a confound.

**No structural constraint prevents the IV from varying.** The filter will reduce signal count (expected signal-quality behavior), not produce a degenerate sweep.

### (b) Claim fidelity
**VERDICT: ACCEPTABLE — with documented caveats**

Darvas's exact claim: wait for price to consolidate in a recognizable trading range (box), then enter ONLY when price BREAKS ABOVE the top of that box on strong action. Do not anticipate the break.

Proposed metric: binary filter on A3_RS signal days requiring (1) tight range over prior N days [max_high / min_low ≤ tightness threshold] AND (2) signal-day close > prior N-day max_high [breakout condition].

**Caveat 1 — Mechanical proxy:** Darvas used visual/judgment-based identification of boxes. A fixed-N, fixed-ratio mechanical proxy is the only testable form and captures the directional core of the claim.

**Caveat 2 — VN limit-bound false-box risk:** VN stocks with ±7% daily limits may appear "tight" (range compressed by the limit mechanism) without genuine accumulation. A stuck/illiquid stock may satisfy the tightness ratio without forming a genuine Darvas box.
→ **Mitigation:** Pre-register a TURNOVER FLOOR on the box-formation window — require non-trivial average daily value during the N-day box period (e.g., ≥ 2B VND/day). This discriminates genuine accumulation from limit-lock. Report results with and without the turnover guard for M2 mechanism analysis.

**Caveat 3 — S1 overlap:** A box-breaking stock is likely near its 52-week high (S1 proximity condition). High M2 overlap between S4 and S1 is expected — this is a descriptor for the mechanism check, not a fidelity failure for the standalone test.

### (c) VN-transfer check
1. Short-selling/borrow/derivatives required? → NO. Long-only entry filter.
2. Survives HOSE mechanics? → YES with the noted bar-compression caveat. Box definition is multi-day; single-bar ±7% limit affects signal timing quality, not the filter's discriminating power.
3. Testable against VN Agent data? → YES. Rolling high-low range + close-above-max computable from OHLCV.
4. Full ADV-qualified universe? → YES.

**VN-TRANSFER VERDICT: PASSES.**

---

## VN-THIN Pre-Check — REQUIRED BEFORE LOCKING GATES

**Why required:** The strict conjunction of three conditions (A3_RS signal day AND tight-range formation AND close-above-box-top) on an already-filtered momentum base rate may produce N_OOS < 30. VN-THIN is an empirical risk (thin distribution), not a structural binding constraint. Cannot rule it out without measurement.

**Pre-check procedure** (same pattern as S2's VN-THIN check, 2026-07-05):
- Data: `data/fireant_ssot/ta_ohlcv_panel.parquet` (OOS 2020–2026, ADV-qualified)
- For each candidate (N=20, N=40), count:
  - A3_RS signal days where the stock has formed a box (max_high/min_low ≤ tightness tercile cutpoint over the prior N days)
  - AND signal-day close > prior N-day max_high
  - Report as: count, % of A3_RS base signal days, estimated OOS filtered trades

**VN-THIN threshold:** N_OOS full primary OOS ≥ 30 (per protocol). If any N candidate clears 30 → proceed to gate locking for that candidate. If all < 15 → VN-THIN, defer. If 15–30 → borderline; flag and consult before committing.

**Report also:** the S1 overlap fraction (% of S4-firing days that also satisfy S1 proximity ≥ 0.80) — descriptive, not a gate.

**Gate thresholds will be locked in a GATES ADDENDUM after the pre-check passes.** Do not proceed to harness execution without a written gates addendum.

---

## Parameter Design (pending VN-THIN pre-check confirmation)

**k = 2** (below the general ≤5 cap — Opus verdict: triple-conjunction on thin base rate cannot support wide parameter search without overfitting)

**Box-window lengths (N):**
- N = 20 trading days (~4 calendar weeks on HOSE)
- N = 40 trading days (~8 calendar weeks)
- Rationale: short enough to match Darvas's swing-trade horizon; long enough to exclude noise ranges from the ±7% daily limit. N < 15 → too noisy (limit-lock risk). N > 60 → N_OOS degrades further.

**Tightness threshold:**
- Use a RELATIVE, distribution-based definition: define tightness as (N-day max_high / N-day min_low) and require it to fall in the **tightest tercile** of that ratio's in-sample distribution (across the ADV-qualified universe).
- Rationale: a fixed absolute ratio (e.g., max/min ≤ 1.10) would import US-calibrated parameters that VN's ±7% mechanism renders meaningless. A distribution-relative threshold auto-adapts to VN's volatility regime.
- The tercile cutpoint is pre-committed from the in-sample period BEFORE computing OOS box formations.

**Volume/Turnover guard (recommended):**
- Require average daily value ≥ 2B VND during the N-day box-formation window.
- Pre-register as a binary on/off parameter (k already spent on window lengths; treat turnover guard as a mandatory quality filter, not a sweep dimension).

---

## Gate Structure (to be locked in gates addendum after VN-THIN pre-check)

Gates will follow the same structure as S1/S2 gates addenda (Book 2).

**Baseline:**
- A3_RS + D3 sector-slot sizing (same as S1/S2 baseline)
- Baseline OOS MAR (primary 2020–present): 0.8386
- Baseline full-sample MAR: 0.5321

**Gate formulas (subject to k-adjustment once k confirmed):**

G1a (relative, primary):
- candidate OOS MAR ≥ baseline OOS MAR + G1a_margin_adjusted
- k=2 → G1a_margin_adjusted = 0.050 + 0.010 × log2(2) = 0.050 + 0.010 = 0.060
- At baseline 0.8386: candidate needs OOS MAR ≥ 0.8986

G1b (absolute floor):
- candidate OOS MAR ≥ G1b_floor_adjusted
- G1b base = 0.500, k=2 → G1b_adj = 0.500 + 0.010 = 0.510

Negative-OOS cap: If both baseline OOS MAR AND candidate OOS MAR are negative → max CONDITIONAL-ADVANCE.

N_OOS targets:
- ≥ 30 raw trades in FULL primary OOS (2020–present)
- ≥ 12 raw trades in EACH of the two pre-committed sub-windows

Pre-committed sub-windows (same as S1/S2): 2020-01-01 → 2022-12-31 and 2023-01-01 → 2026-07-03.

**⚠️ ALL GATE THRESHOLDS ABOVE ARE PROVISIONAL — they must be written to the gates addendum file and locked before any harness execution.**

---

## Verdict mapping (after gates addendum is written and harness run)

- Both sub-windows clear G1a + G1b → candidate CALIBRATED → Step 4 (Interaction test vs C1–C4 baseline)
- G1a fails, belief expressed (N_OOS ≥ 30), both sub-windows fail → INVALIDATED (1 recalibration cycle allowed)
- 1 sub-window passes, 1 fails → INCONCLUSIVE-HOLD (wait for new OOS data; does not consume recalibration budget)
- Full primary N_OOS < 30 → VN-THIN (defer until more data; NOT INVALIDATED)
- IV clamped by structural constraint (not currently expected) → VN-SUBSUMED

---

## Mechanism checks (required in interaction report after CALIBRATED)

| Check | Measure | Concern |
|-------|---------|---------|
| M1 Fire count | How often does box filter change a decision vs unfiltered A3_RS? | < 5% → near-redundant |
| M2 Signal overlap | % of S4-firing days also satisfying S1 proximity ≥ 0.80 | High → S4 may be S1 re-expression |
| M3 Regime sensitivity | Box filter improvement in bull vs bear periods | Benefit only in C1-suppressed bear → no operational value |
| M4 Turnover guard effect | MAR with vs without turnover floor applied | If turnover guard has no effect → limit-lock false-box concern is not empirically material |

---

## Sequencing constraint

This pre-registration documents the degeneracy pre-check verdict (EXPRESSIBLE) and parameter design. Gate thresholds are NOT locked here.

**Required sequencing:**
1. Run VN-THIN pre-check (count N_OOS) → confirm N_OOS ≥ 30 for at least one candidate
2. Write gates addendum (lock G1a, G1b, sub-windows, tightness tercile cutpoint, turnover floor)
3. Build harness script (Cursor handoff)
4. Run harness
5. Apply verdict mapping

**Cursor handoff:** To be written as `00. Command Center/05_AI_Handoffs/YYYY-MM-DD_CursorHandoff_CortexBook3S4DarvasBox.md` after VN-THIN pre-check passes.

---

## Scope boundary

This pre-registration covers ONLY S4 (box breakout filter on A3_RS signal days). It does not:
- Modify live trading code
- Authorize extraction of additional Darvas beliefs (volume / position-management rules) — those require separate pre-registration
- Change the A3_RS signal logic
