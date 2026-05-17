# Phase36 A3/S3 Coordination Decision Memo

Date: 2026-05-17
Status: RESEARCH COMPLETE
Decision: CONDITIONAL_NO_CHANGE

---

## Context

Phase36 researched whether A3 and S3 can be coordinated to improve A3 MAR.
Documented A3 baseline (DP-First, 5B VND, 10% ADV, 20 slots): MAR=0.416, CAGR=5.81%, MaxDD=-13.99%
Acceptance bar: MAR improvement ≥ +0.03 → need MAR ≥ 0.446

**Simulation note:** Phase36 backtests use cloud-only entries (no DP pullback T2).
The cloud-only A3 baseline is MAR≈0.263 at 20 slots — structurally lower than the
documented DP-First 0.416 because T2 pullback re-entries are not modeled. All
within-phase comparisons are internally consistent. Cross-phase comparisons to the
0.416 baseline are indicative only.

---

## Results Summary

| Phase | Best Variant | MAR (sim) | vs cloud-only baseline | Note |
|-------|-------------|-----------|----------------------|------|
| 36B Ranking | ed_score_only / 20 slots | 0.4436 | +0.18 | EMA proximity ranking — strongest signal |
| 36B Ranking | a3_rank_score / 20 slots | 0.3462 | +0.08 | Composite lead+proximity ranking |
| 36C Sizing | lead_best_125x | 0.3746 | +0.03 | 1.25× weight for lead_11_20/lead_21_30 |
| 36D T2 policy | t2_only_if_good_lead | 0.4376 | +0.09 / MaxDD -0.10 | T2 only for good S3 leads |
| 36E Exit | max_hold_180 | 0.2900 | +0.03 | Marginal; tight trail (2.0×) is harmful |
| 36F Satellite | A3_60/S3_40 | 0.3675 | +0.10 | Paper research only; gate passage required |
| 36G Risk | — | — | — | DD correlation data available; see findings |

No variant cleared MAR ≥ 0.446 against the DP-First documented baseline.
Against the internally consistent cloud-only baseline (0.263), multiple variants
show meaningful improvement.

---

## Rationale

No coordination variant cleared the MAR ≥ +0.03 threshold when compared against
the documented DP-First baseline (0.416). A3 production parameters remain unchanged.

Key actionable findings within cloud-only simulation scope:
1. **ed_score (EMA proximity) is a strong ranking signal** — consistently outperforms
   ema_dist_at_entry as a same-day NEW_T1 sort key. Already computed in Phase35 scan.
2. **a3_rank_score (ed + lead quality) improves ranking** — Δ+0.08 MAR vs baseline.
   Adopting as default NEW_T1 sort order is low-risk (no A3 logic change, scan field
   already available).
3. **Tight trail (2.0×) is harmful** — MAR drops to 0.104. Keep A3 at 2.5×ATR14.
4. **Satellite sleeve shows diversification benefit** — monotonic MAR improvement with
   S3 allocation. Requires S3 paper gate passage first (Gate 10/11 not started).

Recommended operational adoption (no A3 logic change, advisory only):
→ Sort same-day NEW_T1 by a3_rank_score DESC (already in Phase35 scan output).

S3 remains PAPER_TRADE_SHADOW. Re-evaluate after 12 months live paper data.

---

## What Does NOT Change

1. A3 EMA20/100 cloud-breakout entry — LOCKED
2. A3 TP=18%, trail=2.5×ATR14, max_hold=250 — LOCKED
3. VNINDEX EMA20>EMA100 hard block for new T1 — LOCKED
4. Breadth T2 gate (pct_cloud_bull_a3 < 35%) — LOCKED
5. ADV50 corrected formula (close_kVND × volume × 1000) — LOCKED
6. S3 = PAPER_TRADE_SHADOW only. No real capital. No DNSE — LOCKED
7. S3 max_hold=60 — LOCKED
8. S3 does not gate A3 — LOCKED

---

## S3 Shadow Status

Gate 10 (S3 shadow 12 months paper): NOT STARTED
Gate 11 (S3 combo paper): NOT STARTED

No S3 upgrade discussion until both gates have live paper evidence.

---

## Next Review Trigger

- After 3 months live a3_rank_score tracking (if ranking was adopted)
- After S3 shadow Gate 10 is met (12 months, MAR≥0.35, MaxDD≤-25%)
