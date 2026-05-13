# Final Paper Trade Readiness Confirmation
**Date:** 2026-05-13

## Status: PAPER TRADE READY — Live capital BLOCKED pending gate passage

---

## Production Candidate (Primary)

| Parameter | Value |
|---|---|
| Label | B_cloud20_100_partial |
| Entry type | cloud_only (EMA 20/100, min 3 bear bars) |
| Exit mode | partial_tp (50% at +15%, trail 2.5xATR14, max 250 bars) |
| Universe | ex-VIN3 (exclude VIC, VHM, VRE, VPL<252bars) |
| Fill mode | ema_dist (rank by EMA distance desc) |
| Max positions | 20 |
| Cost assumption | 40 bps round-trip |

**Backtest baselines (ex-VIN3, ema_dist fill, 2012–2026):**
- CAGR: 12.3%
- Max DD: -30.1%
- Sharpe: 1.202
- OOS avg trade: +6.3%
- Hit rate: 67.9%

---

## Shadow Candidate (Monitoring Only)

| Parameter | Value |
|---|---|
| Label | B_cloud21_55_partial |
| Fill mode | momentum (20-bar price ROC desc) |
| Universe | ex-VIN3 |
| Expected CAGR | 9.9% |
| Expected Sharpe | 0.973 |

Shadow remains monitoring/fallback. Promote only if primary stays in drawdown >6 months while shadow is flat/positive, or at explicit allocation review.

---

## Deliverables — Complete

| File | Status |
|---|---|
| pp_backtest/candidate_strategy_manifest.py | Done — frozen strategy configs |
| pp_backtest/ema_portfolio_sim.py | Done — ranked fill (fifo/ema_dist/momentum) |
| pp_backtest/run_hardening.py | Done — steps 2-6 hardening runner |
| data/research/hardening/paper_trade_spec.md | Done — full operational spec |
| data/research/hardening/final_go_no_go.md | Done — 6-question go/no-go |
| pp_backtest/run_shadow_full_ranked.py | Done — shadow all-universe comparison |
| data/research/hardening/shadow_ranked_fill_full.csv | Done — shadow results |
| data/research/hardening/shadow_verdict.md | Done — ex_vin3 + momentum confirmed |
| pp_backtest/daily_paper_trade_runner.py | Done — full daily pipeline |
| pp_backtest/execution_audit.py | Done — gap analysis + backtest mode |
| pp_backtest/live_gate_check.py | Done — 6-gate live deployment checker |
| pp_backtest/paper_trade_reports.py | Done — daily/weekly/monthly reports |

---

## Live Deployment Gates — Current Status

| Gate | Rule | Status |
|---|---|---|
| G1 | >= 63 trading days paper trading | FAIL (paper trade not started) |
| G2 | >= 20 closed paper trades | FAIL (not started) |
| G3 | Avg trade ret >= 4% | FAIL (not started) |
| G4 | Hit rate >= 60% | FAIL (not started) |
| G5 | < 5% of fills with |gap| > 2% | FAIL (backtest shows 9.2% — see note) |
| G6 | NAV within 10% of paper peak | FAIL (not started) |

**G5 note:** Historical backtest shows 9.2% of fills have |gap|>2%, failing the <5% gate. Avg gap ~0% (balanced). Worst offenders: POM, HPX, thin-float names. Options: (a) switch T+1 entry to ATC (close) to eliminate open gap, (b) raise cost assumption to 60 bps and accept gate as informational, (c) filter out symbols with historical avg_gap > 1%.

---

## Hardening Results Summary

**Cost sensitivity (primary, ex-VIN3):**
- 40 bps: CAGR=12.3%, Sharpe=1.202
- 60 bps: CAGR=11.5%, Sharpe=1.150
- 100 bps: CAGR=10.0%, Sharpe=1.050

**Position sizing:**
- max_pos=10: CAGR=11.8%
- max_pos=15: CAGR=12.1%
- max_pos=20: CAGR=12.3% (selected)

**VIN sensitivity:**
- Full universe: CAGR=10.7%, maxDD=-43.4%
- ex-VIN3: CAGR=12.3%, maxDD=-30.1% (selected — 13pp DD improvement)

**Regime breakdown:**
- 2012–2017: CAGR=11.3%
- 2018–2022: CAGR=19.6%
- 2023–2026: CAGR=-2.3% (2022 bear market unwind; OOS trade quality positive)

---

## Daily Operations Checklist

```
Each trading day (after close):
  1. Update OHLCV panel (scripts/build_fireant_ssot.py or manual)
  2. Run: .venv\Scripts\python.exe pp_backtest/daily_paper_trade_runner.py --date YYYY-MM-DD
  3. Review signals_log.csv for fills and skips
  4. Confirm positions.csv is correct

Weekly (Friday):
  5. Run: .venv\Scripts\python.exe pp_backtest/paper_trade_reports.py --weekly
  6. Run: .venv\Scripts\python.exe pp_backtest/live_gate_check.py

Monthly:
  7. Run: .venv\Scripts\python.exe pp_backtest/paper_trade_reports.py --monthly
  8. Review execution_audit.py output

At 63 trading days:
  9. Run: .venv\Scripts\python.exe pp_backtest/live_gate_check.py
  10. If all 6 gates pass -> proceed to tiny live pilot (1-2% capital)
```

---

## Ledger Files

```
data/paper_trade/
  positions.csv           -- current open positions
  closed_trades.csv       -- all completed trades
  nav_history.csv         -- daily NAV (base=1.0)
  signals_log.csv         -- every signal (filled / skip)
  execution_audit.csv     -- entry gap (signal close vs T+1 open)
  live_gate_status.csv    -- latest gate check output
  reports/
    daily_YYYY-MM-DD.md
    weekly_YYYY-MM-DD.md
    monthly_YYYY-MM.md
```

---

## Key Constraints (Do Not Reopen)

- Parameter space is frozen. No new EMA combinations, ATR stops, or breakout variants.
- level_breakout strategy is discarded — not for paper trade.
- Shadow is monitoring only. Primary is the capital allocation vehicle.
- Live capital requires ALL 6 gates. No exceptions.
