# Breadth Wording Patch Notes (Round 2)

Date: 2026-05-16

---

## Problem

Stale "T2 Reduced" wording reintroduced in Phase35 documents.

The correct rule (established in Phase34 breadth backtest evidence):
- Breadth ≥ 40%: T1 allowed, T2 allowed
- Breadth 35–40%: T1 allowed, **T2 blocked** (`breadth_t2_permission = False`)
- Breadth < 35%: T1 manual review, **T2 blocked**
- VNINDEX bear: T1 hard block, T2 blocked

"Reduced" implies partial T2 is still permitted in caution zone. This is incorrect.
The backtest code sets `breadth_t2_permission = False` for caution and defense.

---

## Files Patched

| File | Old wording | New wording |
|------|-------------|-------------|
| `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` | "Reduced — 30–40% of slot" | "NO — T2 blocked (`breadth_t2_permission = False`)" |
| `UPDATED_FINAL_DAILY_RUNBOOK.md` | "Reduced" | "T2 blocked" |
| `UPDATED_PHASE35_DASHBOARD_SPEC.md` | "BREADTH CAUTION — T2 REDUCED" | "BREADTH CAUTION — T2 BLOCKED" |

---

## Note on Reduced T2 Research

The "30–40% of slot" wording came from an earlier exploratory idea to implement
graduated T2 sizing. This was **never tested or implemented**. The operational rule
is binary: `breadth_t2_permission = True` only when `breadth_zone = normal (≥40%)`.
