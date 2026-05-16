# Final Daily Runbook — A3 DP-First Paper Trade (Updated 2026-05-16)

Supersedes: FINAL_DAILY_RUNBOOK.md
Change: Breadth defense zone no longer blocks T1. Corrected final_action enum. 10-step order.

---

## Pre-Market Checklist (before 9:00 AM)

### Step 1 — Update data panel
```
python scripts/run_weekly_full_fetch.py
```

### Step 2 — Check VNINDEX regime
- Compute: VNINDEX EMA20 vs EMA100
- If EMA20 < EMA100: bear regime → NO new T1 entries today. Review existing positions only.
- If EMA20 > EMA100: bull regime → proceed to Step 3

### Step 3 — Check A3 breadth
- Compute pct_cloud_bull_20_100 from Phase34 scan output
- Current value is shown in every row of phase34_daily_scan_sample.csv

| breadth | Zone | T1 | T2 |
|---------|------|----|-----|
| ≥ 40% | Normal | YES | YES |
| 35–40% | Caution | YES | Reduced |
| < 35% | Defense | YES (review required) | NO |

**Note (2026-05-16 current breadth: 31.9% → Defense zone)**

Defense does NOT mean no entries. It means:
- Check each NEW_T1_MANUAL_REVIEW_BREADTH signal individually
- Confirm: VNINDEX bull? Signal quality OK? Sector concentration < 30%?
- Operator decides whether to enter. Not automatic.

### Step 4 — Run Phase34 scan
```
.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan
```
Review: `data/research/portfolio_optimization/missing_work/phase34_daily_scan_sample.csv`

### Step 5 — Review signals by final_action

| final_action | Meaning | Operator action |
|-------------|---------|----------------|
| NEW_T1 | Normal entry, all gates clear | Check liquidity, place T1 order |
| NEW_T1_MANUAL_REVIEW_BREADTH | Defense zone, T1 allowed with review | Review 3 conditions, decide |
| WAIT_PB | T1 entered, watching for pullback | Monitor pb_trigger_price |
| ADD_T2 | Pullback ≥4% triggered | Add T2 (50% of slot, capped by ADV) |
| HOLD_T1_ONLY | T2 window expired, no pullback | Hold T1, no add |
| NO_T2_BREADTH | T2 blocked by breadth | Hold T1, no T2 add |
| SKIP_LIQUIDITY | ADV cap too low | Skip this symbol |
| SKIP_VNINDEX_BEAR | Regime gate — VNINDEX bear | No new entries |
| WATCH_ONLY | S3/PTS signal, A3 not active | Track only, no action |

### Step 6 — Trade execution (when final_action = NEW_T1 or NEW_T1_MANUAL_REVIEW_BREADTH)

1. Check `recommendation`: must be `full_T1` or `partial_T1`
2. Compute effective T1:
   - `effective_T1_VND = min(T1_target_VND, adv50_VND × 10%)`
   - Shown in `target_T1_M` column (M VND)
3. GK10 multiplier: if `gk10 = True`, slot × 1.25
4. Check sector_l4: if >30% of active portfolio in same L4, flag for review
5. Place limit order at or below current close
6. Vietnam settlement: T+3, minimum hold 5 bars before selling

### Step 7 — T2 add protocol (when WAIT_PB state)

- Monitor: has close dropped ≥4% from ep1 (check pb_trigger_price column)?
- If yes AND within 30 bars AND breadth_t2_permission = True AND cloud still bullish:
  - Add T2 = 50% of slot (capped by ADV)
- If 30 bars expire with no pullback:
  - PTS mode ON: watch 10 more bars for ≥6% strength add
  - PTS mode OFF (default): no T2, hold T1 only

### Step 8 — Monitor existing positions

Check exit rules for all open positions:
- TP1: price ≥ ep1 × 1.18 → sell 50% of position (T1 tranche profit take)
- Trail: close < (highest_close − 2.5 × ATR14) → exit remaining (check trail_price)
- Max hold: 250 bars from entry → exit remaining regardless of P&L
- Minimum lock: no sells within 5 bars of entry (T+3 constraint)

### Step 9 — Sector concentration check

Review active open positions:
- Count positions per sector_l4
- If any single L4 > 30% of active positions → alert (not automatic block)
- If Banking + Securities > 40% combined → elevated alert

### Step 10 — End-of-day log

Update tracking files:
- `data/state/regime_state.json`: breadth, regime, breadth_zone
- `data/decision/allocation_plan.json`: active positions, entry prices, trail stops

---

## Weekly Review

- Review annual P&L vs benchmark
- Check any trades that hit max_hold without TP1 or trail stop
- Update sector concentration report
- Re-run Phase34 scan with updated panel

---

## Key File Locations

| File | Purpose |
|------|---------|
| `missing_work/phase34_daily_scan_sample.csv` | Today's active setups (Phase34 schema) |
| `missing_work/UPDATED_FINAL_DECISION_MEMO_CLEAN.md` | Strategy classification (authoritative) |
| `missing_work/UPDATED_BREADTH_RULE_FINAL.md` | Breadth rules (evidence-based) |
| `missing_work/UPDATED_phase33_paper_trade_rules.md` | Paper trade entry/exit rules |
| `missing_work/sector_l4_map_coverage.csv` | Sector classification |
| `phase31/PHASE31_LIQUIDITY_AUDIT.md` | Liquidity unit audit |
| `missing_work/Cloud_Strategy_A3_20_100_DP_First_FINAL.afl` | AmiBroker production AFL |

---

## Data Sources

- VNINDEX: FireAnt / HOSE data feed
- Panel data: existing parquet pipeline (`src/` and `pp_backtest/`)
- Breadth: computed from panel — no external source needed
- ADV50: `panel["value"].rolling(50).mean()` (VND unit confirmed, Phase 3.1)
