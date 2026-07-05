# Pre-Registration — Sprint 2A: Exit Mechanics (Tier 2a)

**Date filed:** 2026-07-03
**Status:** PRE-REGISTERED — NOT YET RUN
**Council approval:** fable (framework GAP→resolved) + opus (OPTIMIZE-WITHIN, Lever 1) + ChatGPT (APPROVE)
**Full council pack:** `00. Command Center/05_AI_Handoffs/2026-07-02-1800_Council_PhaseEPathway.md`

## Hypothesis
Replacing the current A3 exit (EMA20/EMA100 cloud bear crossover) with a
volatility-adaptive trailing stop (chandelier or ATR-based) reduces MaxDD
by capturing more of a move's give-back before the lagging cloud signal
fires, without materially reducing CAGR.

## Scope confirmation (fable ruling, 2026-07-03)
Exit mechanics are Tier 2a, NOT Tier 1. The "no A3 signal parameter
changes" lock applies to entry/RS-weight logic only. This is settled —
do not re-litigate per sprint.

## Frozen baseline
A3 + D4 (iPower) + D3 (sector size 1.25/0.75) — capital-based, P0 realism
(next-bar open, T+2, 0.40% RT costs, 0.5% slippage).
Baseline MAR: 0.535 | CAGR: ~7-8% est | MaxDD: -14.3%
A3 entry stream must remain byte-identical (frozen-A3 assertion, same
pattern as D3's frozen-A3 gate).

## Candidate (exactly ONE — no grid, no post-hoc variant testing)
**Chandelier exit:** stop = highest high since entry − (ATR(22) × 3.0)
- ATR period: 22 days (standard chandelier default — not tuned to VN data)
- Multiplier: 3.0 (standard default — not tuned to VN data)
- Exit fires next-bar open when close < chandelier stop, OR existing
  cloud-bear exit fires, OR 20-bar time stop — whichever comes first
  (chandelier is additive, not a replacement for the other two gates)

Parameters are fixed to their canonical/textbook defaults specifically to
avoid a fitting exercise. If this pre-registered config fails, the
candidate is retired — do not sweep ATR period or multiplier afterward.

## OOS design
- IS window: same historical window as D3 neighbor sweep (reuse existing
  data pipeline)
- OOS window: most recent 12 months, held out, untouched until IS pass
  completes
- Single OOS evaluation — no iteration

## Success gate (ADVANCE)
ALL of:
1. OOS MAR ≥ 0.535 (no regression vs frozen baseline)
2. OOS MaxDD improves by ≥1.0pt vs frozen baseline (-14.3% → ≤ -13.3%)
3. OOS CAGR does not degrade by more than 0.5pt
4. Frozen-A3 entry stream assertion passes (byte-identical to baseline)

## Fail gate (KILL — default on ANY miss, no borderline iteration)
Any one of gates 1-4 fails → KILL. Retire chandelier-exit candidate.
Do not adjust ATR period/multiplier and re-test in the same quarter.

## Next step after result
- ADVANCE → promote to operational stack; queue Sprint 2B (vol-sizing +
  D3 tilt 1.35/0.65)
- KILL → queue Sprint 2B directly (exit mechanics idea retired, not
  reopened this quarter)

## Verify
`python pp_backtest/sprint2a_exit_chandelier.py` (script not yet created —
Cursor implementation task)
