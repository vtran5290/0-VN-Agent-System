# S3 Upgrade Implementation Notes

Date: 2026-05-16 | Supersedes: S3_UPGRADE_DECISION_MEMO.md (kept as history)

---

## Implementation Status: PHASE35 SCAN + TESTS IMPLEMENTED (2026-05-17)

**Production scan:** `pp_backtest/portfolio_optimization_final_steps.py --step scan`

Implemented in code:
- S3 max60 paper-shadow fields (`PAPER_TRADE_SHADOW`, `PAPER_S3_SHADOW`, max_hold=60)
- S3 GK5+top100 research monitor (`s3_research_monitor_action`, separate from shadow action)
- A3 `a3_s3_lead_5d` ranking boost (1–5 prior bars only)
- A3 exit scan actions: `TP1_PARTIAL`, `TRAIL_EXIT`, `MAX_HOLD_EXIT`
- `order_intent.py`: S3 never tradeable; research monitor via separate column
- Automated tests: `tests/test_s3_phase35.py`

**Not implemented / out of scope:** S3 production promotion, DNSE routing, strategy optimization.

---

## What Was Done (Docs/Schema/Spec)

| File | Change |
|------|--------|
| `updated_final_candidate_classification.csv` | Added S3_max60 (PAPER_TRADE_SHADOW) and S3_GK5_max60_top100 (FUTURE_RETEST_REQUIRED) rows; S3_best_dp → REJECTED |
| `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` | Updated classification table and S3 sections |
| `UPDATED_FINAL_OPEN_ITEMS.md` | Added S3 upgrade tasks to Done list |
| `UPDATED_phase33_paper_trade_rules.md` | Updated S3 section + Phase35 final_action enum |
| `FINAL_DEPLOYMENT_READINESS_CHECKLIST.md` | Updated Gate 10 for S3 shadow |
| `UPDATED_S3_DECISION_MEMO.md` | Full S3 upgrade decision memo |
| `phase35_daily_scan_schema.csv` | 47 fields (37 base + 10 new S3 shadow fields) |
| `phase35_daily_scan_sample.csv` | 10 rows × 47 fields, validated clean |
| `Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl` | AFL with max_hold=60 locked |
| `S3_21_55_Paper_Shadow_User_Guide.md` | AFL usage guide |
| `S3_SHADOW_PAPER_TRADE_RULES.md` | Hard rules for S3 paper shadow |
| `S3_ORDER_INTENT_RULES.md` | Order routing rules (docs only) |
| `S3_SHADOW_GATE_TESTS.md` | Behavioral gate tests (docs only — not automated) |
| `UPDATED_PHASE35_DASHBOARD_SPEC.md` | Panel 6 S3 shadow + Panel 7 research monitor |
| `UPDATED_FINAL_DAILY_RUNBOOK.md` | Step 3b S3 shadow daily check |
| `UPDATED_REAL_CAPITAL_READINESS.md` | Updated gate status |
| `data/trading/live/s3_shadow_paper_trades.csv` | Paper ledger header only |
| `data/trading/live/s3_shadow_positions.csv` | Positions state header only |

---

## What Was NOT Changed

- A3 production config: **unchanged** — EMA20/100, ex-VIN3, T1=50%, T2 on ≥4% pullback, TP1=18%, trail=2.5×ATR14, max_hold=250
- A3 MAR: still 0.416 at 5B/10%
- Breadth rules: unchanged (T1 advisory, T2 blocked <40%)
- Regime gate: unchanged (VNINDEX EMA20>EMA100)
- Real capital status: still NOT READY (Gate 1 paper trade not started)

---

## Pending Code Changes (portfolio_optimization_final_steps.py)

These changes are REQUIRED to produce Phase35 scan output. Not yet implemented.

### 1. `run_scan()` — add S3 shadow fields

```python
# New fields to add to scan output DataFrame (10 new fields → 47 total)
# a3_s3_lead_5d: True if S3 EMA21/55 cloud breakout on same symbol within 5 bars before A3
# s3_shadow_active: True when S3 EMA21/55 has active signal AND max_hold_config=60
# s3_shadow_bars_since: from paper ledger state (s3_shadow_paper_trades.csv)
# s3_shadow_entry_price: from paper ledger
# s3_shadow_tp1_price: s3_shadow_entry_price * 1.18
# s3_shadow_trail_price: peak_close - 3.5 * ATR14  (NOT 2.5 — that is A3)
# s3_shadow_max_hold_remaining: 60 - s3_shadow_bars_since
# s3_shadow_paper_pnl_pct: (current_close - entry_price) / entry_price
# s3_shadow_final_action: NEW_S3_SHADOW | S3_SHADOW_HOLD | S3_SHADOW_EXIT | WATCH_ONLY
# s3_gk5_top100: True when s3_active AND gk10 AND symbol in top-100 ADV (research monitor)
```

### 2. `strategy_classification` assignment — add S3_PAPER_SHADOW case

```python
if s3_active and max_hold_config == 60:
    strategy_classification = "S3_PAPER_SHADOW"
elif s3_active and max_hold_config != 60:
    strategy_classification = "S3_RESEARCH_ONLY"
```

### 3. `final_action` enum — add S3 shadow values

```python
# New values: NEW_S3_SHADOW, S3_SHADOW_HOLD, S3_SHADOW_EXIT
# These are for S3 shadow rows only. A3 rows continue to use existing enum.
```

### 4. Order router guard — must be present before any live routing

```python
PAPER_ONLY_CLASSIFICATIONS = {
    "S3_PAPER_SHADOW", "S3_RESEARCH_ONLY", "PTS_SHADOW", "WATCH_ONLY"
}
if row["strategy_classification"] in PAPER_ONLY_CLASSIFICATIONS:
    log_paper_only(row)
    return  # never route to broker
```

---

## Open Items (Code — Not Yet Done)

| Item | Priority | Notes |
|------|----------|-------|
| Implement Phase35 scan fields in `run_scan()` | HIGH | Blocked on ledger state read |
| Load s3_shadow_paper_trades.csv into scan state | HIGH | Required for bars_since, entry_price |
| Add S3_PAPER_SHADOW strategy_classification logic | HIGH | See section 2 above |
| Add S3 shadow final_action computation | HIGH | max_hold check, trail check |
| Order router guard for S3_PAPER_SHADOW | HIGH | Safety-critical |
| Re-run `s3_combined_test.py` for GK5+max60+top100 | MEDIUM | Required to restore PARALLEL_PAPER_RESEARCH |
| Automated test: `tests/test_s3_shadow_containment.py` | MEDIUM | See S3_SHADOW_GATE_TESTS.md |

---

## Critical Invariants (Must Hold in Code)

| Invariant | Value |
|-----------|-------|
| S3 shadow trail multiplier | **3.5×ATR14** — not 2.5 (that is A3) |
| S3 max_hold in shadow | **60 bars exactly** |
| S3 real capital | **NEVER** |
| S3 DNSE route | **NEVER** |
| A3 max_hold | **250 bars** (unchanged) |
| A3/S3 P&L files | **Separate — never merge** |
| S3 blocking A3 | **NEVER** — a3_s3_lead_5d is sort order only |
| a3_s3_lead_5d window | **5 bars** — not 30 bars |
