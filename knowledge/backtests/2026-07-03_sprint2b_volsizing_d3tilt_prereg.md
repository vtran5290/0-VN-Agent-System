# Pre-Registration — Sprint 2B: Vol-Based Sizing + D3 Tilt 1.35/0.65 (Tier 2a)

**Date filed:** 2026-07-03
**Status:** PRE-REGISTERED — NOT YET RUN
**Council approval:** fable (Tier 2a scope confirmed) + opus (Lever 2 vol-sizing, Lever 3 D3 tilt) + ChatGPT (APPROVE, explicit Sprint 2B prioritization: "volatility-based sizing is the cleanest non-signal lever... D3 tilt 1.35/0.65 has prior structural support from the monotonic sector-tilt research")
**Full council pack:** `00. Command Center/05_AI_Handoffs/2026-07-02-1800_Council_PhaseEPathway.md`
**Preceded by:** Sprint 2A (chandelier exit) — KILLED 2026-07-03, G1 fail. See `2026-07-03_sprint2a_exit_mechanics_prereg.md` and `data/research/portfolio_optimization/sprint2a/sprint2a_report.md`.

## Two candidates, SEPARATE registrations (fable ruling: do not bundle — different risk category)

Per fable's 2026-07-03 follow-up ruling: "Run separately... Bundling would confound
attribution of any MAR change." Each candidate below is tested independently
against the SAME frozen baseline, with its own OOS evaluation. Do not combine
into a single joint-optimization run.

**Baseline for both:** A3 + D4 (iPower) + D3 (sector size 1.25/0.75), P1 honest
exit (the actual operational exit — see Sprint 2A note below), capital-based
accounting. Baseline MAR 0.532 (P1-honest replication, confirmed in Sprint 2A),
MaxDD -14.26%, CAGR 7.59%.

**IMPORTANT — exit-spec correction from Sprint 2A finding:** the Sprint 2A
pre-reg doc mis-described the baseline exit as "cloud-bear + 20-bar." The actual
operational P1 exit is different (see Sprint 2A report for the honest-trail
exit definition actually in use). Both candidates below must use the ACTUAL
P1 operational exit, unmodified — verify against `d3_size_neighbor.py`'s exit
implementation before building either candidate, do not re-derive from the
Sprint 2A pre-reg doc's (incorrect) description.

---

## Candidate 1 — Volatility-Based Position Sizing

**Hypothesis:** Sizing positions inversely to realized volatility (not equal-
weight, not Kelly) reduces MaxDD by underweighting the highest-vol names in
the 20-slot portfolio, without materially reducing CAGR.

**Spec (fixed, no grid):**
- Realized vol: 20-day rolling annualized stdev of daily returns, computed at
  entry date (point-in-time, no lookahead)
- Inverse-vol weight: `weight_i = (1/vol_i) / sum(1/vol_j for j in slots)`,
  renormalized to the existing 20-slot capital allocation (replaces equal-
  weight or RS-weighted sizing — apply on TOP of D3's sector tilt multiplier,
  not instead of it)
- Vol floor: clip vol at 15% annualized minimum to prevent division-by-tiny-
  number blowup on abnormally quiet names
- Kelly is explicitly REJECTED per opus verdict — do not implement or test it

**Success gate (ADVANCE):** ALL of:
1. OOS MAR ≥ 0.532 (no regression vs P1-honest baseline)
2. OOS MaxDD improves by ≥1.0pt vs baseline
3. OOS CAGR does not degrade by more than 0.5pt
4. Frozen-A3 entry stream assertion passes (identical trade count/dates to baseline)

**Fail gate (KILL):** any 1 of the 4 fails → KILL, no iteration on vol lookback/floor.

---

## Candidate 2 — D3 Tilt 1.35/0.65

**Hypothesis:** Moving one notch up the D3 neighbor-sweep curve (1.25/0.75 →
1.35/0.65) captures incremental MAR while staying inside the pre-registered
5-config neighbor sweep already validated in Phase D (not a new parameter,
already tested — this is a PROMOTION, not a fresh sweep).

**Spec (fixed — already validated in Phase D neighbor sweep):**
- Sector tilt multiplier: top-RS sectors 1.35×, bottom-RS sectors 0.65× slot
  weight (vs current operational 1.25×/0.75×)
- No other changes — same sector RS ranking logic, same D4/exit stack

**Reference numbers from Phase D neighbor sweep** (already computed, this
sprint just promotes to operational and re-validates OOS):
- size_1.35: MAR 0.580, incr +0.185 vs A3+D4, MaxDD -13.7% (from
  `data/research/portfolio_optimization/sleeve_d3/size_neighbor/`)

**Success gate (ADVANCE):** ALL of:
1. OOS MAR ≥ 0.532 (no regression vs current 1.25/0.75 baseline)
2. OOS MaxDD does not worsen by more than 1.0pt vs baseline -14.26%
   (concentration risk check — this is the fable/opus flagged risk: higher
   tilt buys MAR via sector concentration that thin VN sector breadth
   under-samples)
3. Sector concentration check: no single sector exceeds 40% of portfolio
   capital at any point in the OOS window (guards against the exact risk
   opus flagged for max-tilt configs)
4. Frozen-A3 entry stream assertion passes

**Fail gate (KILL):** any 1 of the 4 fails → KILL, hold at 1.25/0.75
operational, do not test 1.50/0.50 this quarter.

---

## OOS design (both candidates)
- IS window: same as D3 neighbor sweep / Sprint 2A
- OOS window: most recent 12 months (same window as Sprint 2A, for
  comparability)
- Single OOS evaluation per candidate — no iteration

## Next step after results
- Candidate 1 ADVANCE + Candidate 2 ADVANCE → both promote to operational
  stack (compose: A3+D4+D3@1.35/0.65+vol-sizing); queue Sprint 2c (sector
  cap + DD brake)
- Either KILL → that candidate retired this quarter; the other still
  evaluated independently and promoted if it passes
- Both KILL → queue Sprint 2c directly

## Verify
`python pp_backtest/sprint2b_volsizing.py` (Candidate 1, not yet created)
`python pp_backtest/sprint2b_d3tilt135.py` (Candidate 2, not yet created)
