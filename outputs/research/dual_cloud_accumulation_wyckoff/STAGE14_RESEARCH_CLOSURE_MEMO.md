# Stage 14 — Dual Cloud Accumulation / Wyckoff Research Closure Memo

**Date:** 2026-05-23  |  **Branch:** dual_cloud_accumulation_wyckoff  |  **Stages completed:** 1–13

---

## 1. Executive Summary

This memo closes the Dual Cloud Accumulation / Wyckoff research branch (Stages 1–13).
No production changes are recommended. The A3 paper contract continues unchanged.
S3 max60 remains the official paper-shadow baseline.
No combined A3/S3 sleeve is approved for capital allocation.

Key outcomes:
- **A3 contract**: confirmed viable (MAR=0.16, CAGR=2.9%); no changes required.
- **Old composite score**: permanently rejected.
- **BVE/TPBCQ**: WATCHLIST_ONLY — needs more observations.
- **S3 max60**: PAPER_TRADE_SHADOW — official baseline confirmed.
- **S3 max105**: PARALLEL_PAPER_RESEARCH — promising but not yet official.
- **S3 max120**: WATCHLIST_ONLY — downgraded due to hold-extension risk.
- **Combined sleeves**: CLOSED_NO_ACTION — high A3/S3 correlation limits value.
- **Wyckoff LPS/spring**: REJECT — insufficient evidence.

---

## 2. What Was Tested

| Stage | Description |
|-------|-------------|
| 1 | Feature predictive value (price tightness, volume, breakout features) |
| 2 | A3 candidate ranking: score vs all-signal baseline |
| 3 | A3 T2 timing: ≥4% pullback within 30 bars |
| 4 | S3 shadow quality filter (max60 baseline) |
| 5 | Wyckoff tags: SOS, LPS, spring, UTAD, inverse H&S |
| 6 | Robustness: by-year, by-regime, by-liquidity |
| 7 | Score recalibration and feature ablation |
| 8 | Observation layer and forward validation ledger setup |
| 9 | Forward validation update |
| 10 | Monthly validation report and candidate decision table |
| 11 | Timing pattern decomposition (7 buckets: PRE_S3_ACCUM, FAILED_S3, etc.) |
| 12 | S3 paper-shadow contract validation (24 variants) |
| 12B | S3 max-hold robustness (7 max_hold values, 5 sensitivity variants) |
| 13 | Combined A3/S3 sleeve simulation (10 sleeve configurations) |

---

## 3. What Worked

- **A3 EMA20/100 cloud signal** with T1/T2 blended contract performs as expected.
- **S3 EMA21/55 max60** as a standalone paper-shadow contract is viable (win=22.9%, TP1=37.0%).
- **S3 max105** shows higher avg_net than max60 without MaxDD collapse — promising for further tracking.
- **BVE Q4/Q5** improves TP1 rate — borderline but worth continued monitoring.
- **PRE_S3_ACCUM timing bucket** shows +4.8pp win-rate lift — borderline, needs larger sample.

---

## 4. What Failed

- **Old composite score**: all ablation variants negative — permanently rejected.
- **Wyckoff LPS/spring_test**: no win-rate improvement — rejected.
- **S3 max120**: hold-extension risk flag — downgraded to WATCHLIST_ONLY.
- **Combined A3/S3 sleeves**: high annual return correlation (r=0.67–0.82) prevents diversification benefit.
- **FAILED_S3_BEFORE_A3**: 16.0% win rate — useful as a caution flag, not a gate.

---

## 5. What Remains Watchlist-Only

| Item | Win-rate delta | Next threshold |
|------|---------------|----------------|
| BVE_Q4Q5 | +TP1 rate, win-rate below threshold | n>=80 new matured, +5pp win delta |
| TPBCQ_Q4Q5 | similar to BVE | n>=80 new matured, +5pp win delta |
| PRE_S3_ACCUM | +4.8pp (borderline) | n>=80 matured (currently 41) |
| FAILED_S3_BEFORE_A3 | -6pp (caution) | caution flag only; not a promotion candidate |
| S3_MAX120 | higher win-rate but risk flagged | live paper 2025/2026 clear |
| Wyckoff_SOS | marginal lift | n>=100 SOS-tagged with +5pp delta |

---

## 6. S3 Final Position

| Contract | Classification | Action |
|----------|---------------|--------|
| S3 max60 | PAPER_TRADE_SHADOW | Official baseline; monthly monitoring |
| S3 max105 | PARALLEL_PAPER_RESEARCH | Research-only; 6-month live paper observation |
| S3 max120 | WATCHLIST_ONLY | Downgraded; monitor 2025/2026 live paper |
| S3 max250 | REJECT (not studied) | Defined as MAX_HOLD_REJECTED; not a candidate |

**S3 does not gate A3.** S3 P&L is tracked completely separately from A3.

---

## 7. Combined Sleeve Decision

All 10 A3/S3 sleeve combinations tested in Stage 13:
- S3 max60 with 5% weight: NEUTRAL_SLEEVE
- S3 max60 with 10–20%: DILUTES_A3
- S3 max105 with 5%: NEUTRAL_SLEEVE
- S3 max105 with 10–20%: DILUTES_A3

Root cause: A3/S3 annual return correlation is high (r=0.67 for max60; r=0.82 for max105).
Diversification benefit is absent. Combined sleeve is **CLOSED_NO_ACTION**.

Reopen only if: S3 correlation with A3 drops below 0.5 AND combined MAR improves by >=0.05.

---

## 8. Coverage Against Original Scheme

- **Covered**: 20 items
- **Partially covered**: 3 items
- **Not covered**: 2 items

Key remaining gaps:
- **Bootstrap / FDR controls**: not implemented — all win-rates are point estimates.
- **Sector L4 context**: data not available in current panel.
- **Breadth context**: only VNINDEX regime used as proxy; no advance/decline breadth.

## 9. Monthly Operating Runbook

| Step | Frequency | Action |
|------|-----------|--------|
| 1 | monthly | Run after monthly OHLCV panel update. Stage 9 updates forward validation ledger;… |
| 2 | monthly | Check BVE_Q4Q5 win_rate_delta and TP1_rate_delta. Check PRE_S3_ACCUM matured_n a… |
| 3 | monthly | Review S3 max60 paper-shadow ledger: win_rate, TP1_rate, avg_net_return by year.… |
| 4 | monthly | Review S3 max105 (PARALLEL_PAPER_RESEARCH) metrics. Track avg_hold_bars and MaxD… |
| 5 | monthly | Re-run Stage 11 if panel has been updated by 3+ months. Checks PRE_S3_ACCUM and … |
| 6 | quarterly | Quarterly: re-run S3 shadow contract, maxhold robustness, and sleeve simulation.… |
| 7 | monthly | Archive monthly output snapshot before overwriting with new run. Prevents loss o… |
| 8 | on_event | GUARDRAIL: No research stage may write to production paths. Any promotion of S3 … |

Full runbook commands in `stage14_monthly_runbook.csv`.

---

## 10. Reopen Criteria

| Item | Current Status | Reopen Trigger |
|------|---------------|----------------|
| BVE_Q4Q5 | WATCHLIST_ONLY | n>=80 new matured observations AND win_rate_delta>=+5pp AND TP1_rate_d… |
| TPBCQ_Q4Q5 | WATCHLIST_ONLY | n>=80 new matured AND win_rate_delta>=+5pp AND TP1_rate_delta positive… |
| PRE_S3_ACCUM | WATCHLIST_ONLY | n>=80 matured AND win_rate_delta>=+5pp AND TP1_rate_delta positive… |
| S3_MAX105 | PARALLEL_PAPER_RESEARCH | 6+ months paper-shadow observation with 50+ matured trades… |
| S3_MAX120 | WATCHLIST_ONLY | 2025/2026 live paper shows no MaxDD worsening AND avg_hold delta <30 b… |
| Combined_A3_S3_sleeve | CLOSED_NO_ACTION | S3 standalone MAR improves materially AND A3/S3 annual correlation dro… |
| Old_composite_score | REJECT | do not reopen… |
| Wyckoff_LPS | REJECT | do not reopen with current feature definition… |
| Wyckoff_spring_test | REJECT | do not reopen with current feature definition… |

Full reopen criteria in `stage14_reopen_criteria.csv`.

---

## 11. Safety Confirmation

| Check | Status |
|-------|--------|
| A3 production contract unchanged | ✓ YES |
| S3 not promoted to production | ✓ YES |
| OMS / live / DNSE untouched | ✓ YES |
| `final_action` unchanged | ✓ YES |
| S3 does not gate A3 | ✓ YES |
| S3 P&L separate from A3 | ✓ YES |
| Combined sleeve not approved | ✓ YES |
| BVE/TPBCQ observation-only | ✓ YES |
| PRE_S3_ACCUM observation-only | ✓ YES |
| FAILED_S3_BEFORE_A3 warning-only | ✓ YES |
| Old composite rejected | ✓ YES |
| No production recommendation made | ✓ YES |

---

## 12. Final Recommendation

1. **A3**: continue paper trading per existing frozen contract. No changes.
2. **S3 max60**: continue as official paper-shadow. Monthly ledger review.
3. **S3 max105**: track as PARALLEL_PAPER_RESEARCH. Do not replace max60.
4. **BVE/TPBCQ/PRE_S3_ACCUM**: monitor monthly. Promote only at n>=80 + criteria.
5. **Combined sleeve**: closed. Re-evaluate only if A3/S3 correlation drops below 0.5.
6. **Old composite / LPS / spring**: permanently rejected. Do not reopen.
7. **Bootstrap / sector / breadth**: future enhancement items if branch re-scoped.

**This memo is OBSERVATION / RESEARCH ONLY.**
**No production, OMS, live, or DNSE changes are authorized by this document.**
