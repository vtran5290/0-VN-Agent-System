# Gates Addendum: S18 — VN Sector Same-Day Persistence
# Written: 2026-07-05 (after batch pre-check)
# Pre-check batch report: knowledge/backtests/2026-07-05_schwager_s17_s18_s19_precheck_batch.md
# Pre-reg: knowledge/backtests/2026-07-05_schwager_s18_sector_persistence_prereg.md
# Status: PRE-CHECK COMPLETE → gates locked → READY FOR HARNESS

---

## Pre-check summary

**Overall verdict: EXPRESSIBLE**

| Pre-check item | Result | Threshold | Status |
|---|---|---|---|
| Qualifying sectors (≥10 members) | 8 sectors (Agri, Banks, BDS, Consumer, Logistics, Oil_Gas, Securities, Steel) | ≥3 required | ✓ PASS |
| Fire rate k=1.0 | 16.0% mean sector-days (OOS) | 15-30% target | ✓ PASS |
| Fire rate k=0.75 | 22.8% mean sector-days (OOS) | 15-30% target | ✓ PASS |
| IS continuation rate (k=1.0, up-days) | **56.3%** | >58% preferred | ⚠️ [BORDERLINE] |

---

## ⚠️ BORDERLINE FLAG — IS continuation rate

The pre-reg's Q3 criterion stated: "Should be meaningfully above 50% (>58%) to be worth pre-registering."

The batch pre-check found 56.3% mean IS continuation rate for above-threshold sector-days at k=1.0, IS 2013-2019.

**This is below the stated 58% preference but above the 50% noise floor.**

Implications for the harness:
- The G_persistence gate (≥60% OOS continuation rate) is NOW the critical gate for S18. Given IS = 56.3%, OOS persistence meeting 60% is at genuine risk.
- A CONDITIONAL-ADVANCE verdict is a plausible outcome if OOS continuation rates cluster near 57-59%.
- The k=0.75 candidate (22.8% fire rate, more events, more statistical power) may produce a more reliable persistence rate estimate than k=1.0.

**What this does NOT change:**
- EXPRESSIBLE verdict stands — sector breadth is adequate, fire rates are within target.
- Gate parameters are LOCKED (no changes from pre-reg). 56.3% IS rate is documented context, not a gate adjustment.
- The harness runs as designed. If OOS G_persistence < 60%, verdict = FAIL on that gate; if ≥60%, verdict = PASS.
- The borderline IS rate is a risk indicator, NOT a reason to relax the G_persistence threshold.

---

## Locked gate parameters (NO CHANGES from pre-reg)

```
G1a (relative): OOS MAR ≥ [A3_RS baseline × 1.08]
G1b (absolute): OOS MAR ≥ 0.516
G_persistence:  next-day sector continuation rate ≥ 60% (VN-adjusted; mandatory gate, not optional)
N_OOS floor:    ≥ 30 S18-filtered OOS signal instances per candidate
Borderline rule: G1a margin < 0.02 MAR units AND G_persistence < 65% → CONDITIONAL-ADVANCE only
Standing guardrail: if both baseline AND candidate OOS MAR are negative → CONDITIONAL-ADVANCE only
Window scoping: all gate thresholds calibrated on same OOS window; no cross-window reuse
```

**Candidate priority for harness run:** C2_thresh075 first (highest fire rate at 22.8% → most statistical power for G_persistence estimate), then C1_thresh100, then C3_thresh050.

---

## Additional pre-check context (sector-level detail)

From the batch report:
- 11 sectors qualify on IS activity proxy (broader than OOS panel ≥10 member count)
- OOS universe is HOSE-listed A3_RS-eligible names; sector composition is stable across OOS window
- Banking sector (VCB, BID, CTG, MBB, TCB, ACB, VPB, HDB, TPB, STB, SSB, LPB, OCB): most liquid, expected to dominate S18 signal volume

**±7% band check (deferred to harness):** pre-check did not compute the fraction of above-threshold sector-days where ≥20% of stocks hit the ±7% band. The harness should compute this and flag it if >30% of S18 trigger days have significant band clamping — this would indicate that the measured sector return is a lower bound on the true sector impulse.

---

## Harness instructions

**Script to create:** `pp_backtest/cortex_schwager_s18_sector_persistence.py`

**Run order:**
1. IS slice: compute sector return, rolling std dev, threshold crossings, next-day continuation rate — confirm IS baseline per candidate before OOS slice
2. OOS slice: same computation; compute G_persistence, G1a, G1b per candidate
3. Output: `knowledge/backtests/s18_harness_results.md` with per-candidate gate verdicts

**Key computations:**
- sector_return_t = equal-weight avg daily return of sector members (≥10 in OOS pool) on day t
- rolling_std = pd.Series.rolling(N=20).std()
- threshold condition: sector_return_t > k_thresh × rolling_std AND sector_return_t > 0 (long bias only)
- continuation = sector_return_{t+1} in same direction (>0)
- A3_RS signal filter: only include days where at least one A3_RS candidate in that sector fires on day t+1 (S18 is a filter on A3_RS entries, not an independent signal)

**Report cross-referencing:** sector-day results can share data with S19 harness (both use HOSE sector classification, same universe, same IS/OOS windows). Batch the two harness scripts if practical.

---

## Interaction test queue (post-CALIBRATED only)

1. S18 × S1 (52wk high proximity): gate G_ia = S1-filtered MAR × 1.04
2. S18 × PA-008 (sector cap): post-formalization of PA-008
3. S18 × S19 (intra-sector RS selection): natural combination; minimum N_OOS ≥ 20

---

## References
- Pre-reg: 2026-07-05_schwager_s18_sector_persistence_prereg.md
- Batch pre-check: 2026-07-05_schwager_s17_s18_s19_precheck_batch.md
- Verification harness: .claude/rules/verification-harness.md § promotion gate design
- Knowledge base: .claude/brains/vn-trading-advisor/knowledge.md § S18 (v17, SOURCED)
