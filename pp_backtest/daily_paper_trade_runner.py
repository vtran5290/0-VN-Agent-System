#!/usr/bin/env python3
"""
Daily paper-trade runner — B_cloud20_100_partial (primary production candidate).

Implements the full paper-trade loop:
  - Daily signal scan (cloud_only entry, EMA 20/100)
  - Ranked signal selection (ema_dist)
  - Capacity check vs max_positions=20
  - T+1 open entry (realistic fill vs T-close signal)
  - Exit monitoring: partial TP1 hit, trailing stop, max hold
  - Portfolio NAV tracking
  - Open positions table
  - Closed trades log
  - Execution audit (signal_close vs next_open gap)

Ledger files (append-mode, CSV):
  data/paper_trade/positions.csv       -- current open positions
  data/paper_trade/closed_trades.csv   -- all completed trades
  data/paper_trade/nav_history.csv     -- daily NAV
  data/paper_trade/signals_log.csv     -- all signals (filled + skipped)
  data/paper_trade/execution_audit.csv -- entry gap analysis

Usage:
  # First run / backfill from a date:
  .venv\\Scripts\\python.exe pp_backtest/daily_paper_trade_runner.py --date 2026-05-13

  # Run for today (uses latest panel date):
  .venv\\Scripts\\python.exe pp_backtest/daily_paper_trade_runner.py

  # Backfill a range to populate ledger from historical data:
  .venv\\Scripts\\python.exe pp_backtest/daily_paper_trade_runner.py --backfill 2026-01-01

  # Status report only (no new signals):
  .venv\\Scripts\\python.exe pp_backtest/daily_paper_trade_runner.py --status
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry
from pp_backtest.candidate_strategy_manifest import PRIMARY

# ── Config (frozen — do not change without manifest update) ───────────────────
EMA_FAST      = PRIMARY["ema_fast"]        # 20
EMA_SLOW      = PRIMARY["ema_slow"]        # 100
EXIT_MODE     = PRIMARY["exit_mode"]       # partial_tp
MAX_HOLD      = PRIMARY["max_hold"]        # 250
MAX_POS       = PRIMARY["max_positions"]   # 20
COST          = 0.004                      # 40 bps round-trip
TP_PCT        = 0.15                       # +15% first target
TRAIL_MULT    = 2.5                        # 2.5 × ATR14 trailing stop
ATR_PERIOD    = 14
MIN_BARS_BEAR = 3
WARMUP        = max(EMA_SLOW + 5, 60)     # 105 bars

EX_VIN3        = {"VIC", "VHM", "VRE"}
EXCLUDE_ALWAYS = {"VPL"}

PANEL_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
OUT_DIR    = REPO / "data" / "paper_trade"
OUT_DIR.mkdir(parents=True, exist_ok=True)

POSITIONS_CSV     = OUT_DIR / "positions.csv"
CLOSED_CSV        = OUT_DIR / "closed_trades.csv"
NAV_CSV           = OUT_DIR / "nav_history.csv"
SIGNALS_CSV       = OUT_DIR / "signals_log.csv"
AUDIT_CSV         = OUT_DIR / "execution_audit.csv"


# ── Schema definitions ────────────────────────────────────────────────────────

POSITIONS_COLS = [
    "symbol", "entry_date", "entry_signal_close", "entry_price",
    "tp1_price", "tp1_hit", "tp1_exit_date", "tp1_return",
    "high_water", "trail_stop", "hold_bars", "status",
    "ema_dist_at_entry", "atr_at_entry",
]

CLOSED_COLS = [
    "symbol", "entry_date", "entry_price", "exit_date", "exit_price",
    "gross_return", "net_return", "hold_bars", "exit_reason",
    "tp1_hit", "ema_dist_at_entry",
]

NAV_COLS    = ["date", "nav", "drawdown_from_peak", "open_positions", "cash_pct"]
SIGNALS_COLS = [
    "date", "symbol", "signal_close", "ema_dist", "action",
    "skip_reason", "entry_price",
]
AUDIT_COLS  = [
    "date", "symbol", "signal_close", "next_open", "gap_pct",
    "direction",   # positive = gap up (costs more to buy), negative = gap down (favorable)
]


# ── Ledger helpers ────────────────────────────────────────────────────────────

def _load(path: Path, cols: list[str]) -> pd.DataFrame:
    if path.exists() and path.stat().st_size > 0:
        df = pd.read_csv(path, parse_dates=["date"] if "date" in cols else None)
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
        return df[cols]
    return pd.DataFrame(columns=cols)


def _append(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


def load_positions() -> pd.DataFrame:
    df = _load(POSITIONS_CSV, POSITIONS_COLS)
    if not df.empty:
        df["entry_date"]    = pd.to_datetime(df["entry_date"])
        df["tp1_exit_date"] = pd.to_datetime(df["tp1_exit_date"], errors="coerce")
        # Ensure numeric columns are float (not object) after CSV round-trip
        for col in ["entry_price", "tp1_price", "high_water", "trail_stop",
                    "hold_bars", "ema_dist_at_entry", "atr_at_entry", "tp1_return"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_closed() -> pd.DataFrame:
    df = _load(CLOSED_CSV, CLOSED_COLS)
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])
    return df


def load_nav() -> pd.DataFrame:
    return _load(NAV_CSV, NAV_COLS)


def save_positions(df: pd.DataFrame) -> None:
    df.to_csv(POSITIONS_CSV, index=False)


# ── Indicator helpers ─────────────────────────────────────────────────────────

def compute_indicators(sdf: pd.DataFrame) -> dict:
    """Compute EMA cloud, ATR, and signal for one symbol's price series."""
    close = sdf["close"]
    high  = sdf["high"]
    low   = sdf.get("low", close)

    cloud     = ema_cloud(close, EMA_FAST, EMA_SLOW)
    fast_ema  = cloud["ema_fast"]
    slow_ema  = cloud["ema_slow"]
    bull      = cloud["cloud_bull"]
    atr       = compute_atr(high, low, close, period=ATR_PERIOD)
    sig       = cloud_only_entry(close, fast_ema, bull,
                                 min_bars_bear=MIN_BARS_BEAR, warmup=WARMUP)
    return {
        "fast_ema":  fast_ema,
        "slow_ema":  slow_ema,
        "cloud_bull": bull,
        "atr":       atr,
        "signal":    sig,
    }


# ── Signal scan ───────────────────────────────────────────────────────────────

def scan_signals(panel: pd.DataFrame, universe: list[str],
                 as_of_date: pd.Timestamp) -> pd.DataFrame:
    """
    Scan universe for entry signals as of as_of_date.
    Returns DataFrame of signals sorted by ema_dist desc (ranked).
    Entry would happen at T+1 open (next trading day).
    """
    sub = panel[panel["symbol"].isin(universe) & (panel["date"] <= as_of_date)]
    signals = []

    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < WARMUP + 10:
            continue
        ind = compute_indicators(sdf)
        if not ind["signal"].iloc[-1]:
            continue
        last  = sdf.iloc[-1]
        close = float(last["close"])
        slow  = float(ind["slow_ema"].iloc[-1])
        atr   = float(ind["atr"].iloc[-1])
        ema_dist = (close - slow) / slow if slow > 0 else 0.0
        signals.append({
            "symbol":            sym,
            "signal_date":       as_of_date,
            "signal_close":      close,
            "slow_ema":          slow,
            "ema_dist":          ema_dist,
            "atr":               atr,
            "tp1_price":         close * (1 + TP_PCT),
        })

    df = pd.DataFrame(signals)
    if not df.empty:
        df.sort_values("ema_dist", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


# ── Exit monitoring ───────────────────────────────────────────────────────────

def check_exits(
    positions: pd.DataFrame,
    panel: pd.DataFrame,
    as_of_date: pd.Timestamp,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Check open positions against today's price data.
    Returns (updated_positions, list_of_closed_trades).
    """
    if positions.empty:
        return positions, []

    closed = []
    to_drop = []

    for idx, pos in positions.iterrows():
        sym  = pos["symbol"]
        srow = panel[(panel["symbol"] == sym) & (panel["date"] == as_of_date)]
        if srow.empty:
            continue

        c         = float(srow["close"].iloc[0])
        h         = float(srow.get("high", srow["close"]).iloc[0])
        entry_p   = float(pos["entry_price"])
        tp1_price = float(pos["tp1_price"])
        tp1_hit   = bool(pos["tp1_hit"]) if pd.notna(pos["tp1_hit"]) else False
        hw        = float(pos["high_water"]) if pd.notna(pos["high_water"]) else entry_p
        atr_e     = float(pos["atr_at_entry"]) if pd.notna(pos["atr_at_entry"]) else 0.01 * entry_p
        hold      = int(pos["hold_bars"]) + 1
        exit_reason = None
        exit_price  = c

        # Update high water using today's high
        hw = max(hw, h, c)
        trail_stop = hw - TRAIL_MULT * atr_e

        # TP1 check
        if not tp1_hit and c >= tp1_price:
            tp1_hit = True
            tp1_ret = (c - entry_p) / entry_p
            positions.at[idx, "tp1_hit"]      = True
            positions.at[idx, "tp1_exit_date"] = as_of_date
            positions.at[idx, "tp1_return"]    = tp1_ret

        # Trailing stop check (only after TP1 hit)
        if tp1_hit and c <= trail_stop:
            exit_reason = "trail_stop"

        # Max hold
        if hold >= MAX_HOLD:
            exit_reason = "max_hold"

        # Update position
        positions.at[idx, "high_water"]  = hw
        positions.at[idx, "trail_stop"]  = trail_stop
        positions.at[idx, "hold_bars"]   = hold

        if exit_reason:
            tp1_ret_val = float(pos["tp1_return"]) if pd.notna(pos.get("tp1_return")) else 0.0
            if tp1_hit:
                gross = 0.5 * tp1_ret_val + 0.5 * ((exit_price - entry_p) / entry_p)
            else:
                gross = (exit_price - entry_p) / entry_p
            closed.append({
                "symbol":           sym,
                "entry_date":       pos["entry_date"],
                "entry_price":      entry_p,
                "exit_date":        as_of_date,
                "exit_price":       exit_price,
                "gross_return":     gross,
                "net_return":       gross - COST,
                "hold_bars":        hold,
                "exit_reason":      exit_reason,
                "tp1_hit":          tp1_hit,
                "ema_dist_at_entry": pos.get("ema_dist_at_entry", np.nan),
            })
            to_drop.append(idx)

    positions = positions.drop(index=to_drop).reset_index(drop=True)
    return positions, closed


# ── Entry fill ────────────────────────────────────────────────────────────────

def fill_entries(
    signals: pd.DataFrame,
    positions: pd.DataFrame,
    panel: pd.DataFrame,
    entry_date: pd.Timestamp,
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    """
    Fill available slots with top-ranked signals not already in portfolio.
    Entry price = T+1 open (next day open after signal date).
    Returns (updated_positions, new_entries, signals_log_rows).
    """
    open_syms     = set(positions["symbol"].tolist()) if not positions.empty else set()
    available     = MAX_POS - len(open_syms)
    new_positions = []
    signals_log   = []
    audit_rows    = []

    for _, sig in signals.iterrows():
        sym = sig["symbol"]
        if sym in open_syms:
            signals_log.append({
                "date": entry_date, "symbol": sym,
                "signal_close": sig["signal_close"], "ema_dist": sig["ema_dist"],
                "action": "skip", "skip_reason": "already_open", "entry_price": np.nan,
            })
            continue

        # Get T+1 open price
        next_row = panel[(panel["symbol"] == sym) & (panel["date"] == entry_date)]
        if next_row.empty:
            signals_log.append({
                "date": entry_date, "symbol": sym,
                "signal_close": sig["signal_close"], "ema_dist": sig["ema_dist"],
                "action": "skip", "skip_reason": "no_next_open", "entry_price": np.nan,
            })
            continue

        entry_p    = float(next_row["open"].iloc[0]) if "open" in next_row.columns else float(next_row["close"].iloc[0])
        signal_cl  = float(sig["signal_close"])
        gap_pct    = (entry_p - signal_cl) / signal_cl if signal_cl > 0 else 0.0

        audit_rows.append({
            "date":         entry_date,
            "symbol":       sym,
            "signal_close": signal_cl,
            "next_open":    entry_p,
            "gap_pct":      gap_pct,
            "direction":    "up" if gap_pct > 0 else "down",
        })

        if available <= 0:
            signals_log.append({
                "date": entry_date, "symbol": sym,
                "signal_close": signal_cl, "ema_dist": sig["ema_dist"],
                "action": "skip", "skip_reason": "capacity_full", "entry_price": np.nan,
            })
            continue

        new_positions.append({
            "symbol":            sym,
            "entry_date":        entry_date,
            "entry_signal_close": signal_cl,
            "entry_price":       entry_p,
            "tp1_price":         entry_p * (1 + TP_PCT),
            "tp1_hit":           False,
            "tp1_exit_date":     pd.NaT,
            "tp1_return":        np.nan,
            "high_water":        entry_p,
            "trail_stop":        entry_p - TRAIL_MULT * float(sig["atr"]),
            "hold_bars":         0,
            "status":            "open",
            "ema_dist_at_entry": float(sig["ema_dist"]),
            "atr_at_entry":      float(sig["atr"]),
        })
        signals_log.append({
            "date": entry_date, "symbol": sym,
            "signal_close": signal_cl, "ema_dist": sig["ema_dist"],
            "action": "filled", "skip_reason": "", "entry_price": entry_p,
        })
        open_syms.add(sym)
        available -= 1

    if new_positions:
        new_df    = pd.DataFrame(new_positions)
        positions = pd.concat([positions, new_df], ignore_index=True)

    return positions, signals_log, audit_rows


# ── NAV calculation ───────────────────────────────────────────────────────────

def compute_nav(nav_history: pd.DataFrame, closed_today: list[dict],
                n_open: int, as_of_date: pd.Timestamp) -> tuple[float, float]:
    """Compute NAV from closed trades log and return (nav, drawdown)."""
    pos_weight = 1.0 / MAX_POS
    nav = float(nav_history["nav"].iloc[-1]) if not nav_history.empty else 1.0
    for trade in closed_today:
        nav += nav * pos_weight * trade["net_return"]
    peak = float(nav_history["nav"].max()) if not nav_history.empty else 1.0
    peak = max(peak, nav)
    dd   = (nav - peak) / peak if peak > 0 else 0.0
    return nav, dd


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_daily_status(
    as_of_date: pd.Timestamp,
    signals:    pd.DataFrame,
    positions:  pd.DataFrame,
    closed_today: list[dict],
    nav:        float,
    dd:         float,
) -> str:
    """Print and return daily status string."""
    filled   = signals[signals["action"] == "filled"] if "action" in signals.columns else pd.DataFrame()
    skipped  = signals[signals["action"] == "skip"]   if "action" in signals.columns else pd.DataFrame()

    lines = [
        "",
        f"{'='*60}",
        f"DAILY PAPER TRADE STATUS — {as_of_date.date()}",
        f"{'='*60}",
        f"  NAV:          {nav:.4f}  (start=1.0000)",
        f"  Drawdown:     {dd:.1%} from peak",
        f"  Open pos:     {len(positions)} / {MAX_POS}",
        f"  Cash:         {(1 - len(positions)/MAX_POS)*100:.0f}%",
        "",
        f"  Signals today:  {len(signals)} total  |  {len(filled)} filled  |  {len(skipped)} skipped",
    ]

    if not filled.empty:
        lines.append("  New entries:")
        for _, r in filled.iterrows():
            lines.append(f"    {r.symbol:<8}  entry={r.entry_price:.2f}  ema_dist={r.ema_dist:.1%}")

    if skipped[skipped["skip_reason"] == "capacity_full"].shape[0] > 0:
        cap_skip = skipped[skipped["skip_reason"] == "capacity_full"]["symbol"].tolist()
        lines.append(f"  Skipped (capacity): {', '.join(cap_skip[:8])}"
                     + ("..." if len(cap_skip) > 8 else ""))

    if closed_today:
        lines.append(f"\n  Exits today ({len(closed_today)}):")
        for t in closed_today:
            lines.append(f"    {t['symbol']:<8}  net={t['net_return']:.1%}  "
                         f"hold={t['hold_bars']}d  reason={t['exit_reason']}")

    if not positions.empty:
        lines.append(f"\n  Open positions ({len(positions)}):")
        pos_sorted = positions.sort_values("entry_date")
        for _, p in pos_sorted.iterrows():
            tp_flag = "[TP1]" if p["tp1_hit"] else "     "
            lines.append(f"    {p.symbol:<8}  entry={p.entry_price:.2f}  "
                         f"hold={int(p.hold_bars)}d  {tp_flag}  "
                         f"ema_dist={p.ema_dist_at_entry:.1%}")

    lines.append("")
    report = "\n".join(lines)
    print(report)
    return report


# ── Main runner ───────────────────────────────────────────────────────────────

def run_day(panel: pd.DataFrame, universe: list[str],
            signal_date: pd.Timestamp, entry_date: pd.Timestamp) -> dict:
    """
    Run one day of the paper-trade loop.
    signal_date: the date we scan signals on (T close)
    entry_date:  the date we enter positions (T+1 open)
    Returns summary dict.
    """
    positions   = load_positions()
    nav_history = load_nav()

    # 1. Check exits on signal_date close
    positions, closed_today = check_exits(positions, panel, signal_date)

    # 2. Scan new signals as of signal_date
    signals = scan_signals(panel, universe, signal_date)

    # 3. Fill entries at entry_date open
    positions, signals_log, audit_rows = fill_entries(
        signals, positions, panel, entry_date
    )

    # 4. Update NAV
    nav, dd = compute_nav(nav_history, closed_today,
                          len(positions), signal_date)

    # 5. Persist
    save_positions(positions)

    if closed_today:
        _append(pd.DataFrame(closed_today, columns=CLOSED_COLS), CLOSED_CSV)

    nav_row = pd.DataFrame([{
        "date":               signal_date,
        "nav":                nav,
        "drawdown_from_peak": dd,
        "open_positions":     len(positions),
        "cash_pct":           1 - len(positions) / MAX_POS,
    }])
    _append(nav_row, NAV_CSV)

    if signals_log:
        _append(pd.DataFrame(signals_log, columns=SIGNALS_COLS), SIGNALS_CSV)

    if audit_rows:
        _append(pd.DataFrame(audit_rows, columns=AUDIT_COLS), AUDIT_CSV)

    # 6. Print status
    sig_df = pd.DataFrame(signals_log, columns=SIGNALS_COLS) if signals_log else pd.DataFrame(columns=SIGNALS_COLS)
    print_daily_status(signal_date, sig_df, positions, closed_today, nav, dd)

    return {"date": signal_date, "nav": nav, "dd": dd,
            "n_open": len(positions), "n_closed": len(closed_today)}


def run_backfill(panel: pd.DataFrame, universe: list[str],
                 from_date: pd.Timestamp) -> None:
    """Run the paper-trade loop from from_date to end of panel."""
    all_dates = sorted(panel["date"].unique())
    start_idx = next((i for i, d in enumerate(all_dates)
                      if pd.Timestamp(d) >= from_date), None)
    if start_idx is None:
        print(f"No panel dates >= {from_date.date()}")
        return

    dates = all_dates[start_idx:]
    print(f"Backfill: {len(dates)} trading days from {pd.Timestamp(dates[0]).date()}")

    for i, signal_ts in enumerate(dates[:-1]):
        signal_date = pd.Timestamp(signal_ts)
        entry_date  = pd.Timestamp(dates[i + 1])
        run_day(panel, universe, signal_date, entry_date)

    # Final day — no entry (no next-open data)
    last_date = pd.Timestamp(dates[-1])
    positions = load_positions()
    positions, closed_today = check_exits(positions, panel, last_date)
    save_positions(positions)
    if closed_today:
        _append(pd.DataFrame(closed_today, columns=CLOSED_COLS), CLOSED_CSV)
    print(f"\nBackfill complete. Final date: {last_date.date()}")


def print_status_only() -> None:
    """Print current portfolio status without running a new day."""
    positions   = load_positions()
    nav_history = load_nav()
    closed      = load_closed()

    nav = float(nav_history["nav"].iloc[-1]) if not nav_history.empty else 1.0
    peak = float(nav_history["nav"].max()) if not nav_history.empty else 1.0
    dd  = (nav - peak) / peak if peak > 0 else 0.0

    last_date = nav_history["date"].iloc[-1] if not nav_history.empty else "n/a"

    print(f"\n{'='*60}")
    print(f"PAPER TRADE STATUS (as of {last_date})")
    print(f"{'='*60}")
    print(f"  NAV:          {nav:.4f}")
    print(f"  Drawdown:     {dd:.1%}")
    print(f"  Open pos:     {len(positions)} / {MAX_POS}")

    if not closed.empty:
        rets     = closed["net_return"].dropna()
        hit      = (rets > 0).mean()
        avg_ret  = rets.mean()
        n_trades = len(rets)
        print(f"\n  Closed trades: {n_trades}")
        print(f"  Hit rate:      {hit:.1%}  (backtest baseline: 67.9%)")
        print(f"  Avg net ret:   {avg_ret:.1%}  (backtest baseline: 5.9%)")

    if not positions.empty:
        print(f"\n  Open positions:")
        for _, p in positions.sort_values("entry_date").iterrows():
            days = int(p["hold_bars"])
            tp   = "[TP1]" if p["tp1_hit"] else "     "
            print(f"    {p.symbol:<8}  entry={p.entry_price:.2f}  "
                  f"hold={days}d  {tp}  dist={p.ema_dist_at_entry:.1%}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date",     default=None,  help="Signal date (YYYY-MM-DD). Default = latest panel date.")
    ap.add_argument("--backfill", default=None,  help="Backfill from this date (YYYY-MM-DD).")
    ap.add_argument("--status",   action="store_true", help="Print status only, no new run.")
    ap.add_argument("--panel",    default=str(PANEL_PATH))
    args = ap.parse_args()

    if args.status:
        print_status_only()
        return

    panel = pd.read_parquet(args.panel)
    panel["date"] = pd.to_datetime(panel["date"])
    if "open" not in panel.columns:
        # Fallback: use close as open (will show 0% gap in audit)
        panel["open"] = panel["close"]
    panel.sort_values(["symbol", "date"], inplace=True)

    all_symbols = sorted(panel["symbol"].unique().tolist())
    universe    = [s for s in all_symbols
                   if s not in EXCLUDE_ALWAYS and s not in EX_VIN3]
    print(f"Universe: {len(universe)} symbols (ex-VIN3)")

    if args.backfill:
        from_date = pd.Timestamp(args.backfill)
        run_backfill(panel, universe, from_date)
        return

    all_dates   = sorted(panel["date"].unique())
    if args.date:
        signal_date = pd.Timestamp(args.date)
    else:
        signal_date = pd.Timestamp(all_dates[-2])   # second-to-last = latest complete day

    # entry_date = next available trading day after signal_date
    future = [d for d in all_dates if pd.Timestamp(d) > signal_date]
    if not future:
        print(f"No next-day data after {signal_date.date()}. Run tomorrow.")
        return
    entry_date = pd.Timestamp(future[0])

    print(f"Signal date: {signal_date.date()}  →  Entry date: {entry_date.date()}")
    run_day(panel, universe, signal_date, entry_date)


if __name__ == "__main__":
    main()
