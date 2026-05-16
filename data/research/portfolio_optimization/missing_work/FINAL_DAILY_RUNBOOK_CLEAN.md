# Final Daily Runbook — A3 DP-First Paper Trade

Version: CLEAN | Date: 2026-05-16 | Classification: PRODUCTION_CANDIDATE

---

## Step 1 — Update Data Panel

```
python scripts/run_weekly_full_fetch.py
```

Run before market open. Pulls HOSE/HNX prices, volume, value. Updates parquet panel.

---

## Step 2 — Check VNINDEX Regime (Hard Gate)

Compute VNINDEX EMA20 vs EMA100.

- **EMA20 > EMA100 (bull):** proceed to Step 3
- **EMA20 < EMA100 (bear):** STOP. No new T1 entries today. Review existing positions only.

This is the only automatic hard T1 block in the system.

---

## Step 3 — Run Phase34 Daily Scan

```
.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan
```

Output: `data/research/portfolio_optimization/missing_work/phase34_daily_scan_sample.csv`

---

## Step 4 — Check A3 Breadth (Advisory)

Read `pct_cloud_bull_a3` from scan output header row.

| Breadth | Zone | T1 | T2 | Action modifier |
|---------|------|----|-----|----------------|
| ≥ 40% | Normal | YES | YES | No modifier |
| 35–40% | Caution | YES | Reduced | Note caution in trade log |
| < 35% | Defense | YES (review req'd) | NO | Signals show NEW_T1_MANUAL_REVIEW_BREADTH |

**Breadth does not block T1 automatically. Only VNINDEX bear regime does.**

Current as of 2026-05-16: 31.9% → Defense (manual review required for new T1s)

---

## Step 5 — Review Signals

Filter scan by `final_action`:

| final_action | Operator action |
|-------------|----------------|
| NEW_T1 | Check liquidity → place T1 order |
| NEW_T1_MANUAL_REVIEW_BREADTH | Review 3 criteria → decide (see Step 6) |
| WAIT_PB | Monitor `pb_trigger_price` daily |
| ADD_T2 | Add T2 (50% slot, capped by ADV) |
| HOLD_T1_ONLY | Hold existing T1. Monitor trail stop. |
| NO_T2_BREADTH | In position. T2 blocked by breadth. Monitor exit only. |
| SKIP_LIQUIDITY | Skip — ADV cap too low |
| SKIP_VNINDEX_BEAR | Skip — regime gate active |
| WATCH_ONLY | S3/PTS signal. No capital action. |

---

## Step 6 — Manual Review (when final_action = NEW_T1_MANUAL_REVIEW_BREADTH)

Confirm ALL three before entering T1:

1. **Regime:** VNINDEX EMA20 > EMA100? (must be yes)
2. **Signal quality:** Cloud strong, EMA dist < 10%, liq_warn_T1 = OK or WARN_NEAR?
3. **Sector concentration:** < 30% of active positions in same sector_l4?

All yes → enter T1 (may reduce size at operator discretion).
Any no → skip this symbol today.

---

## Step 7 — Execute T1 Entry

1. Confirm `recommendation` = full_T1 or partial_T1
2. Effective T1 = min(target_T1_M, max_10pct_M) in M VND
3. If gk10 = True: slot already includes 1.25× multiplier in target_T1_M
4. Place limit order at or below current close
5. Log: symbol, entry date, ep1 price, T1 size

Vietnam T+3: shares settle in 3 business days. Minimum hold 5 bars before selling.

---

## Step 8 — T2 Add Protocol

Check existing positions with final_action = WAIT_PB:

- Has close dropped ≥4% from ep1 (below `pb_trigger_price`)?
- Is breadth_t2_permission = True?
- Are we still within 30 bars of entry?
- Is cloud still bullish?

All yes → add T2 = 50% of slot (capped by ADV). Log new average entry.

PTS shadow mode only (if enabled): after 30-bar window, watch 10 more bars for ≥6% strength add.

---

## Step 9 — Monitor Exit Rules

Check all open positions:

| Exit condition | Action |
|---------------|--------|
| Close ≥ ep1 × 1.18 (TP1) | Sell 50% of position (T1 tranche). Keep remaining. |
| Close < trail_price (2.5×ATR14 from peak) | Exit remaining position |
| Bars held ≥ 250 (max hold) | Exit remaining position |
| Bars held < 5 (T+3 lock) | No sells allowed |

---

## Step 10 — End-of-Day Log

Update state files:
- `data/state/regime_state.json`: regime_bull, pct_cloud_bull_a3, breadth_zone
- `data/decision/allocation_plan.json`: active positions, ep1, trail levels, T2 status

Check sector concentration:
- Any single sector_l4 > 30% of active positions → log warning

---

## Weekly Review

- Run full scan with refreshed panel
- Check annual P&L vs VNINDEX benchmark
- Review trades that hit max_hold without TP1 or trail stop
- Update breadth trend chart (20-bar moving average)

---

## Key Reference Files

| File | Purpose |
|------|---------|
| `UPDATED_FINAL_DECISION_MEMO_CLEAN.md` | Classification (authoritative) |
| `UPDATED_BREADTH_RULE_FINAL.md` | Breadth rules with T1/T2 permission logic |
| `UPDATED_phase33_paper_trade_rules.md` | Entry/exit rules |
| `phase34_daily_scan_sample.csv` | Daily scan output |
| `FINAL_DASHBOARD_SPEC.md` | Dashboard panel spec |
| `Cloud_Strategy_A3_20_100_DP_First_FINAL.afl` | AmiBroker production AFL |
| `AFL_PARITY_NOTES.md` | AFL vs Python scan reconciliation |
