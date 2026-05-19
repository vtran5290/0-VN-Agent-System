# Daily Scan Operator Guide

**SSOT:** `data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv`  
**Aliases:** `phase35_daily_scan_sample.csv`, `phase34_daily_scan_sample.csv`  
**Phase36 decision:** `CONDITIONAL_NO_CHANGE` — see `docs/trading/PHASE36_FREEZE_NOTE.md`

---

## Run scan

```powershell
.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan
```

Operator summary (panels): `data/research/portfolio_optimization/missing_work/phase36_daily_operator_report.md`

**Full daily packet (like weekly report):** `data/decision/daily_scan.md` — regenerated on every `--step scan`. Rebuild from CSV only:

```powershell
.venv\Scripts\python.exe scripts/reporting/daily_scan_report.py
```

---

## Authoritative column: `final_action`

- OMS and real capital use **`final_action` only**.
- Do not buy/sell from `s3_shadow_action`, `a3_rank_score`, or AFL visuals.

---

## Phase36 — review sort (frozen at commit 1116480)

### What changed

Same-day A3 new-entry rows are listed in this order:

1. `NEW_T1` first  
2. `NEW_T1_MANUAL_REVIEW_BREADTH` second  
3. Within each group: **`a3_rank_score` DESC** (higher = review first)  
4. Then liquidity, S3 fresh-lead, sector concentration, symbol  

Column: `phase36_operator_priority` (1 = top of file for review).

### What did NOT change

| Item | Status |
|------|--------|
| `final_action` rules | Unchanged |
| T1/T2 sizing (`target_T1_M`, ADV caps) | Unchanged |
| Exit policy (TP1 18%, trail 2.5×ATR14) | Unchanged |
| Breadth / VNINDEX gates | Unchanged |
| Risk engine / OMS | Unchanged |
| S3 production / DNSE | Not allowed |

### How to read rank

- **Higher `a3_rank_score`** → review that name first when several show `NEW_T1` on the same day.
- **Not** an auto-buy signal.
- **Not** a block if score is low.
- S3 lead / rank context does **not** gate A3 eligibility.

Example wording: *"Today's A3 NEW_T1 candidates are sorted by a3_rank_score DESC for operator review. This sorting does not change final_action, size, or risk checks."*

---

## Pending-entry signals (`a3_signal_today = True`)

When the A3 signal fires on the **latest EOD bar** (today's close), the scan outputs:

| Field | Value |
|---|---|
| `final_action` | `NEW_T1` or `NEW_T1_MANUAL_REVIEW_BREADTH` |
| `a3_signal_today` | `True` |
| `a3_planned_entry_timing` | `NEXT_OPEN` |
| `pb_trigger_price` | `NaN` (entry price unknown) |
| `tp1_price` | `NaN` (entry price unknown) |
| `trail_price` | `NaN` (entry price unknown) |
| `final_action_reason` | "…Signal confirmed at today's close; planned fill is next session open." |

**What this means:**
Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.

**Operator workflow:**
1. Identify symbols with `a3_signal_today=True` in `final_action_reason` or `daily_scan.md` ("\* Pending entry" note).
2. Entry size per T1 rules; fill at next session open (T+1 market open).
3. pb_trigger_price / tp1_price / trail_price will appear in next EOD scan after the open fill price is recorded.
4. Do not enter at ATC assuming trigger — use full EOD close confirmation only.

---

## Phase35 S3 (unchanged)

- S3 max60 = `PAPER_S3_SHADOW` only — separate paper ledger.
- `s3_no_real_order_flag` always True.
- No live orders, no DNSE from S3 fields.

---

## Quick action table

| final_action | Operator |
|--------------|----------|
| NEW_T1 | T1 eligible (after rank sort for review order) |
| NEW_T1_MANUAL_REVIEW_BREADTH | Manual review, then T1 if approved |
| ADD_T2 | Add T2 if PB + breadth OK |
| NO_T2_BREADTH | Hold T1; no T2 |
| TRAIL_EXIT / TP1_PARTIAL / MAX_HOLD_EXIT | Manage exit per A3 rules |
| SKIP_VNINDEX_BEAR / SKIP_LIQUIDITY | No new entry |
| WATCH_ONLY | No A3 production action |

---

## Related docs

- `data/research/portfolio_optimization/missing_work/DAILY_SCAN_OPERATOR_GUIDE.md` (extended copy)
- `data/research/portfolio_optimization/missing_work/PHASE36_DECISION_MEMO_SUMMARY.md`
- `docs/trading/REAL_CAPITAL_READINESS.md`
