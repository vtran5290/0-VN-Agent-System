"""
EMA cloud strategy portfolio simulator (daily frequency).

Simulates a real portfolio with:
- max_positions: max simultaneous open positions
- Equal weight: each position = 1/max_positions of portfolio
- FIFO entry fill: oldest pending signal fills first
- Exit modes: cloud_loss_3, trailing_2.5, partial_tp
- 40 bps round-trip cost

Outputs:
- trades_df: all trades with entry/exit details
- equity: daily equity curve (starting at 1.0)
- summary metrics: CAGR, max_dd, Sharpe, MAR, hit_rate, turnover

Usage:
    python pp_backtest/run_portfolio_comparison.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_levels.indicators import ema_cloud, rolling_resistance, pivot_highs, compute_atr
from pp_backtest.ema_levels.entry import (
    breakout_signals, donchian_breakout, base_high_breakout, cloud_only_entry,
)

COST = 0.004   # 40 bps round-trip
ANN  = 252


# ── Exit helpers ──────────────────────────────────────────────────────────────

def _exit_cloud_loss(close_vals: np.ndarray, slow_ema_vals: np.ndarray,
                     start: int, k: int = 3, max_hold: int = 250) -> int:
    """Return bar index (relative to start) when k consecutive closes below slow EMA."""
    below = close_vals < slow_ema_vals
    consec = 0
    end = min(start + max_hold, len(close_vals) - 1)
    for j in range(start, end + 1):
        if j >= len(below):
            return end - start
        if below[j]:
            consec += 1
            if consec >= k:
                return j - start
        else:
            consec = 0
    return end - start


def _exit_trailing(close_vals: np.ndarray, atr_vals: np.ndarray,
                   start: int, mult: float = 2.5, max_hold: int = 250) -> int:
    """Return bar index (relative to start) when close < high_water - mult*ATR."""
    high_water = close_vals[start]
    end = min(start + max_hold, len(close_vals) - 1)
    for j in range(start, end + 1):
        c = close_vals[j]
        high_water = max(high_water, c)
        stop = high_water - mult * atr_vals[j]
        if c <= stop:
            return j - start
    return end - start


def _exit_partial_tp(close_vals: np.ndarray, atr_vals: np.ndarray,
                     start: int, entry_price: float,
                     tp_pct: float = 0.15, trail_mult: float = 2.5,
                     max_hold: int = 250) -> tuple[int, float]:
    """
    Partial TP: 50% exit at +tp_pct from entry, trail remainder at trail_mult*ATR.
    Returns (bars_held, blended_net_return).
    """
    tp_price = entry_price * (1 + tp_pct)
    tp_hit   = False
    tp_ret   = 0.0
    high_water = entry_price
    end = min(start + max_hold, len(close_vals) - 1)

    for j in range(start, end + 1):
        c = close_vals[j]
        if not tp_hit and c >= tp_price:
            tp_hit   = True
            tp_ret   = (c - entry_price) / entry_price
            high_water = c
        if tp_hit:
            high_water = max(high_water, c)
            stop = high_water - trail_mult * atr_vals[j]
            if c <= stop:
                rem = (c - entry_price) / entry_price
                return j - start, (0.5 * tp_ret + 0.5 * rem) - COST
    # Position never stopped out
    c = close_vals[end]
    if tp_hit:
        rem = (c - entry_price) / entry_price
        return end - start, (0.5 * tp_ret + 0.5 * rem) - COST
    # TP never hit
    return end - start, (c - entry_price) / entry_price - COST


# ── Per-symbol simulation ─────────────────────────────────────────────────────

def sim_symbol(
    sdf:        pd.DataFrame,
    entry_type: str,
    ema_fast:   int,
    ema_slow:   int,
    exit_mode:  str,
    max_hold:   int = 250,
) -> list[dict]:
    """Simulate all trades for one symbol. Returns list of trade dicts."""
    if len(sdf) < max(ema_slow + 10, 100):
        return []

    sdf   = sdf.copy().reset_index(drop=True)
    close  = sdf["close"]
    high   = sdf["high"]
    low    = sdf.get("low", close)
    volume = sdf.get("volume", pd.Series(np.ones(len(sdf)), index=sdf.index))
    symbol = sdf["symbol"].iloc[0]
    dates  = sdf["date"]

    cloud_d    = ema_cloud(close, ema_fast, ema_slow)
    fast_ema   = cloud_d["ema_fast"]
    slow_ema   = cloud_d["ema_slow"]
    cloud_bull = cloud_d["cloud_bull"]
    atr        = compute_atr(high, low, close, period=14)
    warmup     = max(ema_slow + 5, 60)

    # Generate entry signal
    if entry_type == "level_breakout":
        ph = pivot_highs(high, pivot_window=5)
        resistance, r_strength = rolling_resistance(ph, lookback=252,
                                                    cluster_pct=0.02, min_touches=3)
        sig = breakout_signals(close, volume, resistance, r_strength,
                               cloud_bull, fast_ema, buffer_pct=0.005,
                               min_touches=3, warmup=warmup)
    elif entry_type.startswith("donchian_"):
        n = int(entry_type.split("_")[1])
        sig = donchian_breakout(close, n=n)
    elif entry_type == "base_high":
        sig = base_high_breakout(close, cloud_bull, fast_ema, n=50,
                                 fresh_window=10, warmup=warmup)
    elif entry_type == "cloud_only":
        sig = cloud_only_entry(close, fast_ema, cloud_bull, min_bars_bear=3,
                               warmup=warmup)
    else:
        raise ValueError(f"Unknown entry_type: {entry_type}")

    # Numpy arrays for fast exit computation
    close_arr   = close.values
    slow_arr    = slow_ema.values
    atr_arr     = atr.values
    date_arr    = dates.values
    n           = len(sdf)

    trades = []
    entry_bars = np.where(sig.values)[0].tolist()

    for ei in entry_bars:
        entry_i = ei + 1   # enter at next bar
        if entry_i >= n:
            continue
        entry_price = close_arr[entry_i]
        if entry_price <= 0 or np.isnan(entry_price):
            continue

        if exit_mode == "cloud_loss_3":
            bars_held = _exit_cloud_loss(close_arr, slow_arr, entry_i, k=3,
                                         max_hold=max_hold)
            exit_i    = min(entry_i + bars_held, n - 1)
            exit_price = close_arr[exit_i]
            net_ret    = (exit_price - entry_price) / entry_price - COST

        elif exit_mode == "trailing_2.5":
            bars_held = _exit_trailing(close_arr, atr_arr, entry_i, mult=2.5,
                                       max_hold=max_hold)
            exit_i    = min(entry_i + bars_held, n - 1)
            exit_price = close_arr[exit_i]
            net_ret    = (exit_price - entry_price) / entry_price - COST

        elif exit_mode == "partial_tp":
            bars_held, net_ret = _exit_partial_tp(close_arr, atr_arr, entry_i,
                                                   entry_price, tp_pct=0.15,
                                                   trail_mult=2.5, max_hold=max_hold)
            exit_i = min(entry_i + bars_held, n - 1)

        else:
            raise ValueError(f"Unknown exit_mode: {exit_mode}")

        trades.append({
            "symbol":      symbol,
            "entry_date":  date_arr[entry_i],
            "exit_date":   date_arr[exit_i],
            "entry_price": entry_price,
            "net_return":  net_ret,
            "hold_bars":   bars_held,
        })

    return trades


# ── Portfolio simulation ───────────────────────────────────────────────────────

def run_portfolio(
    panel:         pd.DataFrame,
    symbols:       list[str],
    entry_type:    str,
    ema_fast:      int,
    ema_slow:      int,
    exit_mode:     str,
    max_positions: int = 20,
    max_hold:      int = 250,
    start_date:    str = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Run portfolio simulation across all symbols with position limit.
    Returns (trades_df, equity_curve).
    """
    sub = panel[panel["symbol"].isin(symbols)]
    all_trades = []

    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = sdf.copy()
        if start_date:
            sdf = sdf[sdf["date"] >= start_date]
        if len(sdf) < 100:
            continue
        all_trades.extend(sim_symbol(sdf, entry_type, ema_fast, ema_slow,
                                      exit_mode, max_hold=max_hold))

    if not all_trades:
        return pd.DataFrame(), pd.Series(dtype=float)

    trades_df = pd.DataFrame(all_trades)
    trades_df["entry_date"] = pd.to_datetime(trades_df["entry_date"])
    trades_df["exit_date"]  = pd.to_datetime(trades_df["exit_date"])
    trades_df.sort_values("entry_date", inplace=True)
    trades_df.reset_index(drop=True, inplace=True)

    equity = _build_equity(trades_df, max_positions)
    return trades_df, equity


def _build_equity(trades_df: pd.DataFrame, max_positions: int) -> pd.Series:
    """
    Position-constrained equity curve.
    Each position has equal weight = 1/max_positions.
    Positions fill FIFO; a new position only opens if < max_positions are active.
    Equity accrues the position's net_return when it closes.
    """
    if trades_df.empty:
        return pd.Series(dtype=float)

    all_dates = pd.date_range(
        trades_df["entry_date"].min(),
        trades_df["exit_date"].max(),
        freq="B",
    )
    pos_weight = 1.0 / max_positions

    # Sort by entry_date for FIFO
    by_entry  = {}
    for _, row in trades_df.iterrows():
        ed = row["entry_date"]
        if ed not in by_entry:
            by_entry[ed] = []
        by_entry[ed].append(row)

    by_exit  = {}
    for idx, row in trades_df.iterrows():
        xd = row["exit_date"]
        if xd not in by_exit:
            by_exit[xd] = []
        by_exit[xd].append((idx, row))

    portfolio_val = 1.0
    active = {}   # trade_idx -> row
    equity = {}

    for date in all_dates:
        # Close positions that exit today
        for tid, row in by_exit.get(date, []):
            if tid in active:
                portfolio_val += portfolio_val * pos_weight * row["net_return"]
                del active[tid]

        # Open new positions (FIFO within this date's signals)
        for row in by_entry.get(date, []):
            if len(active) >= max_positions:
                break
            tid = row.name if hasattr(row, "name") else id(row)
            active[tid] = row

        equity[date] = portfolio_val

    return pd.Series(equity)


# ── Portfolio metrics ──────────────────────────────────────────────────────────

def portfolio_metrics(
    equity:    pd.Series,
    trades_df: pd.DataFrame,
    test_start: str = "2023-01-01",
) -> dict:
    if equity.empty or len(equity) < 5:
        return {}

    total_ret = equity.iloc[-1] / equity.iloc[0] - 1.0
    n_years   = max(len(equity) / ANN, 0.1)
    cagr      = (1.0 + total_ret) ** (1.0 / n_years) - 1.0

    daily_ret = equity.pct_change().dropna()
    sharpe    = (daily_ret.mean() / daily_ret.std(ddof=1) * np.sqrt(ANN)
                 if daily_ret.std() > 0 else np.nan)

    run_max = equity.cummax()
    dd      = (equity - run_max) / run_max
    max_dd  = float(dd.min())
    mar     = cagr / abs(max_dd) if max_dd < 0 else np.nan

    # Trade-level stats
    m: dict = {
        "cagr":      cagr,
        "total_ret": total_ret,
        "max_dd":    max_dd,
        "sharpe":    sharpe,
        "mar":       mar,
        "n_years":   round(n_years, 1),
        "start":     str(equity.index[0].date()),
        "end":       str(equity.index[-1].date()),
    }

    if not trades_df.empty and "net_return" in trades_df.columns:
        rets     = trades_df["net_return"].dropna()
        hit_rate = (rets > 0).mean()
        avg_ret  = rets.mean()
        med_ret  = rets.median()
        wins     = rets[rets > 0].sum()
        loss     = abs(rets[rets < 0].sum()) or 1e-12
        n_tr     = len(rets)
        avg_hold = trades_df["hold_bars"].mean() if "hold_bars" in trades_df.columns else np.nan
        dur      = max((trades_df["exit_date"].max() - trades_df["entry_date"].min()).days / 365.25, 0.1)
        turnover = n_tr / dur

        # OOS metrics
        oos_mask = trades_df["entry_date"] >= test_start
        oos_rets = rets[oos_mask.values[:len(rets)]]
        oos_avg  = float(oos_rets.mean()) if len(oos_rets) >= 5 else np.nan
        oos_hit  = float((oos_rets > 0).mean()) if len(oos_rets) >= 5 else np.nan

        m.update({
            "n_trades":      n_tr,
            "hit_rate":      hit_rate,
            "avg_trade_ret": avg_ret,
            "med_trade_ret": med_ret,
            "profit_factor": wins / loss,
            "avg_hold_bars": avg_hold,
            "trades_per_yr": turnover,
            "oos_avg_ret":   oos_avg,
            "oos_hit_rate":  oos_hit,
        })

    return m
