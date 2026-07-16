> # ⛔ SUPERSEDED-BY-MANIFEST-2026-07-16 — DO NOT APPLY
>
> **Superseded by:** `D:\V\00. Command Center\05_AI_Handoffs\2026-07-16-1100_VNAgent_BrainReconciliation_MANIFEST.md`
> **Authority:** Trigger #3 council 2026-07-16 — Opus REDIRECT + Fable CONFLICT + ChatGPT REDIRECT (independent). V approved decisions 1–3 and B, 2026-07-16.
> **Status changed:** `STAGED — V must apply` → **SUPERSEDED. Do not apply any sub-patch.**
>
> **Why this must not be applied as written:**
> 1. **4A contradicts a V decision.** It keeps `S21` = fixed stop-loss. V approved (2026-07-16) retiring bare `S21`/`S22` as `AMBIGUOUS-LEGACY` with fresh IDs for **all** claimants. This patch predates that ruling and would re-cement the contested ID.
> 2. **4B is unsafe in isolation — verified.** It absolutises the brain path, repointing VN sessions from the domain copy (v26) to canonical (v29). Canonical has **0 hits** for the `"may NEVER be cited to argue for overriding C1"` safety annotation, and contains **neither S20 nor S22**. Applying 4B before the merge **strips a safety restriction from every session's read path and removes two beliefs from view.** This patch states 4B "can be applied before or after 4A" — that latitude is the defect.
> 3. **Scope predates the C=v60 discovery.** This patch reasons about A (v29) and B (v26). It does not know `knowledge_ACTIVE.md` is v60 — 31 versions ahead — and is the actual content basis.
>
> **What survives and is being harvested into the manifest — this work was good:**
> - The S25/S26 slot reservations (V-approved 2026-07-16; the manifest honours them)
> - The S25/S26 row text **verbatim**, including the preserved `MANDATORY ANNOTATION` on the Pedersen belief — the single highest-consequence text in this conflict
> - The 4B path fix, resequenced to **after** the merge per ChatGPT ACTION 4
> - The root-cause diagnosis (relative path in `.claude/CLAUDE.md` line 14), independently confirmed by the council
>
> **Kept, not deleted** — this file is evidence, and its investigation notes are sound. It is disarmed, not discarded.
>
> **Meta:** this is the third correct diagnosis staged and never applied (v25 batch → knowledge.md v29→v30 → this). That pattern *is* the root cause finding of the 2026-07-16 council: the compliant path is high-friction **and gitignored**, so fixes rot in staging while drift accrues in the writable file.

---

# PATCH 4 CORRECTED — Brain Sync (Pedersen Re-slot + Path Fix)
**Date:** 2026-07-15
**Author:** Claude Sonnet (Cowork, read-only investigation → staged write)
**Status:** ⛔ **SUPERSEDED 2026-07-16 — DO NOT APPLY** (was: STAGED — V must apply all three sub-patches in order 4A → 4B → 4C)
**V-ONLY:** Yes — all three patches require V action. No Cursor delegation without explicit V approval.
**Supersedes:** Patch 4 in `D:\V\00. Command Center\APPLY_ALL_PATCHES_2026-07-14.md`

---

## WHY THE ORIGINAL PATCH 4 WAS WRONG

The original Patch 4 (in `APPLY_ALL_PATCHES_2026-07-14.md`) targeted:
```
File: D:\V\0. VN Agent System\.claude\brains\vn-trading-advisor\knowledge.md
```

That is the **domain copy** (v26, stale). The canonical brain per `source-of-truth.md` brain placement rules is:
```
File: D:\V\.claude\brains\vn-trading-advisor\knowledge.md  (v29, current)
```

**Why the original would have caused harm if applied:**
- Step 1 looked for "Pedersen momentum crash" in the S21 slot — that text does NOT exist in v29. S21 in v29 is the fixed stop-loss (PARKED, harness complete, 2026-07-11). The step would be a silent no-op or find the wrong row.
- Step 4 would have inserted a new S21 (NearEntry Zone) into v29 — creating a DUPLICATE S21. v29 already has S21 = fixed stop-loss.
- Steps 6–7 would apply state updates written for v26 state against entries already at v28/v29 state, potentially overwriting PARKED/harness-complete data with pre-harness SOURCED versions.
- Net result: v27/v28 work (the cortex_s21_fixed_stoploss.py harness run + G1b FAIL results) would be lost or corrupted in the canonical.

**Root cause of the domain copy existing:** `D:\V\0. VN Agent System\.claude\CLAUDE.md` line 14 uses a relative path `.claude/brains/vn-trading-advisor/`. Any Claude Code or Cursor session running with the VN Agent folder as CWD resolves this to the domain copy. Patch 4B fixes this.

**Investigation source:** `D:\V\00. Command Center\PATCH4_INVESTIGATION_20260715.md`

---

## SLOT ASSIGNMENT VERIFICATION

Canonical brain (v29) `§ Sourced Beliefs` table — S-numbers present:
S3 (VN-Subsumed), S4, S5, S6, S7, S8, S9, S10, S11, S12, S13, S14, S15, S16, S17, S18, S21 (PARKED)

S-numbers absent from canonical (all available):
S20, S22, S23, S24, S25, S26

Slots reserved per staged pipeline (not yet in canonical):
- S20 = Minervini climax-top (domain copy only; in pipeline but not part of this patch)
- S22 = NearEntry timing regime-conditional, KEEP_BASE (knowledge_ACTIVE.md only; full Patch 4 steps would add this)
- S23 = B-1 crash-detection sub-mechanism, SOURCED (Fable handoff Appendix B; staged)
- S24 = Breadth drop-rate, PARKED (Fable handoff Appendix B; staged)

**S25 and S26 are confirmed free.** Pedersen beliefs are assigned here.

---

## PATCH 4A — Re-slot Pedersen Beliefs in Canonical Brain
**Target file:** `D:\V\.claude\brains\vn-trading-advisor\knowledge.md`
**Action:** INSERT two new rows at the END of the `§ Sourced Beliefs` table, after the S21 row
**Safety:** Read-only on all other content. Do not modify any existing row. Do not change the version header yet (version bump happens in step 6).

### Step 1 — Locate the insertion point

Open `D:\V\.claude\brains\vn-trading-advisor\knowledge.md`. Find the S21 row — it starts with:
```
| S21 | A fixed initial stop-loss in the 5–10% range from entry price
```
The S21 row is the LAST row in the `§ Sourced Beliefs` table. The next line after S21 is:
```

---

## § VN-Subsumed Beliefs
```

### Step 2 — Insert S25 row AFTER the S21 row

Place the following row between the S21 row and the `---` separator:

```
| S25 | Momentum crashes are liquidity events, not regime failures: correlated deleveraging by same-strategy leveraged investors forces synchronized selling of liquid momentum names; prices overshoot then snap back when forced selling exhausts (diagnostic: multi-day losses at regular short intervals defy random walk) | SOURCED | VN-UNKNOWN | agnostic (risk-management framing) | 2015 global cross-asset quant (Pedersen; AQR Aug-2007 & Sep-Oct-2008 momentum crashes) | Pedersen, "Efficiently Inefficient" (2015), Preface + Ch.9 — liquidity spiral / momentum crash mechanism | MECHANISM: funding-liquidity spiral — margin calls/redemptions → forced sale of most-liquid positions → correlated price drop → more margin calls (self-reinforcing); reverses on exhaustion. TRIAGE: BELIEF, Lane B — NON-BACKTESTABLE retrospectively; no controlled test available on whether a given drawdown was a liquidity event. Advisory only. FABLE GATE: PASS. RE-SLOTTED: originally filed as S21 in domain copy (v26, 2026-07-06); re-slotted to S25 in canonical because S21 slot was occupied by fixed stop-loss (PARKED 2026-07-11) before domain copy was reconciled. MANDATORY ANNOTATION: S25 may NEVER be cited to argue for overriding C1 ("it's only a liquidity event, keep signals on") — CALIBRATED C1 outranks SOURCED S25 per source-of-truth.md hierarchy. VN-UNKNOWN: VN margin-financing concentration and correlated-deleveraging precondition unverified in VN context. Lane B calibration: if A3_RS experiences a multi-day synchronized drawdown across momentum names with subsequent snap-back, that is 1 CONFIRM datapoint (diagnostic: correlated losses, not fundamental deterioration). | 2026-07-15 (re-slot from domain v26 entry 2026-07-06) | STRUCTURAL — quarterly review cadence | Complements C1 bear-gate (S25 provides interpretive layer on crash causation; C1 is action gate — different levels, no conflict). Complements S11 (Lo AMH — S25 explains the mechanism of correlated shocks that AMH predicts will wipe identical-behavior agents). CROSS-REF S26 (Pedersen edge decay — complementary, independently falsifiable). |
```

### Step 3 — Insert S26 row AFTER the S25 row

Place the following row immediately after S25, still before the `---` separator:

```
| S26 | A live edge (e.g. A3_RS) decays gradually toward risk-adjusted breakeven as competing capital chases it — expected alpha = marginal compensation for costs+risk, not a step-function to zero | SOURCED | VN-UNKNOWN | agnostic (edge-monitoring framing) | 2015 global quant equilibrium theory (Pedersen) | Pedersen, "Efficiently Inefficient" (2015), Introduction — efficiently-inefficient equilibrium | MECHANISM: competitive equilibrium — capital enters until net-of-cost expected alpha equals compensation required for strategy's costs and risks; edge narrows smoothly. TRIAGE: BELIEF, Lane B — NON-BACKTESTABLE as forward proposition; makes monitorable directional prediction (narrowing MAR trend over time). FABLE GATE: PASS + KEEP_AS_INDEPENDENT (not merged into S11 — independently falsifiable: a sudden step-death of A3_RS alpha would weaken S26 while leaving S11 intact; one belief ID = one falsifiable unit). RE-SLOTTED: originally filed as S22 in domain copy (v26, 2026-07-06) with note KEEP_AS_S22; re-slotted to S26 in canonical because S22 slot was absent from canonical and reserved for NearEntry timing result. CROSS-REF: S11 (Lo AMH — complementary framing; S11=evolutionary adoption mechanism; S26=competitive equilibrium mechanism; independently falsifiable). Monitor: A3_RS MAR trend across quarterly backtest cycles as primary observable for directional prediction. Lane B calibration: sustained declining trend in A3_RS MAR over ≥4 cycles with no regime explanation = 1 CONFIRM. | 2026-07-15 (re-slot from domain v26 entry 2026-07-06) | STRUCTURAL — quarterly review cadence | CROSS-REF S11 (Lo AMH — complementary framing, independently falsifiable). CROSS-REF S25 (Pedersen momentum crash — same author, complementary mechanism). No hard conflict with any calibrated belief. |
```

### Step 4 — Update S11 conflicts field in canonical

Find the S11 row in the canonical. Its conflicts field currently ends with:
```
C1 machine rule wins per source-of-truth.md hierarchy
```
(The canonical's S11 does NOT have a CROSS-REF S22 line — this is expected; S22/Pedersen was never in the canonical before this patch.)

Append to the end of S11's conflicts cell:
```
 CROSS-REF S26 (SOURCED 2026-07-15 re-slot from domain v26): Pedersen competitive equilibrium mechanism — complementary, independently falsifiable. Sudden step-death of A3_RS alpha would weaken S26 while leaving S11 intact.
```

### Step 5 — Verify the resulting table

After inserting, the end of the `§ Sourced Beliefs` table should read:
```
| S21 | A fixed initial stop-loss... | PARKED | ... |
| S25 | Momentum crashes are liquidity events... | SOURCED | VN-UNKNOWN | agnostic ... |
| S26 | A live edge (e.g. A3_RS) decays gradually... | SOURCED | VN-UNKNOWN | agnostic ... |

---

## § VN-Subsumed Beliefs
```

Confirm S21 row is UNCHANGED (still PARKED, still fixed stop-loss content).

### Step 6 — Update the version header

Change line 2 of the canonical brain from:
```
# v29 | 2026-07-11 | 5 CALIBRATED / 6 SOURCED / 5 AXIOMATIC / 1 INVALIDATED / 2 VN-SUBSUMED / 1 VN-THIN / 1 TESTED / 5 DEGRADING-REJECT / 1 VN-DEGENERATE / 1 PARKED
```
To:
```
# v30 | 2026-07-15 | 5 CALIBRATED / 8 SOURCED / 5 AXIOMATIC / 1 INVALIDATED / 2 VN-SUBSUMED / 1 VN-THIN / 1 TESTED / 5 DEGRADING-REJECT / 1 VN-DEGENERATE / 1 PARKED
```
(SOURCED count increases from 6 to 8: +S25, +S26)

### Step 7 — Add changelog entry

At the TOP of the `## § Changelog` table, insert a new row:

```
| 2026-07-15 | v30 | Patch 4 corrected: re-slot Pedersen beliefs from domain copy (v26) to canonical. S25 SOURCED filed — Pedersen momentum crash/liquidity spiral (Lane B, NON-BACKTESTABLE; originally filed as S21 in domain copy 2026-07-06; re-slotted because canonical S21 slot was occupied by fixed stop-loss PARKED 2026-07-11). S26 SOURCED filed — Pedersen efficiently-inefficient equilibrium / edge decay (Lane B, NON-BACKTESTABLE; originally filed as S22 in domain copy 2026-07-06 with KEEP_AS_S22 Fable note; re-slotted because S22 reserved for NearEntry timing result). S11 conflicts field updated: CROSS-REF S26 added. Header: 6 SOURCED → 8 SOURCED. Investigation: 00. Command Center/PATCH4_INVESTIGATION_20260715.md. |
```

---

## PATCH 4B — Fix Domain CLAUDE.md Relative Path
**Target file:** `D:\V\0. VN Agent System\.claude\CLAUDE.md`
**Action:** Change Brain path from relative to absolute
**Prerequisite:** None — can be applied before or after 4A, but MUST be applied before 4C
**Safety:** Change only the Brain row in the System Architecture table. Do not touch any other line.

### Step 1 — Locate the exact line

Open `D:\V\0. VN Agent System\.claude\CLAUDE.md`. Find line 14 (the Brain row in the System architecture table):

```
| Brain | `.claude/brains/vn-trading-advisor/` | Cortex belief system |
```

### Step 2 — Replace with absolute path

Change that line to:

```
| Brain | `D:\V\.claude\brains\vn-trading-advisor\` | Cortex belief system |
```

### Step 3 — Verify

After the edit, confirm the file still renders as a valid markdown table. The Brain row should be:
```
| Brain | `D:\V\.claude\brains\vn-trading-advisor\` | Cortex belief system |
```

No other lines should change.

### Why this fixes the root cause

After this change, any Claude Code or Cursor session running with `D:\V\0. VN Agent System\` as CWD will resolve the Brain path to `D:\V\.claude\brains\vn-trading-advisor\` — the canonical. The domain copy will no longer be silently read or written by `/vn-review` commands or session-start checklists.

---

## PATCH 4C — Delete Domain Copy
**Target file:** `D:\V\0. VN Agent System\.claude\brains\vn-trading-advisor\knowledge.md`
**Action:** DELETE this file
**Prerequisite — MUST apply 4A and 4B first:**
- 4A must be complete: Pedersen beliefs are now in canonical as S25/S26 (no content is lost)
- 4B must be complete: CLAUDE.md path fixed so no session will recreate the domain copy
**V-ONLY:** Yes. Do not delegate deletion to Cursor without explicit V approval.

### Step 1 — Verify prerequisites are met

Before deleting, confirm both:
1. Canonical brain (`D:\V\.claude\brains\vn-trading-advisor\knowledge.md`) now contains S25 and S26 rows
2. Domain CLAUDE.md (`D:\V\0. VN Agent System\.claude\CLAUDE.md`) line 14 shows the absolute path `D:\V\.claude\brains\vn-trading-advisor\`

Only proceed if both checks pass.

### Step 2 — Delete the domain copy

```
Delete: D:\V\0. VN Agent System\.claude\brains\vn-trading-advisor\knowledge.md
```

In Windows Explorer: navigate to `D:\V\0. VN Agent System\.claude\brains\vn-trading-advisor\`, right-click `knowledge.md`, Delete (or Shift+Delete to skip Recycle Bin).

Via terminal:
```cmd
del "D:\V\0. VN Agent System\.claude\brains\vn-trading-advisor\knowledge.md"
```

### Step 3 — Verify deletion

```cmd
dir "D:\V\0. VN Agent System\.claude\brains\vn-trading-advisor\"
```

Expected: file `knowledge.md` is gone. The directory may remain empty — that is fine (or it can also be deleted if empty, but it is not required).

### Step 4 — Confirm canonical is intact

```cmd
python -c "
with open('D:/V/.claude/brains/vn-trading-advisor/knowledge.md') as f:
    c = f.read()
assert 'v30' in c, 'VERSION WRONG'
assert 'S25' in c and 'Momentum crashes are liquidity events' in c, 'S25 MISSING'
assert 'S26' in c and 'decays gradually toward risk-adjusted breakeven' in c, 'S26 MISSING'
assert 'S21' in c and 'fixed initial stop-loss' in c, 'S21 CORRUPTED'
print('VERIFY PASS: canonical v30, S25 and S26 present, S21 intact')
"
```

Expected output: `VERIFY PASS: canonical v30, S25 and S26 present, S21 intact`

---

## APPLICATION ORDER SUMMARY

```
Step 1: Apply PATCH 4A — insert S25, S26 into canonical brain; update S11 cross-ref; bump to v30
Step 2: Apply PATCH 4B — fix domain CLAUDE.md relative path → absolute
Step 3: Run Step 4 verification from PATCH 4C to confirm canonical is intact
Step 4: Apply PATCH 4C — delete domain copy
```

4B can be applied at any point before 4C. 4A must be complete before 4C.

---

## POST-PATCH STATE

After all three patches:

| Item | Before | After |
|------|--------|-------|
| Canonical brain version | v29 | v30 |
| Canonical S25 | ABSENT | Pedersen momentum crash (SOURCED, Lane B) |
| Canonical S26 | ABSENT | Pedersen edge decay (SOURCED, Lane B) |
| Canonical S21 | Fixed stop-loss (PARKED) | UNCHANGED |
| Domain copy | EXISTS (v26, stale, conflict) | DELETED |
| Domain CLAUDE.md Brain path | `.claude/brains/...` (relative) | `D:\V\.claude\brains\...` (absolute) |
| Sessions in VN Agent CWD | Resolve to domain copy | Resolve to canonical |

---

## WHAT THIS PATCH DOES NOT DO

These items were in the original Patch 4 but are NOT part of this corrected patch. They require separate work (full Patch 4 rewrite or new patches):

- S22 (NearEntry timing, KEEP_BASE) — still only in knowledge_ACTIVE.md. Not added here; reserved slot.
- S21 NearEntry Zone sweet spot — not added here; reserved for future patch.
- S20 (Minervini climax-top) — not added here; in domain copy only; domain copy will be deleted.
  **NOTE:** After PATCH 4C deletes the domain copy, S20 content is LOST unless separately re-filed.
  V should decide whether to re-register S20 in the canonical before deleting the domain copy.
- PA-0xx entries, S15-VN, S23, S24, S23 framework beliefs — all require separate patch targeting canonical.
- Version bump beyond v30 — happens in those subsequent patches.

**S20 LOSS RISK:** The domain copy (v26) contains S20 (Minervini climax-top exhaustion, SOURCED, with Fable gate CONDITIONAL mandate for degeneracy pre-check). This belief does NOT exist in the canonical. When 4C deletes the domain copy, S20 is orphaned. If V wants to preserve S20, it should be re-registered in the canonical before running 4C. This patch does not include S20 because: (a) the task scope is Pedersen beliefs only; (b) S20 has a mandatory gate-zero pre-check before testing — it is advisory-only and low urgency.

---

## IN PLAIN ENGLISH

The original brain sync patch was aimed at the wrong file. It would have edited a stale backup copy of the belief system, leaving the real (canonical) file untouched — and if applied blindly, would have corrupted the canonical by creating duplicate belief IDs. This corrected version has three parts. First, two Pedersen beliefs about how momentum crashes work and how edge decays over time are added to the real belief file as slots S25 and S26. Second, a one-line fix in the VN Agent folder's config file changes a shortcut path to an absolute path, so future sessions stop accidentally reading and writing the stale backup. Third, once those two fixes are confirmed, the stale backup is deleted. V must apply these three steps in order.
