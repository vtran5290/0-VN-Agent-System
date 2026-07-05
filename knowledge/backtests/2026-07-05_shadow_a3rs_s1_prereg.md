# Pre-Registration: Shadow A3_RS + S1 Paper Runner

**Pre-registered:** 2026-07-05  
**Council approval:** Opus APPROVE + Fable GAP resolved + ChatGPT APPROVE = 3/3  
**Slug:** 2026-07-05-2100_VNAgent_S1S2PromotionPath  
**Status:** ACTIVE — runner created same session, paper only

---

## 1. Purpose

Accumulate live-adjacent paper evidence for the A3_RS + S1 combination under a quarantined
shadow track. The production runner (B_cloud20_100, `daily_paper_trade_runner.py`) is unchanged.

This shadow runner is research infrastructure only. Its output is NOT admissible as evidence
for B_cloud promotion (separate Trigger #5 required — different universe and architecture).

---

## 2. Strategy specification

| Parameter | Value |
|---|---|
| Entry signal | A3_RS: `cloud_only_entry` on EMA-20/100 cloud, A3 universe |
| Proximity filter (S1) | `signal_close / 52w_rolling_high >= 0.85` (CALIBRATED threshold) |
| Volume filter (S2) | **FORBIDDEN** — S1+S2 interaction OOS MAR = 0.5821 (destroys both edges) |
| Regime gate | `binary_gate_ema20_100(VNINDEX)` — suppress signals when gate = False |
| Max positions | 20 (same as A3 harness) |
| Portfolio size | 5,000,000,000 VND (same as A3 harness) |
| ADV participation | 10% (same as A3 harness) |

---

## 3. Evidence baseline (calibrated at pre-registration)

| Metric | Value | Source |
|---|---|---|
| A3_RS OOS MAR (baseline) | 0.8386 | `cortex_book2_common.py:BASE_OOS_MAR` |
| A3_RS + S1 OOS MAR | 1.7844 | `s1_harness_results.md` |
| Improvement vs baseline | +113% | Calibrated on A3 universe 2020-2026 |
| Sub-B (2023-2026) MAR | Positive (S1 held; MA-stack, quality, timing strategies collapsed) | `s14-s16 harness results` |

---

## 4. Acceptance gates (for shadow-to-paper-graduation review)

Minimum threshold before any Trigger #5 graduation review can be requested:

| Gate | Criterion |
|---|---|
| Minimum decisions | ≥ 20 paper entry signals logged |
| Tracking error tolerance | Shadow MAR within ±0.3 of calibrated baseline (1.7844) per quarter |
| Kill criterion | If shadow MAR falls below 0.50 after ≥ 20 decisions, flag [KILL-CANDIDATE] |
| Architecture barrier | This shadow evidence is NOT admissible for B_cloud promotion |

---

## 5. Kill criterion (hard stop)

If after ≥ 20 paper entry decisions the running shadow MAR falls below **0.50** (40% below
calibrated baseline G1B floor of 0.516), flag `[KILL-CANDIDATE]` in daily output and ping
user for review. Do NOT auto-remove from monitoring — user decision required.

The `--kill-after-n` flag defaults to **260 trading days** (~52 weeks). After this period,
the evidence base is assessed for Trigger #5 review or retirement.

---

## 6. Scope boundaries

**IN SCOPE:**
- Paper signal logging for A3_RS + S1 on A3 universe
- Daily comparison output vs B_cloud signals
- Kill criterion flag tracking

**OUT OF SCOPE:**
- Live trading (no `live_auto`, no DNSE)
- S2 filter application (forbidden per council)
- Writing to `final_action` or any OMS-consumed path
- Serving as evidence for B_cloud promotion (different universe/architecture)
- PA-007 ATR sizing overlay (separate PA, separate sign-off required)

---

## 7. Output paths

```
data/decision/shadow_a3rs_s1/
  YYYY-MM-DD_shadow_signals.csv   — today's A3_RS+S1 entry signals
  YYYY-MM-DD_comparison.md        — daily comparison vs B_cloud
  shadow_ledger.csv               — cumulative signal ledger
  kill_criterion_status.json      — running kill criterion tracker
```

**QUARANTINE HARD RULE**: runner MUST NEVER write to `final_action` or any OMS-consumed file.
Any write outside `data/decision/shadow_a3rs_s1/` is a Trigger #3 source-of-truth violation.

---

## 8. Trigger #5 graduation path (future)

When ≥ 20 paper decisions accumulate AND the user chooses to review for promotion:
1. Build Trigger #5 dual-judge review pack (opus + ChatGPT independent)
2. Fable seat required (first cross-architecture promotion of this category)
3. If approved: separate backtest on B_cloud universe required before integration
4. User written sign-off required

This pre-registration document does NOT constitute graduation approval.

---

## 9. References

- Council verdicts: `00. Command Center/05_AI_Handoffs/2026-07-05-2100_VNAgent_S1S2PromotionPath_OpusVerdict.md`
- ChatGPT decision: `00. Command Center/05_AI_Handoffs/2026-07-05-2100_VNAgent_S1S2PromotionPath_DecisionReceived.md`
- S1 calibration: `knowledge/backtests/s1_harness_results.md`
- Rule additions: `D:\V\.claude\rules\verification-harness.md` (cross-architecture section)
- Runner: `pp_backtest/shadow_a3rs_s1_runner.py`
