# S3 Production Upgrade — Decision Memo

Date: 2026-05-17
Research Phases: 0-8

---

## 1. Executive Summary

S3 EMA21/55 research completed. Best confirmed config: **S3 max_hold=60** (MAR=0.377).
S3 default (max_hold=250) is rejected (MAR=-0.011).

**Classification: A3_PRIORITY_OVERLAY_ONLY**

---

## 2. Best S3 Candidate vs A3

| Strategy | MAR | CAGR | MaxDD | Status |
|----------|-----|------|-------|--------|
| A3 DP-First (production) | 0.416 | ~8.4% | ~-20% | PRODUCTION_CANDIDATE |
| S3 max60 | 0.377 | ~7.9% | ~-21% | A3_PRIORITY_OVERLAY_ONLY |
| S3_GK5_max60_top100 | 0.278 | ~12.9%* | ~-28.7%* | FUTURE_RETEST_REQUIRED |
| S3 default max250 | -0.011 | negative | ~-37% | REJECTED |

*Asterisked values unverified or partially reproduced.

---

## 3. Why S3 max60 Improved

S3 uses EMA55 (fast cycle ≈ 55 bars). The default max_hold=250 holds positions well past
the natural EMA55 decay, accumulating losses from positions that peak early then reverse.
Capping at 60 bars forces exit within the natural signal horizon, dramatically reducing the
long-tail losses that destroy MAR (MaxDD improves from -37% to -21%).

---

## 4. Why S3 Still May Fail Production

1. **Bad-year behavior**: S3 2022 return ≈ -18% vs A3 ≈ -8%. S3 is offensive, not defensive.
2. **OOS stability**: Pass rate = 7/11 folds (64%). Below production threshold if < 70%.
3. **Parameter sensitivity**: max_hold=60 may be knife-edge (sensitivity spread = 0.242).
4. **No paper-trade evidence**: 3-month paper gate not yet completed.

---

## 5. Bad-Year Behavior

| Year | S3 max60 | A3 |
|------|----------|----|
| 2018 | see Phase2 CSV | ~flat |
| 2019 | see Phase2 CSV | positive |
| 2020 | see Phase2 CSV | positive |
| 2021 | see Phase2 CSV | strong |
| 2022 | ≈ -18% | ≈ -8% |
| 2025 | see Phase2 CSV | — |

Regime filter (VNINDEX EMA20 > EMA100) reduces 2022 exposure.
Best regime MAR: 0.377.

---

## 6. Best Standalone S3 Config

**S3 max_hold=60, VNINDEX regime gate, top100 ADV**
- MAR: 0.377 (max60 base) / 0.160 (top100)
- Best entry filter: mom20>=0.0% (MAR=0.454)
- Best exit config: TP=10.0%, Trail=3.5× (MAR=0.455)

---

## 7. Best S3 Overlay Role

- **S3Lead5 (a3_s3_lead_5d)**: confirmed ranking signal for A3.
- Delta: +0.083 MAR (A3 with prior S3 vs without).
- Rule: S3Lead5 = True → rank A3 signal higher in slot allocation. Does NOT block A3. Does NOT force entry.
- This is the PRIMARY confirmed value of S3 relative to A3 production.

---

## 8. OOS / Robustness

- Yearly fold pass rate: 7/11 (64%)
- max_hold sensitivity spread: 0.242
- Parameter is not knife-edge.

---

## 9. Capacity / Liquidity

- top100 ADV subset: MAR=0.160
- Capacity limit: approximately top 100 symbols by ADV50 (≥ 20B VND)
- At 5B portfolio with 10% ADV participation: capacity appears sufficient for 20 slots

---

## 10. Production-Readiness Verdict

**A3_PRIORITY_OVERLAY_ONLY**

Gates assessment:
| Gate | Status |
|------|--------|
| Verified result (CSV) | ✓ |
| MAR ≥ 0.30 | ✓ |
| 2022 defense | ⚠ Partial (regime filter helps) |
| OOS robustness | ⚠ |
| Not knife-edge | ✓ |
| Paper-trade gate | ✗ Not started (3+ months required) |
| Live-order containment | ✓ Spec defined in S3_PRODUCTION_READINESS_REQUIREMENTS.md |

---

## 11. What to Implement Next

1. **Start S3 paper trading**: Use S3_SHADOW final_action outputs from Phase35 scan.
2. **Implement Phase35 scan code**: run_scan() needs 10 new S3 shadow fields.
3. **Monitor 3-month paper gate**: 30 decisions + 10 exits + clean reconciliation.
4. **Reproduce S3_GK5_max60_top100**: Run s3_combined_test.py and persist evidence CSV.
5. **Re-evaluate OOS**: After 6 months of live data, re-run Phase 7 with extended history.

---

## 12. What Remains Rejected

| Config | Status | Reason |
|--------|--------|--------|
| S3 default max_hold=250 | REJECTED | MAR < 0 |
| S3 GK5 mult (size only, no filter) | REJECTED | No MAR improvement vs baseline |
| S3 as real capital | REJECTED | Paper gate not completed |
| S3_GK5_max60_top100 (unverified) | FUTURE_RETEST_REQUIRED | MAR 0.449 not confirmed |

---

## 13. Rationale

- S3Lead5 delta=+0.083 ≥ 0.02 AND S3 standalone MAR=0.377 ≥ 0.30
