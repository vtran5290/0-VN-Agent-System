# Review Prompt v2 — VN EMA-Cloud Strategy System (Phase34, post-patch)

**For:** External AI reviewer
**Date:** 2026-05-16 | Round 2 (after 5 patches applied from Round 1 review)
**Author:** Claude Code (Sonnet 4.6)

---

## What Changed Since Round 1

A prior review found 5 required patches. All have been applied. This is the verification pass.

| # | Patch | Files |
|---|-------|-------|
| 1 | `run_breadth()` now writes correct breadth table to `BREADTH_RULE_FINAL.md` | `portfolio_optimization_final_steps.py` lines ~1051–1063 |
| 2 | `run_scan()` now writes correct breadth rules to `phase33_paper_trade_rules.md` | `portfolio_optimization_final_steps.py` lines ~1393–1433 |
| 3 | User guide: breadth removed from hard entry conditions; T2 threshold corrected | `A3_DP_First_User_Guide_FINAL.md` lines 43 and 60 |
| 4 | Stale cross-reference fixed | `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` line 101 |
| 5 | `breadth_t2_permission = "Reduced"` → `"False (T2 blocked)"` in caution zone | `UPDATED_phase33_paper_trade_rules.md`, `UPDATED_BREADTH_RULE_FINAL.md`, `phase34_daily_scan_schema.csv` |
| minor | ABB leading space in `final_action` fixed | `phase34_daily_scan_sample.csv` |
| minor | HPG `trail_price` populated (22.02) | `phase34_daily_scan_sample.csv` |

---

## Strategy Summary (unchanged)

**A3 DP-First** — EMA20/100 cloud breakout, ex-VIN3 universe, DP pullback-only entry.
- T1 = 50% of slot at cloud breakout. T2 = 50% on ≥4% pullback within 30 bars.
- Exit: TP1 +18%, trail 2.5×ATR14, max 250 bars. Vietnam T+3, min 5-bar sell lock.
- Regime gate: VNINDEX EMA20>EMA100 = **only** hard T1 block.
- Breadth: advisory only. Controls T2 (blocked when breadth <40%). Never blocks T1.
- Reference performance: MAR=0.416, CAGR=5.81%, MaxDD=-13.99% at 5B VND / 10% ADV.

Other strategies: PTS=PAPER_TRADE_SHADOW (MAR 0.343), S3=RESEARCH_ONLY (MAR 0.190).

---

## The Single Core Invariant

Every file in the package must express this consistently:

> **Only VNINDEX bear regime (EMA20 < EMA100) is a hard T1 block.**
> **Breadth <40% blocks T2 (breadth_t2_permission = False). Breadth never blocks T1.**
> **Defense zone (<35%) sets final_action = NEW_T1_MANUAL_REVIEW_BREADTH, not NO_NEW_ENTRY_BREADTH.**

---

## Files in This Package

| File | Role |
|------|------|
| `Cloud_Strategy_A3_20_100_DP_First_FINAL.afl` | AmiBroker production AFL |
| `Cloud_Strategy_S3_21_55_RESEARCH_ONLY.afl` | AmiBroker S3 research AFL |
| `A3_DP_First_User_Guide_FINAL.md` | End-user guide (patched) |
| `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` | Classification — authoritative (patched) |
| `UPDATED_BREADTH_RULE_FINAL.md` | Breadth rules (patched) |
| `UPDATED_phase33_paper_trade_rules.md` | Paper trade entry/exit rules (patched) |
| `FINAL_DAILY_RUNBOOK_CLEAN.md` | 10-step daily runbook |
| `FINAL_DASHBOARD_SPEC.md` | 9-panel dashboard spec |
| `FINAL_DEPLOYMENT_READINESS_CHECKLIST.md` | Pre-live gates |
| `phase34_daily_scan_schema.csv` | 37-field scan schema (patched) |
| `phase34_daily_scan_sample.csv` | Sample scan output (patched) |
| `updated_final_candidate_classification.csv` | Strategy classification table |
| `UPDATED_FINAL_OPEN_ITEMS.md` | Done/rejected/pending tracker |

---

## Review Focus — 5 Checks

### Check 1: Patch 1 verified — `BREADTH_RULE_FINAL.md` generated content

The Python code `run_breadth()` writes `BREADTH_RULE_FINAL.md`. Verify the written content is now correct.

Read `portfolio_optimization_final_steps.py` around lines 1051–1063. The operating rules table written to `BREADTH_RULE_FINAL.md` must:
- NOT contain "No new live entries" for defense or caution zones
- Contain `breadth_t1_permission` and `breadth_t2_permission` columns
- Show: caution = T2 False, defense = T1 review + T2 False, bear = T1 hard block

**Old (wrong):** `| < 35% | Defense | No new live entries |`
**New (correct):** `| < 35% | Defense | True (review req'd) | False | T1 with operator review. T2 blocked. |`

### Check 2: Patch 2 verified — `phase33_paper_trade_rules.md` generated content

Read `portfolio_optimization_final_steps.py` around lines 1393–1433. The content written to `phase33_paper_trade_rules.md` must:
- NOT list "A3 breadth ≥ 40%" as an entry condition
- NOT say "No new entries" or "No new initiations" for caution/defense
- Say "VNINDEX regime = bull (EMA20 > EMA100) — ONLY hard T1 block" as condition #3
- Say breadth zones are "advisory for T1, binding for T2"

### Check 3: Patch 3 verified — `A3_DP_First_User_Guide_FINAL.md`

Check lines 43 and 60:
- Line 43 must NOT say `A3 breadth ≥ 40%` as entry condition
- Line 43 must reference `breadth_t1_permission` and VNINDEX as the hard block
- Line 60 (T2 Add Rules) must say T2 blocked below 40% (not "below 35%")

### Check 4: Patch 5 verified — caution zone breadth_t2_permission = False everywhere

Verify "Reduced" is gone from all three locations:
- `UPDATED_phase33_paper_trade_rules.md` line ~30: caution row must say `False (T2 blocked)`
- `UPDATED_BREADTH_RULE_FINAL.md` line ~39: caution row must say `False (T2 blocked)`
- `phase34_daily_scan_schema.csv`: `breadth_t2_permission` description must say caution = False

All three must now agree: caution zone → `breadth_t2_permission = False`.

### Check 5: Sample CSV clean

`phase34_daily_scan_sample.csv`:
- ABB row: `final_action` must be exactly `WATCH_ONLY` (no leading space)
- HPG row: `trail_price` must be populated (not empty), should be ~22.02
- All 10 rows must have exactly 37 comma-separated fields (count commas + 1 per row = 37)

---

## Key Numbers (canonical — flag any discrepancy)

| Metric | Value |
|--------|-------|
| A3 DP MAR | 0.416 |
| A3 DP CAGR | 5.81% |
| A3 DP MaxDD | -13.99% |
| PTS MAR | 0.343 |
| S3 MAR | 0.190 |
| TP1 | +18% |
| A3 trail mult | 2.5×ATR14 |
| S3 trail mult | 3.5×ATR14 |
| T2 pullback depth | ≥4% |
| T2 pullback window | 30 bars |
| Max hold | 250 bars |
| Min sell lock | 5 bars |
| GK10 mult | 1.25× |
| ADV participation | 10% |
| Max slots | 20 |
| hard_40 MAR (evidence) | 0.344 |
| hard_40 blocked winners | 1125 |
| hard_40 blocked losers | 616 |

---

## Response Format

```
## PASS / FAIL / NEEDS_REVISION

### Check 1 — run_breadth() output: [PASS|FAIL]
Lines read: [line numbers]
Finding: ...

### Check 2 — run_scan() output: [PASS|FAIL]
Lines read: [line numbers]
Finding: ...

### Check 3 — User guide: [PASS|FAIL]
Lines read: [line numbers]
Finding: ...

### Check 4 — Caution breadth_t2_permission = False: [PASS|FAIL]
Finding: ...

### Check 5 — Sample CSV: [PASS|FAIL]
ABB final_action: "[value]"
HPG trail_price: [value]
Field count: [n]
Finding: ...

### Remaining Issues (if any):
1. [file] line [n]: [issue]

### Overall Verdict:
```
