"""
EMA cloud strategy portfolio simulator (daily frequency).

Simulates a real portfolio with:
- max_positions: max simultaneous open positions
- Equal weight: each position = 1/max_positions of portfolio
- Entry fill modes: fifo | ema_dist | momentum
- Exit modes: cloud_loss_3, trailing_2.5, partial_tp
- Parameterised round-trip cost (default 40 bps)

Key design:
- compute_all_trades()  : generate raw per-symbol trades (no position limit)
- build_portfolio()     : apply position limits + rank mode to trades
- run_portfolio()       : convenience wrapper for both steps
- portfolio_metrics()   : equity-curve + trade-level stats

Separating compute_all_trades from build_portfolio lets hardening runs
reuse the same trade set across different max_positions / cost / universe
variants without re-running signal generation.

Trade dicts include gross_return (pre-cost) so cost sensitivity can be
tested by adjusting net_return = gross_return - new_cost without re-simulating.
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

DEFAULT_COST = 0.004   # 40 bps round-trip
ANN          = 252


# ── Exit helpers ──────────────────────────────────────────────────────────────

def _exit_cloud_loss(close_vals: np.ndarray, slow_ema_vals: np.ndarray,
                     start: int, k: int = 3, max_hold: int = 250) -> int:
    """Return hold bars when k consecutive closes fall below slow EMA."""
    below  = close_vals < slow_ema_vals
    consec = 0
    end    = min(start + max_hold, len(close_vals) - 1)
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
    """Return hold bars when close < high_water - mult*ATR."""
    high_water = close_vals[start]
    end        = min(start + max_hold, len(close_vals) - 1)
    for j in range(start, end + 1):
        c          = close_vals[j]
        high_water = max(high_water, c)
        if c <= high_water - mult * atr_vals[j]:
            return j - start
    return end - start


def _exit_partial_tp(close_vals: np.ndarray, atr_vals: np.ndarray,
                     start: int, entry_price: float,
                     tp_pct: float = 0.15, trail_mult: float = 2.5,
                     max_hold: int = 250) -> tuple[int, float, float]:
    """
    Partial TP: 50% exit at +tp_pct from entry, trail remainder at trail_mult*ATR.
    Returns (bars_held, gross_blended_return, exit_bar_index_relative).
    Caller applies cost.
    """
    tp_price   = entry_price * (1 + tp_pct)
    tp_hit     = False
    tp_ret     = 0.0
    high_water = entry_price
    end        = min(start + max_hold, len(close_vals) - 1)

    for j in range(start, end + 1):
        c = close_vals[j]
        if not tp_hit and c >= tp_price:
            tp_hit     = True
            tp_ret     = (c - entry_price) / entry_price
            high_water = c
        if tp_hit:
            high_water = max(high_water, c)
            if c <= high_water - trail_mult * atr_vals[j]:
                rem   = (c - entry_price) / entry_price
                gross = 0.5 * tp_ret + 0.5 * rem
                return j - start, gross, j - start
    c     = close_vals[end]
    rem   = (c - entry_price) / entry_price
    gross = (0.5 * tp_ret + 0.5 * rem) if tp_hit else rem
    return end - start, gross, end - start


# ── Per-symbol simulation ─────────────────────────────────────────────────────

def sim_symbol(
    sdf:        pd.DataFrame,
    entry_type: str,
    ema_fast:   int,
    ema_slow:   int,
    exit_mode:  str,
    max_hold:   int  = 250,
    cost:       float = DEFAULT_COST,
) -> list[dict]:
    """
    Simulate all possible trades for one symbol (no position limit).

    Returns trade dicts with:
        symbol, entry_date, exit_date, entry_price,
        gross_return    -- pre-cost blended return
        net_return      -- gross_return - cost
        hold_bars
        ema_dist_at_entry  -- (entry - slow_ema) / slow_ema   [ranking feature]
        mom20_at_entry     -- 20-bar price ROC at entry        [ranking feature]
        vol_at_entry       -- volume at entry bar              [ranking feature]
    """
    if len(sdf) < max(ema_slow + 10, 100):
        return []

    sdf    = sdf.copy().reset_index(drop=True)
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

    # 20-bar momentum for ranking
    mom20 = close.pct_change(20).fillna(0.0)

    if entry_type == "level_breakout":
        ph = pivot_highs(high, pivot_window=5)
        resistance, r_strength = rolling_resistance(ph, lookback=252,
                                                    cluster_pct=0.02, min_touches=3)
        sig = breakout_signals(close, volume, resistance, r_strength,
                               cloud_bull, fast_ema, buffer_pct=0.005,
                               min_touches=3, warmup=warmup)
    elif entry_type.startswith("donchian_"):
        n   = int(entry_type.split("_")[1])
        sig = donchian_breakout(close, n=n)
    elif entry_type == "base_high":
        sig = base_high_breakout(close, cloud_bull, fast_ema, n=50,
                                 fresh_window=10, warmup=warmup)
    elif entry_type == "cloud_only":
        sig = cloud_only_entry(close, fast_ema, cloud_bull, min_bars_bear=3,
                               warmup=warmup)
    else:
        raise ValueError(f"Unknown entry_type: {entry_type}")

    close_arr  = close.values
    slow_arr   = slow_ema.values
    atr_arr    = atr.values
    mom20_arr  = mom20.values
    vol_arr    = volume.values
    date_arr   = dates.values
    n          = len(sdf)

    trades     = []
    entry_bars = np.where(sig.values)[0].tolist()

    for ei in entry_bars:
        entry_i = ei + 1
        if entry_i >= n:
            continue
        entry_price = close_arr[entry_i]
        if entry_price <= 0 or np.isnan(entry_price):
            continue

        if exit_mode == "cloud_loss_3":
            bars_held  = _exit_cloud_loss(close_arr, slow_arr, entry_i, k=3,
                                          max_hold=max_hold)
            exit_i     = min(entry_i + bars_held, n - 1)
            gross      = (close_arr[exit_i] - entry_price) / entry_price

        elif exit_mode == "trailing_2.5":
            bars_held  = _exit_trailing(close_arr, atr_arr, entry_i, mult=2.5,
                                        max_hold=max_hold)
            exit_i     = min(entry_i + bars_held, n - 1)
            gross      = (close_arr[exit_i] - entry_price) / entry_price

        elif exit_mode == "partial_tp":
            bars_held, gross, _ = _exit_partial_tp(close_arr, atr_arr, entry_i,
                                                    entry_price, tp_pct=0.15,
                                                    trail_mult=2.5, max_hold=max_hold)
            exit_i = min(entry_i + bars_held, n - 1)

        else:
            raise ValueError(f"Unknown exit_mode: {exit_mode}")

        # Ranking features
        slow_at_e = slow_arr[entry_i]
        ema_dist  = float((entry_price - slow_at_e) / slow_at_e) if slow_at_e > 0 else 0.0
        mom20_e   = float(mom20_arr[entry_i]) if entry_i < len(mom20_arr) else 0.0
        vol_e     = float(vol_arr[entry_i])

        trades.append({
            "symbol":           symbol,
            "entry_date":       date_arr[entry_i],
            "exit_date":        date_arr[exit_i],
            "entry_price":      entry_price,
            "gross_return":     gross,
            "net_return":       gross - cost,
            "hold_bars":        bars_held,
            "ema_dist_at_entry": ema_dist,
            "mom20_at_entry":   mom20_e,
            "vol_at_entry":     vol_e,
        })

    return trades


# ── Portfolio construction ────────────────────────────────────────────────────

def compute_all_trades(
    panel:      pd.DataFrame,
    symbols:    list[str],
    entry_type: str,
    ema_fast:   int,
    ema_slow:   int,
    exit_mode:  str,
    max_hold:   int   = 250,
    cost:       float = DEFAULT_COST,
    start_date: str   = None,
) -> pd.DataFrame:
    """
    Generate raw per-symbol trades for all symbols in the list.
    No position limits applied here.
    Returns DataFrame with one row per trade signal.
    """
    sub        = panel[panel["symbol"].isin(symbols)]
    all_trades = []

    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = sdf.copy()
        if start_date:
            sdf = sdf[sdf["date"] >= start_date]
        if len(sdf) < 100:
            continue
        all_trades.extend(sim_symbol(sdf, entry_type, ema_fast, ema_slow,
                                     exit_mode, max_hold=max_hold, cost=cost))

    if not all_trades:
        return pd.DataFrame()

    df = pd.DataFrame(all_trades)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])
    df.sort_values("entry_date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_portfolio(
    trades_df:     pd.DataFrame,
    max_positions: int   = 20,
    rank_mode:     str   = "fifo",
) -> pd.Series:
    """
    Apply position limits to a pre-computed trades_df.
    rank_mode: 'fifo' | 'ema_dist' | 'momentum'

    For efficiency, callers can reuse the same trades_df across multiple
    build_portfolio calls (different max_positions, rank_mode, or cost).
    To vary cost: trades_df["net_return"] = trades_df["gross_return"] - new_cost
    """
    return _build_equity(trades_df, max_positions, rank_mode)


def run_portfolio(
    panel:         pd.DataFrame,
    symbols:       list[str],
    entry_type:    str,
    ema_fast:      int,
    ema_slow:      int,
    exit_mode:     str,
    max_positions: int   = 20,
    max_hold:      int   = 250,
    start_date:    str   = None,
    rank_mode:     str   = "fifo",
    cost:          float = DEFAULT_COST,
) -> tuple[pd.DataFrame, pd.Series]:
    """Convenience wrapper: compute trades then build equity."""
    trades_df = compute_all_trades(panel, symbols, entry_type, ema_fast, ema_slow,
                                   exit_mode, max_hold=max_hold, cost=cost,
                                   start_date=start_date)
    if trades_df.empty:
        return pd.DataFrame(), pd.Series(dtype=float)
    equity = build_portfolio(trades_df, max_positions, rank_mode)
    return trades_df, equity


def _build_equity(
    trades_df:     pd.DataFrame,
    max_positions: int,
    rank_mode:     str = "fifo",
) -> pd.Series:
    """
    Position-constrained equity curve (position weight = 1/max_positions).
    On each entry date, signals competing for available slots are ordered by:
      fifo      -- trade_df row order (alphabetical by symbol within date)
      ema_dist  -- distance of entry price above slow EMA, descending
      momentum  -- 20-bar price ROC at entry, descending
    Signals that cannot fill on their entry date are dropped (not queued).
    """
    if trades_df.empty:
        return pd.Series(dtype=float)

    all_dates  = pd.date_range(
        trades_df["entry_date"].min(),
        trades_df["exit_date"].max(),
        freq="B",
    )
    pos_weight = 1.0 / max_positions

    rank_col = {"ema_dist": "ema_dist_at_entry", "momentum": "mom20_at_entry"}.get(rank_mode)

    # Build by_entry: date → ordered list of trade rows
    by_entry: dict = {}
    if rank_col and rank_col in trades_df.columns:
        for ed, grp in trades_df.groupby("entry_date", sort=False):
            by_entry[ed] = [row for _, row in
                            grp.sort_values(rank_col, ascending=False).iterrows()]
    else:
        for _, row in trades_df.iterrows():
            ed = row["entry_date"]
            if ed not in by_entry:
                by_entry[ed] = []
            by_entry[ed].append(row)

    # Build by_exit: date → list of (trade_idx, row)
    by_exit: dict = {}
    for idx, row in trades_df.iterrows():
        xd = row["exit_date"]
        if xd not in by_exit:
            by_exit[xd] = []
        by_exit[xd].append((idx, row))

    portfolio_val = 1.0
    active: dict  = {}
    equity: dict  = {}

    for date in all_dates:
        for tid, row in by_exit.get(date, []):
            if tid in active:
                portfolio_val += portfolio_val * pos_weight * row["net_return"]
                del active[tid]

        for row in by_entry.get(date, []):
            if len(active) >= max_positions:
                break
            tid = row.name if hasattr(row, "name") else id(row)
            active[tid] = row

        equity[date] = portfolio_val

    return pd.Series(equity)


# ── Portfolio metrics ──────────────────────────────────────────────────────────

def portfolio_metrics(
    equity:     pd.Series,
    trades_df:  pd.DataFrame,
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
        hit_rate = float((rets > 0).mean())
        n_tr     = len(rets)
        wins     = rets[rets > 0].sum()
        loss     = abs(rets[rets < 0].sum()) or 1e-12
        avg_hold = (trades_df["hold_bars"].mean()
                    if "hold_bars" in trades_df.columns else np.nan)
        dur      = max((trades_df["exit_date"].max() -
                        trades_df["entry_date"].min()).days / 365.25, 0.1)

        oos_mask = trades_df["entry_date"] >= test_start
        oos_rets = rets[oos_mask.values[:len(rets)]]
        oos_avg  = float(oos_rets.mean())   if len(oos_rets) >= 5 else np.nan
        oos_hit  = float((oos_rets > 0).mean()) if len(oos_rets) >= 5 else np.nan

        m.update({
            "n_trades":      n_tr,
            "hit_rate":      hit_rate,
            "avg_trade_ret": float(rets.mean()),
            "med_trade_ret": float(rets.median()),
            "profit_factor": wins / loss,
            "avg_hold_bars": avg_hold,
            "trades_per_yr": n_tr / dur,
            "oos_avg_ret":   oos_avg,
            "oos_hit_rate":  oos_hit,
        })

    return m
