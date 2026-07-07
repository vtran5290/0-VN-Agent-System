# Pre-Registration: B_cloud Kill/Degradation Criterion

**Pre-registered:** 2026-07-07  
**Reason:** Fable council (2026-07-07) identified that B_cloud was running as a production
runner with no kill criterion and no improvement pathway — an unmanaged state in both
directions. This registration closes that gap and is a **blocking precondition** for any
future A3_RS shadow graduation Trigger #5 review.

---

## 1. What this governs

B_cloud20_100 (`daily_paper_trade_runner.py`) — the current production paper runner.  
Evidence base: its own live paper trading history (NOT A3_RS evidence — cross-architecture
comparison is inadmissible per verification-harness.md).

---

## 2. Monitoring criteria

| Metric | Kill threshold | Degradation flag |
|---|---|---|
| Rolling 6-month paper MAR | < 0 (negative) sustained ≥ 2 consecutive quarters | < 0.20 for 1 quarter |
| Max drawdown (rolling 6m) | > 35% | > 25% |
| Signal count | Zero signals for ≥ 8 consecutive weeks outside bear regime | — |

**Minimum evidence required before kill/degradation verdict:** ≥ 3 months of paper trading data with ≥ 5 closed paper trades.

---

## 3. Incumbent disposition pathway (triggered at A3_RS shadow graduation)

When A3_RS shadow runner reaches Trigger #5 graduation review, the review pack **must** include an explicit incumbent disposition field with one of:

| Disposition | Meaning | Preconditions |
|---|---|---|
| **Replace** | B_cloud retired, A3_RS becomes sole production runner | A3_RS graduation approved; B_cloud meets kill criterion OR user explicit decision |
| **Coexist** | Both runners continue in separate capital lanes | Distinct universes, no shared OMS path, separate monitoring |
| **Sunset** | B_cloud winds down on defined timeline | User decision; Trigger #4 discipline for canonical file removal |

Disposition decision = part of Trigger #5 dual-judge (opus + ChatGPT), same review pack.  
No implicit disposition — must be stated explicitly.

---

## 4. B_cloud improvement pathway (conditional)

Per opus council verdict (2026-07-07, CONDITIONAL): B_cloud filter research is deferred until:

1. A3_RS shadow runner accumulates ≥ 20 paper decisions, AND
2. A lightweight diagnostic is pre-registered and run: sub-period breakdown (sub-A 2020-2022 / sub-B 2023-2026) + S1 proximity filter test on B_cloud universe

Only if the diagnostic shows a non-trivial improvement path does B_cloud earn full S-testing investment. The diagnostic must be pre-registered before running (baseline = B_cloud's own live paper MAR, relative gate, OOS window) — no retroactive result fitting.

---

## 5. Current status

- B_cloud paper trading: ACTIVE (monitoring only, no research investment)
- Kill criterion: **REGISTERED** (this document)
- Improvement pathway: DEFERRED pending A3_RS shadow ≥ 20 decisions
- Incumbent disposition at graduation: PENDING (to be resolved at Trigger #5)

---

## 6. References

- Council verdicts: `00. Command Center/05_AI_Handoffs/2026-07-07_BcloudDirection_Council.md`
- Fable rule addition: `D:\V\.claude\rules\verification-harness.md` (cross-arch + incumbent disposition)
- A3_RS shadow pre-registration: `knowledge/backtests/2026-07-05_shadow_a3rs_s1_prereg.md`
- Production runner: `pp_backtest/daily_paper_trade_runner.py` — read-only, no changes
