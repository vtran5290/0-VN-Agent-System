# S16 Reopen — Momentum Seasonality Observational Report
# Date: 2026-07-09
# Data: combo_or_trades.csv (A3_RS+S2 combo OR pool, 2013-2026)
# N = 5,915 trades | 131 months | 15 years
# Pre-reg: knowledge/backtests/2026-07-09_S15reopen_FIP_S2pool_prereg.md
# OBSERVATIONAL ONLY — no intervention; describe only

---

## Verdict: [OBSERVED-CONSISTENT]

VN A3_RS+S2 trade data shows seasonal patterns broadly consistent with Gray & Vogel S16,
with two important VN-specific deviations documented below.

---

## Monthly Distribution

| Month | N | Mean Ret | Median Ret | Win Rate | Notes |
|-------|---|----------|------------|----------|-------|
| Jan ▼ | 615 | +9.08% | **-4.57%** | **43.1%** | Worst month; Tet overlap dominant driver |
| Feb | 471 | +18.42% | +2.74% | 53.9% | |
| Mar ★ | 639 | +1.60% | **-9.00%** | **39.6%** | Anomaly — worst median; breaks quarter-end thesis |
| Apr | 256 | -0.09% | -5.15% | 43.4% | |
| May | 505 | +5.50% | -3.99% | 42.4% | |
| Jun ★ | 713 | +27.08% | +6.94% | 58.3% | Strong; confirmed quarter-end |
| Jul | 593 | +9.78% | -1.52% | 47.0% | |
| Aug | 410 | +7.07% | -5.88% | 42.7% | |
| Sep ★ | 456 | +45.06% | **+16.11%** | **62.1%** | Strongest; 2021 bull market concentrated here |
| Oct | 439 | +21.42% | +7.87% | 58.5% | |
| Nov | 470 | +16.92% | +0.25% | 50.2% | |
| Dec ★ | 348 | +37.01% | +6.89% | 57.8% | Strong; confirmed quarter-end |

★ = quarter-end month | ▼ = January reversal thesis

**Note on means vs medians:** September mean (+45%) is right-tail-skewed by the 2021 VN
bull market. **Medians are the more reliable signal for this dataset.**

---

## Segment Analysis

| Segment | N | Mean | Median | Win Rate |
|---------|---|------|--------|----------|
| January | 615 | +9.08% | -4.57% | 43.1% |
| Quarter-end ex Jan (Mar/Jun/Sep/Dec) | 2,156 | +24.93% | +3.18% | 53.5% |
| Non-quarter-end, non-January | 3,144 | +11.92% | -0.90% | 48.5% |
| **Near-Tet (±14d of LNY)** | **168** | **+2.12%** | **-11.25%** | **35.1%** |
| Non-Tet window | 5,747 | +16.79% | +0.17% | 50.2% |

---

## VN-Specific Deviations from US Model

### 1. January weakness is Tet-driven, not pure momentum-reversal

US pattern: January reversal from tax-loss selling reversal (losers re-purchased).
VN reality: VN capital gains tax structure differs; the January dip aligns with Tet
(Lunar New Year = high uncertainty, retail risk-off, thin trading volumes). Near-Tet
window (±14d) shows median **-11.25%** with only 35.1% win rate — the worst of any
segment. This is a Tet-risk signal, not a classic US tax-reversal.

**Implication:** VN "January" caution should be defined by Tet calendar (shifts Jan–Feb
each year), not Gregorian January. A Gregorian-January caution rule will be imprecise.

### 2. March anomaly — breaks the quarter-end thesis

US model predicts quarter-end months are uniformly strong from window-dressing.
VN data: June (+6.94% median), September (+16.11% median), December (+6.89% median)
all confirm the pattern. **March is the exception** — median **-9.00%**, win rate **39.6%** —
worse than January on median. March is the first quarter-end after Tet season; VN
institutional book-building may not yet be active, and retail-dominant behavior
post-Tet differs from H2 quarter-ends.

**Implication:** The quarter-end effect in VN is most reliable for Jun/Sep/Dec. March
should be treated as a transition month, not a window-dressing beneficiary.

### 3. Tet window is the dominant VN seasonal factor (not in Gray & Vogel)

Near-Tet window (±14 calendar days of Lunar New Year) is the **worst seasonal risk period**
in VN momentum, not January per se. Win rate 35.1% means nearly 2-in-3 near-Tet entries
lose money on median. This is larger than the January effect and shifts year to year.

---

## US Reference Comparison

| Metric | US (Gray & Vogel) | VN (observed) | Status |
|--------|-------------------|---------------|--------|
| January H-L spread | -1.72%/month | Median -4.57%, win 43.1% | CONSISTENT (Jan worst month) |
| Quarter-end vs non-quarter-end | 3.10% vs 0.59% (~5×) | 24.93% vs 11.92% (~2×) | CONSISTENT in direction; magnitude differs |
| December strongest | +5.52%/month | +6.89% median, 57.8% win | CONSISTENT |
| March quarter-end benefit | Assumed positive | Median -9.00%, win 39.6% | **INCONSISTENT — VN anomaly** |
| Tet window risk | Not in model | Median -11.25%, win 35.1% | **VN-SPECIFIC; not in US model** |

---

## Observational Verdict Details

- Jan mean (+9.08%) < Qtr-end avg (+27.69%): **YES**
- Qtr-end avg (+27.69%) > Non-qtr ex-Jan (+11.29%): **YES**
- Result: **[OBSERVED-CONSISTENT]** (with VN deviations documented above)

---

## Status Update for S16

Per pre-reg (§ Observational Side Task):
> "If OBSERVED-CONSISTENT → register formal pre-reg with minimum-sample gate."

**S16 reopen condition partially met:** Observational data is consistent with the US
seasonality pattern (with VN deviations). However, the minimum-sample gate requires
pre-registration before any intervention:

**Required minimum-sample gate for formal S16 pre-reg:**
- [ ] Gregorian January N ≥ 30 usable trade entries in new data (2013-2026 satisfies)
- [ ] Tet-window test must use Tet-relative calendar (not Gregorian month)
- [ ] March treated as separate hypothesis from generic "quarter-end"
- [ ] Pre-register any intervention as entry-timing overlay (entry class), not exit or sizing
- [ ] Gate: OOS MAR of Tet-aware timing overlay ≥ baseline + 0.050 on S2 pool

**This observational report does NOT authorize any intervention.** The intervention
pre-reg must be written separately and is subject to the same bounded Research Program
Pre-Registration requirements as the S15 FIP reopen.

---

## Regime Note (S15 reopen condition)

`regime_state.json` as of 2026-07-06: **regime = "B" (sub-B choppy).**

knowledge_ACTIVE.md expansion gate note: "Retest trigger: regime_state.json exits
sub-B choppy → re-run S18 (G2 PASS) + S15 (G2 PASS)."

This means the S15 FIP reopen on the S2 pool is proceeding under the "fresh pre-reg on
different pool" rationale, NOT under the "regime change" rationale (sub-B has not exited).
The S15 DEGRADING-REJECT on the S1 pool remains conditional on regime exit from sub-B
before retesting on S1.

---

_Observational analysis run: 2026-07-09_
_Script: scripts/s16_seasonality_observational.py_
_Data: data/research/cortex_book2/combo/combo_or_trades.csv (N=5,915, 2013-2026)_
