# Daily Scan Operator Guide — A3 Production + S3 Paper Shadow

**Date:** 2026-05-17 | **Scan SSOT:** `phase36_daily_scan_sample.csv` (aliases: phase35, phase34)  
**Phase36:** CONDITIONAL_NO_CHANGE — ranking sorts review order only; `final_action` unchanged.

## 1. Run scan

```powershell
.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan
```

Legacy satellite (not SSOT): `python pp_backtest/daily_three_strategy_scan.py`

## 2. Panel 1 — Data health

- Check `as_of_date` vs latest market session (stale if panel lag > 1 session).
- `regime_bull`: VNINDEX EMA20/100.
- `pct_cloud_bull_a3` / `breadth_zone`: defense `<35%`, caution `35–40%`, normal `≥40%`.

## 3. Panel 2 — A3 production (ONLY real-capital actions)

Use **`final_action`** only. OMS must not recompute signals.  
Review multiple `NEW_T1` names in CSV order (`phase36_operator_priority` / `a3_rank_score` DESC) — **does not change eligibility or size**.

| final_action | Operator |
|--------------|----------|
| NEW_T1 | T1 eligible (sort `a3_priority_boost_from_s3` first) |
| NEW_T1_MANUAL_REVIEW_BREADTH | Manual review then T1 if approved |
| ADD_T2 | Add T2 if PB rules met |
| NO_T2_BREADTH | Hold T1; T2 blocked by breadth |
| TP1_PARTIAL / TRAIL_EXIT / MAX_HOLD_EXIT | Manage open position per A3 rules |
| SKIP_VNINDEX_BEAR | No new T1 |
| SKIP_LIQUIDITY | No entry — ADV fail |

**S3 does not change A3 eligibility.**

## 4. Panel 3 — S3 paper shadow (max_hold=60)

Filter `s3_shadow_action == PAPER_S3_SHADOW`.

- `s3_shadow_classification` must be `PAPER_TRADE_SHADOW`.
- `s3_max_hold` = 60; `s3_no_real_order_flag` = True.
- Log to **separate** `s3_shadow_paper_trades.csv` — not A3 P&L.
- **No live orders. No DNSE.**

Rejected: S3 max_hold=250 → `REJECTED_CONFIG` / `S3_MAX250_REJECTED` — do not trade.

## 5. Panel 4 — S3 research monitor

Filter `s3_gk5_top100_monitor == True`.

- `s3_research_monitor_action` = `PAPER_S3_RESEARCH_MONITOR`
- Parallel paper research only; no capital, no DNSE.

## 6. Panel 5 — Legacy satellite

`daily_three_strategy_scan` outputs (B20/100, B21/55, C_GK) are **context only**.

## 7. Warnings

- Duplicate symbol already in live book
- Stale panel / FireAnt gaps
- Liquidity WARN/CRITICAL
- Do not mix S3 shadow P&L with A3

## 8. Order intents

```powershell
python -m src.trading.live.run_daily  # or your OMS entrypoint
```

- A3: from `final_action` only.
- S3: `PAPER_S3_SHADOW` / `PAPER_S3_RESEARCH_MONITOR` → quantity 0, no DNSE.
