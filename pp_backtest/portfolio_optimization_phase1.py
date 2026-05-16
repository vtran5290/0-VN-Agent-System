#!/usr/bin/env python3
"""
Portfolio Optimization Phase 1 — REVISED after implementation audit.

Bugs fixed vs portfolio_optimization_research.py:
  - Equal-weight: max_position_pct now enforced; max_total_exposure added
  - Rank sizing: linear weights normalized so sum <= max_total_exposure
  - Risk-per-trade: stop exits now simulated with T+5 sell-lock
  - Walk-forward: reuses pre-built ledger (already fixed in prior session)

New phases:
  1B — Pullback scale-in robustness (depth × window × quality × split grid)
  1C — Rank sizing with position caps, drawdown guard, + pullback interaction
  1D — Risk-per-trade feasibility with actual stop execution
  1E — A3+GK and S3+GK convergence overlays
  1I — Annual and regime decomposition for all results

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase1.py --phase 1b
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase1.py --phase 1c
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase1.py --phase 1d
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase1.py --phase 1e
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase1.py --phase all
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import warnings
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_portfolio_sim import (
    DEFAULT_COST,
    portfolio_metrics,
)
from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry

try:
    from pp_backtest.daily_three_strategy_scan import (
        compute_gk, vnindex_regime_gate,
    )
except Exception:
    GK_LEN, GK_MULT, GK_ATR, GK_LAG = 100, 2.0, 14, 49

    def compute_gk(close, high, low):
        past = close.shift(GK_LAG).fillna(close)
        zl_in = close + (close - past)
        gk_zl = zl_in.ewm(span=GK_LEN, adjust=False).mean()
        atr = compute_atr(high, low, close, period=GK_ATR)
        gk_upper = gk_zl + GK_MULT * atr
        gk_lower = gk_zl - GK_MULT * atr
        above = close > gk_upper
        zl_rising = gk_zl > gk_zl.shift(1)
        gk_bull = above & above.shift(1).fillna(False).astype(bool) & zl_rising
        trend = pd.Series(np.nan, index=close.index, dtype=float)
        trend.loc[gk_bull] = 1.0
        trend.loc[close < gk_lower] = -1.0
        trend = trend.ffill().fillna(0).astype(int)
        prev = trend.shift(1).fillna(0).astype(int)
        gk_buy = (trend == 1) & (prev != 1)
        flip = (trend != prev) & (trend != 0)
        return {
            "gk_zl": gk_zl, "atr": atr,
            "gk_upper": gk_upper, "gk_lower": gk_lower,
            "gk_bull": gk_bull, "trend": trend,
            "gk_buy": gk_buy.fillna(False),
            "gk_sell": (flip & (trend == -1)).fillna(False),
        }

    def vnindex_regime_gate(vnx):
        w = vnx.sort_values("date").reset_index(drop=True)
        c = w["close"].astype(float)
        ema20 = c.ewm(span=20, adjust=False).mean()
        ema50 = c.ewm(span=50, adjust=False).mean()
        gate = (c > ema50) & (ema20 > ema50)
        idx = pd.to_datetime(w["date"]).dt.normalize()
        return pd.Series(gate.values, index=idx), bool(gate.iloc[-1]) if len(gate) else False


# ── Constants ─────────────────────────────────────────────────────────────────
ANN          = 252
EXCLUDE_VIN3 = {"VIC", "VHM", "VRE", "VPL"}
EXIT_18_25   = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5,
                "trail_basis": "close", "max_hold": 250}
EXIT_18_35   = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5,
                "trail_basis": "close", "max_hold": 250}
STRATEGY_CONFIGS = {
    "A3": {"ema_fast": 20, "ema_slow": 100, "exit_cfg": EXIT_18_25,
           "rank_col": "ema_dist", "universe": "ex_vin3"},
    "S3": {"ema_fast": 21, "ema_slow":  55, "exit_cfg": EXIT_18_35,
           "rank_col": "mom20",    "universe": "full"},
}
OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "phase1"
LEDGER  = REPO / "data" / "research" / "portfolio_optimization" / "trade_ledger_baseline.csv"


# ── Data loading ───────────────────────────────────────────────────────────────

def load_panel(max_symbols: int | None = None) -> pd.DataFrame:
    path = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if max_symbols:
        syms = sorted(df["symbol"].unique())[:max_symbols]
        df = df[df["symbol"].isin(syms)]
    return df


def load_vnindex() -> pd.DataFrame:
    path = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def get_universe(panel: pd.DataFrame, u: str) -> list[str]:
    syms = sorted(panel["symbol"].unique())
    return [s for s in syms if s not in EXCLUDE_VIN3] if u == "ex_vin3" else syms


def load_ledger() -> pd.DataFrame:
    if LEDGER.exists():
        df = pd.read_csv(LEDGER)
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])
        df["signal_date"] = pd.to_datetime(df["signal_date"])
        return df
    return pd.DataFrame()


# ── Exit engine ────────────────────────────────────────────────────────────────

def _exit_tp_trail(
    close_arr: np.ndarray,
    high_arr:  np.ndarray,
    atr_arr:   np.ndarray,
    start:     int,
    entry_price: float,
    exit_cfg:  dict,
) -> tuple[int, float, str]:
    """TP1 + trail exit. Returns (hold_bars, gross_return, exit_reason)."""
    tp_pct     = float(exit_cfg.get("tp_pct", 0.18))
    tp_frac    = float(exit_cfg.get("tp_frac", 0.50))
    trail_mult = float(exit_cfg.get("trail_mult", 2.5))
    max_hold   = int(exit_cfg.get("max_hold", 250))

    tp_price   = entry_price * (1.0 + tp_pct)
    tp_hit     = False
    high_water = entry_price
    n = len(close_arr)

    for k in range(start + 1, min(start + max_hold + 1, n)):
        c   = close_arr[k]
        atr = atr_arr[k]

        if not tp_hit:
            if high_arr[k] >= tp_price:
                tp_hit = True
                tp_ret = tp_pct * tp_frac
                high_water = max(c, tp_price)

        if tp_hit:
            high_water = max(high_water, c)
            trail_stop = high_water - trail_mult * atr
            if c <= trail_stop:
                gross = tp_ret + (c - entry_price * (1.0 + tp_pct)) / entry_price * (1.0 - tp_frac)
                gross = (tp_frac * tp_pct) + ((1.0 - tp_frac) * (c / entry_price - 1.0))
                return k - start, gross, "tp_trail"

    # max_hold
    c     = close_arr[min(start + max_hold, n - 1)]
    gross = (c / entry_price) - 1.0
    reason = "max_hold" if tp_hit else "tp_not_hit_max_hold"
    return min(max_hold, n - 1 - start), gross, reason


def _exit_with_stop(
    close_arr:   np.ndarray,
    high_arr:    np.ndarray,
    atr_arr:     np.ndarray,
    start:       int,
    entry_price: float,
    stop_dist:   float,
    exit_cfg:    dict,
    min_lock:    int = 5,
) -> tuple[int, float, str, int, float]:
    """
    Exit with T+min_lock sell-lock and explicit stop.
    Returns (hold_bars, gross, exit_reason, blocked_stop_events, locked_loss).

    Stop modes:
      - stop observed at bar k
      - if k - start < min_lock: cannot exit yet; continue holding; record blocked event
      - once k - start >= min_lock: if stop still breached, exit at close[k]
    After sell-lock, fall through to normal TP/trail logic if stop not breached.
    """
    stop_price = entry_price * (1.0 - stop_dist)
    tp_pct     = float(exit_cfg.get("tp_pct", 0.18))
    tp_frac    = float(exit_cfg.get("tp_frac", 0.50))
    trail_mult = float(exit_cfg.get("trail_mult", 2.5))
    max_hold   = int(exit_cfg.get("max_hold", 250))
    n          = len(close_arr)

    blocked_stop_events = 0
    locked_loss         = 0.0
    tp_hit              = False
    high_water          = entry_price

    for k in range(start + 1, min(start + max_hold + 1, n)):
        c   = close_arr[k]
        atr = atr_arr[k]
        bar = k - start

        # Stop check
        if c <= stop_price:
            if bar < min_lock:
                blocked_stop_events += 1
                locked_loss = max(locked_loss, (stop_price - c) / entry_price)
                continue  # still locked; keep holding
            else:
                # Exit at stop price (slippage simplified to close)
                gross = (c / entry_price) - 1.0
                return bar, gross, "stop_exit", blocked_stop_events, locked_loss

        # TP/trail (only after min_lock)
        if bar >= min_lock:
            if not tp_hit:
                if high_arr[k] >= entry_price * (1.0 + tp_pct):
                    tp_hit     = True
                    high_water = max(c, entry_price * (1.0 + tp_pct))
            if tp_hit:
                high_water = max(high_water, c)
                trail_stop = high_water - trail_mult * atr
                if c <= trail_stop:
                    gross = (tp_frac * tp_pct) + ((1.0 - tp_frac) * (c / entry_price - 1.0))
                    return bar, gross, "tp_trail", blocked_stop_events, locked_loss

    c      = close_arr[min(start + max_hold, n - 1)]
    gross  = (c / entry_price) - 1.0
    reason = "max_hold" if tp_hit else "tp_not_hit_max_hold"
    return min(max_hold, n - 1 - start), gross, reason, blocked_stop_events, locked_loss


# ── Corrected equity builder ───────────────────────────────────────────────────

def _build_corrected_equity(
    trades_df:        pd.DataFrame,
    max_positions:    int   = 20,
    max_position_pct: float = 0.05,
    max_total_exp:    float = 1.0,
    rank_col:         str   = "ema_dist_at_entry",
    rank_mode:        str   = "equal",
    dd_guard:         dict  | None = None,
) -> tuple[pd.Series, dict]:
    """
    Corrected equity simulation.

    max_position_pct: hard cap per position (enforced, not cosmetic)
    max_total_exp:    gross exposure cap (sum of active weights <= this)
    dd_guard: None or {"dd10": mult, "dd15": mult, "dd20": mult}
              e.g. {"dd10": 0.5, "dd15": 0.25, "dd20": 0.0}

    Returns (equity_series, stats_dict).
    """
    if trades_df.empty:
        return pd.Series(dtype=float), {}

    # Base weight per position
    base_w = min(1.0 / max(max_positions, 1), max_position_pct)
    # Effective max positions given exposure cap
    eff_max = min(max_positions, int(max_total_exp / max(base_w, 1e-9)))

    df = trades_df.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])

    # Rank-based weight override
    if rank_mode in ("linear", "top_heavy", "sqrt") and rank_col in df.columns:
        df["_rank_pct"] = df.groupby("entry_date")[rank_col].rank(pct=True, na_option="bottom")
    else:
        df["_rank_pct"] = 0.5

    all_dates = pd.date_range(df["entry_date"].min(), df["exit_date"].max(), freq="B")

    by_entry: dict = {}
    sort_col = rank_col if rank_col in df.columns else "_rank_pct"
    for ed, grp in df.groupby("entry_date", sort=False):
        by_entry[ed] = [(int(i), r) for i, r in grp.sort_values(sort_col, ascending=False).iterrows()]

    by_exit: dict = {}
    for i, row in df.iterrows():
        xd = row["exit_date"]
        by_exit.setdefault(xd, []).append((int(i), row))

    portfolio_val = 1.0
    peak_val      = 1.0
    active: dict[int, tuple] = {}  # tid -> (row, weight)
    equity: dict  = {}
    n_filled      = 0
    n_dd_blocked  = 0

    for date_val in all_dates:
        # Exits
        for tid, row in by_exit.get(date_val, []):
            if tid in active:
                _, w = active.pop(tid)
                portfolio_val += portfolio_val * w * float(row["net_return"])

        peak_val = max(peak_val, portfolio_val)

        # Drawdown guard
        current_dd = portfolio_val / peak_val - 1.0
        size_mult  = 1.0
        if dd_guard:
            if current_dd <= -abs(dd_guard.get("dd20", -0.20)):
                size_mult = 0.0
            elif current_dd <= -abs(dd_guard.get("dd15", -0.15)):
                size_mult = float(dd_guard.get("dd15_mult", 0.25))
            elif current_dd <= -abs(dd_guard.get("dd10", -0.10)):
                size_mult = float(dd_guard.get("dd10_mult", 0.50))

        # Entries
        remaining = eff_max - len(active)
        if remaining > 0 and size_mult > 0:
            queued = by_entry.get(date_val, [])[:remaining]
            if queued:
                # Compute weights for this batch
                weights = []
                for tid, row in queued:
                    rp = float(row.get("_rank_pct", 0.5))
                    if rank_mode == "linear":
                        raw_w = base_w * (1.0 + (rp - 0.5))   # ±0.5× base
                    elif rank_mode in ("top_heavy", "sqrt"):
                        raw_w = rp ** 0.5
                    else:
                        raw_w = base_w
                    weights.append(raw_w)

                # Normalize batch so total weight of batch <= remaining/eff_max * max_total_exp
                batch_target = (len(queued) / max(eff_max, 1)) * max_total_exp
                if rank_mode in ("linear", "top_heavy", "sqrt"):
                    total_raw = sum(weights)
                    if total_raw > 0:
                        scale = min(1.0, batch_target / total_raw)
                        weights = [w * scale for w in weights]

                # Cap per-position and apply drawdown mult
                weights = [min(w, max_position_pct) * size_mult for w in weights]

                # Verify sum doesn't exceed remaining exposure
                active_exp  = sum(w for _, w in active.values())
                avail_exp   = max(0.0, max_total_exp - active_exp)
                batch_sum   = sum(weights)
                if batch_sum > avail_exp + 1e-9:
                    scale2  = avail_exp / batch_sum if batch_sum > 0 else 0.0
                    weights = [w * scale2 for w in weights]

                for (tid, row), w in zip(queued, weights):
                    if w > 1e-9:
                        active[tid] = (row, w)
                        n_filled += 1
                    else:
                        n_dd_blocked += 1

        equity[date_val] = portfolio_val

    eq_series = pd.Series(equity)
    stats = {"n_filled": n_filled, "n_dd_blocked": n_dd_blocked}
    return eq_series, stats


# ── Phase 1B: Pullback robustness ─────────────────────────────────────────────

def _build_signal_cache(panel: pd.DataFrame, strategy: str) -> dict:
    """
    Pre-compute per-symbol: signals, close/high/atr arrays, EMA arrays.
    Returns dict[symbol -> cache_dict].
    """
    cfg      = STRATEGY_CONFIGS[strategy]
    ema_f    = cfg["ema_fast"]
    ema_s    = cfg["ema_slow"]
    universe = get_universe(panel, cfg["universe"])
    warmup   = max(ema_s + 5, 60)

    cache = {}
    for sym, sdf in panel[panel["symbol"].isin(universe)].groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < warmup + 10:
            continue
        close   = sdf["close"].astype(float)
        high    = sdf["high"].astype(float)
        low     = sdf.get("low", close).astype(float)
        dates   = pd.to_datetime(sdf["date"])
        volume  = sdf.get("volume", pd.Series(np.ones(len(sdf)))).astype(float)

        cloud_d    = ema_cloud(close, ema_f, ema_s)
        fast_ema   = cloud_d["ema_fast"]
        slow_ema   = cloud_d["ema_slow"]
        cloud_bull = cloud_d["cloud_bull"]
        atr        = compute_atr(high, low, close, period=14)
        mom20      = close.pct_change(20).fillna(0.0)

        sig = cloud_only_entry(close, fast_ema, cloud_bull, min_bars_bear=3, warmup=warmup)
        sig_idxs = np.where(sig.values)[0]

        if len(sig_idxs) == 0:
            continue

        close_loc = (close - low) / (high - low).clip(lower=1e-9)

        cache[sym] = {
            "close":     close.values.astype(float),
            "high":      high.values.astype(float),
            "atr":       atr.values.astype(float),
            "fast":      fast_ema.values.astype(float),
            "slow":      slow_ema.values.astype(float),
            "cloud":     cloud_bull.values.astype(bool),
            "mom20":     mom20.values.astype(float),
            "close_loc": close_loc.values.astype(float),
            "dates":     dates.values,
            "sig_idxs":  sig_idxs,
        }
    return cache


def _quality_ok(data: dict, bar: int, quality_mode: str) -> bool:
    """Check pullback quality filter at bar."""
    c = data["close"][bar]
    if quality_mode == "slow_097":
        return c > data["slow"][bar] * 0.97
    elif quality_mode == "slow_100":
        return c > data["slow"][bar]
    elif quality_mode == "fast_ema":
        return c > data["fast"][bar]
    elif quality_mode == "reclaim_fast":
        if bar < 1:
            return False
        # Was below fast, now above
        return c > data["fast"][bar] and data["close"][bar - 1] <= data["fast"][bar - 1]
    elif quality_mode == "close_loc_05":
        return data["close_loc"][bar] >= 0.5
    elif quality_mode == "close_loc_07":
        return data["close_loc"][bar] >= 0.7
    return True


def _sim_pullback_symbol(
    sym:          str,
    data:         dict,
    strategy:     str,
    exit_cfg:     dict,
    cost:         float,
    pb_depth:     float,    # e.g. 0.02 for -2%
    pb_window:    int,      # bars to look for pullback
    quality_mode: str,      # quality filter name
    w1:           float,    # tranche 1 weight
    w2:           float,    # tranche 2 weight
    min_lock:     int = 5,
    gate_by_date: pd.Series | None = None,
) -> list[dict]:
    """
    For one symbol and one pullback config, simulate all entry signals.
    Returns per-trade list with full diagnostics.
    """
    close_arr = data["close"]
    high_arr  = data["high"]
    atr_arr   = data["atr"]
    dates     = data["dates"]
    n         = len(close_arr)
    max_hold  = int(exit_cfg.get("max_hold", 250))

    trades = []

    for si in data["sig_idxs"]:
        entry_i = si + 1
        if entry_i >= n:
            continue

        sig_date   = pd.Timestamp(dates[si])
        entry_date = pd.Timestamp(dates[entry_i])

        # Regime gate
        if gate_by_date is not None:
            regime_date = sig_date.normalize()
            if not bool(gate_by_date.get(regime_date, True)):
                continue

        sig_close = float(close_arr[si])
        ep1       = float(close_arr[entry_i])
        if ep1 <= 0 or np.isnan(ep1):
            continue

        pullback_target = sig_close * (1.0 - pb_depth)

        # Search for pullback tranche
        t2_i = None
        for j in range(entry_i + 1, min(entry_i + pb_window + 1, n)):
            if close_arr[j] <= pullback_target and _quality_ok(data, j, quality_mode):
                t2_i = j
                break

        has_pullback = t2_i is not None
        ep2          = float(close_arr[t2_i]) if t2_i is not None else None

        # Blended entry
        if has_pullback:
            tot = w1 + w2
            blended_ep = (w1 * ep1 + w2 * ep2) / tot
            n_tranches  = 2
        else:
            blended_ep = ep1
            n_tranches  = 1

        # Exit from blended entry
        hold, gross, reason = _exit_tp_trail(
            close_arr, high_arr, atr_arr, entry_i, blended_ep, exit_cfg
        )
        net = gross - cost

        # Counterfactual: exit from t1-only entry
        hold_t1, gross_t1, _ = _exit_tp_trail(
            close_arr, high_arr, atr_arr, entry_i, ep1, exit_cfg
        )
        net_t1 = gross_t1 - cost

        exit_i    = min(entry_i + hold, n - 1)
        exit_date = pd.Timestamp(dates[exit_i])

        # MAE / MFE
        window_close = close_arr[entry_i: entry_i + hold + 1]
        mae = (np.min(window_close) / blended_ep) - 1.0 if len(window_close) else 0.0
        mfe = (np.max(window_close) / blended_ep) - 1.0 if len(window_close) else 0.0

        # Year / regime
        year   = sig_date.year
        vnx_ok = bool(gate_by_date.get(sig_date.normalize(), True)) if gate_by_date is not None else True

        trades.append({
            "symbol":         sym,
            "strategy":       strategy,
            "signal_date":    sig_date,
            "entry_date":     entry_date,
            "exit_date":      exit_date,
            "sig_close":      sig_close,
            "ep1":            ep1,
            "ep2":            ep2,
            "blended_ep":     blended_ep,
            "has_pullback":   has_pullback,
            "n_tranches":     n_tranches,
            "t2_bar":         (t2_i - entry_i) if t2_i is not None else None,
            "gross":          gross,
            "net_return":     net,
            "net_t1_only":    net_t1,
            "blended_benefit": net - net_t1,   # improvement from blending vs t1-only
            "hold_bars":      hold,
            "exit_reason":    reason,
            "mae":            mae,
            "mfe":            mfe,
            "year":           year,
            "vnx_regime_on":  vnx_ok,
            "mom20":          float(data["mom20"][si]),
        })

    return trades


def _build_pb_equity(
    trades: list[dict],
    max_positions: int      = 20,
    max_position_pct: float = 0.05,
    max_total_exp: float    = 1.0,
) -> tuple[pd.Series, dict]:
    """Build equity from pullback trade list using corrected equal-weight."""
    if not trades:
        return pd.Series(dtype=float), {}
    df = pd.DataFrame(trades)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])
    eq, stats = _build_corrected_equity(
        df, max_positions=max_positions,
        max_position_pct=max_position_pct, max_total_exp=max_total_exp,
    )
    return eq, stats


def _pullback_summary_row(
    experiment_id: str,
    strategy:      str,
    pb_depth:      float,
    pb_window:     int,
    quality_mode:  str,
    split_label:   str,
    trades:        list[dict],
    max_positions: int = 20,
) -> dict | None:
    if not trades:
        return None

    df     = pd.DataFrame(trades)
    pb_df  = df[df["has_pullback"]]
    npb_df = df[~df["has_pullback"]]

    eq, _  = _build_pb_equity(trades, max_positions=max_positions)
    if eq.empty:
        return None

    m = portfolio_metrics(eq, df, test_start="2023-01-01")

    return {
        "experiment_id":          experiment_id,
        "strategy":               strategy,
        "pb_depth_pct":           pb_depth * 100,
        "pb_window_bars":         pb_window,
        "quality_mode":           quality_mode,
        "split":                  split_label,
        "n_trades_total":         len(df),
        "n_pullback":             len(pb_df),
        "n_no_pullback":          len(npb_df),
        "pct_pullback":           len(pb_df) / max(len(df), 1),
        "mean_net_all":           float(df["net_return"].mean()),
        "mean_net_pullback":      float(pb_df["net_return"].mean()) if len(pb_df) else np.nan,
        "mean_net_no_pullback":   float(npb_df["net_return"].mean()) if len(npb_df) else np.nan,
        "mean_t1_only":           float(df["net_t1_only"].mean()),
        "mean_blended_benefit":   float(df["blended_benefit"].mean()),
        "hit_pullback":           float((pb_df["net_return"] > 0).mean()) if len(pb_df) else np.nan,
        "hit_no_pullback":        float((npb_df["net_return"] > 0).mean()) if len(npb_df) else np.nan,
        "cagr":                   m.get("cagr", np.nan),
        "max_dd":                 m.get("max_dd", np.nan),
        "sharpe":                 m.get("sharpe", np.nan),
        "mar":                    m.get("mar", np.nan),
        "avg_t2_bar":             float(pb_df["t2_bar"].mean()) if len(pb_df) else np.nan,
    }


def run_phase1b_pullback(
    panel:         pd.DataFrame,
    vnx:           pd.DataFrame,
    strategies:    list[str] = None,
    cost:          float = DEFAULT_COST,
    min_lock:      int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Phase 1B: Pullback scale-in robustness grid.
    Returns: (robustness_df, quality_df, by_year_df, by_regime_df)
    """
    print("Phase 1B: pullback robustness...", flush=True)
    if strategies is None:
        strategies = ["A3", "S3"]

    gate_by_date, _ = vnindex_regime_gate(vnx)

    # Core grid: 5 depths × 5 windows (default quality=slow_097, split=50/50)
    depths  = [0.01, 0.02, 0.03, 0.04, 0.05]
    windows = [5, 10, 15, 20, 30]

    # Quality variants (tested at best depth/window → post-hoc, run all at d=0.02, w=20)
    quality_modes = ["slow_097", "slow_100", "fast_ema", "reclaim_fast",
                     "close_loc_05", "close_loc_07"]

    # Split variants
    splits = [
        ("50_50",  0.50, 0.50),
        ("60_40",  0.60, 0.40),
        ("70_30",  0.70, 0.30),
        ("40_60",  0.40, 0.60),
    ]

    robustness_rows = []
    all_trade_records: list[dict] = []

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        cfg      = STRATEGY_CONFIGS[strategy]
        exit_cfg = cfg["exit_cfg"]

        print(f"  [{strategy}] building signal cache...", flush=True)
        cache = _build_signal_cache(panel, strategy)
        print(f"  [{strategy}] {len(cache)} symbols cached", flush=True)

        # ── Core depth × window grid (slow_097, 50/50) ──
        for depth, window in itertools.product(depths, windows):
            eid = f"PB_{strategy}_d{int(depth*100)}_w{window}_slow097_5050"
            trades = []
            for sym, data in cache.items():
                trades.extend(_sim_pullback_symbol(
                    sym, data, strategy, exit_cfg, cost,
                    pb_depth=depth, pb_window=window,
                    quality_mode="slow_097", w1=0.5, w2=0.5,
                    min_lock=min_lock, gate_by_date=gate_by_date,
                ))

            row = _pullback_summary_row(eid, strategy, depth, window, "slow_097", "50_50", trades)
            if row:
                robustness_rows.append(row)
                # Tag and collect for diagnostics (only for d=0.02, w=20 baseline)
                if abs(depth - 0.02) < 1e-9 and window == 20:
                    for t in trades:
                        t["pb_config"] = "base"
                    all_trade_records.extend(trades)

            print(f"    {eid}: {len(trades)} trades, "
                  f"pullback_pct={sum(1 for t in trades if t['has_pullback'])/max(len(trades),1):.1%}",
                  flush=True)

        # ── Quality variants at d=0.02, w=20 ──
        for qm in quality_modes:
            if qm == "slow_097":
                continue  # already in core grid
            eid = f"PB_{strategy}_d2_w20_{qm}_5050"
            trades = []
            for sym, data in cache.items():
                trades.extend(_sim_pullback_symbol(
                    sym, data, strategy, exit_cfg, cost,
                    pb_depth=0.02, pb_window=20,
                    quality_mode=qm, w1=0.5, w2=0.5,
                    min_lock=min_lock, gate_by_date=gate_by_date,
                ))
            row = _pullback_summary_row(eid, strategy, 0.02, 20, qm, "50_50", trades)
            if row:
                robustness_rows.append(row)

        # ── Split variants at d=0.02, w=20, slow_097 ──
        for s_label, w1, w2 in splits:
            if s_label == "50_50":
                continue  # already in core grid
            eid = f"PB_{strategy}_d2_w20_slow097_{s_label}"
            trades = []
            for sym, data in cache.items():
                trades.extend(_sim_pullback_symbol(
                    sym, data, strategy, exit_cfg, cost,
                    pb_depth=0.02, pb_window=20,
                    quality_mode="slow_097", w1=w1, w2=w2,
                    min_lock=min_lock, gate_by_date=gate_by_date,
                ))
            row = _pullback_summary_row(eid, strategy, 0.02, 20, "slow_097", s_label, trades)
            if row:
                robustness_rows.append(row)

    robustness_df = pd.DataFrame(robustness_rows)

    # ── pullback_vs_no_pullback_trade_quality ──
    quality_rows = []
    for strategy in strategies:
        base_trades = [t for t in all_trade_records if t["strategy"] == strategy]
        if not base_trades:
            continue
        df  = pd.DataFrame(base_trades)
        pb  = df[df["has_pullback"]]
        npb = df[~df["has_pullback"]]

        for grp_label, grp_df in [("all", df), ("pullback_occurred", pb), ("no_pullback", npb)]:
            if grp_df.empty:
                continue
            quality_rows.append({
                "strategy":       strategy,
                "group":          grp_label,
                "n":              len(grp_df),
                "mean_net":       float(grp_df["net_return"].mean()),
                "mean_t1_only":   float(grp_df["net_t1_only"].mean()),
                "mean_benefit":   float(grp_df["blended_benefit"].mean()),
                "hit_rate":       float((grp_df["net_return"] > 0).mean()),
                "mean_mae":       float(grp_df["mae"].mean()),
                "mean_mfe":       float(grp_df["mfe"].mean()),
                "mean_hold":      float(grp_df["hold_bars"].mean()),
                "pct_tp_trail":   float((grp_df["exit_reason"] == "tp_trail").mean()),
            })

    quality_df = pd.DataFrame(quality_rows)

    # ── By-year breakdown (at d=0.02, w=20 default) ──
    year_rows = []
    for strategy in strategies:
        base_trades = [t for t in all_trade_records if t["strategy"] == strategy]
        if not base_trades:
            continue
        df = pd.DataFrame(base_trades)
        for yr, grp in df.groupby("year"):
            if len(grp) < 5:
                continue
            year_rows.append({
                "strategy":   strategy,
                "year":       yr,
                "n_trades":   len(grp),
                "n_pullback": int(grp["has_pullback"].sum()),
                "pct_pb":     float(grp["has_pullback"].mean()),
                "mean_net":   float(grp["net_return"].mean()),
                "mean_t1":    float(grp["net_t1_only"].mean()),
                "mean_benefit": float(grp["blended_benefit"].mean()),
                "hit_rate":   float((grp["net_return"] > 0).mean()),
            })
    by_year_df = pd.DataFrame(year_rows)

    # ── By-regime breakdown ──
    regime_rows = []
    for strategy in strategies:
        base_trades = [t for t in all_trade_records if t["strategy"] == strategy]
        if not base_trades:
            continue
        df = pd.DataFrame(base_trades)
        for regime_on in [True, False]:
            grp = df[df["vnx_regime_on"] == regime_on]
            if len(grp) < 5:
                continue
            regime_rows.append({
                "strategy":   strategy,
                "vnx_regime": "ON" if regime_on else "OFF",
                "n_trades":   len(grp),
                "n_pullback": int(grp["has_pullback"].sum()),
                "pct_pb":     float(grp["has_pullback"].mean()),
                "mean_net":   float(grp["net_return"].mean()),
                "mean_t1":    float(grp["net_t1_only"].mean()),
                "mean_benefit": float(grp["blended_benefit"].mean()),
                "hit_rate":   float((grp["net_return"] > 0).mean()),
            })
    by_regime_df = pd.DataFrame(regime_rows)

    return robustness_df, quality_df, by_year_df, by_regime_df


# ── Phase 1C: Rank sizing with caps ───────────────────────────────────────────

def _run_corrected_sizing_experiment(
    trades_df:        pd.DataFrame,
    strategy:         str,
    experiment_id:    str,
    rank_mode:        str,
    max_positions:    int,
    max_position_pct: float,
    max_total_exp:    float,
    dd_guard:         dict | None,
    rank_col:         str = "ema_dist_at_entry",
) -> dict | None:
    if trades_df.empty:
        return None

    sub = trades_df[trades_df["strategy"] == strategy].copy()
    if sub.empty:
        return None

    eq, stats = _build_corrected_equity(
        sub,
        max_positions=max_positions,
        max_position_pct=max_position_pct,
        max_total_exp=max_total_exp,
        rank_col=rank_col,
        rank_mode=rank_mode,
        dd_guard=dd_guard,
    )
    if eq.empty:
        return None

    m = portfolio_metrics(eq, sub, test_start="2023-01-01")
    return {
        "experiment_id":    experiment_id,
        "strategy":         strategy,
        "rank_mode":        rank_mode,
        "max_positions":    max_positions,
        "max_position_pct": max_position_pct,
        "max_total_exp":    max_total_exp,
        "dd_guard":         json.dumps(dd_guard) if dd_guard else "none",
        "cagr":             m.get("cagr", np.nan),
        "max_dd":           m.get("max_dd", np.nan),
        "sharpe":           m.get("sharpe", np.nan),
        "mar":              m.get("mar", np.nan),
        "n_trades":         m.get("n_trades", 0),
        "hit_rate":         m.get("hit_rate", np.nan),
        "n_filled":         stats.get("n_filled", 0),
        "n_dd_blocked":     stats.get("n_dd_blocked", 0),
        "prod_class":       _classify_result(m.get("max_dd", np.nan), m.get("mar", np.nan)),
    }


def _classify_result(max_dd: float, mar: float) -> str:
    if np.isnan(max_dd):
        return "INSUFFICIENT_DATA"
    if max_dd > -0.30:
        return "PRODUCTION_CANDIDATE"
    if max_dd > -0.40:
        return "SHADOW_TEST"
    if max_dd > -0.50:
        return "RESEARCH_ONLY"
    return "REJECT"


def run_phase1c_rank_sizing(
    trades_df: pd.DataFrame,
    strategies: list[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Phase 1C: Corrected rank sizing with caps + drawdown guard + interaction.
    Returns: (rank_sizing_df, interaction_df, dd_guard_df)
    """
    print("Phase 1C: rank sizing with caps...", flush=True)
    if strategies is None:
        strategies = ["A3", "S3"]

    results         = []
    interaction_rows= []
    dd_guard_rows   = []

    rank_col_map = {"A3": "ema_dist_at_entry", "S3": "mom20_at_entry"}

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        rank_col = rank_col_map.get(strategy, "ema_dist_at_entry")
        sub_all  = trades_df[trades_df["strategy"] == strategy]

        # ── Corrected baseline (equal-weight) ──
        for max_pos, max_pct, max_exp in itertools.product(
            [10, 15, 20, 30],
            [0.05, 0.075, 0.10, 0.15, 0.20],
            [0.80, 1.00],
        ):
            eid = f"EQ_{strategy}_pos{max_pos}_pct{int(max_pct*100)}_exp{int(max_exp*100)}"
            row = _run_corrected_sizing_experiment(
                trades_df, strategy, eid, "equal",
                max_pos, max_pct, max_exp, None, rank_col,
            )
            if row:
                results.append(row)

        # ── Rank modes × caps ──
        for mode, max_pos, max_pct, max_exp in itertools.product(
            ["linear", "top_heavy", "sqrt"],
            [15, 20, 30],
            [0.075, 0.10, 0.15, 0.20],
            [0.80, 1.00],
        ):
            eid = f"{mode.upper()}_{strategy}_pos{max_pos}_pct{int(max_pct*100)}_exp{int(max_exp*100)}"
            row = _run_corrected_sizing_experiment(
                trades_df, strategy, eid, mode,
                max_pos, max_pct, max_exp, None, rank_col,
            )
            if row:
                results.append(row)

        print(f"  [{strategy}] rank sizing: {len(results)} rows so far", flush=True)

        # ── Drawdown guard (at equal pos=20, pct=5%, exp=1.0) ──
        guard_configs = [
            ("no_guard",  None),
            ("guard_mild",  {"dd10": 0.10, "dd10_mult": 0.50, "dd15": 0.15, "dd15_mult": 0.25, "dd20": 0.20}),
            ("guard_firm",  {"dd10": 0.10, "dd10_mult": 0.25, "dd15": 0.15, "dd15_mult": 0.0,  "dd20": 0.20}),
            ("guard_strict",{"dd10": 0.05, "dd10_mult": 0.0,  "dd15": 0.15, "dd15_mult": 0.0,  "dd20": 0.20}),
        ]
        for guard_label, guard_cfg in guard_configs:
            for mode in ["equal", "linear"]:
                eid = f"DDG_{strategy}_{mode}_{guard_label}"
                row = _run_corrected_sizing_experiment(
                    trades_df, strategy, eid, mode,
                    20, 0.05, 1.0, guard_cfg, rank_col,
                )
                if row:
                    row["guard_label"] = guard_label
                    dd_guard_rows.append(row)

    rank_sizing_df = pd.DataFrame(results)
    dd_guard_df    = pd.DataFrame(dd_guard_rows)

    # ── Interaction: baseline × linear × pullback × linear+pullback ──
    # (pullback_trades_df passed separately if available)
    # Interaction computed from rank_sizing_df vs baseline
    print("  Phase 1C: interaction computation deferred to run_phase1c_interaction()", flush=True)
    interaction_df = pd.DataFrame()   # filled by run_phase1c_interaction()

    return rank_sizing_df, interaction_df, dd_guard_df


def run_phase1c_interaction(
    baseline_eq:  pd.Series,
    linear_eq:    pd.Series,
    pullback_eq:  pd.Series,
    combo_eq:     pd.Series,
    baseline_m:   dict,
    linear_m:     dict,
    pullback_m:   dict,
    combo_m:      dict,
) -> pd.DataFrame:
    """Compute interaction effect for linear × pullback combination."""
    rows = []
    for metric in ["cagr", "max_dd", "sharpe", "mar"]:
        b = baseline_m.get(metric, np.nan)
        l = linear_m.get(metric, np.nan)
        p = pullback_m.get(metric, np.nan)
        c = combo_m.get(metric, np.nan)
        interaction = c - l - p + b if all(not np.isnan(x) for x in [b, l, p, c]) else np.nan
        rows.append({
            "metric":            metric,
            "baseline":          b,
            "linear_only":       l,
            "pullback_only":     p,
            "combo":             c,
            "additive_expected": l + p - b,
            "interaction":       interaction,
            "interaction_sign":  "synergy" if (not np.isnan(interaction) and interaction > 0) else "conflict",
        })
    return pd.DataFrame(rows)


# ── Phase 1D: Risk-per-trade feasibility ──────────────────────────────────────

def _sim_rpt_symbol(
    sym:        str,
    data:       dict,
    strategy:   str,
    exit_cfg:   dict,
    cost:       float,
    risk_pct:   float,
    stop_dist:  float,
    min_lock:   int = 5,
    gate_by_date: pd.Series | None = None,
) -> list[dict]:
    """Simulate risk-per-trade with actual stop execution."""
    close_arr = data["close"]
    high_arr  = data["high"]
    atr_arr   = data["atr"]
    dates     = data["dates"]
    n         = len(close_arr)
    max_hold  = int(exit_cfg.get("max_hold", 250))

    trades = []
    for si in data["sig_idxs"]:
        entry_i = si + 1
        if entry_i >= n:
            continue
        sig_date   = pd.Timestamp(dates[si])
        entry_date = pd.Timestamp(dates[entry_i])

        if gate_by_date is not None:
            if not bool(gate_by_date.get(sig_date.normalize(), True)):
                continue

        ep = float(close_arr[entry_i])
        if ep <= 0 or np.isnan(ep):
            continue

        # Dynamic ATR stop if requested
        atr_pct = float(atr_arr[entry_i]) / ep if ep > 0 else 0.04

        hold, gross, reason, blocked_stops, locked_loss = _exit_with_stop(
            close_arr, high_arr, atr_arr, entry_i, ep, stop_dist, exit_cfg, min_lock=min_lock,
        )
        net = gross - cost

        # Weight: risk_pct / stop_dist
        weight = min(risk_pct / max(stop_dist, 0.01), 0.25)

        exit_i    = min(entry_i + hold, n - 1)
        exit_date = pd.Timestamp(dates[exit_i])

        trades.append({
            "symbol":              sym,
            "strategy":            strategy,
            "signal_date":         sig_date,
            "entry_date":          entry_date,
            "exit_date":           exit_date,
            "entry_price":         ep,
            "gross":               gross,
            "net_return":          net,
            "weight":              weight,
            "hold_bars":           hold,
            "exit_reason":         reason,
            "blocked_stop_events": blocked_stops,
            "locked_loss":         locked_loss,
            "stop_dist_pct":       stop_dist * 100,
            "risk_pct":            risk_pct * 100,
            "atr_pct":             atr_pct * 100,
            "year":                sig_date.year,
            "vnx_regime_on":       bool(gate_by_date.get(sig_date.normalize(), True))
                                   if gate_by_date is not None else True,
        })

    return trades


def _build_rpt_equity(
    trades:     list[dict],
    max_pos:    int   = 20,
    max_exp:    float = 1.0,
    dd_guard:   dict | None = None,
) -> pd.Series:
    """Build equity for risk-per-trade using variable weights."""
    if not trades:
        return pd.Series(dtype=float)

    df = pd.DataFrame(trades)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])

    all_dates = pd.date_range(df["entry_date"].min(), df["exit_date"].max(), freq="B")
    by_entry  = {}
    for ed, grp in df.groupby("entry_date", sort=False):
        by_entry[ed] = [(int(i), r) for i, r in grp.iterrows()]
    by_exit   = {}
    for i, row in df.iterrows():
        by_exit.setdefault(row["exit_date"], []).append((int(i), row))

    portfolio_val = 1.0
    peak_val      = 1.0
    active: dict  = {}
    equity: dict  = {}

    for date_val in all_dates:
        for tid, row in by_exit.get(date_val, []):
            if tid in active:
                _, w = active.pop(tid)
                portfolio_val += portfolio_val * w * float(row["net_return"])

        peak_val   = max(peak_val, portfolio_val)
        current_dd = portfolio_val / peak_val - 1.0

        size_mult = 1.0
        if dd_guard:
            if current_dd <= -0.20:
                size_mult = 0.0
            elif current_dd <= -0.15:
                size_mult = dd_guard.get("dd15_mult", 0.25)
            elif current_dd <= -0.10:
                size_mult = dd_guard.get("dd10_mult", 0.50)

        remaining  = max_pos - len(active)
        queued     = by_entry.get(date_val, [])
        active_exp = sum(w for _, w in active.values())

        for tid, row in queued[:remaining]:
            w = float(row.get("weight", 0.05)) * size_mult
            w = min(w, max_exp - active_exp)
            if w > 1e-9:
                active[tid] = (row, w)
                active_exp += w

        equity[date_val] = portfolio_val

    return pd.Series(equity)


def _get_stop_distance(stop_mode: str, atr_pct: float) -> float:
    """Resolve stop distance from mode string and ATR estimate."""
    if stop_mode == "fixed_5":    return 0.05
    if stop_mode == "fixed_7":    return 0.07
    if stop_mode == "fixed_10":   return 0.10
    if stop_mode == "fixed_12":   return 0.12
    if stop_mode == "atr_20":     return atr_pct * 2.0
    if stop_mode == "atr_25":     return atr_pct * 2.5
    if stop_mode == "atr_30":     return atr_pct * 3.0
    if stop_mode == "atr_35":     return atr_pct * 3.5
    if stop_mode == "hybrid_7_25":  return max(0.07, atr_pct * 2.5)
    if stop_mode == "hybrid_10_30": return max(0.10, atr_pct * 3.0)
    return 0.07


def run_phase1d_risk_per_trade(
    panel:      pd.DataFrame,
    vnx:        pd.DataFrame,
    strategies: list[str] = None,
    cost:       float = DEFAULT_COST,
    min_lock:   int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Phase 1D: Risk-per-trade feasibility with actual stop simulation.
    Returns: (feasibility_df, stop_delay_df, regime_gate_df)
    """
    print("Phase 1D: risk-per-trade feasibility...", flush=True)
    if strategies is None:
        strategies = ["A3", "S3"]

    gate_by_date, _ = vnindex_regime_gate(vnx)

    risk_pcts  = [0.0025, 0.005, 0.0075, 0.010, 0.0125, 0.015, 0.020]
    stop_modes = ["fixed_5", "fixed_7", "fixed_10", "fixed_12",
                  "atr_20", "atr_25", "atr_30", "atr_35",
                  "hybrid_7_25", "hybrid_10_30"]

    feasibility_rows  = []
    stop_delay_rows   = []
    regime_gate_rows  = []

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        cfg      = STRATEGY_CONFIGS[strategy]
        exit_cfg = cfg["exit_cfg"]

        print(f"  [{strategy}] building signal cache...", flush=True)
        cache = _build_signal_cache(panel, strategy)
        print(f"  [{strategy}] {len(cache)} symbols, running RPT grid...", flush=True)

        # Pre-build base trades (with fixed_7 stop for stop_delay analysis)
        base_stop = 0.07
        base_rp   = 0.01
        base_trades: list[dict] = []
        for sym, data in cache.items():
            atr_est = float(np.nanmedian(data["atr"][:len(data["close"])])) / max(
                float(np.nanmedian(data["close"][:len(data["close"])])), 1e-9)
            sd = _get_stop_distance("fixed_7", atr_est)
            base_trades.extend(_sim_rpt_symbol(
                sym, data, strategy, exit_cfg, cost,
                risk_pct=base_rp, stop_dist=sd, min_lock=min_lock,
                gate_by_date=gate_by_date,
            ))

        # Stop delay analysis from base trades
        if base_trades:
            df_sd = pd.DataFrame(base_trades)
            stop_delay_rows.append({
                "strategy":              strategy,
                "n_stop_exits":          int((df_sd["exit_reason"] == "stop_exit").sum()),
                "n_blocked_stop_events": int(df_sd["blocked_stop_events"].sum()),
                "mean_locked_loss_pct":  float(df_sd["locked_loss"].mean() * 100),
                "max_locked_loss_pct":   float(df_sd["locked_loss"].max() * 100),
                "pct_trades_with_block": float((df_sd["blocked_stop_events"] > 0).mean()),
                "mean_hold_stop_exit":   float(df_sd.loc[df_sd["exit_reason"] == "stop_exit", "hold_bars"].mean())
                                         if (df_sd["exit_reason"] == "stop_exit").any() else np.nan,
            })

        # ── Feasibility grid (risk_pct × stop_mode) ──
        for rp, sm in itertools.product(risk_pcts, stop_modes):
            eid = f"RPT_{strategy}_rp{int(rp*1000)}__{sm}"
            trades: list[dict] = []
            for sym, data in cache.items():
                atr_est = float(np.nanmedian(data["atr"])) / max(float(np.nanmedian(data["close"])), 1e-9)
                sd = _get_stop_distance(sm, atr_est)
                trades.extend(_sim_rpt_symbol(
                    sym, data, strategy, exit_cfg, cost,
                    risk_pct=rp, stop_dist=sd, min_lock=min_lock,
                    gate_by_date=gate_by_date,
                ))

            if not trades:
                continue
            df_t = pd.DataFrame(trades)
            eq   = _build_rpt_equity(trades, max_pos=20, max_exp=1.0)
            if eq.empty:
                continue
            m   = portfolio_metrics(eq, df_t, test_start="2023-01-01")
            cls = _classify_result(m.get("max_dd", np.nan), m.get("mar", np.nan))
            feasibility_rows.append({
                "experiment_id":   eid,
                "strategy":        strategy,
                "risk_pct":        rp * 100,
                "stop_mode":       sm,
                "n_trades":        len(df_t),
                "n_stop_exits":    int((df_t["exit_reason"] == "stop_exit").sum()),
                "pct_stop_exits":  float((df_t["exit_reason"] == "stop_exit").mean()),
                "blocked_events":  int(df_t["blocked_stop_events"].sum()),
                "mean_locked_loss": float(df_t["locked_loss"].mean() * 100),
                "cagr":            m.get("cagr", np.nan),
                "max_dd":          m.get("max_dd", np.nan),
                "sharpe":          m.get("sharpe", np.nan),
                "mar":             m.get("mar", np.nan),
                "prod_class":      cls,
            })

        # ── Regime gate test (at rp=0.01, fixed_7) ──
        regime_modes = [
            ("no_gate",      None),
            ("vnx_ema50",    gate_by_date),
        ]
        for rg_label, rg_gate in regime_modes:
            trades_rg: list[dict] = []
            for sym, data in cache.items():
                trades_rg.extend(_sim_rpt_symbol(
                    sym, data, strategy, exit_cfg, cost,
                    risk_pct=0.01, stop_dist=0.07, min_lock=min_lock,
                    gate_by_date=rg_gate,
                ))
            if not trades_rg:
                continue
            df_rg = pd.DataFrame(trades_rg)
            eq_rg = _build_rpt_equity(trades_rg, max_pos=20, max_exp=1.0)
            if eq_rg.empty:
                continue
            m_rg  = portfolio_metrics(eq_rg, df_rg, test_start="2023-01-01")
            regime_gate_rows.append({
                "strategy":     strategy,
                "regime_gate":  rg_label,
                "n_trades":     len(df_rg),
                "cagr":         m_rg.get("cagr", np.nan),
                "max_dd":       m_rg.get("max_dd", np.nan),
                "sharpe":       m_rg.get("sharpe", np.nan),
                "mar":          m_rg.get("mar", np.nan),
                "prod_class":   _classify_result(m_rg.get("max_dd", np.nan), m_rg.get("mar", np.nan)),
            })

        print(f"  [{strategy}] feasibility: {len(feasibility_rows)} rows", flush=True)

    return pd.DataFrame(feasibility_rows), pd.DataFrame(stop_delay_rows), pd.DataFrame(regime_gate_rows)


# ── Phase 1E: Convergence overlays (A3+GK, S3+GK) ────────────────────────────

def _build_gk_signal_dates(panel: pd.DataFrame, strategy: str) -> dict[str, pd.DatetimeIndex]:
    """Build GK signal date lookup for all symbols."""
    lookup: dict[str, pd.DatetimeIndex] = {}
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf  = sdf.sort_values("date").reset_index(drop=True)
        cl   = sdf["close"].astype(float)
        hi   = sdf["high"].astype(float)
        lo   = sdf.get("low", cl).astype(float)
        gk_d = compute_gk(cl, hi, lo)
        buy  = gk_d["gk_buy"]
        dates_with_buy = pd.to_datetime(sdf["date"])[buy.values.astype(bool)]
        if len(dates_with_buy):
            lookup[sym] = pd.DatetimeIndex(dates_with_buy)
    return lookup


def _has_signal_near(lookup: dict, sym: str, sig_date: pd.Timestamp, window: int) -> bool:
    if sym not in lookup:
        return False
    diffs = np.abs((lookup[sym] - sig_date).days)
    return bool(np.any(diffs <= window))


def run_phase1e_convergence(
    panel:      pd.DataFrame,
    vnx:        pd.DataFrame,
    ledger:     pd.DataFrame,
    strategies: list[str] = None,
    cost:       float = DEFAULT_COST,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Phase 1E: Convergence overlays — A3+GK, S3+GK.
    Returns: (a3s3_diag_df, a3gk_df, s3gk_df)
    """
    print("Phase 1E: convergence overlays...", flush=True)
    if strategies is None:
        strategies = ["A3", "S3"]

    gate_by_date, _ = vnindex_regime_gate(vnx)

    # A3+S3 diagnostic — breakdown by ema_dist / entry label / regime
    a3s3_rows = []
    a3_trades = ledger[ledger["strategy"] == "A3"].copy()
    s3_lookup: dict[str, pd.DatetimeIndex] = {}
    s3_trades = ledger[ledger["strategy"] == "S3"]
    for sym, grp in s3_trades.groupby("symbol"):
        s3_lookup[sym] = pd.to_datetime(grp["signal_date"].values)

    if not a3_trades.empty:
        a3_trades["signal_date"] = pd.to_datetime(a3_trades["signal_date"])
        a3_trades["has_s3_3d"]  = a3_trades.apply(
            lambda r: _has_signal_near(s3_lookup, r["symbol"], r["signal_date"], 3), axis=1)
        a3_trades["has_s3_5d"]  = a3_trades.apply(
            lambda r: _has_signal_near(s3_lookup, r["symbol"], r["signal_date"], 5), axis=1)

        for col, label_col in [("ema_dist_at_entry", "ema_dist_bucket"),
                                ("near_entry_label",  "entry_label")]:
            if col not in a3_trades.columns:
                continue
            if col == "ema_dist_at_entry":
                a3_trades["_bucket"] = pd.qcut(a3_trades[col], q=4,
                                                labels=["Q1_low","Q2","Q3","Q4_high"], duplicates="drop")
            else:
                a3_trades["_bucket"] = a3_trades[col]

            for bkt, grp in a3_trades.groupby("_bucket"):
                for has_s3_col in ["has_s3_3d", "has_s3_5d"]:
                    for s3_val in [True, False]:
                        sub = grp[grp[has_s3_col] == s3_val]
                        if len(sub) < 3:
                            continue
                        a3s3_rows.append({
                            "bucket_type":  label_col,
                            "bucket":       str(bkt),
                            "convergence":  has_s3_col,
                            "has_s3":       s3_val,
                            "n":            len(sub),
                            "mean_net":     float(sub["net_return"].mean()),
                            "hit_rate":     float((sub["net_return"] > 0).mean()),
                            "mean_mae":     float(sub["mae"].mean()) if "mae" in sub.columns else np.nan,
                        })

    # Build GK signal lookup
    print("  Building GK signal date lookup...", flush=True)
    gk_lookup = _build_gk_signal_dates(panel, "A3")  # same panel for all

    # ── A3+GK overlay variants ──
    a3gk_rows = []
    if not a3_trades.empty and gk_lookup:
        a3_trades["signal_date"] = pd.to_datetime(a3_trades["signal_date"])

        for window in [3, 5, 10]:
            col = f"has_gk_{window}d"
            a3_trades[col] = a3_trades.apply(
                lambda r: _has_signal_near(gk_lookup, r["symbol"], r["signal_date"], window), axis=1)

        for window in [3, 5, 10]:
            col = f"has_gk_{window}d"
            for include_gk in [True, False]:
                filtered = a3_trades[a3_trades[col] == include_gk]
                label    = "A3+GK" if include_gk else "A3_no_GK"
                eid      = f"CONV_A3GK_w{window}_{label}"

                if filtered.empty:
                    continue
                eq, _ = _build_corrected_equity(filtered, max_positions=20, max_position_pct=0.05)
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, filtered, test_start="2023-01-01")

                a3gk_rows.append({
                    "experiment_id":  eid,
                    "strategy":       "A3",
                    "gk_window":      window,
                    "has_gk":         include_gk,
                    "n_trades":       len(filtered),
                    "coverage_pct":   len(filtered) / max(len(a3_trades), 1),
                    "mean_net":       float(filtered["net_return"].mean()),
                    "cagr":           m.get("cagr", np.nan),
                    "max_dd":         m.get("max_dd", np.nan),
                    "sharpe":         m.get("sharpe", np.nan),
                    "mar":            m.get("mar", np.nan),
                    "prod_class":     _classify_result(m.get("max_dd", np.nan), m.get("mar", np.nan)),
                })

            # A3 normal + 1.25× size on GK confirmation (multiplier)
            filtered_all  = a3_trades.copy()
            gk_mask       = a3_trades[col].values
            filtered_all["ema_dist_at_entry"] = a3_trades["ema_dist_at_entry"].values * \
                                                 np.where(gk_mask, 1.25, 1.0)
            eq_mult, _ = _build_corrected_equity(
                filtered_all, max_positions=20, max_position_pct=0.05,
                rank_col="ema_dist_at_entry", rank_mode="linear",
            )
            if not eq_mult.empty:
                m_mult = portfolio_metrics(eq_mult, filtered_all, test_start="2023-01-01")
                a3gk_rows.append({
                    "experiment_id":  f"CONV_A3GK_w{window}_size125x",
                    "strategy":       "A3",
                    "gk_window":      window,
                    "has_gk":         "mult_125x",
                    "n_trades":       len(filtered_all),
                    "coverage_pct":   1.0,
                    "mean_net":       float(filtered_all["net_return"].mean()),
                    "cagr":           m_mult.get("cagr", np.nan),
                    "max_dd":         m_mult.get("max_dd", np.nan),
                    "sharpe":         m_mult.get("sharpe", np.nan),
                    "mar":            m_mult.get("mar", np.nan),
                    "prod_class":     _classify_result(m_mult.get("max_dd", np.nan), m_mult.get("mar", np.nan)),
                })

    # ── S3+GK overlay variants ──
    s3gk_rows = []
    s3_trades_full = ledger[ledger["strategy"] == "S3"].copy()
    if not s3_trades_full.empty and gk_lookup:
        s3_trades_full["signal_date"] = pd.to_datetime(s3_trades_full["signal_date"])
        for window in [3, 5, 10]:
            s3_trades_full[f"has_gk_{window}d"] = s3_trades_full.apply(
                lambda r: _has_signal_near(gk_lookup, r["symbol"], r["signal_date"], window), axis=1)

        for window in [3, 5, 10]:
            col = f"has_gk_{window}d"
            for include_gk in [True, False]:
                filtered = s3_trades_full[s3_trades_full[col] == include_gk]
                label    = "S3+GK" if include_gk else "S3_no_GK"
                eid      = f"CONV_S3GK_w{window}_{label}"
                if filtered.empty:
                    continue
                eq, _ = _build_corrected_equity(filtered, max_positions=20, max_position_pct=0.05)
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, filtered, test_start="2023-01-01")
                s3gk_rows.append({
                    "experiment_id":  eid,
                    "strategy":       "S3",
                    "gk_window":      window,
                    "has_gk":         include_gk,
                    "n_trades":       len(filtered),
                    "coverage_pct":   len(filtered) / max(len(s3_trades_full), 1),
                    "mean_net":       float(filtered["net_return"].mean()),
                    "cagr":           m.get("cagr", np.nan),
                    "max_dd":         m.get("max_dd", np.nan),
                    "sharpe":         m.get("sharpe", np.nan),
                    "mar":            m.get("mar", np.nan),
                    "prod_class":     _classify_result(m.get("max_dd", np.nan), m.get("mar", np.nan)),
                })

    return (pd.DataFrame(a3s3_rows), pd.DataFrame(a3gk_rows), pd.DataFrame(s3gk_rows))


# ── Phase 1I: Annual and regime decomposition ─────────────────────────────────

def decompose_by_year_regime(
    trades_df:    pd.DataFrame,
    equity_dict:  dict[str, pd.Series],
    gate_by_date: pd.Series,
    label:        str = "baseline",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Produce year and regime decomposition for any trade set.
    Returns: (by_year_df, by_regime_df)
    """
    if trades_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = trades_df.copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["year"]       = df["entry_date"].dt.year
    df["vnx_regime"] = df["entry_date"].apply(
        lambda d: "ON" if bool(gate_by_date.get(d.normalize(), True)) else "OFF"
    )

    year_rows   = []
    regime_rows = []

    for strategy in df["strategy"].unique():
        sub = df[df["strategy"] == strategy]

        # By year
        for yr, grp in sub.groupby("year"):
            if len(grp) < 3:
                continue
            year_rows.append({
                "label":         label,
                "strategy":      strategy,
                "year":          yr,
                "n_trades":      len(grp),
                "mean_net":      float(grp["net_return"].mean()),
                "hit_rate":      float((grp["net_return"] > 0).mean()),
                "pct_tp_trail":  float((grp["exit_reason"] == "tp_trail").mean()) if "exit_reason" in grp.columns else np.nan,
                "mean_hold":     float(grp.get("holding_days", grp.get("hold_bars", pd.Series())).mean()) if "holding_days" in grp.columns or "hold_bars" in grp.columns else np.nan,
            })

        # By regime
        for regime_val, grp in sub.groupby("vnx_regime"):
            if len(grp) < 3:
                continue
            regime_rows.append({
                "label":        label,
                "strategy":     strategy,
                "vnx_regime":   regime_val,
                "n_trades":     len(grp),
                "mean_net":     float(grp["net_return"].mean()),
                "hit_rate":     float((grp["net_return"] > 0).mean()),
                "pct_tp_trail": float((grp["exit_reason"] == "tp_trail").mean()) if "exit_reason" in grp.columns else np.nan,
            })

    return pd.DataFrame(year_rows), pd.DataFrame(regime_rows)


# ── Final reports ──────────────────────────────────────────────────────────────

def write_phase1_findings(
    out_dir:        Path,
    pb_robust:      pd.DataFrame,
    pb_quality:     pd.DataFrame,
    rank_sizing:    pd.DataFrame,
    dd_guard:       pd.DataFrame,
    rpt_feasible:   pd.DataFrame,
    a3gk_df:        pd.DataFrame,
    s3gk_df:        pd.DataFrame,
    by_year:        pd.DataFrame,
    by_regime:      pd.DataFrame,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Phase 1 Revised — Top Findings\n", f"Generated: {date.today()}\n\n"]

    # Baseline reminder
    lines += [
        "## Baseline (equal-weight, corrected engine)\n\n",
        "A3: CAGR=13.61%, MaxDD=-26.51%, Sharpe=1.18, MAR=0.51 | "
        "S3: CAGR=11.91%, MaxDD=-27.36%, Sharpe=1.04, MAR=0.44\n\n",
    ]

    # 1B pullback top 5
    lines.append("## Phase 1B — Pullback Scale-in Robustness\n\n")
    if not pb_robust.empty:
        top5 = pb_robust.dropna(subset=["mar"]).nlargest(5, "mar")
        lines += ["| ID | Strategy | Depth | Window | Quality | Split | CAGR | MaxDD | Sharpe | MAR | PB% |\n",
                  "|----|----------|-------|--------|---------|-------|------|-------|--------|-----|-----|\n"]
        for _, r in top5.iterrows():
            lines.append(
                f"| {r['experiment_id']} | {r['strategy']} | {r['pb_depth_pct']:.0f}% | "
                f"{r['pb_window_bars']}b | {r['quality_mode']} | {r['split']} | "
                f"{r['cagr']:.2%} | {r['max_dd']:.2%} | {r['sharpe']:.2f} | "
                f"{r['mar']:.2f} | {r['pct_pullback']:.1%} |\n"
            )

    # 1B quality table
    lines.append("\n### Pullback vs No-Pullback Trade Quality\n\n")
    if not pb_quality.empty:
        lines += ["| Strategy | Group | N | Mean Net | Mean T1 | Benefit | Hit Rate |\n",
                  "|----------|-------|---|----------|---------|---------|----------|\n"]
        for _, r in pb_quality.iterrows():
            lines.append(
                f"| {r['strategy']} | {r['group']} | {r['n']} | "
                f"{r['mean_net']:.2%} | {r['mean_t1_only']:.2%} | "
                f"{r['mean_benefit']:.2%} | {r['hit_rate']:.2%} |\n"
            )

    # 1C rank sizing top 5
    lines.append("\n## Phase 1C — Rank Sizing with Caps\n\n")
    if not rank_sizing.empty:
        cands = rank_sizing[rank_sizing["prod_class"] == "PRODUCTION_CANDIDATE"].nlargest(5, "mar")
        if cands.empty:
            cands = rank_sizing.dropna(subset=["mar"]).nlargest(5, "mar")
        lines += ["| ID | Strategy | Mode | Pos | Pct | Exp | Guard | CAGR | MaxDD | MAR | Class |\n",
                  "|----|----------|------|-----|-----|-----|-------|------|-------|-----|-------|\n"]
        for _, r in cands.iterrows():
            lines.append(
                f"| {r['experiment_id']} | {r['strategy']} | {r['rank_mode']} | "
                f"{r['max_positions']} | {r['max_position_pct']:.1%} | "
                f"{r['max_total_exp']:.0%} | {r['dd_guard']} | "
                f"{r['cagr']:.2%} | {r['max_dd']:.2%} | {r['mar']:.2f} | {r['prod_class']} |\n"
            )

    # 1D feasibility summary
    lines.append("\n## Phase 1D — Risk-Per-Trade Feasibility\n\n")
    if not rpt_feasible.empty:
        prod = rpt_feasible[rpt_feasible["prod_class"] == "PRODUCTION_CANDIDATE"]
        lines.append(f"Production candidates (MaxDD > -30%): {len(prod)}\n")
        shadow = rpt_feasible[rpt_feasible["prod_class"] == "SHADOW_TEST"]
        lines.append(f"Shadow test (MaxDD -30% to -40%): {len(shadow)}\n")
        rejected = rpt_feasible[rpt_feasible["prod_class"] == "REJECT"]
        lines.append(f"Rejected (MaxDD < -50%): {len(rejected)}\n\n")
        if not prod.empty:
            lines += ["| ID | Strategy | Risk% | Stop | CAGR | MaxDD | MAR |\n",
                      "|----|----------|-------|------|------|-------|-----|\n"]
            for _, r in prod.nlargest(5, "mar").iterrows():
                lines.append(
                    f"| {r['experiment_id']} | {r['strategy']} | {r['risk_pct']:.2f}% | "
                    f"{r['stop_mode']} | {r['cagr']:.2%} | {r['max_dd']:.2%} | {r['mar']:.2f} |\n"
                )

    # 1E convergence
    lines.append("\n## Phase 1E — A3+GK and S3+GK Convergence\n\n")
    for df, label in [(a3gk_df, "A3+GK"), (s3gk_df, "S3+GK")]:
        if not df.empty:
            lines.append(f"### {label}\n\n")
            lines += ["| ID | Window | Has GK | Coverage | CAGR | MaxDD | MAR | Class |\n",
                      "|----|--------|--------|----------|------|-------|-----|-------|\n"]
            for _, r in df.sort_values("mar", ascending=False).head(6).iterrows():
                lines.append(
                    f"| {r['experiment_id']} | {r['gk_window']}d | {r['has_gk']} | "
                    f"{r['coverage_pct']:.1%} | {r['cagr']:.2%} | {r['max_dd']:.2%} | "
                    f"{r['mar']:.2f} | {r['prod_class']} |\n"
                )

    top_path = out_dir / "PHASE1_REVISED_TOP_FINDINGS.md"
    top_path.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {top_path}", flush=True)

    # Classification summary
    def _write_class(cls_name: str, df: pd.DataFrame) -> list[str]:
        sub = df[df.get("prod_class", pd.Series()) == cls_name] if "prod_class" in df.columns else pd.DataFrame()
        out = [f"# {cls_name} Rules\n\nGenerated: {date.today()}\n\n"]
        if sub.empty:
            out.append("No rules in this class from Phase 1 batch.\n")
        else:
            out.append(sub.to_markdown(index=False) + "\n")
        return out

    _classifiable = [df for df in [rank_sizing, rpt_feasible, a3gk_df, s3gk_df] if not df.empty]
    if _classifiable:
        all_results = pd.concat(_classifiable, ignore_index=True)
        for cls in ["PRODUCTION_CANDIDATE", "SHADOW_TEST", "RESEARCH_ONLY", "REJECT"]:
            fname = out_dir / f"{cls.lower()}_rules.md"
            fname.write_text("".join(_write_class(cls, all_results)), encoding="utf-8")
        print(f"  Wrote classification files to {out_dir}", flush=True)


# ── CLI / main ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio Optimization Phase 1 Revised")
    parser.add_argument("--phase",        choices=["1b", "1c", "1d", "1e", "1i", "all"], default="all")
    parser.add_argument("--strategies",   default="A3,S3")
    parser.add_argument("--max-symbols",  type=int, default=None)
    parser.add_argument("--min-lock",     type=int, default=5)
    parser.add_argument("--cost",         type=float, default=DEFAULT_COST)
    args = parser.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",")]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading data (max_symbols={args.max_symbols})...", flush=True)
    panel = load_panel(max_symbols=args.max_symbols)
    vnx   = load_vnindex()
    print(f"  Panel: {len(panel):,} rows, {panel['symbol'].nunique()} symbols", flush=True)

    ledger = load_ledger()
    if ledger.empty:
        print("  WARNING: trade ledger not found; run portfolio_optimization_research.py --run-baseline first")
    else:
        print(f"  Ledger: {len(ledger):,} trades", flush=True)

    gate_by_date, _ = vnindex_regime_gate(vnx)

    # ── Outputs accumulate across phases ──
    pb_robust     = pd.DataFrame()
    pb_quality    = pd.DataFrame()
    pb_year       = pd.DataFrame()
    pb_regime     = pd.DataFrame()
    rank_sizing   = pd.DataFrame()
    interaction   = pd.DataFrame()
    dd_guard      = pd.DataFrame()
    rpt_feasible  = pd.DataFrame()
    rpt_stop      = pd.DataFrame()
    rpt_regime    = pd.DataFrame()
    a3s3_diag     = pd.DataFrame()
    a3gk_df       = pd.DataFrame()
    s3gk_df       = pd.DataFrame()
    by_year       = pd.DataFrame()
    by_regime     = pd.DataFrame()

    run_1b = args.phase in ("1b", "all")
    run_1c = args.phase in ("1c", "all")
    run_1d = args.phase in ("1d", "all")
    run_1e = args.phase in ("1e", "all")
    run_1i = args.phase in ("1i", "all")

    # ── Phase 1B ──
    if run_1b:
        pb_robust, pb_quality, pb_year, pb_regime = run_phase1b_pullback(
            panel, vnx, strategies=strategies, cost=args.cost, min_lock=args.min_lock,
        )
        pb_robust.to_csv(OUT_DIR / "scalein_pullback_robustness.csv", index=False)
        pb_quality.to_csv(OUT_DIR / "pullback_vs_no_pullback_trade_quality.csv", index=False)
        pb_year.to_csv(OUT_DIR / "pullback_scalein_by_year.csv", index=False)
        pb_regime.to_csv(OUT_DIR / "pullback_scalein_by_regime.csv", index=False)
        print(f"  1B saved: {len(pb_robust)} robustness rows", flush=True)

    # ── Phase 1C ──
    if run_1c and not ledger.empty:
        rank_sizing, interaction, dd_guard = run_phase1c_rank_sizing(ledger, strategies=strategies)
        rank_sizing.to_csv(OUT_DIR / "rank_sizing_with_caps.csv", index=False)
        dd_guard.to_csv(OUT_DIR / "rank_sizing_drawdown_guard.csv", index=False)
        if not interaction.empty:
            interaction.to_csv(OUT_DIR / "linear_plus_pullback_interaction.csv", index=False)
        print(f"  1C saved: {len(rank_sizing)} rank sizing rows", flush=True)
    elif run_1c:
        print("  1C skipped: no trade ledger", flush=True)

    # ── Phase 1D ──
    if run_1d:
        rpt_feasible, rpt_stop, rpt_regime = run_phase1d_risk_per_trade(
            panel, vnx, strategies=strategies, cost=args.cost, min_lock=args.min_lock,
        )
        rpt_feasible.to_csv(OUT_DIR / "risk_per_trade_feasibility.csv", index=False)
        rpt_stop.to_csv(OUT_DIR / "risk_per_trade_stop_delay.csv", index=False)
        rpt_regime.to_csv(OUT_DIR / "risk_per_trade_regime_gate.csv", index=False)
        print(f"  1D saved: {len(rpt_feasible)} RPT feasibility rows", flush=True)

    # ── Phase 1E ──
    if run_1e and not ledger.empty:
        a3s3_diag, a3gk_df, s3gk_df = run_phase1e_convergence(
            panel, vnx, ledger, strategies=strategies, cost=args.cost,
        )
        a3s3_diag.to_csv(OUT_DIR / "convergence_diagnostics_A3S3.csv", index=False)
        a3gk_df.to_csv(OUT_DIR / "convergence_A3GK_overlay.csv", index=False)
        s3gk_df.to_csv(OUT_DIR / "convergence_S3GK_overlay.csv", index=False)
        print(f"  1E saved: A3+GK={len(a3gk_df)}, S3+GK={len(s3gk_df)}, A3S3 diag={len(a3s3_diag)}", flush=True)
    elif run_1e:
        print("  1E skipped: no trade ledger", flush=True)

    # ── Phase 1I: Year/regime decomposition ──
    if run_1i and not ledger.empty:
        by_year, by_regime = decompose_by_year_regime(ledger, {}, gate_by_date, label="baseline")
        by_year.to_csv(OUT_DIR / "component_by_year.csv", index=False)
        by_regime.to_csv(OUT_DIR / "component_by_regime.csv", index=False)

        if run_1b and not pb_robust.empty:
            # Find best pullback variant and add to decomp
            best_pb_eid = pb_robust.dropna(subset=["mar"]).nlargest(1, "mar")
            if not best_pb_eid.empty:
                print(f"  1I: best pullback variant = {best_pb_eid.iloc[0]['experiment_id']}", flush=True)
        print(f"  1I saved: {len(by_year)} year rows, {len(by_regime)} regime rows", flush=True)

    # ── Phase 1J: Final report (load existing CSVs for phases not run this session) ──
    def _load_csv(df: pd.DataFrame, fname: str) -> pd.DataFrame:
        if not df.empty:
            return df
        p = OUT_DIR / fname
        return pd.read_csv(p) if p.exists() else df

    pb_robust   = _load_csv(pb_robust,   "scalein_pullback_robustness.csv")
    pb_quality  = _load_csv(pb_quality,  "pullback_vs_no_pullback_trade_quality.csv")
    rank_sizing = _load_csv(rank_sizing, "rank_sizing_with_caps.csv")
    dd_guard    = _load_csv(dd_guard,    "rank_sizing_drawdown_guard.csv")
    rpt_feasible= _load_csv(rpt_feasible,"risk_per_trade_feasibility.csv")
    a3gk_df     = _load_csv(a3gk_df,    "convergence_A3GK_overlay.csv")
    s3gk_df     = _load_csv(s3gk_df,    "convergence_S3GK_overlay.csv")
    by_year     = _load_csv(by_year,     "component_by_year.csv")
    by_regime   = _load_csv(by_regime,   "component_by_regime.csv")

    write_phase1_findings(
        OUT_DIR, pb_robust, pb_quality, rank_sizing, dd_guard,
        rpt_feasible, a3gk_df, s3gk_df, by_year, by_regime,
    )

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
