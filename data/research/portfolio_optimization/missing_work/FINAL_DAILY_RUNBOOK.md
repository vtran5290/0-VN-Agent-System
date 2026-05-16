# Final Daily Runbook — A3 DP-First Paper Trade

As of: 2026-05-16

---

## Pre-Market Checklist (before 9:00 AM)

1. **Update data panel**
   ```
   python scripts/run_weekly_full_fetch.py
   ```

2. **Check VNINDEX regime**
   - Open Phase33 scan or compute: VNINDEX EMA20 vs EMA100
   - If bear regime → NO new entries today. Review existing positions only.

3. **Check A3 breadth**
   - Compute pct_cloud_bull_20_100 from phase33_daily_scan_sample.csv
   - ≥ 40%: normal mode
   - 35–40%: caution (T1 only, no T2)
   - < 35%: defense (no new entries, block T2)
   - Current (2026-05-16): **31.9% → DEFENSE**

4. **Run Phase33 scan**
   ```
   .venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan
   ```
   Review: `data/research/portfolio_optimization/missing_work/phase33_daily_scan_sample.csv`

---

## Signal Interpretation

| final_action | Meaning | Action |
|-------------|---------|--------|
| NEW_T1 | Enter T1 (50% of slot) today | Check liquidity, place order |
| WAIT_PB | Signal active, no T2 yet | Monitor for ≥4% pullback |
| ADD_T2 | Pullback ≥4% hit within window | Add T2 (50% of slot) |
| HOLD_T1_ONLY | Bear regime, no T2 add | Hold existing T1, no add |
| NO_NEW_ENTRY_BREADTH | Breadth in defense zone | No new entries |
| SKIP_LIQUIDITY | ADV cap too low | Skip, position too large for liquidity |
| WATCH_ONLY | S3 signal or not in A3 universe | No action, track only |

---

## Trade Execution (when final_action = NEW_T1)

1. Check `recommendation`: must be `full_T1` or `partial_T1`
2. Compute effective T1:
   - `effective_T1_VND = min(T1_target_VND, adv50_VND × 10%)`
   - `effective_T1_VND` shown in `target_T1_M` column (in M VND)
3. GK10 multiplier: if `gk10 = True`, slot × 1.25
4. Check sector_l4: if >30% of active portfolio already in same L4, review concentration
5. Place limit order at or below current close (prefer entry on minor pullback intraday)
6. Vietnam settlement: shares bought today settle T+3, minimum hold 5 bars before selling

---

## T2 Add Protocol (when in PB_WAIT state)

- Monitor daily: has close dropped ≥4% from entry price (ep1)?
- If yes AND still within 30 bars AND cloud still bullish:
  - Add T2 = 50% of slot (capped by ADV)
  - New average entry = (T1 × ep1 + T2 × ep2) / (T1 + T2)
- If 30 bars expire with no pullback:
  - If PTS mode ON: watch 10 more bars for ≥6% strength add (cloud + EMA bullish)
  - If PTS mode OFF (default): no T2, hold T1 only

---

## Exit Protocol

1. **TP1**: when price ≥ ep1 × 1.18 → sell 50% of position (T1 tranche profit take)
2. **Trail stop**: when close < (highest_close_since_entry − 2.5 × ATR14) → exit remaining
3. **Max hold**: after 250 bars → exit remaining regardless of P&L
4. **Minimum lock**: no sells within 5 bars of entry (T+3 VN settlement)

---

## Weekly Review

- Update `data/state/regime_state.json` with current breadth and regime
- Check annual P&L tracking vs benchmark
- Review any trades that hit max_hold without TP1 or trail stop
- Update `data/decision/allocation_plan.json` with current active positions

---

## Key File Locations

| File | Purpose |
|------|---------|
| `missing_work/phase33_daily_scan_sample.csv` | Today's active setups |
| `missing_work/FINAL_DECISION_MEMO_CLEAN.md` | Strategy classification |
| `missing_work/BREADTH_RULE_FINAL.md` | Breadth gate rules (evidence-based) |
| `missing_work/sector_l4_map_coverage.csv` | Sector classification |
| `phase31/PHASE31_LIQUIDITY_AUDIT.md` | Liquidity unit audit |
| `phase25/phase25a_dp_trade_ledger.csv` | A3 DP historical trades |

---

## Emergency Contacts / Data Sources

- VNINDEX: FireAnt / HOSE data feed
- Panel data: existing parquet pipeline (see `src/` and `pp_backtest/`)
- Breadth: computed from panel — no external source needed
- ADV50: computed from panel["value"] column (VND unit confirmed)
