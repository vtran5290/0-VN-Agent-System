# Gates Addendum: S19 — VN Intra-Sector Relative Strength Selection
# Written: 2026-07-05 (after batch pre-check)
# Pre-check batch report: knowledge/backtests/2026-07-05_schwager_s17_s18_s19_precheck_batch.md
# Pre-reg: knowledge/backtests/2026-07-05_schwager_s19_buy_strongest_prereg.md
# Status: PRE-CHECK COMPLETE → gates locked → READY FOR HARNESS

---

## Pre-check summary

**Overall verdict: EXPRESSIBLE**

| Pre-check item | Result | Threshold | Status |
|---|---|---|---|
| Co-sector cohort days (OOS) | **1001** | ≥30 required | ✓ PASS (33×) |
| VIN leader stability — BDS (VIC/VHM/VRE) | 4.1% each | <80% per sector | ✓ PASS (not degenerate) |
| VIN leader stability — Banks | 11.2% | <80% per sector | ✓ PASS |
| VIN leader stability — max across all sectors | 40.0% (Textile) | <80% per sector | ✓ PASS |
| IS leader vs laggard spread | NOT COMPUTED | >0.2% preferred | ⚠️ [DEFERRED — harness IS slice] |

---

## VIN distortion: NOT expressed in pre-check

The key degeneracy concern for S19 was C3 (VIN distortion): if VIC/VHM/VRE always rank #1 in their sector (BDS), then S19 degenerates to "always pick VIN" and provides no new information beyond C3.

**Pre-check result:** BDS leader stability = 4.1% per VIN name. VIC, VHM, and VRE each dominate the BDS sector leader position on only ~4% of co-sector signal days. The BDS sector leader rotates across names.

This means:
- S19 is NOT pre-collapsed to C3 (VIN always wins)
- The intra-sector selection mechanism has genuine variation in BDS
- G2 (VIN guard at harness) still applies — leader stability in pre-check ≠ outcome attribution at harness

**All sectors pass the <80% degeneracy threshold.** Maximum single-sector stability is 40.0% (Textile), which is well below the degenerate threshold and indicates meaningful rotation.

---

## IS leader vs laggard spread: deferred to harness

The batch pre-check computed cohort frequency and VIN leader stability but did NOT compute the IS leader vs laggard return spread (pre-reg Q3: "mean forward return of sector leader vs sector laggard in IS period"). This computation requires the full IS return slice and was deferred to the harness.

**Harness instruction:** compute this as the FIRST output of the IS slice before proceeding to OOS.
- If IS spread < 0.2% (leaders barely outperform laggards in IS): flag as [IS-SPREAD-THIN] in harness output. The OOS run still proceeds (pre-check EXPRESSIBLE stands), but a thin IS spread is a yellow flag for expected OOS G1a margins.
- If IS spread ≥ 0.2%: confirms S19 hypothesis holds in IS. OOS run proceeds normally.

**This is not a new gate** — the pre-reg did not set a formal IS-spread gate. It is diagnostic information for interpreting OOS results.

---

## Locked gate parameters (NO CHANGES from pre-reg)

```
G1a (relative): OOS MAR ≥ co-sector-subset baseline × 1.10
                (10% relative floor; active selection, higher bar than single filter)
G1b (absolute): OOS MAR ≥ 0.516
G2 (VIN guard): leader-selection edge NOT driven >60% by single stock in any single sector
                (even if pre-check Q2 shows rotation, outcomes may still be VIN-driven)
N_OOS floor:    ≥ 30 co-sector-signal-day instances per candidate
Borderline rule: G1a margin < 0.03 MAR units → CONDITIONAL-ADVANCE (edge too thin)
Standing guardrail: if both baseline AND candidate OOS MAR are negative → CONDITIONAL-ADVANCE only
Window scoping: all gate thresholds calibrated on same OOS window; no cross-window reuse
```

**Candidate count: maintain k=3** — co-sector cohort OOS = 1001 days (>> 60 threshold for k=2 alternative), so k=3 candidate set (C1_leader_only, C2_leader_weight, C3_exclude_laggard) proceeds as planned.

**Baseline reminder:** the co-sector-subset baseline is NOT the full A3_RS OOS MAR (0.8386). The baseline must be computed as A3_RS standalone MAR conditioned on the SAME co-sector-signal days — the subset where ≥2 same-sector candidates fired simultaneously. This is a conditional baseline, and Cursor must compute it from the co-sector cohort, not use the global MAR figure.

---

## Additional pre-check context

**Co-sector cohort breakdown by sector (expected ordering):**
- Banking sector: most liquid, most A3_RS candidates, expected largest share of co-sector cohort days (VCB/BID/CTG/MBB/TCB/ACB co-fire most often)
- BDS sector: VIC/VHM/VRE/NVL/DXG/KDH — moderate co-signal frequency
- Securities sector: VND/SSI/HCM — varies with market regime
- Other sectors: infrequent co-signals; may have N < 30 per sector individually → report per-sector N in harness output

**S1 × S19 overlap (expected ~70-80%):** the pre-reg flagged high expected overlap between S1 (52wk high proximity preference) and S19 (highest RS in sector). Harness should compute the overlap fraction explicitly and flag if >80% — at that level S19 is likely a proxy for S1 at sector-cohort level rather than providing independent selection information.

---

## Harness instructions

**Script to create:** `pp_backtest/cortex_schwager_s19_buy_strongest.py`

**Run order:**
1. IS slice: identify co-sector signal cohorts → compute IS leader vs laggard return spread → report [IS-SPREAD-THIN] if <0.2%
2. Co-sector baseline: compute A3_RS MAR conditioned on co-sector-signal days only (this is the G1a denominator)
3. OOS slice: per candidate (C1/C2/C3) → G1a, G1b, G2 (VIN attribution) per candidate
4. S1 overlap check: compute fraction of S19 leader selections that also satisfy S1 condition → flag if >80%
5. Output: `knowledge/backtests/s19_harness_results.md` with per-candidate gate verdicts + G2 attribution table

**G2 attribution computation:**
- For each OOS sector: compute what fraction of S19's OOS edge (return contribution) comes from the single most-selected stock
- If that fraction > 60% for any sector → G2 FAIL for that sector; note which sectors drive G2 failure
- A result is G2-VALID if no single stock drives >60% of edge in any single sector

**Batching:** S19 and S18 harness scripts share sector-membership data. Batch if practical to avoid re-computing sector classification.

---

## Interaction test queue (post-CALIBRATED only)

1. S19 × S18 (natural combination): S18 selects which sector → S19 selects which stock within that sector. Gate: (S18 × S19) MAR ≥ S18 standalone MAR × 1.04. Minimum N_OOS ≥ 20 (will be thin — flag if VN-THIN risk).
2. S19 × C3 (VIN distortion): G2 at harness directly tests this interaction.
3. S19 × S1 (52wk high proximity): document overlap fraction; if overlap <80%, test if combined S1+S19 filter produces additive improvement.
4. S19 × C1 (bear gate): upstream; no interaction test needed.

---

## References
- Pre-reg: 2026-07-05_schwager_s19_buy_strongest_prereg.md
- Batch pre-check: 2026-07-05_schwager_s17_s18_s19_precheck_batch.md
- S18 gates addendum: 2026-07-05_schwager_s18_sector_persistence_gates_addendum.md
- C3 calibrated belief: .claude/brains/vn-trading-advisor/knowledge.md § C3 (VIN distortion, CALIBRATED)
- Verification harness: .claude/rules/verification-harness.md § VN Agent System → promotion gate design
- Knowledge base: .claude/brains/vn-trading-advisor/knowledge.md § S19 (v17, SOURCED)
