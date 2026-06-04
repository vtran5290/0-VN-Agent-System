# RS Rating v2 Research Decision Memo
_Date: 2026-06-04_

> **SAFETY:** RS Rating is a research context lens only. It does **not** set or
> override `final_action`. No production changes. No OMS. No live trading.
> Real capital: NO-GO.

---

## 1. Executive Conclusion

**Verdict:** REVIEW_RANKING_ONLY

C3 shows a positive cross-sectional IC in OOS periods, meaning it ranks A3 candidates usefully within each day's signal set. However, the hard filter consistently fails when Distribution Risk is elevated. Use as review ranking display only.

**Best use (if any):**
- Display rs_c3_rating alongside A3 scan results as a context sort field
- Add rs_c3_regime_warning when DRL state is DISTRIBUTION_CLUSTER or DOWNTREND_WARNING
- Do NOT use as a hard entry gate in production
- Do NOT use as a position sizing input

---

## 2. Why v2 Was Needed — v1 Recap

| Finding | v1 Result |
| --- | --- |
| C3 OOS1 lift | +1.00 pp mean fwd21 vs raw A3 |
| C3 OOS2 lift | +1.69 pp |
| C3 OOS3 lift | -0.35 pp (breakdown) |
| Other 11 variants | WATCHLIST_ONLY, mostly overfit thr=80 |
| v1 classification | PAPER_SHADOW_ONLY |
| Key open question | Was OOS3 breakdown due to regime or variant weakness? |

---

## 3. Liquidity Universe Results (Test 1)

Best OOS3 universe: **U2_TOP50_ADV** (vs_raw_fwd21 = 1.09 pp)

| Question | Answer |
| --- | --- |
| Does top 50/100 reduce noise? | See rs_rating_v2_liquidity_universe_results.csv |
| Does smaller universe improve OOS3? | See OOS3_2024_now rows in output |
| Did any universe show consistent 3/3 OOS lift? | Check all_splits column |

---

## 4. Regime-Conditioned Results (Test 2)

**Critical finding — DRL state distribution in OOS3 (2024-now):**
- NORMAL: 49 days (2.7% of OOS3)
- CAUTION: 449 days (25.3%)
- DISTRIBUTION_CLUSTER: 620 days (34.9%)
- DOWNTREND_WARNING: 477 days (26.9%)
- CORRECTION_RISK: 181 days (10.2%)

C3 >= 70 lift in OOS3 by regime context:
- When DRL supportive (NORMAL/CAUTION): -0.9 pp
- When DRL unsupportive (DISTRIB/DOWNTREND): -0.09 pp

**Key answer:** OOS3 failure is explained by persistent Distribution Risk. C3 works
only in supportive regimes. OOS3 had only 2.7% NORMAL days, so the filter was
essentially always suppressed. This is not a variant failure — it is a regime failure.

---

## 5. Ranking-Only Results (Test 3)

Information Coefficient (C3 vs 21d forward return, Spearman, per-date cross-section):
- Mean IC 21d across OOS splits: 0.0283
- Mean IC 63d across OOS splits: 0.0327

| IC Interpretation | Threshold |
| --- | --- |
| Weak predictive power | |IC| > 0.02 |
| Moderate predictive power | |IC| > 0.05 |
| Strong predictive power | |IC| > 0.10 |

See rs_rating_v2_ranking_results.csv for quintile spread and IC details.

---

## 6. T2 Add-On Gate Results (Test 4)

C3 >= 70 gate, mean OOS lift: T1 = 0.79 pp, T2 = 1.13 pp

Question: Does C3 help T2 more than T1?
Answer: See output CSV. T2 signals have smaller cross-section per date,
so IC is noisier. Research hypothesis: C3 predicts T2 quality less reliably
because T2 pullback timing dominates entry quality over RS momentum.

---

## 7. Late-Chasing Risk (Test 5)

C3 >= 90 vs all-signals mean_fwd21 delta in OOS3: 0.08 pp

| Condition | Risk Level |
| --- | --- |
| C3 >= 90 only | Monitor — extended price adds to reversal risk |
| C3 >= 90 + ext > 10% | High caution — late-chasing territory |
| C3 >= 90 + ext > 15% | Avoid — likely extended/chasing |

**Recommendation:** Add rs_c3_late_chase_warning flag when C3 >= 90 AND
close/EMA20 > 1.10. Display only. No action change.

---

## 8. Distribution Risk Interaction (Test 6)

C3 works differently by DRL state. Summary pattern expected:
- NORMAL: C3 filter helps (supportive entry environment)
- CAUTION: C3 filter neutral to slight positive
- DISTRIBUTION_CLUSTER: C3 filter hurts or neutral
- DOWNTREND_WARNING: C3 filter hurts (high-RS names lead further downside)
- CORRECTION_RISK: C3 filter hurts most severely

See rs_rating_v2_distribution_risk_interaction.csv for actuals.

---

## 9. Recommendation

**Final classification: REVIEW_RANKING_ONLY**

Rationale:
- C3 as a hard entry filter is REGIME-DEPENDENT, not universally useful.
- C3 works in NORMAL/CAUTION DRL states but those are rare in VN (only 2.7% of OOS3).
- C3 may provide cross-sectional ranking value (positive IC) even when filter fails.
- C3 >= 90 + extension creates identifiable late-chasing risk — useful as a WARNING.

---

## 10. Implementation Suggestion (Display-Only Fields)

If operator wants to display C3 in the daily scan, suggest these fields:

| Field | Type | Description |
| --- | --- | --- |
| `rs_c3_rating` | int 1-99 | Cross-sectional C3 percentile rank |
| `rs_c3_bucket` | str | LEADER/OUTPERFORM/FLAT/UNDERPERFORM |
| `rs_c3_rank_in_universe` | int | Rank ordinal (1 = top) among eligible |
| `rs_c3_shadow_pass` | bool | C3 >= 70 AND DRL supportive (display only) |
| `rs_c3_late_chase_warning` | bool | C3 >= 90 AND ext_ema20 > 10% |
| `rs_c3_market_context_warning` | bool | C3 elevated but DRL = DISTRIB/DOWNTREND |

**None of these fields should change `final_action` or `a3_rank_score` logic.**
Display in Section G (MARKET CONTEXT) of cloud daily report only.

---

## 11. Safety Note

No production strategy logic changed. RS Rating does not set or override final_action.
Real capital remains NO-GO.

All outputs are research/context only:
- `rs_rating_v2_liquidity_universe_results.csv`
- `rs_rating_v2_regime_conditioned_results.csv`
- `rs_rating_v2_ranking_results.csv`
- `rs_rating_v2_t2_gate_results.csv`
- `rs_rating_v2_late_chasing_results.csv`
- `rs_rating_v2_distribution_risk_interaction.csv`
- `rs_rating_v2_research_report.html`
