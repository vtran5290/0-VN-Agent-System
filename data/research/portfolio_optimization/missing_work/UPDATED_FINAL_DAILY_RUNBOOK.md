# Final Daily Runbook — A3 DP-First + S3 Shadow

Version: PHASE36 | Date: 2026-05-17 | Decision: **CONDITIONAL_NO_CHANGE**
Change: Phase36 operator sort by `a3_rank_score` DESC (display only). A3 production logic unchanged. See `phase36_daily_operator_report.md`.

---

## Pre-Market Checklist (before 9:00 AM)

### Step 1 — Update data panel
```
python scripts/run_weekly_full_fetch.py
```

### Step 2 — Check VNINDEX regime
- Compute: VNINDEX EMA20 vs EMA100
- If EMA20 < EMA100: bear regime → NO new A3 T1. NO new S3 shadow entries. Review exits only.
- If EMA20 > EMA100: bull regime → proceed to Step 3

### Step 3 — Run Phase35 scan
```
.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan
```
Review: `data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv` (aliases: phase35, phase34)
Schema: 82 fields. See `phase36_daily_scan_schema.csv`.
Operator report: `phase36_daily_operator_report.md`

### Step 3b — S3 Shadow Check (NEW — Phase35)

After scan, filter by `s3_shadow_action`:

| s3_shadow_action | Operator action |
|------------------------|----------------|
| PAPER_S3_SHADOW | Confirm regime=bull + max_hold=60 + liquidity → log paper entry (separate ledger) |
| WATCH_ONLY | No shadow entry (regime/liquidity/cloud fail or inactive) |
| s3_research_monitor_action = PAPER_S3_RESEARCH_MONITOR | GK5+max60+top100 research track only — no live order |
| REJECTED_CONFIG / S3_MAX250_REJECTED | Do not use max_hold=250 shadow — research rejected |

**MAX HOLD CHECK (CRITICAL):** Any S3 shadow row with `s3_shadow_bars_since ≥ 60` MUST be exited today. No exceptions. Log exit_reason = MAX_HOLD_60.

### Step 4 — Check A3 breadth (advisory)

| breadth | Zone | T1 | T2 |
|---------|------|----|-----|
| ≥ 40% | Normal | YES | YES |
| 35–40% | Caution | YES | T2 blocked |
| < 35% | Defense | YES (review required) | NO |

Defense does NOT block T1. Only VNINDEX bear blocks T1.
Current as of 2026-05-16: 31.9% → Defense zone.

### Step 5 — Review A3 signals by final_action

| final_action | Operator action |
|-------------|----------------|
| NEW_T1 | Sort a3_s3_lead_5d=True first, then ADV. Check liquidity. Place T1 order (after real capital approval). |
| NEW_T1_MANUAL_REVIEW_BREADTH | Review: regime OK? signal quality OK? sector < 30%? Enter if all yes. |
| WAIT_PB | Monitor pb_trigger_price |
| ADD_T2 | Add T2 (50% slot, ADV capped) |
| HOLD_T1_ONLY | Hold T1, no add |
| NO_T2_BREADTH | Hold T1, T2 blocked |
| SKIP_LIQUIDITY | Skip |
| SKIP_VNINDEX_BEAR | No new entries |
| NEW_S3_SHADOW | Paper only — handled in Step 3b |

**A3 priority rule (Phase36):** Multiple NEW_T1 same day → sort by `a3_rank_score` descending.
Lead_11_20 (best, +2.0) and lead_21_30 (good, +1.0) rank highest. same_bar_0 (chase, -0.5) ranks lowest.
`a3_s3_lead_5d=True` (legacy boolean) can be used as a secondary sort filter.

### Step 6 — Trade execution (A3 — after real capital approval only)

1. Check `recommendation`: full_T1 or partial_T1
2. Effective T1 = min(target_T1_M, max_10pct_M)
3. If `gk10 = True`: slot × 1.25
4. Check sector_l4 concentration < 30%
5. Place limit order at or below current close
6. T+3: minimum hold 5 bars before selling. Log entry.

### Step 7 — T2 add protocol (A3 WAIT_PB positions)

- Close dropped ≥4% from ep1 (check pb_trigger_price)?
- breadth_t2_permission = True?
- Within 30 bars of entry?
- Cloud still bullish?

All yes → add T2. Log new average entry.

### Step 8 — Monitor A3 exits

| Exit condition | Action |
|---------------|--------|
| Close ≥ ep1 × 1.18 | Sell 50% (TP1) |
| Close < trail_price (2.5×ATR14) | Exit remaining |
| Bars held ≥ 250 | Exit remaining |
| Bars held < 5 | No sells (T+3 lock) |

### Step 8b — Monitor S3 shadow exits (paper only)

| Exit condition | Action |
|---------------|--------|
| Close ≥ s3_entry × 1.18 | Log paper partial exit (TP1 50%) |
| Close < s3_shadow_trail_price (3.5×ATR14) | Log paper exit |
| **s3_shadow_bars_since ≥ 60** | **Force paper exit — HARD RULE** |
| Bars held < 5 | No exits |

### Step 9 — Sector concentration check

- Any single sector_l4 > 30% of active A3 positions → alert (not block)

### Step 10 — End-of-day log

- `data/state/regime_state.json`: regime_bull, pct_cloud_bull_a3, breadth_zone
- `data/decision/allocation_plan.json`: A3 active positions, ep1, trail levels
- `data/trading/live/s3_shadow_positions.csv`: S3 shadow open positions
- `data/trading/live/s3_shadow_paper_trades.csv`: S3 completed trades

---

## Weekly Review

- Run full scan with refreshed panel
- Check A3 paper P&L vs VNINDEX (separate equity curve from S3)
- Check S3 shadow paper P&L vs VNINDEX (separate equity curve)
- Review trades that hit max_hold (A3: 250 bars; S3: 60 bars)
- Update breadth trend chart (20-bar moving average)

---

## Key File Locations

| File | Purpose |
|------|---------|
| `missing_work/phase35_daily_scan_sample.csv` | Today's active setups (Phase35, 47 fields) |
| `missing_work/UPDATED_S3_DECISION_MEMO.md` | S3 upgrade decision (authoritative) |
| `missing_work/S3_SHADOW_PAPER_TRADE_RULES.md` | S3 shadow hard rules |
| `missing_work/UPDATED_FINAL_DECISION_MEMO_CLEAN.md` | Strategy classification |
| `missing_work/UPDATED_BREADTH_RULE_FINAL.md` | Breadth rules |
| `missing_work/UPDATED_phase33_paper_trade_rules.md` | Paper trade entry/exit rules |
| `data/trading/s3_shadow_paper_trades.csv` | S3 shadow paper ledger (Phase35 base, TP=18%) |
| `data/trading/s3_shadow_paper_positions.csv` | S3 shadow open positions |
| `data/trading/s3_combo_paper_trades.csv` | S3 combo paper ledger (Phase36, TP=10%) |
| `data/trading/s3_combo_paper_positions.csv` | S3 combo open positions |
| `missing_work/Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl` | S3 shadow AFL (Phase35 base, TP=18%) |
| `missing_work/Cloud_Strategy_A3_20_100_DP_First_FINAL.afl` | A3 production AFL |
