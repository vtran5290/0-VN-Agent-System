# Pre-Registration: S19 — VN Intra-Sector Relative Strength Selection
# Belief ID: S19
# Status: INVALIDATED — scope: S1-deployment context (2026-07-05)
# Council verdict (opus + fable, 2026-07-05): INVALIDATED [S1-context]. Unanimously approved Option B.
#   Opus: mechanism reversal (IS+/OOS−, N=253, independent variable expressed, pre-registered gate)
#         constitutes INVALIDATED in deployment context. −0.0791 OOS spread carries adversarial information;
#         VN-SUBSUMED predicts null, not reversal.
#   Fable: FRAMEWORK HOLDS. INVALIDATED + scope annotation covers mechanism-reversal cases. No new
#         lifecycle state (would be hypertrophy + gaming vector). Annotation added to verification-harness.md.
# Scope note: Ramsey's principle is INVALIDATED for the S1-filtered VN deployment context as tested.
#   The unscoped parent principle ("buy strongest in sector, non-S1 pool") is untested — file as fresh
#   SOURCED if ever pursued with a separate pre-registration.
# Falsification pathway: FIRED. Expansion gate mechanism criterion: 1/1 satisfied.
# Inverse finding (not formalized): laggard > leader in S1 co-sector pool — potential new hypothesis.
#   Per Boris anti-hypertrophy: do NOT formalize until 2nd occurrence or explicit user approval.
# Date: 2026-07-05
# Prepared by: Claude CLI (Schwager hidden gems extraction session — completion pass)
# Source: Scott Ramsey, Hedge Fund Market Wizards (2012), Ch.4 ("Buy Strength, Not Weakness")
#   — "Ramsey will always buy the strongest market in a sector for long positions and sell
#      the weakest market in a sector for short positions. Many novice traders make the error
#      of buying laggards as a proxy, assuming they 'haven't yet made their move.'"
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor runs the harness.
# No gate changes after data is seen.

---

## Belief statement (LOCKED)

"Within the A3_RS OOS candidate pool, when multiple stocks from the same sector appear as simultaneous momentum candidates on the same signal day, the stock with the highest intra-sector relative strength (RS rank among same-sector peers) will outperform the same-sector laggard on forward returns — and selecting only the sector leader (not the laggard) improves OOS MAR."

VN operationalization:
- On any given A3_RS signal day t where ≥2 stocks from the same sector fire simultaneously:
  - Rank the co-sector candidates by their RS score (or A3_RS momentum score)
  - "Sector leader" = highest RS rank in the cohort; "sector laggard" = lowest RS rank
  - Test: does holding the sector leader vs the sector laggard produce higher forward returns?
- Signal output: intra-sector RS ranking produces a priority-weighted candidate list on days with multiple same-sector signals

Architecture note: S19 is a RANKING SIGNAL within the A3_RS candidate pool, not an entry/exit signal itself. It determines which stocks to prefer when A3_RS fires on multiple same-sector candidates simultaneously. It does NOT change entry criteria, stop logic, or regime gating.

---

## Key degeneracy concern: C3 VIN distortion

C3 (CALIBRATED) states: VIC/VHM/VRE dominate size calculations in broad VN momentum screens. The S19 degeneracy risk is symmetric: if VIC/VHM/VRE ARE ALWAYS the top RS stocks in their respective sectors (real estate, construction materials), then S19 = "always pick VIC/VHM/VRE" — which would be degenerate because the IV (intra-sector RS rank variation) never varies.

**S19 degeneracy is VN-SUBSUMED if:** within every sector, the same large-cap name(s) always rank #1 across the entire OOS period. The independent variable (which stock in the sector ranks highest) must vary meaningfully across time.

---

## Data requirements (check before running)

1. **Sector membership:** same as S18 — HOSE/HNX sector classification per stock. S19 can share sector-membership data with S18 if both are pre-checked in the same Cursor batch.

2. **Co-sector signal cohort:** on any given signal day, identify all A3_RS candidates where sector is the same. S19 only activates when the cohort size ≥ 2 (need at least one leader vs one other to rank).

3. **RS score for ranking:** use the A3_RS momentum score (same metric used for the primary A3_RS ranking). Do NOT introduce a new RS definition — S19 uses the existing A3_RS score for intra-sector comparison.

4. **Minimum occurrence count:** the co-sector signal cohort (≥2 same-sector candidates on the same day) must occur ≥30 times in the OOS period to produce a valid N_OOS. Pre-check must verify this frequency.

---

## Degeneracy pre-check — COMPLETE (2026-07-05, batch cortex_schwager_s17_s18_s19_precheck_batch.py)

**VERDICT: EXPRESSIBLE**

| Metric | Value | Assessment |
|--------|-------|------------|
| Co-sector signal days OOS (≥2 same-sector) | **1001** | ✓ well above ≥30 floor |
| VIN check (VHM/VRE/VIC in BDS) | 4.1% leader stability | ✓ NOT degenerate — leader rotates |
| Most stable sector | Textile 40%, Tech 38.1% | ⚠️ monitor (not degenerate, but S19 adds less value there) |
| Most variable sectors | BDS 4.1%, Consumer 6.4%, Oil_Gas 9.3% | ✓ strongest S19 application |

**VIN finding:** VHM/VRE/VIC each show only 4.1% leader stability in BDS (leader rotates ~24× across the OOS period). C3 distortion does NOT make S19 degenerate. The independent variable (which stock leads intra-sector) varies meaningfully.

---

## Gate parameters (LOCKED 2026-07-05)

**Test design:** S19 as intra-sector priority ranking. On days with ≥2 same-sector A3_RS+S1 signals, select only the top RS-ranked stock (sector leader); skip the laggard.

```
Baseline:       S1-filtered OOS MAR = 1.7844 (S19 is a ranking refinement within S1-filtered pool)
k = 1 candidate (binary — select leader, skip laggard)
k-adjustment:   0 (k=1)

G1a (aggregate MAR gate): S1+S19-selected OOS MAR ≥ S1-only baseline × 1.02 = 1.820
                (2% improvement over S1 alone — aggregate system must improve)
G1b (absolute): S1+S19-selected OOS MAR ≥ 0.516
G2 (mechanism gate): (a) leader OOS MAR ≥ laggard OOS MAR on the co-sector subset
                     AND (b) mean leader forward return > mean laggard forward return by > 0.20% per trade
                     FAIL on G2 = mechanism not confirmed; report verdict as MECHANISM-FAIL even if G1a passes
                     (G1a could pass due to portfolio composition effects, not actual leader selection value)
G3 (sample floor): N_OOS co-sector cohort days ≥ 30 (confirmed: 1001 — ✓)
Neg-OOS-cap: if S1+S19 OOS MAR < 0 → PARKED
Sector-level gate: if <2 sectors show leader > laggard → signal does not generalize; NEUTRAL verdict

High-stability exemption: sectors with >35% leader stability (Textile, Tech) may degenerate for S19;
    report sector-level leader premium separately; do not let stable-sector degenerate cases mask
    the variable-sector signal.
```

Gate relabel note (2026-07-05, opus REDIRECT): G1a was previously a dual-condition (aggregate MAR AND leader>laggard MAR). Split into G1a (aggregate only) + G2 mechanism (leader>laggard MAR condition absorbed here). No threshold changes. The split allows clean attribution on FAIL: a G1a FAIL is an aggregate MAR shortfall; a G2 FAIL is a mechanism failure (leader selection does not work) even if aggregate MAR happens to improve by other means.

**Attribution required:** report G1a leader-vs-laggard spread by sector. BDS/Consumer/Oil_Gas
(low stability) are the primary S19 value sectors. Report these separately from Textile/Tech.

---

## Degeneracy pre-check (original section — now complete — ANSWERED BELOW)

**Pre-check Question 1: Cohort frequency — does S19 fire enough?**
- In the A3_RS OOS period: count signal-days where ≥2 stocks from the SAME sector fire simultaneously
- If this count < 30 across the full OOS → VN-THIN → pre-reg cannot be locked (defer until universe expands)
- Target minimum: ≥30 co-sector co-signal days in the OOS period

**Pre-check Question 2: VIN distortion check (C3 interaction)**
- For each qualifying sector in the A3_RS OOS pool: list the top RS-ranked stock by month
- Check: is the same stock always #1 in each sector, or does the leader rotate?
- Threshold: if the same stock holds #1 rank in a sector for >80% of all co-signal days → that sector's signal is effectively degenerate for S19 (picks the same stock every time → not testing intra-sector selection)
- If 2+ sectors have rotation: S19 is EXPRESSIBLE for those sectors even if others are degenerate
- Report: sector-level leader stability score (fraction of co-signal days dominated by a single stock)

**Pre-check Question 3: Leader vs laggard baseline return spread**
- In the IS period: for co-sector cohort days, compute mean forward return of sector leader vs sector laggard
- If leader forward return > laggard forward return by any margin: supports S19
- If leader ≈ laggard (spread < 0.2% mean forward return): signal provides minimal benefit

**Pre-check verdict:**
```
COSECTOR_COHORT_DAYS_OOS:       1001 (≥30 threshold PASS)
VIN_LEADER_STABILITY_BANKING:   11.2% (Banks — NOT degenerate)
VIN_LEADER_STABILITY_REALESTATE: 4.1% (BDS — VIC/VHM/VRE rotate; NOT >80% single-name lock)
VIN_LEADER_STABILITY_OTHERSECTORS: max 40% (Textile); all sectors <80% degeneracy threshold
IS_LEADER_VS_LAGGARD_SPREAD:    not computed in batch (harness IS slice)
VERDICT: EXPRESSIBLE
Batch report: knowledge/backtests/2026-07-05_schwager_s17_s18_s19_precheck_batch.md (2026-07-05)
C3 interaction: VIN names share BDS sector but leader rotates — S19 not collapsed to always-pick-VIN.
```

---

## Lane A test design (activate ONLY if pre-check = EXPRESSIBLE)

### Candidate parameters (k=3 per protocol)

| Candidate | Signal condition | Rank criterion | Hypothesis |
|-----------|-----------------|----------------|------------|
| C1_leader_only | On co-sector-signal days: hold ONLY the top-RS-ranked stock; skip all same-sector co-signals | Top RS only | Leader selection strictly outperforms holding all co-sector candidates |
| C2_leader_weight | On co-sector-signal days: hold all candidates, but give 2× weight to the top-RS-ranked stock | Weighted | Leader receives double allocation; laggard half-allocation — softer preference |
| C3_exclude_laggard | On co-sector-signal days: hold top 50% of RS-ranked candidates; skip bottom 50% | Quartile filter | Exclude clear laggards, keep the rest |

Baseline: A3_RS standalone (all co-sector candidates held equally); compare each candidate to this baseline on CO-SECTOR SIGNAL DAYS ONLY (not the full A3_RS OOS universe — S19 only applies when ≥2 same-sector signals co-fire).

**Alternative baseline if C1-C3 thin:** if co-sector cohort days are ≥30 but <60 (borderline N), reduce to k=2 candidates (C1 + C2 only) to preserve statistical power.

### Test universe
- ONLY A3_RS OOS signal days where the co-sector condition fires (≥2 same-sector candidates simultaneously)
- IS period: same as S1/S2 IS period
- OOS period: sub-A 2020-2022, sub-B 2023-2026 (same as existing)

### Baseline
- A3_RS standalone on co-sector-signal-day subset (not the full A3_RS OOS MAR 0.8386 — the baseline is conditioned on the same co-sector days to ensure like-for-like comparison)

### Gate parameters (LOCK after pre-check, BEFORE Cursor runs harness)

```
G1a (relative): OOS MAR of selected candidate ≥ co-sector-subset baseline × 1.10
                (10% relative improvement floor; higher than single-filter because S19 makes
                an active stock SELECTION decision, not just a filter — higher bar justified)
G1b (absolute): OOS MAR ≥ 0.516 (standard absolute floor)
G2 (C3 VIN guard): leader-selection result must NOT be driven >60% by a single stock
                   in any single sector. If one stock accounts for >60% of S19's OOS edge,
                   the result is degenerate (C3 VIN distortion expressed in outcomes).
N_OOS floor: ≥ 30 co-sector-signal-day instances per candidate (separate from full-OOS N)
Borderline rule: G1a margin < 0.03 MAR units → CONDITIONAL-ADVANCE (selection edge too thin to act on)
Standing guardrail: if both baseline AND candidate OOS MAR are negative → CONDITIONAL-ADVANCE only
Window scoping: all gate thresholds calibrated on same OOS window; no cross-window reuse
```

G2 (VIN guard) rationale: even if pre-check Q2 shows rotation, outcomes could still be VIN-driven if VIN names have systematically higher forward returns due to liquidity and size (not RS-selection quality). G2 checks the attribution of where OOS edge comes from.

---

## Interaction test design

**S19 × S18 (sector persistence):**
- S18 identifies which sectors to prioritize for A3_RS entry; S19 identifies which stock within that sector to prefer
- Combined: S18 fires on sector t → S19 selects the highest RS stock in that sector for entry on day t+1
- Gate: OOS MAR of (S18-filtered sector signals × S19 intra-sector leader selection) ≥ S18 standalone MAR × 1.04
- Test only after BOTH S18 and S19 independently CALIBRATED

**S19 × C3 (VIN distortion calibrated belief):**
- C3 states that VIN names dominate size calculations. G2 (VIN guard) above directly tests if VIN also dominates S19 performance attribution.
- If G2 fails: S19 does not prove intra-sector RS selection — it proves VIN always wins (C3 mechanism, already CALIBRATED)
- If G2 passes: S19 provides genuinely new selection information beyond C3

**S19 × S1 (52wk high proximity):**
- S1 prefers stocks near their 52-week high; S19 prefers the highest RS stock in the sector. These are highly correlated by construction (highest RS in a sector is usually near its 52wk high).
- Expected: M2 overlap ~70-80% → test separately but document overlap carefully
- If overlap > 80%: S19 may be a proxy for S1 at the sector-cohort level → DEGRADING-REJECT risk

**S19 × C1 (bear gate):**
- C1 is upstream; S19 applies within C1-permitted (bull) periods only. No interaction test needed.

---

## WIP cap check

Per sources.md WIP cap:
- S19 pre-registration (this document) reduces the untested-without-prereg backlog by 1
- After S18 + S19 pre-regs: backlog ~5 (below the pause threshold of 6 → OPEN for limited extraction)
- Confirm in sources.md before any new extraction session

---

## Files to create (Cursor, after pre-check passes)

1. `pp_backtest/cortex_schwager_s19_buy_strongest.py` — harness script (after pre-check passes)
2. `knowledge/backtests/2026-07-05_schwager_s19_buy_strongest_degeneracy.md` — pre-check results (Q1-Q3 answers)
3. `knowledge/backtests/2026-07-05_schwager_s19_buy_strongest_gates_addendum.md` — gates addendum (after pre-check, before OOS run)

Optional (if S18 and S19 pre-checks can be batched):
4. `pp_backtest/cortex_schwager_s18_s19_precheck_batch.py` — combined pre-check script (S18 sector breadth + S19 cohort frequency + VIN leader stability) to share sector-membership data and reduce Cursor runs

---

## VN-specific considerations

**Thin sector cohorts:** VN has fewer liquid stocks per sector than US. The banking sector is the most liquid (VCB, BID, CTG, MBB, TCB, ACB, VPB, HDB, TPB, STB, SSB, LPB, OCB = 13+ names), making it the sector most likely to produce co-signal cohorts. Real estate sector (VHM, NVL, DXG, KDH, NLG, PDR, BCM = 7-10 names) is borderline. Energy and steel sectors may have too few A3_RS-eligible names (potential VN-THIN risk for these sectors specifically).

**A3_RS pre-selection already does sector-level work:** the existing A3_RS ranking is market-wide, not sector-neutral. High-RS stocks in a concentrated bull sector will naturally all appear in A3_RS candidates. S19 adds a within-cohort selection rule — but the co-sector cohort must actually be large enough to benefit from ranking (if A3_RS only picks 1-2 stocks per sector, there's nothing to rank).

**Layman description:** "When multiple stocks from the same sector all look good on the same day (by the momentum scan), should you buy all of them or just the strongest? Schwager's Scott Ramsey says buy only the strongest. S19 tests if this rule improves returns in the VN market — specifically, does picking the top-ranked momentum stock within a sector (vs any random one) produce better forward returns?"

---

## HARD RULES

- Do NOT run the harness before pre-check Q1, Q2, and Q3 are answered
- Do NOT change thresholds after seeing OOS results
- G2 (VIN guard) is mandatory — a result driven by VIC/VHM/VRE dominance is NOT evidence for S19
- k=3 candidates may reduce to k=2 if co-sector cohort N_OOS < 60 — pre-commit this decision before checking OOS data

---

## References
- Belief source: Ramsey, Hedge Fund Market Wizards (2012), Ch.4 — HFMW L1915
- Extraction document: D:\V\knowledge_base\2026-07-05_Schwager_HiddenGems_Extraction.md (GEM-HFMW-7)
- Knowledge base: D:\V\.claude\brains\vn-trading-advisor\knowledge.md § S19 (v17)
- Sources log: D:\V\.claude\brains\vn-trading-advisor\sources.md
- S18 pre-reg: D:\V\0. VN Agent System\knowledge\backtests\2026-07-05_schwager_s18_sector_persistence_prereg.md
- C3 calibrated belief: knowledge.md § Calibrated (VIN distortion)
- Verification: verification-harness.md § VN Agent System → promotion gate design section
