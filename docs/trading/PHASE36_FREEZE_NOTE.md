# Phase36 Freeze Note

**Status:** FROZEN (QA cleanup)  
**Freeze commit:** `1116480` — *Phase36 sorting layer: operator review sort + 4 behavioral tests*  
**Decision:** `CONDITIONAL_NO_CHANGE`  
**QA re-run date:** 2026-05-17

---

## What Phase36 changed

| Changed | Not changed |
|---------|-------------|
| Same-day A3 `NEW_T1` / `NEW_T1_MANUAL_REVIEW_BREADTH` rows sorted by `a3_rank_score` DESC in daily scan CSV | A3 production logic |
| `phase36_operator_priority` display field | `final_action` rules |
| Operator report / dashboard text | T1/T2 sizing |
| | Exit rules (TP1 18%, trail 2.5×ATR14, max_hold 250) |
| | Breadth / VNINDEX gates |
| | OMS routing contract |

**Only approved implementation:** operator sorting by `a3_rank_score` DESC for review priority.

- `a3_rank_score` affects **review order only**.
- `a3_rank_score` **cannot** create, block, size, or modify orders.

---

## Production contract (unchanged)

- **A3** remains the only production / real-capital engine.
- **S3** remains radar / paper-shadow only — no real capital, no DNSE.
- **Daily scan CSV** remains SSOT (`phase36_daily_scan_sample.csv`, aliases phase35/phase34).
- **OMS** consumes `final_action` only; must not recompute signals.
- **AFLs** are visual cockpit only — not execution SSOT.

---

## Order intent

- No Phase36 change to `order_intent.py` logic beyond preserving existing behavior.
- `a3_rank_score` is **not** in `ACTION_MAP`.
- S3 shadow actions remain paper-only (`PAPER_S3_SHADOW`, `PAPER_S3_RESEARCH_MONITOR`).
- A3+S3 dual-active rows still route to A3 production intent (not S3 shadow swallow).

---

## Tests

| Snapshot | Result |
|----------|--------|
| At freeze commit `1116480` | 44/44 pass (per handoff) |
| QA re-run (2026-05-17) | **57/57 pass** (`test_s3_phase35`, `test_trading_order_intent`, `test_phase36_daily_scan`) |

Command:

```powershell
python -m pytest tests/test_s3_phase35.py tests/test_trading_order_intent.py tests/test_phase36_daily_scan.py -q
```

---

## Artifacts

- `data/research/portfolio_optimization/missing_work/phase36_sorting_validation.md`
- `data/research/portfolio_optimization/missing_work/phase36_order_intent_validation.md`
- `phase36_daily_scan_review_package.zip`
- `docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md`

---

## Explicit non-goals (frozen out)

- S3 production promotion
- S3-based T2 policy (`t2_only_if_good_lead`)
- S3-based sizing (`lead_best_125x`)
- Tight trail 2.0×ATR
- A3/S3 satellite real allocation
- Any use of rank fields to gate or modify `final_action`
