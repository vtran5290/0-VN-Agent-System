# ⚠️ SUPERSEDED — 2026-07-05
# The S1+S2 interaction test was pre-registered and run by a concurrent session BEFORE this file was written.
# Authoritative pre-reg: knowledge/backtests/2026-07-05_cortex_book2_s1s2_interaction_prereg.md
# Result: DEGRADING-REJECT (combined OOS MAR 0.5821 < S1 standalone 1.7844). S1+S2 combined use FORBIDDEN.
# This file is VOID. Do not dispatch or reference for any test.
# ---------------------------------------------------------------------------------
# Pre-Registration: S1+S2 Interaction Test (SUPERSEDED)
# Date: 2026-07-05
# Authority: Opus REDIRECT (higher council, 2026-07-05) — #1 dispatch priority (NOW RESOLVED)
# Background: S2 (O'Neil breakout volume, 1.4× threshold) achieved CALIBRATED (standalone) OOS MAR 2.5447.
#   M2 alert: ~59% of S2-filtered signals overlap with S1 (within_15pct 52wk high proximity).
#   Combined effect is unknown. Must test before declaring S2 CALIBRATED (FULL) or running both live.
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor runs the harness.
# No gate changes after data is seen.
# Run ISOLATED: PA-007 off, PA-008 off, all other overlays off. Baseline must be clean.

---

## Interaction statement (LOCKED)

"Applying both S1 (within 15% of 52-week high filter) and S2 (1.4× volume breakout filter) as simultaneous entry conditions to A3_RS signals will produce OOS performance no worse than S2 applied alone, while reducing signal count and improving signal quality."

Interaction type: FILTER STACK (both conditions must be true; this is an AND filter, not OR or sequential)
Critical sub-question: with 59% overlap already, does the combined filter add information or is it noise reduction only?

---

## Baseline values (read from knowledge.md before running — do not use stale figures)

```
A3_RS standalone OOS MAR:       0.8386  (frozen reference baseline)
S2-alone selected OOS MAR:      2.5447  (from knowledge.md CALIBRATED entry — verify before run)
S1-alone OOS MAR:               [READ FROM knowledge.md — S1 CALIBRATED entry]
```

These are the control arms. All gates are relative to these values on the SAME OOS window.

---

## Candidate parameters (k=1 — no tuning; the thresholds are already locked from individual calibrations)

| Candidate | Condition | Description |
|-----------|-----------|-------------|
| C1_s1s2_and | S1 (within_15pct) AND S2 (vol_ratio ≥ 1.4×) AND A3_RS signal | Both filters must be true simultaneously |

No additional parameter tuning. S1 uses its calibrated threshold (within_15pct of 52-week high). S2 uses its calibrated threshold (1.4× volume ratio). Both are LOCKED from their individual calibration runs.

---

## Gate parameters (LOCKED — do not adjust after seeing OOS data)

```
G_ia (non-degradation): combined OOS MAR ≥ S2-alone OOS MAR × 1.00
                        (combined must at minimum match the better standalone — no degradation permitted)
G_ib (improvement bar): combined OOS MAR ≥ S2-alone OOS MAR × 1.04
                        (4% improvement = ADDITIVE; 0-4% = NEUTRAL; below G_ia = DEGRADING)
G2 (sample floor):      N_OOS ≥ 30 signals in combined filter
G3 (over-filtering):    combined signal count ≥ 15% of A3_RS baseline signal count
                        (if combined filter leaves < 15% of signals, signal is too sparse to be operational)
Standing guardrail:     if both S2-alone AND combined OOS MAR are negative → CONDITIONAL only
Borderline rule:        if G_ia pass but G_ib fail (0-4% improvement) → NEUTRAL / no upgrade to FULL CALIBRATED
Window scoping:         all gates use the SAME OOS window as the existing S2 calibration; no cross-window reuse
```

Verdict mapping:
- G_ia PASS + G_ib PASS + G2 PASS + G3 PASS → ADDITIVE (S2 upgrades to CALIBRATED FULL; S1+S2 stack approved)
- G_ia PASS + G_ib FAIL + G2 PASS + G3 PASS → NEUTRAL (S1+S2 doesn't help; run them independently, not stacked)
- G_ia FAIL → DEGRADING (S1 and S2 are redundant or conflicting; do NOT stack; flag M2 interaction as CONFLICT)
- G3 FAIL → OVER-FILTERING (stack is operationally unviable; downgrade to NEUTRAL, flag signal sparsity)

---

## Attribution slices required alongside gate verdicts

- Overlap composition: what fraction of combined signals come from S1-first vs. S2-first? (confirm ~59% overlap)
- Year attribution: combined OOS MAR by year (2019-2025) — does the stack hurt in specific years?
- Sector attribution: does the stack over-concentrate in specific sectors vs. S2-alone?
- Signal count table: S1-alone count | S2-alone count | S1+S2 count | A3_RS baseline count

---

## Delta report requirement (mandatory before expansion gate decision)

Cursor must produce a delta report comparing:
- S2-alone (current CALIBRATED standalone) vs. S1+S2-combined
- Explicit before/after on: MAR, MaxDD, signal count, sector distribution, year breakdown
- One-line verdict: ADDITIVE | NEUTRAL | DEGRADING

The delta report is the input to the expansion gate decision. Do not make the gate decision without it.

---

## Expansion gate implication

Per higher council approval (2026-07-05):
- Gate is split: mechanism gate (belief criteria) + usage gate (/cortex sessions)
- Mechanism gate needs: ≥3 new CALIBRATED beliefs (S1 ✓, S2 ✓ standalone, need 1 more new CALIBRATED)
- If this test returns ADDITIVE: S2 upgrades to CALIBRATED (FULL); mechanism gate needs 1 more new CALIBRATED from a different belief (S3-S19 pool)
- If this test returns NEUTRAL or DEGRADING: S2 stays CALIBRATED (STANDALONE); they are run independently, not stacked; still counts toward gate (S2 is already CALIBRATED)
- EITHER WAY: this test does not directly add a new CALIBRATED — it resolves S2's operational mode (stacked vs. independent)

---

## Files to create (Cursor)

1. `pp_backtest/cortex_s1s2_interaction.py` — interaction test harness
2. `knowledge/backtests/2026-07-05_s1s2_interaction_deltaReport.md` — delta report output
3. `data/decision/2026-07-05_s1s2_interaction_result.json` — structured result for memory system

---

## HARD RULES

- Run COMPLETELY ISOLATED. PA-007, PA-008, all PAs off. Only S1 filter + S2 filter active.
- Use EXACTLY the same IS/OOS split as the existing S2 calibration (same dates, same universe)
- Do NOT tune S1 or S2 thresholds. They are locked.
- If combined signal count < 30 in OOS: report G2 FAIL immediately; do not run gate G_ia
- Write delta report BEFORE writing any gate verdict — no orphaned conclusions

---

## References
- S1 calibration: knowledge.md § Calibrated Beliefs, S1 entry
- S2 calibration: knowledge.md § Calibrated Beliefs, S2 entry (standalone, selected 1.4×, OOS MAR 2.5447)
- M2 alert: memory_log.md 2026-07-05 ~19:00 entry ("~59% S2-filtered signals overlap with S1")
- Dispatch authority: higher council opus REDIRECT, 2026-07-05-2200 session
- Gate design: verification-harness.md § VN Agent System → promotion gate design
