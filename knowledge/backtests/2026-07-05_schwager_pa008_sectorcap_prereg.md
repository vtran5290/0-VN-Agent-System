# Pre-Registration: PA-008 — Sector Cap / Diversification Overlay
# ⚠️ PA Status: PARKED — DEGENERATE (as designed, 2026-07-05)
# Degeneracy pre-check result: cap=4 binds on 0.0% of entry-cohort days (threshold ≥5%).
# A3_RS+S1 filter naturally produces ≤4 same-sector signals/day; selection rule never fires.
# Pre-check file: knowledge/backtests/2026-07-05_pa008_sectorcap_degeneracy.md
# REFRAME OPTION: redesign as HOLDING rule (daily open positions binding 85.7%) — requires
#   new pre-registration + new gate design + Trigger #5 dual-judge before any harness run.
# DO NOT DISPATCH this pre-reg as written. Design must change first.
# ---------------------------------------------------------------------------------
# Original status (before pre-check):
# PA Status: APPROVED-FORMALIZE ✓ UNBLOCKED
# ✅ User sign-off received: 2026-07-05 ("approved" — Claude Cowork session, higher council review)
# Date: 2026-07-05
# Council authority: ChatGPT APPROVE (advisory) + opus APPROVE + fable GAP resolved
# Source: Blake, The New Market Wizards (1992) — "diversifying the SAME edge across correlated sectors
#   pushes 55% individual probability → ~75% portfolio probability (binomial theorem)"
# VN application: implement a sector concentration cap on A3_RS positions — limit max simultaneous
#   positions in any single VN sector; ensure edge is diversified across sectors rather than
#   concentrated in one sector's momentum cluster
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor runs the harness.
# No gate changes after data is seen.
# Activation requires: (1) user sign-off here; (2) Trigger #5 dual-judge on first run; (3) config flag enabled:false.

---

## User sign-off (required before any run)
```
USER SIGN-OFF: [ ] NOT YET RECEIVED
Date: ___________
Signed: ___________
```
Do not run harness until this section is completed with user's written sign-off.

---

## Belief / protocol amendment statement (LOCKED)

"Capping the maximum number of simultaneous A3_RS positions in any single VN sector (sector concentration cap) will improve risk-adjusted returns by distributing the momentum edge across uncorrelated sector clusters, reducing the drawdown exposure from any single sector shock, while preserving the total number of active positions."

PA type: PORTFOLIO ARCHITECTURE — does NOT modify entry criteria, exit criteria, or signal logic. Only affects which signals are activated when multiple signals from the same sector fire simultaneously.

Architecture note: This is portfolio construction (which positions to hold), not alpha generation (when to enter/exit). Blake's original finding (sector persistence 70-82%) is separate — that is S18. PA-008 formalizes the DIVERSIFICATION principle regardless of whether S18 is active.

---

## Architecture constraints (HARD RULES — do not override)

1. **Entry/exit frozen:** PA-008 modifies ONLY position selection when sector cap is binding. No change to A3_RS signal logic, exit signals, or regime gating.
2. **Sector cap is a selection rule, not a kill switch:** When more than N A3_RS signals fire in one sector simultaneously, select the top-ranked N by A3_RS score and skip the rest for that period. The skipped positions are NOT banned — they compete in next period.
3. **C1 bear-regime block is upstream:** PA-008 applies only within C1-permitted (bull) periods.
4. **Independent test first:** PA-008 must be tested in isolation (PA-008 only, PA-007 off) before any combined run.
5. **Do not confuse PA-008 with S18:** S18 tests Blake's sector persistence SIGNAL (sector return → next-day continuation). PA-008 tests sector DIVERSIFICATION as a portfolio construction rule. They are distinct. PA-008 can be tested even if S18 is still SOURCED.
6. **D3/sector-cap alignment:** This PA aligns with the existing D3 direction (combined sector-cap logic already in design consideration). If D3 is formalized before PA-008 is tested, check for overlap before running duplicate harness.

---

## Lane A test design (activate ONLY after user sign-off)

### Candidate parameters (k=3 sector cap values)

| Candidate | Sector cap | Description |
|-----------|-----------|-------------|
| C1_cap3 | Max 3 positions per sector | Tight cap; forces high diversification |
| C2_cap4 | Max 4 positions per sector | Moderate cap |
| C3_cap5 | Max 5 positions per sector | Loose cap; only binds in highly concentrated periods |

VN sector definition: use HOSE/HNX sector classifications (banking / real-estate / steel / food-bev / energy / logistics / securities / utilities). Minimum sector membership for cap to bind: ≥ 5 stocks in A3_RS candidate pool. If a sector has fewer than 5 A3_RS candidates in a given period, no cap applies to it.

### Baseline
- A3_RS standalone frozen baseline OOS MAR: per current knowledge.md calibrated value

### Test universe
- All A3_RS OOS signal periods (same IS/OOS split as existing calibrated signals)
- Compare: full A3_RS pool vs. sector-capped sub-pool

### Gate parameters (LOCK before run, AFTER user sign-off)

```
G1a (relative): OOS MAR ≥ baseline × 1.03 (3% relative improvement — conservative; portfolio rule)
                Note: portfolio construction rules may show smaller absolute MAR improvement while
                providing MaxDD benefit; prioritize G2 (MaxDD) alongside G1a for this PA type.
G1b (absolute): OOS MAR ≥ 0.516 (standard absolute floor)
G2 (MaxDD): OOS MaxDD ≤ frozen-baseline MaxDD × 0.95 (5% improvement in max drawdown — primary benefit)
            Rationale: if G2 does not improve, sector diversification provides no structural benefit
G3 (turnover): turnover increase vs. baseline ≤ 15% (skipping same-sector signals creates minimal churn)
G4 (2021 capture): 2021 sub-period OOS MAR ≥ baseline 2021 sub-period × 0.95 (no major 2021 impairment)
                   2021 VN bull run may have been concentrated in specific sectors; cap must not
                   significantly impair 2021 capture to be valid as a general rule
G5 (sector-shock test): identify any historical sector shock period (e.g. real-estate 2022, banking
                        stress events); compare PA-008 MaxDD in those periods vs. baseline MaxDD
Standing guardrail: if both baseline AND candidate OOS MAR are negative → CONDITIONAL-ADVANCE only
Borderline rule: G1a margin < 0.02 MAR units AND G2 does not improve → REJECT (both legs must justify)
Window scoping: all gate thresholds calibrated on same OOS window as candidate; no cross-window reuse
```

### Attribution slices required

- Sector attribution: which sectors see most frequent cap binding? Which sectors drive the MAR improvement?
- Year attribution: 2019-2025 (identify years where cap impairs vs. improves)
- Cap-binding frequency: what % of signal periods have the cap binding? If <5%, cap is never binding → degenerate (no effect)

---

## Degeneracy pre-check (should run BEFORE harness)

**Pre-check:** Does the sector cap actually bind in the A3_RS OOS candidate pool?
- If A3_RS OOS candidates are naturally distributed (never more than 3-4 per sector at the same time), the cap is effectively inactive → DEGENERATE → PA-008 becomes VN-SUBSUMED (natural diversification)
- Check: compute max simultaneous same-sector signals across all OOS signal periods
- If max is ≤ 3 in >90% of periods for any cap level tested → degenerate for that cap level

Pre-check verdict:
```
MAX_SAME_SECTOR_SIGNALS_OOS (same-day cohort): 4
CAP_BINDING_FREQUENCY_AT_3: 1.52% of cohort days
CAP_BINDING_FREQUENCY_AT_4: 0.0% of cohort days (same-day new signals)
CAP_BINDING_FREQUENCY_AT_5: 0.0% of cohort days
Daily open positions — cap=4 binding: 85.74% of sector-day observations
VERDICT: EXPRESSIBLE (cap binds on overlapping holdings, not same-day cohort alone)
Report: knowledge/backtests/2026-07-05_pa008_sectorcap_degeneracy.md
```

---

## Interaction test (after standalone PA-008 passes)

**PA-008 × PA-007 combined test:**
- Gate: OOS MAR ≥ max(PA-007-alone, PA-008-alone) × 1.02; turnover ≤ 25% above baseline

**PA-008 × S18 (if S18 CALIBRATED by then):**
- S18 selects which sector to trade based on sector momentum persistence; PA-008 caps exposure within each sector
- Combined: sector-level S18 signal → pick sector; position-level PA-008 → cap positions within that sector
- Gate: same as standalone PA-008 G1a-G5; run after S18 is CALIBRATED, not before

---

## Config flag

```yaml
# A3_RS system config
pa008_sectorcap:
  enabled: false    # HARD DEFAULT — do not enable without user sign-off + Trigger #5 dual-judge
  sector_cap: 4     # max positions per sector; lock after test (C1_cap3, C2_cap4, or C3_cap5)
  min_sector_size: 5  # minimum A3_RS candidates in a sector for cap to apply
  definition: hose_hnx_sector  # which sector classification to use
```

---

## Files to create (Cursor, after user sign-off + degeneracy pre-check)

1. `pp_backtest/cortex_pa008_sectorcap.py` — harness script
2. `knowledge/backtests/2026-07-05_pa008_sectorcap_degeneracy.md` — degeneracy pre-check results
3. `knowledge/backtests/2026-07-05_pa008_sectorcap_gates_addendum.md` — gates addendum after IS calibration
4. `pp_backtest/attribution/pa008_sector_attribution.py` — sector binding frequency + attribution

---

## References
- Source: Blake, The New Market Wizards (1992) — pattern-extracted from E:\Calibre-books\...\The New Market Wizards\
- Related belief: S18 (same source; sector persistence SIGNAL — distinct from this PA's DIVERSIFICATION rule)
- Council: 2026-07-05-2100_SchwagerPACandidates_Council.md
- Verification gates: verification-harness.md § VN Agent System → promotion gate design
- PA lifecycle: sources.md → PA candidate ledger (once sources.md PENDING_WRITE is applied)
