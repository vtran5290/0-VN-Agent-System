# B_cloud Exit-Mode Research Program — Pre-Registration

**Pre-registered:** 2026-07-08
**Domain:** VN Agent System — B_cloud exit-mode research program
**Operator authorization:** User: "how about both?" (2026-07-08) — clears opus REDIRECT condition from 2026-07-08_BcloudDirection_Council.md
**Prior program:** `2026-07-07_bcloud_research_program_prereg.md` — closed as CLOSED-NEGATIVE (filters + ranking exhausted)
**Status:** PRE-REGISTERED — RESEARCH-ONLY

## Goal

OOS MAR > 2.5447 (A3+S2 benchmark) — same as prior program.
Hypothesis: partial_tp's TP1=+15% clip compresses the return distribution regardless of entry quality. Removing the clip (fixed-hold) should allow large winners to compound, materially lifting MAR.

This is a **falsification test** of the compression hypothesis. If fixed-hold barely moves MAR vs partial_tp baseline, the compression hypothesis is refuted and B_cloud closes with confidence. If MAR lifts toward ~1.0–1.8 range (estimated ceiling with better exit), it justifies a bounded exit-mode program.

---

## 1. Search Space (exit-mode class ONLY)

**Authorized changes:** Exit mode parameter only — TP1 clip ON/OFF, max_hold value.
**Locked (must not change):** Entry (EMA20/100, cloud_only), universe (ex_vin3), ranking (FIFO), max_pos=20, cost=40bps.

**Not authorized in this program:**
- Filter overlays (S1/S2) — exhausted in prior program
- Ranking mode changes — exhausted in prior program
- Universe changes
- Entry logic changes
- Any combination with filter/ranking changes

Any parameter outside the above = **new program pre-reg required**.

---

## 2. Phases

### Phase 1 — Exit-mode sweep (3 candidates)

| # | Mode | Description | TP1 | Trail | max_hold |
|---|------|-------------|-----|-------|----------|
| 1 | `fixed_60` | Short-term fixed hold | OFF | OFF | 60 bars |
| 2 | `fixed_120` | Medium-term fixed hold (decisive test) | OFF | OFF | 120 bars |
| 3 | `trail_only` | ATR trail from entry, no TP1 clip | OFF | ON (2.5×ATR from entry) | 250 bars |

**Decisive test is `fixed_120`** per opus recommendation. Others provide directional context.

Phase 1 → Phase 2 advisory gate: if best Phase 1 OOS MAR ≥ baseline + 0.200 → authorized for Phase 2. Else CLOSED-NEGATIVE.
Fire-consequence if gate fails: CLOSED-NEGATIVE (B_cloud program ends; paper monitoring continues).

### Phase 2 — Exit-mode + best ranking (conditional, requires Phase 1 advisory gate pass)

Test the winning Phase 1 exit mode combined with the best-performing Phase 2 ranking mode from the prior program (ema_dist, OOS MAR 0.4816). One candidate only.
Phase 2 → Phase 3 advisory gate: if result ≥ Phase 1 best + 0.100 → authorized for Phase 3 (full RS ranking port).
Fire-consequence if gate fails: CLOSED-NEGATIVE.

### Phase 3 — Full D3 sector-RS ranking port (conditional, requires Phase 2 advisory gate pass)

Port D3 sector-RS sort key into B_cloud with winning exit mode. Requires new build (not available in current ema_portfolio_sim).
Fire-consequence if gate fails: FAILED (formal kill; this was the final authorized phase).

---

## 3. Baseline

**B_cloud PRIMARY with partial_tp (Phase 1+2 program measured):**
- OOS MAR: **0.4698**
- OOS CAGR: 13.1%
- OOS MaxDD: -27.8%
- Windows: Full OOS 2020–2026; Sub-A 2020–2022; Sub-B 2023–2026

Baseline is recomputed fresh for each test run on the **same window** as the candidate.

---

## 4. Gates (pre-registered, locked before any run)

### G1a — Relative gate (binding)
```
candidate OOS MAR >= 0.4698 + 0.066 = 0.5357
```
Same +0.066 margin as prior program (same k-adjustment protocol, 3 candidates).

### G1b — Absolute floor (advisory)
```
candidate OOS MAR >= max(0.10, 0.4698 × 0.50) = 0.2349
```

### N_OOS minimum
```
N_OOS (full): >= 30
N_OOS (sub-A): >= 12
N_OOS (sub-B): >= 12
```

### Neg-OOS cap
Both baseline AND candidate OOS MAR negative → CONDITIONAL-ADVANCE cap (not full ADVANCE).

---

## 5. Terminal-State Taxonomy

| State | Condition |
|---|---|
| COMPLETED-SUCCESS | Any candidate OOS MAR > 2.5447 (goal met) |
| FAILED | Phase 3 best result < 2.5447 AND Phase 3 was entered |
| CLOSED-NEGATIVE | Phase advisory gate fires (Phase 1→2 or Phase 2→3) — authorized search space gated off |
| SUPERSEDED | New program pre-reg replaces this one |

**Paper monitoring (B_cloud PRIMARY in paper mode) is unaffected by any terminal state above.** Kill criterion (`2026-07-07_bcloud_kill_criterion_prereg.md`) governs production separately.

---

## 6. Program-Level Kill Criterion

If best Phase 1 OOS MAR < 0.50 (below G1b floor AND below B_cloud current baseline):
→ Compression hypothesis NOT confirmed. B_cloud is genuinely capped at current MAR levels under any exit mode.
→ Program closes as FAILED (not just CLOSED-NEGATIVE) — stronger signal that architecture is structurally limited.

---

## 7. Iteration Cap

Maximum 3 candidates per phase. Maximum 3 phases. No re-running previously-failed candidates with small parameter tweaks — that is the "sunk-cost creep" risk flagged by opus.

---

## 8. Output Paths

```
Phase 1: data/research/bcloud_exit/bcloud_exit_phase1_report.md
Phase 2: data/research/bcloud_exit/bcloud_exit_phase2_report.md
Phase 3: data/research/bcloud_exit/bcloud_exit_phase3_report.md
```

---

## 9. Parallel Track Note

This program runs in parallel with the A3_RS shadow runner track (operator authorized "both" 2026-07-08). At N=2 tracks, resource priority is operator judgment (multi-track prioritization rule; routine-library.md candidate pattern). No formal priority scoring required.

`RESEARCH_ONLY_NOT_PRODUCTION`
