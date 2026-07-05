# Pre-Registration — Sprint 2c: Sector Cap + Drawdown Brake (Tier 2b)

**Date filed:** 2026-07-03
**Status:** PRE-REGISTERED — NOT YET RUN
**Council approval:** ChatGPT Trigger #5 dual-judge APPROVE (2026-07-03) unblocked this sprint; opus + fable pre-approved Tier 2b scope in the original council pack.
**Preceded by:** Sprint 2A (chandelier exit, KILL) + Sprint 2B (vol-sizing CONDITIONAL-ADVANCE/confirmation-only, D3 tilt 1.35/0.65 KILL). See `config/sleeve_taxonomy.yaml` Phase E block for full history.

## Corrected gate design (mandatory for this and all future Tier 2/3 sprints)
Per `.claude/rules/verification-harness.md` "Promotion gate design" (codified 2026-07-03 after Sprint 2A/2B gate-flaw discovery):
- **G1a (relative):** candidate OOS metric ≥ same-window baseline OOS metric + pre-registered margin
- **G1b (absolute floor):** candidate full-sample metric ≥ pre-registered full-sample floor (same window as calibration)
- **Negative-window guardrail:** if both baseline and candidate are negative on the OOS window, max status = CONDITIONAL-ADVANCE, never full ADVANCE
- **Borderline-pass rule:** a G1a pass inside a thin margin requires a separate confirmation test before promotion

**Baseline (all candidates):** A3 + D4 (iPower) + D3 (sector size 1.25/0.75), P1 honest exit (actual operational exit per `d3_size_neighbor.py` — NOT the Sprint 2A pre-reg doc's incorrect description). Full-sample MAR 0.532, MaxDD -14.26%. OOS (most recent 12mo) baseline MAR -0.891, MaxDD -8.19%.

---

## Candidate 1 — Sector Exposure Hard Cap (Tier 2b)

**Hypothesis:** Capping any single sector at ≤35% of portfolio capital prevents concentration blow-up risk that D3's tilt mechanism doesn't itself guard against (validated concern: 2B-C2 hit 75% Consumer concentration at 1.35/0.65 tilt).

**Spec (fixed):**
- Hard cap: no sector may exceed 35% of allocated capital at any rebalance point
- When cap would be breached: redistribute excess capital pro-rata to next-highest-RS sectors under their own cap
- Applies on top of existing D3 1.25/0.75 tilt (operational config, NOT the killed 1.35/0.65)
- Portfolio-level machinery only — no signal/entry logic touched

**Pre-registered gates:**
1. G1a: OOS MAR ≥ -0.891 + 0.10 = -0.791
2. G1b: Full-sample MAR ≥ 0.532
3. Sector concentration: max sector exposure ≤ 35% confirmed throughout OOS window (this IS the candidate's mechanism — verify it holds, not just measure outcome)
4. Frozen-A3 entry stream assertion passes
5. Negative-window guardrail applies if G1a passes but both OOS values negative → cap at CONDITIONAL-ADVANCE

## Candidate 2 — Drawdown-Contingent De-Risking (Tier 2b)

**Hypothesis:** When portfolio drawdown from peak exceeds a threshold, reducing active slot count or position size limits further loss during adverse regimes — a portfolio-level brake independent of any per-position exit.

**Spec (fixed):**
- Trigger: portfolio drawdown from trailing peak equity exceeds 12%
- Action: reduce active slots from 20 to 12 (60%) until drawdown recovers to within 8% of peak, then restore to 20
- No change to which stocks are selected (D3/RS ranking unchanged) — only how many concurrent positions are held
- Portfolio-level machinery only — no signal/entry logic touched

**Pre-registered gates:**
1. G1a: OOS MAR ≥ -0.791 (same relative margin as Candidate 1)
2. G1b: Full-sample MAR ≥ 0.532
3. MaxDD improvement: candidate MaxDD ≤ baseline MaxDD - 1.0pt (this IS the mechanism's purpose — must show real DD reduction, not just pass G1a/G1b)
4. Frozen-A3 entry stream assertion passes
5. Negative-window guardrail as above

---

## Optional — 2B-C1 Confirmation (per ChatGPT's constraint)
ChatGPT's decision permits including 2B-C1 (inverse-vol sizing) in Sprint 2c ONLY as
a confirmation/interaction candidate, explicitly pre-registered here:

**2B-C1 Confirmation test:** re-run inverse-vol sizing on a DIFFERENT held-out
window (not the same 12-month OOS already used) to check whether the thin
~0.002 MAR G1a margin replicates or was noise. If a second independent window
is not available with sufficient history, this confirmation is DEFERRED to
next quarter rather than reusing the same window (reusing the same window
would not be a genuine confirmation test).
**This does NOT block Sprint 2c's two primary Tier 2b candidates above.**

---

## Budget check
This registration covers 2 Tier 2b candidates (sector cap, DD brake) + 1
optional confirmation (2B-C1, deferred if no clean second window exists) =
within the 2-3 candidate/quarter cap per fable's framework.

## Next step after results
- Both ADVANCE → promote both to operational stack (compose: A3+D4+D3+
  sector-cap+DD-brake); Phase E.1 (slow mean-reversion) becomes next priority
- Either/both KILL → retire this quarter; queue backlog items (RS delta,
  regime-conviction sizing, RS persistence) for next quarter
- 2B-C1 confirmation PASS on second window → promote to operational
- 2B-C1 confirmation FAIL or DEFERRED → hold at CONDITIONAL-ADVANCE,
  re-evaluate next quarter

## Verify
`python pp_backtest/sprint2c_sectorcap.py` (Candidate 1, not yet created)
`python pp_backtest/sprint2c_ddbrake.py` (Candidate 2, not yet created)
