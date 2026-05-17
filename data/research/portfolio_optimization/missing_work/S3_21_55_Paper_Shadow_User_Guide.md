# S3 EMA21/55 Paper Shadow — User Guide

Date: 2026-05-16 | AFL: Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl

---

## What This Is

S3 EMA21/55 is now a **PAPER_TRADE_SHADOW** strategy. It was upgraded from RESEARCH_ONLY
after one finding: setting max_hold = 60 bars raises MAR from -0.011 to 0.377.

**This is a paper-tracking tool only.** It never creates real orders.

---

## The max_hold=60 Rule

S3 uses EMA21/55 — a faster cycle than A3 (EMA20/100).
Positions held beyond 60 bars ride the full reversal of the 55-bar signal.
60 bars ≈ 3 trading months = natural horizon for a 55-bar EMA trend.

**The AFL locks max_hold at exactly 60. The Param slider range is [60, 60] — it cannot be changed.**

---

## How to Use the AFL

1. Load `Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl` in AmiBroker
2. Run as an exploration or chart overlay (NOT a live backtest for sizing)
3. Chart signals:
   - Cyan up-triangle: S3 cloud breakout (potential paper entry)
   - Orange down-triangle: max_hold=60 force exit
   - Red down-triangle: trail stop exit
   - Hollow green up-triangle: TP1 +18% hit
4. Title bar shows: bars since entry, max hold remaining, TP1 and trail levels

---

## What to Do with Signals

When exploration shows `Status = PAPER_SHADOW` and `Exit Status = HOLD`:

1. Check `Cloud = BULL` and `Bars Since` < 60
2. Check VNINDEX regime = bull (EMA20 > EMA100 in separate chart)
3. If both true → log a paper entry in `data/trading/live/s3_shadow_paper_trades.csv`
4. Monitor daily for:
   - `Exit Status = TRAIL_EXIT` → log paper exit
   - `Exit Status = TP1_HIT` → log partial paper exit (50%)
   - `Max Hold Remaining = 0` → `Exit Status = FORCE_EXIT_MAX60` → log paper exit

---

## What NOT to Do

- Do NOT use position sizes from this AFL for real orders
- Do NOT route to DNSE or any broker
- Do NOT combine this P&L with A3 production P&L
- Do NOT change max_hold from 60 to any other value

---

## S3 as A3 Lead Signal

When running both S3 shadow (this AFL) and A3 production scan simultaneously:

If S3 fires on symbol X at bar N, and A3 fires on the same symbol within bars N+1 to N+5:
- Tag the A3 signal with `a3_s3_lead_5d = True`
- On days with multiple A3 NEW_T1 signals, prioritize `a3_s3_lead_5d=True` first

This is a sort order hint only. A3 decisions are never blocked by S3 absence.

---

## Performance Reference

| Config | MAR | CAGR | MaxDD | Status |
|--------|-----|------|-------|--------|
| S3 max_hold=250 | -0.011 | — | — | REJECTED |
| S3 max_hold=60 | 0.377 | 7.92% | -20.99% | PAPER_TRADE_SHADOW |
| S3+GK5+max60+top100 | 0.449 | 12.90% | -28.73% | RESEARCH MONITOR |

Backtest: 2012-2026, 5B VND, 10% ADV participation (corrected Phase 3.1 liquidity).

---

## Production Upgrade Path

S3 requires ALL before any production discussion:
1. 12 months of live paper data with max_hold=60
2. Live paper MAR ≥ 0.35 over the 12-month period
3. No 12-month rolling MaxDD exceeding -25%
4. Bear year performance better than -18% (current backtest worst year 2022)
5. Explicit operator decision after reviewing live paper results

No timeline. No automatic upgrade.
