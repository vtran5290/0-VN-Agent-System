#!/usr/bin/env python3
"""
Paper trade reporting — daily, weekly, monthly.

Reads ledger files from data/paper_trade/ and generates structured reports.
Reports are written to data/paper_trade/reports/ as markdown + CSV.

Usage:
    .venv\\Scripts\\python.exe pp_backtest/paper_trade_reports.py --daily
    .venv\\Scripts\\python.exe pp_backtest/paper_trade_reports.py --weekly
    .venv\\Scripts\\python.exe pp_backtest/paper_trade_reports.py --monthly
    .venv\\Scripts\\python.exe pp_backtest/paper_trade_reports.py --all
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO     = Path(__file__).resolve().parents[1]
PT_DIR   = REPO / "data" / "paper_trade"
REP_DIR  = PT_DIR / "reports"
REP_DIR.mkdir(parents=True, exist_ok=True)

CLOSED_CSV = PT_DIR / "closed_trades.csv"
NAV_CSV    = PT_DIR / "nav_history.csv"
SIGNALS_CSV = PT_DIR / "signals_log.csv"
POSITIONS_CSV = PT_DIR / "positions.csv"

# Backtest baselines
BT_AVG_RET  = 0.063
BT_HIT_RATE = 0.679
BT_CAGR     = 0.123
BT_SHARPE   = 1.202
BT_MAX_DD   = -0.301


def _load(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    df = pd.read_csv(path)
    for col in ["date", "entry_date", "exit_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _nav_stats(nav: pd.DataFrame) -> dict:
    if nav.empty:
        return {}
    nav_vals = nav["nav"].dropna()
    current  = float(nav_vals.iloc[-1])
    peak     = float(nav_vals.max())
    dd       = (current - peak) / peak
    n_days   = len(nav)
    n_years  = max(n_days / 252, 0.01)
    cagr     = (current / 1.0) ** (1 / n_years) - 1.0
    dr       = nav_vals.pct_change().dropna()
    sharpe   = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else np.nan
    return {
        "nav": current, "peak": peak, "dd": dd,
        "cagr": cagr, "sharpe": sharpe, "n_days": n_days,
    }


def _trade_stats(trades: pd.DataFrame) -> dict:
    if trades.empty or "net_return" not in trades.columns:
        return {}
    rets = trades["net_return"].dropna()
    if len(rets) == 0:
        return {}
    wins   = rets[rets > 0].sum()
    loss   = abs(rets[rets < 0].sum()) or 1e-12
    return {
        "n_trades":   len(rets),
        "hit_rate":   float((rets > 0).mean()),
        "avg_ret":    float(rets.mean()),
        "med_ret":    float(rets.median()),
        "pf":         wins / loss,
        "avg_hold":   float(trades["hold_bars"].mean()) if "hold_bars" in trades.columns else np.nan,
    }


# ── Daily report ──────────────────────────────────────────────────────────────

def daily_report(as_of: pd.Timestamp = None) -> str:
    nav     = _load(NAV_CSV)
    closed  = _load(CLOSED_CSV)
    signals = _load(SIGNALS_CSV)
    pos     = _load(POSITIONS_CSV)

    if nav.empty:
        return "No paper trade data available yet."

    last_date = as_of or nav["date"].max()
    ns   = _nav_stats(nav)
    nav_today = nav[nav["date"] == last_date]

    # Today's signals
    sig_today = signals[signals["date"] == last_date] if not signals.empty else pd.DataFrame()
    filled    = sig_today[sig_today["action"] == "filled"] if not sig_today.empty else pd.DataFrame()
    skipped   = sig_today[sig_today["action"] == "skip"]   if not sig_today.empty else pd.DataFrame()

    # Today's closes
    cls_today = closed[closed["exit_date"] == last_date] if not closed.empty else pd.DataFrame()

    lines = [
        f"# Daily Paper Trade Report — {last_date.date()}",
        "",
        "## Portfolio Status",
        f"| Metric | Value |",
        f"|---|---|",
        f"| NAV | {ns.get('nav', 1.0):.4f} |",
        f"| Drawdown from peak | {ns.get('dd', 0):.1%} |",
        f"| Open positions | {len(pos)} / 20 |",
        f"| Cash | {(1 - len(pos)/20)*100:.0f}% |",
        f"| Running CAGR | {ns.get('cagr', 0):.1%} |",
        "",
        "## Today's Signals",
        f"| Metric | Value |",
        f"|---|---|",
        f"| New signals | {len(sig_today)} |",
        f"| Filled | {len(filled)} |",
        f"| Skipped (capacity) | {len(skipped[skipped.get('skip_reason','') == 'capacity_full']) if not skipped.empty and 'skip_reason' in skipped else 0} |",
        f"| Skipped (already open) | {len(skipped[skipped.get('skip_reason','') == 'already_open']) if not skipped.empty and 'skip_reason' in skipped else 0} |",
        "",
    ]

    if not filled.empty:
        lines += ["## New Entries", "| Symbol | Entry Price | EMA Dist |", "|---|---|---|"]
        for _, r in filled.iterrows():
            lines.append(f"| {r.symbol} | {r.get('entry_price', 'n/a'):.2f} | {r.get('ema_dist', 0):.1%} |")
        lines.append("")

    if not cls_today.empty:
        lines += ["## Exits Today", "| Symbol | Net Ret | Hold | Reason |", "|---|---|---|---|"]
        for _, r in cls_today.iterrows():
            lines.append(f"| {r.symbol} | {r.get('net_return', 0):.1%} | {int(r.get('hold_bars', 0))}d | {r.get('exit_reason', '')} |")
        lines.append("")

    if not pos.empty:
        lines += ["## Open Positions", "| Symbol | Entry | Hold | TP1 | EMA Dist |", "|---|---|---|---|---|"]
        for _, p in pos.sort_values("entry_date").iterrows():
            tp_flag = "Hit" if p.get("tp1_hit") else "-"
            lines.append(f"| {p.symbol} | {p.entry_price:.2f} | {int(p.hold_bars)}d | {tp_flag} | {p.get('ema_dist_at_entry', 0):.1%} |")
        lines.append("")

    report = "\n".join(lines)
    out = REP_DIR / f"daily_{last_date.date()}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Daily report: {out}")
    return report


# ── Weekly report ─────────────────────────────────────────────────────────────

def weekly_report(weeks_back: int = 0) -> str:
    nav    = _load(NAV_CSV)
    closed = _load(CLOSED_CSV)

    if nav.empty:
        return "No paper trade data available yet."

    last_date  = nav["date"].max()
    week_start = last_date - pd.Timedelta(days=7 * (weeks_back + 1))
    week_end   = last_date - pd.Timedelta(days=7 * weeks_back)

    week_closed = (closed[(closed["exit_date"] >= week_start) &
                          (closed["exit_date"] <= week_end)]
                   if not closed.empty else pd.DataFrame())
    week_ts     = _trade_stats(week_closed)
    all_ts      = _trade_stats(closed)
    ns          = _nav_stats(nav)

    # Rolling Sharpe (last 52 weeks)
    if len(nav) >= 10:
        dr     = nav["nav"].pct_change().dropna()
        sharpe = float(dr.tail(252).mean() / dr.tail(252).std() * np.sqrt(252)) if dr.tail(252).std() > 0 else np.nan
    else:
        sharpe = np.nan

    def _cmp(val, bt_val, label, higher_is_better=True):
        if np.isnan(val):
            return f"{label}: n/a"
        delta = val - bt_val
        sign  = "+" if delta >= 0 else ""
        flag  = "[OK]" if (delta >= 0) == higher_is_better else "[!!]"
        return f"{label}: {val:.1%}  {flag} ({sign}{delta:.1%} vs backtest {bt_val:.1%})"

    lines = [
        f"# Weekly Paper Trade Report — Week ending {week_end.date()}",
        "",
        "## Portfolio",
        f"| NAV | {ns.get('nav', 1.0):.4f} |",
        f"|---|---|",
        f"| Drawdown | {ns.get('dd', 0):.1%} |",
        f"| Running CAGR | {ns.get('cagr', 0):.1%}  (backtest: {BT_CAGR:.1%}) |",
        f"| Rolling Sharpe (52w) | {sharpe:.3f}  (backtest: {BT_SHARPE:.3f}) |" if not np.isnan(sharpe) else "| Rolling Sharpe | insufficient data |",
        "",
        "## This Week's Trades",
        f"| Trades closed | {week_ts.get('n_trades', 0)} |",
        f"|---|---|",
        f"| Avg net return | {week_ts.get('avg_ret', 0):.1%} |",
        f"| Hit rate | {week_ts.get('hit_rate', 0):.1%} |",
        f"| Avg hold | {week_ts.get('avg_hold', 0):.0f} days |",
        "",
        "## Cumulative vs Backtest Baseline",
        f"| Metric | Paper | Backtest | Status |",
        f"|---|---|---|---|",
        f"| Avg trade ret | {all_ts.get('avg_ret', float('nan')):.1%} | {BT_AVG_RET:.1%} | {'[OK]' if all_ts.get('avg_ret', 0) >= BT_AVG_RET * 0.7 else '[!!]'} |",
        f"| Hit rate | {all_ts.get('hit_rate', float('nan')):.1%} | {BT_HIT_RATE:.1%} | {'[OK]' if all_ts.get('hit_rate', 0) >= 0.60 else '[!!]'} |",
        f"| Max DD | {ns.get('dd', 0):.1%} | {BT_MAX_DD:.1%} | {'[OK]' if ns.get('dd', 0) >= BT_MAX_DD else '[!!]'} |",
        "",
    ]

    if not week_closed.empty:
        lines += ["## Closed Trades This Week",
                  "| Symbol | Net Ret | Hold | Reason |", "|---|---|---|---|"]
        for _, r in week_closed.sort_values("exit_date").iterrows():
            lines.append(f"| {r.symbol} | {r.get('net_return', 0):.1%} | {int(r.get('hold_bars', 0))}d | {r.get('exit_reason', '')} |")
        lines.append("")

    report = "\n".join(lines)
    out = REP_DIR / f"weekly_{week_end.date()}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Weekly report: {out}")
    return report


# ── Monthly report ────────────────────────────────────────────────────────────

def monthly_report(months_back: int = 0) -> str:
    nav    = _load(NAV_CSV)
    closed = _load(CLOSED_CSV)
    signals = _load(SIGNALS_CSV)

    if nav.empty:
        return "No paper trade data available yet."

    last_date   = nav["date"].max()
    month_start = (last_date - pd.DateOffset(months=months_back + 1)).replace(day=1)
    month_end   = (last_date - pd.DateOffset(months=months_back)).replace(day=1) - pd.Timedelta(days=1)

    month_closed  = (closed[(closed["exit_date"] >= month_start) &
                            (closed["exit_date"] <= month_end)]
                     if not closed.empty else pd.DataFrame())
    month_signals = (signals[(signals["date"] >= month_start) &
                             (signals["date"] <= month_end)]
                     if not signals.empty else pd.DataFrame())

    mts = _trade_stats(month_closed)
    ats = _trade_stats(closed)
    ns  = _nav_stats(nav)

    # Capacity usage: filled / total_signals
    if not month_signals.empty and "action" in month_signals.columns:
        n_filled  = (month_signals["action"] == "filled").sum()
        n_total   = len(month_signals)
        cap_usage = n_filled / n_total if n_total > 0 else 0.0
    else:
        n_filled = n_total = 0
        cap_usage = 0.0

    # Turnover: positions opened per month
    n_open = len(month_closed)

    lines = [
        f"# Monthly Paper Trade Report — {month_start.strftime('%B %Y')}",
        "",
        "## Month Summary",
        f"| Metric | This Month | Cumulative | Backtest |",
        f"|---|---|---|---|",
        f"| Trades closed | {mts.get('n_trades', 0)} | {ats.get('n_trades', 0)} | — |",
        f"| Avg trade ret | {mts.get('avg_ret', float('nan')):.1%} | {ats.get('avg_ret', float('nan')):.1%} | {BT_AVG_RET:.1%} |",
        f"| Hit rate | {mts.get('hit_rate', float('nan')):.1%} | {ats.get('hit_rate', float('nan')):.1%} | {BT_HIT_RATE:.1%} |",
        f"| Profit factor | {mts.get('pf', float('nan')):.2f} | {ats.get('pf', float('nan')):.2f} | — |",
        f"| Avg hold | {mts.get('avg_hold', float('nan')):.0f}d | {ats.get('avg_hold', float('nan')):.0f}d | 138d |",
        "",
        "## Portfolio",
        f"| NAV | {ns.get('nav', 1.0):.4f} |",
        f"|---|---|",
        f"| Max DD (paper) | {ns.get('dd', 0):.1%}  (backtest: {BT_MAX_DD:.1%}) |",
        f"| Running CAGR | {ns.get('cagr', 0):.1%}  (backtest: {BT_CAGR:.1%}) |",
        "",
        "## Capacity & Turnover",
        f"| Signals this month | {n_total} |",
        f"|---|---|",
        f"| Filled | {n_filled} ({cap_usage:.0%} of signals) |",
        f"| Skipped (capacity) | {n_total - n_filled} |",
        "",
        "## Paper vs Backtest — Diagnostic",
    ]

    # Diagnostic flags
    avg_ret  = ats.get("avg_ret", float("nan"))
    hit_rate = ats.get("hit_rate", float("nan"))
    dd_now   = ns.get("dd", 0)

    def flag(condition, good_msg, bad_msg):
        return f"  - {'[OK] ' + good_msg if condition else '[!!] ' + bad_msg}"

    if not np.isnan(avg_ret):
        lines.append(flag(avg_ret >= BT_AVG_RET * 0.7,
                          f"Avg trade {avg_ret:.1%} >= 70% of backtest baseline",
                          f"Avg trade {avg_ret:.1%} below 70% of backtest {BT_AVG_RET:.1%} — review signal quality"))
    if not np.isnan(hit_rate):
        lines.append(flag(hit_rate >= 0.60,
                          f"Hit rate {hit_rate:.1%} >= 60% gate",
                          f"Hit rate {hit_rate:.1%} below 60% gate"))
    lines.append(flag(abs(dd_now) <= 0.35,
                      f"Drawdown {dd_now:.1%} within tolerance",
                      f"Drawdown {dd_now:.1%} exceeds -35% monitoring threshold"))

    lines.append("")
    report = "\n".join(lines)
    out = REP_DIR / f"monthly_{month_start.strftime('%Y-%m')}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Monthly report: {out}")
    return report


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily",   action="store_true")
    ap.add_argument("--weekly",  action="store_true")
    ap.add_argument("--monthly", action="store_true")
    ap.add_argument("--all",     action="store_true")
    args = ap.parse_args()

    if args.all or args.daily:
        print(daily_report())
    if args.all or args.weekly:
        print(weekly_report())
    if args.all or args.monthly:
        print(monthly_report())

    if not any([args.daily, args.weekly, args.monthly, args.all]):
        ap.print_help()


if __name__ == "__main__":
    main()
