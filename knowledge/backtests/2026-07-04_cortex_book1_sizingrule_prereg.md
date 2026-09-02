# Pre-Registration — Cortex Book #1: Fixed-Fractional Risk-Per-Trade Sizing (Tharp/Minervini family)

**Date filed:** 2026-07-04
**Status:** RUN COMPLETE — 2026-07-04 (see `2026-07-04_cortex_book1_sizingrule_gates_addendum.md` + `data/research/cortex_book1_sizing/cortex_book1_sizing_report.md`)
**Council approval:** opus (artifact seat, REDIRECT — approved as belief-lifecycle instrument, firewalled from session counter) + fable (framework seat, HOLDS — existing rules already resolve the session-vs-lifecycle question)
**Full council pack:** `00. Command Center/05_AI_Handoffs/2026-07-04-0800_OpusVerdict_VNBrainBacktestPipeline.md`, `2026-07-04-0800_FableVerdict_VNBrainBacktestPipeline.md`
**Cortex brain:** `D:\V\.claude\brains\vn-trading-advisor\knowledge.md` — beliefs under test: S6 (Tharp, psychology/sizing/system 60/30/10 split) and S3 (Minervini, 1.25–2.5% risk-per-trade cap)

## Why this book/belief first (not Minervini's entry rules)
Opus verdict flagged a category-error risk: the existing `minervini_backtest/` suite tests
**entry selection** (FA-score, funnel, walk-forward), not **position sizing**. S3's actual claim
is about risk-per-trade sizing, which that suite does not test. Confirmed via direct read of
`src/trading/live/sizing_policy.py`: this is live **execution-level** sizing (cash/ADV/max-order
caps), not a research backtest harness for a risk-per-trade *rule*. No ready-made harness exists
for this specific claim — this pre-registration requires a new research script (NOT a
modification of `sizing_policy.py`, which is live trading code and out of scope per hard rules).

## Hypothesis under test
Capping risk-per-trade at a fixed-fractional band (1.25–2.5% of equity, per S3/Minervini;
framed by S6/Tharp as "the sizing lever matters more than entry-signal refinement") improves
risk-adjusted return (MAR) versus the current baseline sizing approach, when both are run
against the SAME entry signals over the SAME window.

## Baseline
Current operational sizing (whatever `sizing_policy.py` + the live A3_RS/D3/D4 stack currently
produces, replicated as a RESEARCH-ONLY simulation — do not touch or import the live module's
account-state side effects). Same entry signals as the current production stack (A3_RS +
existing overlays). Window: 2012-01-01 to present (or the earliest date VN Agent's price data
actually supports — verify and record the true start date; do not assume 2012 without checking
data coverage first).

## Candidate
Same entry signals, same window, but position size is set by fixed-fractional risk-per-trade:
`position_size = (equity * risk_pct) / (entry_price - stop_price)`, with `risk_pct` swept across
the S3-specified band (1.25%, 1.75%, 2.5%) as three separate, clearly-labeled sub-candidates —
NOT a single blended number. Stop-price definition must be stated explicitly and held fixed
across all three sub-candidates (use the existing production stop logic if one exists; if not,
state the assumed stop rule explicitly and flag it as an assumption, not a hidden default).

## Gates (fixed before running — no post-hoc adjustment)
- **G1a (relative, primary):** candidate OOS MAR ≥ baseline OOS MAR + [MARGIN — to be set by
  whoever builds this, BEFORE running, wide enough to clear noise-band concerns per opus's
  explicit caution: do not reuse a prior sprint's ~0.002 hairline margin]
- **G1b (absolute floor):** candidate OOS MAR ≥ its own pre-set floor, derived from THIS window
  only — do not import a floor calibrated on a different window
- **Negative-OOS cap:** if both baseline and candidate OOS MAR are negative → max status is
  CONDITIONAL-ADVANCE, never full ADVANCE (per verification-harness.md promotion-gate rules)
- **Realism:** ADV-adjusted returns, fee=30/min_hold=3 (match existing Minervini-suite realism
  conventions), survivorship-checked, no look-ahead
- **Window discipline:** do not re-select or narrow the 2012-present window post-hoc if results
  are unfavorable — if the window genuinely needs adjustment, that requires a fresh pre-reg,
  not a silent edit to this one

## Verdict mapping (per belief, applies independently to S3 and S6)
- Clears G1a + G1b → promote SOURCED → CALIBRATED in knowledge.md, cite this test as evidence
  (window, metric values, date). Counts toward the 0/3 NEW CALIBRATED gate criterion.
- Fails cleanly and robustly → mark INVALIDATED in knowledge.md with the disconfirming evidence
  (window, metric values, date, why it failed). Counts toward the 0/1 INVALIDATED criterion.
- Fails but the test itself may be mis-specified (e.g. stop-rule assumption looks wrong in
  hindsight) → ONE recalibration cycle allowed: revise the test spec, re-run once, then accept
  whichever of the two outcomes above applies. Counts toward the 0/1 recalibration-cycle criterion.

## Explicit rule this test does NOT touch
Per fable's ruling (2026-07-04): running this backtest, regardless of outcome, does **NOT**
advance the "10 real /cortex sessions" counter (currently 1/10). This is CALIBRATION activity
per the updated cortex SKILL.md Step 7 definition — it logs to this file and to knowledge.md's
changelog only, never to `session_log.md`.

## Scope boundary (explicit)
This pre-registration and any resulting implementation touches ONLY the vn-trading-advisor
brain's existing 6 SOURCED beliefs. The 5 newly-acquired books (Lo, Aronson, Carver, Harris,
Khanna) remain FROZEN per the 2026-07-03 opus verdict — this pipeline is not a justification
to unfreeze them, and building this harness must not be treated as license to process the
book backlog "while we're at it."

## Next step (handoff required — new backtest code, not live-code modification)
Building the actual research backtest script (candidate sizing simulation, gate scoring,
report output) is new code development, not a live-trading-logic change — but per this repo's
Claude/Cursor division ("Cursor: build/architect/refactor"), the harness itself should be
built via a Cursor handoff, not written directly in this session. See companion handoff:
`00. Command Center/05_AI_Handoffs/2026-07-04-0830_CursorHandoff_CortexBook1SizingBacktest.md`
