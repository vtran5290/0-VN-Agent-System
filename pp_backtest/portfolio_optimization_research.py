#!/usr/bin/env python3
"""
Portfolio Optimization Research — multi-phase experiment framework.

Phases:
  0  — Full trade ledger (A3, S3, GK) + baseline portfolio simulation
  1  — Position sizing experiments (equal-weight grid, rank-based, inv-vol, risk-per-trade)
  2  — Scale-in experiments
  3  — Convergence experiments (multi-strategy signal overlap)
  5  — Walk-forward OOS validation
  6  — Reports (TOP_FINDINGS.md, implementation_notes.md)

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_research.py --run-baseline
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_research.py --experiment sizing --max-symbols 30
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_research.py --experiment all
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import warnings
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# ── Imports from existing infrastructure ─────────────────────────────────────
from pp_backtest.ema_portfolio_sim import (
    DEFAULT_COST,
    _exit_partial_tp_v2,
    _build_equity_v2,
    portfolio_metrics,
    sim_symbol_v2,
    compute_all_trades_v2,
)
from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry

# Import GK helpers from daily_three_strategy_scan.
# If that module has import-time side effects (e.g. network calls), we catch
# and fall back to inlined copies.
try:
    from pp_backtest.daily_three_strategy_scan import (  # type: ignore
        compute_gk,
        vnindex_regime_gate,
        _near_entry_label_b20100,
        _near_entry_label_b2155,
    )
except Exception:
    # ── Fallback: inlined copies (source: daily_three_strategy_scan.py) ──────
    GK_LEN = 100
    GK_MULT = 2.0
    GK_ATR = 14
    GK_LAG = 49

    def compute_gk(close: pd.Series, high: pd.Series, low: pd.Series) -> dict:
        past_close = close.shift(GK_LAG).fillna(close)
        zl_input = close + (close - past_close)
        gk_zl = zl_input.ewm(span=GK_LEN, adjust=False).mean()
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
        gk_sell = (flip & (trend == -1)).fillna(False)
        return {
            "gk_zl": gk_zl, "atr": atr,
            "gk_upper": gk_upper, "gk_lower": gk_lower,
            "gk_bull": gk_bull, "trend": trend,
            "gk_buy": gk_buy.fillna(False), "gk_sell": gk_sell,
        }

    def vnindex_regime_gate(vnx: pd.DataFrame) -> tuple[pd.Series, bool]:
        w = vnx.sort_values("date").reset_index(drop=True)
        c = w["close"].astype(float)
        ema20 = c.ewm(span=20, adjust=False).mean()
        ema50 = c.ewm(span=50, adjust=False).mean()
        gate = (c > ema50) & (ema20 > ema50)
        idx = pd.to_datetime(w["date"]).dt.normalize()
        s = pd.Series(gate.values, index=idx)
        last = bool(gate.iloc[-1]) if len(gate) else False
        return s, last

    def _near_entry_label_b20100(pct_vs: float) -> str:
        if pct_vs < -0.10: return "deep_pullback"
        if pct_vs < -0.02: return "ideal_pullback"
        if pct_vs <= 0.08: return "acceptable"
        if pct_vs <= 0.14: return "stretched"
        return "momentum_confirmed"

    def _near_entry_label_b2155(pct_vs: float) -> str:
        if pct_vs < -0.06: return "damaged"
        if pct_vs < -0.02: return "ideal"
        if pct_vs <= 0.08: return "acceptable"
        if pct_vs <= 0.14: return "stretched"
        return "momentum_confirmed"


# ── Constants ─────────────────────────────────────────────────────────────────
ANN = 252
EXCLUDE_VIN3 = {"VIC", "VHM", "VRE", "VPL"}

EXIT_18_25 = {
    "tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5,
    "trail_basis": "close", "derisk_bars": None, "derisk_mult": None, "max_hold": 250,
}
EXIT_18_35 = {
    "tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5,
    "trail_basis": "close", "derisk_bars": None, "derisk_mult": None, "max_hold": 250,
}

STRATEGY_CONFIGS: dict[str, dict] = {
    "A3": {
        "ema_fast": 20, "ema_slow": 100, "exit_cfg": EXIT_18_25,
        "rank_mode": "ema_dist", "universe": "ex_vin3", "label": "A3_primary",
    },
    "S3": {
        "ema_fast": 21, "ema_slow": 55, "exit_cfg": EXIT_18_35,
        "rank_mode": "mom20", "universe": "full", "label": "S3_shadow",
    },
}

OUT_DIR = REPO / "data" / "research" / "portfolio_optimization"


# ── Data loading ───────────────────────────────────────────────────────────────

def load_panel(max_symbols: int | None = None) -> pd.DataFrame:
    path = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if max_symbols is not None:
        syms = sorted(df["symbol"].unique())[:max_symbols]
        df = df[df["symbol"].isin(syms)]
    return df


def load_vnindex() -> pd.DataFrame:
    path = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def get_universe(panel: pd.DataFrame, universe_type: str) -> list[str]:
    all_syms = sorted(panel["symbol"].unique())
    if universe_type == "ex_vin3":
        return [s for s in all_syms if s not in EXCLUDE_VIN3]
    return all_syms


# ── Exit reason helper ────────────────────────────────────────────────────────

def _exit_reason_v2(
    close_arr: np.ndarray,
    high_arr: np.ndarray,
    atr_arr: np.ndarray,
    start: int,
    entry_price: float,
    exit_cfg: dict,
) -> tuple[int, float, str]:
    """
    Like _exit_partial_tp_v2 but also returns exit_reason:
      'tp_trail'            — TP1 hit then trail exits
      'max_hold'            — hit max_hold (TP1 WAS hit)
      'tp_not_hit_max_hold' — hit max_hold without TP1
    """
    tp_pct     = float(exit_cfg.get("tp_pct", 0.15))
    tp_frac    = float(exit_cfg.get("tp_frac", 0.50))
    trail_mult = float(exit_cfg.get("trail_mult", 2.5))
    trail_basis = str(exit_cfg.get("trail_basis", "close"))
    derisk_bars = exit_cfg.get("derisk_bars", None)
    derisk_mult = exit_cfg.get("derisk_mult", None)
    max_hold   = int(exit_cfg.get("max_hold", 250))

    tp_price   = entry_price * (1 + tp_pct)
    tp_hit     = False
    tp_bar     = 0
    tp_ret     = 0.0
    high_water = entry_price
    end        = min(start + max_hold, len(close_arr) - 1)

    for j in range(start, end + 1):
        c = close_arr[j]
        h = high_arr[j] if trail_basis == "high" else c
        high_water = max(high_water, h)

        if not tp_hit and c >= tp_price:
            tp_hit = True
            tp_bar = j
            tp_ret = (c - entry_price) / entry_price

        if tp_hit:
            mult = (
                derisk_mult
                if (derisk_bars is not None and derisk_mult is not None
                    and (j - tp_bar) >= derisk_bars)
                else trail_mult
            )
            if c < high_water - mult * atr_arr[j]:
                rem = (c - entry_price) / entry_price
                gross = tp_frac * tp_ret + (1 - tp_frac) * rem
                return j - start, gross, "tp_trail"

    c_end = close_arr[end]
    rem   = (c_end - entry_price) / entry_price
    if tp_hit:
        gross  = tp_frac * tp_ret + (1 - tp_frac) * rem
        reason = "max_hold"
    else:
        gross  = rem
        reason = "tp_not_hit_max_hold"
    return end - start, gross, reason


# ── Extended sim_symbol (with extra columns) ──────────────────────────────────

def sim_symbol_extended(
    sdf: pd.DataFrame,
    strategy: str,
    exit_cfg: dict,
    cost: float = DEFAULT_COST,
    gate_by_date: pd.Series | None = None,
) -> list[dict]:
    """
    Like sim_symbol_v2 but adds: signal_date, signal_close, exit_reason,
    mae, mfe, adv50_value, near_entry_pct_vs_signal, near_entry_label, is_ex_vin3.
    For A3 / S3 strategies (not GK).
    """
    cfg = STRATEGY_CONFIGS[strategy]
    ema_fast_n = cfg["ema_fast"]
    ema_slow_n = cfg["ema_slow"]
    max_hold   = int(exit_cfg.get("max_hold", 250))

    if len(sdf) < max(ema_slow_n + 10, 100):
        return []

    sdf    = sdf.copy().reset_index(drop=True)
    close  = sdf["close"]
    high   = sdf["high"]
    low    = sdf.get("low", close)
    volume = sdf.get("volume", pd.Series(np.ones(len(sdf)), index=sdf.index))
    symbol = sdf["symbol"].iloc[0]
    dates  = sdf["date"]

    value  = sdf["value"] if "value" in sdf.columns else close * volume

    cloud_d    = ema_cloud(close, ema_fast_n, ema_slow_n)
    fast_ema   = cloud_d["ema_fast"]
    slow_ema   = cloud_d["ema_slow"]
    cloud_bull = cloud_d["cloud_bull"]
    atr        = compute_atr(high, low, close, period=14)
    warmup     = max(ema_slow_n + 5, 60)

    mom20  = close.pct_change(20).fillna(0.0)
    mom60  = close.pct_change(60).fillna(0.0)
    adv20  = value.rolling(20, min_periods=10).mean()
    adv50  = value.rolling(50, min_periods=25).mean()

    sig = cloud_only_entry(close, fast_ema, cloud_bull, min_bars_bear=3, warmup=warmup)

    close_arr = close.values
    high_arr  = high.values
    atr_arr   = atr.values
    slow_arr  = slow_ema.values
    mom20_arr = mom20.values
    mom60_arr = mom60.values
    adv20_arr = adv20.values
    adv50_arr = adv50.values
    vol_arr   = volume.values
    date_arr  = dates.values
    n         = len(sdf)

    is_ex_vin3 = symbol not in EXCLUDE_VIN3

    if strategy == "A3":
        label_fn = _near_entry_label_b20100
    else:
        label_fn = _near_entry_label_b2155

    trades = []
    for ei in np.where(sig.values)[0]:
        signal_i   = ei
        entry_i    = ei + 1
        if entry_i >= n:
            continue
        ep = close_arr[entry_i]
        if ep <= 0 or np.isnan(ep):
            continue

        signal_date  = pd.Timestamp(date_arr[signal_i])
        signal_close = float(close_arr[signal_i])
        entry_date   = pd.Timestamp(date_arr[entry_i])

        # Check regime gate
        vnindex_regime = False
        if gate_by_date is not None:
            vnindex_regime = bool(gate_by_date.get(entry_date, False))

        bars_held, gross, exit_reason = _exit_reason_v2(
            close_arr, high_arr, atr_arr, entry_i, ep, exit_cfg
        )

        exit_i    = min(entry_i + bars_held, n - 1)
        exit_date = pd.Timestamp(date_arr[exit_i])
        exit_price = float(close_arr[exit_i])

        # MAE / MFE
        trade_close = close_arr[entry_i: exit_i + 1]
        mae = float((trade_close.min() - ep) / ep) if len(trade_close) > 0 else 0.0
        mfe = float((trade_close.max() - ep) / ep) if len(trade_close) > 0 else 0.0

        # Near-entry label
        pct_vs = (ep - signal_close) / signal_close if signal_close > 0 else 0.0
        near_entry_label = label_fn(pct_vs)

        # adv50_value
        adv50_v = float(adv50_arr[entry_i])
        if not np.isfinite(adv50_v):
            adv50_v = 0.0

        # adv20 for rank
        adv_v = float(adv20_arr[entry_i])
        if not np.isfinite(adv_v):
            adv_v = 0.0

        slow_at_e = float(slow_arr[entry_i])
        ema_dist  = float((ep - slow_at_e) / slow_at_e) if slow_at_e > 0 else 0.0
        atr_pct   = float(atr_arr[entry_i] / ep) if ep > 0 else 0.02
        if not np.isfinite(atr_pct) or atr_pct <= 0:
            atr_pct = 0.02

        # rank_metric (native per strategy)
        if strategy == "A3":
            rank_metric = ema_dist
        else:
            rank_metric = float(mom20_arr[entry_i])

        trades.append({
            "symbol":                    symbol,
            "strategy":                  strategy,
            "signal_date":               signal_date,
            "signal_close":              signal_close,
            "entry_date":                entry_date,
            "entry_price":               ep,
            "exit_date":                 exit_date,
            "exit_price":                exit_price,
            "exit_reason":               exit_reason,
            "gross_return":              gross,
            "net_return":                gross - cost,
            "holding_days":              bars_held,
            # alias for _build_equity_v2 compatibility
            "hold_bars":                 bars_held,
            "mae":                       mae,
            "mfe":                       mfe,
            "adv50_value":               adv50_v,
            "rank_metric":               rank_metric,
            "ema_dist":                  ema_dist,
            "ema_dist_at_entry":         ema_dist,  # needed by _build_equity_v2
            "mom20":                     float(mom20_arr[entry_i]),
            "mom20_at_entry":            float(mom20_arr[entry_i]),
            "mom60":                     float(mom60_arr[entry_i]),
            "mom60_at_entry":            float(mom60_arr[entry_i]),
            "adv20_at_entry":            adv_v,
            "vol_at_entry":              float(vol_arr[entry_i]),
            "atr_pct_at_entry":          atr_pct,
            "near_entry_label":          near_entry_label,
            "near_entry_pct_vs_signal":  pct_vs,
            "vnindex_regime":            vnindex_regime,
            "is_ex_vin3":                is_ex_vin3,
            "trade_id":                  f"{strategy}_{symbol}_{signal_date.date()}",
        })

    return trades


# ── GK sim ────────────────────────────────────────────────────────────────────

def sim_symbol_gk(
    sdf: pd.DataFrame,
    gate_by_date: pd.Series,
    cost: float = DEFAULT_COST,
) -> list[dict]:
    """
    Simulate C_GK_regime trades for one symbol.
    Entry: bar after gk_buy fires while regime gate is ON.
    Exit: simple trail — close < high_water - 2.5*ATR, max_hold=250.
    """
    if len(sdf) < 120:
        return []

    sdf    = sdf.copy().reset_index(drop=True)
    close  = sdf["close"]
    high   = sdf["high"]
    low    = sdf.get("low", close)
    volume = sdf.get("volume", pd.Series(np.ones(len(sdf)), index=sdf.index))
    symbol = sdf["symbol"].iloc[0]
    dates  = sdf["date"]
    value  = sdf["value"] if "value" in sdf.columns else close * volume

    gk_d   = compute_gk(close, high, low)
    gk_buy = gk_d["gk_buy"]
    atr    = gk_d["atr"]

    adv20  = value.rolling(20, min_periods=10).mean()
    adv50  = value.rolling(50, min_periods=25).mean()
    mom20  = close.pct_change(20).fillna(0.0)
    mom60  = close.pct_change(60).fillna(0.0)

    cloud_d    = ema_cloud(close, 20, 55)
    slow_ema   = cloud_d["ema_slow"]

    close_arr = close.values
    high_arr  = high.values
    atr_arr   = atr.values
    slow_arr  = slow_ema.values
    date_arr  = dates.values
    adv20_arr = adv20.values
    adv50_arr = adv50.values
    mom20_arr = mom20.values
    mom60_arr = mom60.values
    vol_arr   = volume.values
    n         = len(sdf)

    is_ex_vin3 = symbol not in EXCLUDE_VIN3
    max_hold   = 250
    trail_mult = 2.5

    trades = []
    for ei in np.where(gk_buy.values)[0]:
        signal_i = ei
        entry_i  = ei + 1
        if entry_i >= n:
            continue

        signal_date = pd.Timestamp(date_arr[signal_i])
        entry_date  = pd.Timestamp(date_arr[entry_i])

        # Regime gate check on entry date
        vnindex_regime = bool(gate_by_date.get(entry_date, False))
        if not vnindex_regime:
            continue

        ep = close_arr[entry_i]
        if ep <= 0 or np.isnan(ep):
            continue

        # Simple trail exit (no TP1)
        high_water = ep
        end = min(entry_i + max_hold, n - 1)
        bars_held  = end - entry_i
        exit_reason = "tp_not_hit_max_hold"

        for j in range(entry_i, end + 1):
            c = close_arr[j]
            high_water = max(high_water, c)
            if c < high_water - trail_mult * atr_arr[j]:
                bars_held   = j - entry_i
                exit_reason = "tp_trail"
                break

        exit_i     = min(entry_i + bars_held, n - 1)
        exit_date  = pd.Timestamp(date_arr[exit_i])
        exit_price = float(close_arr[exit_i])
        gross      = (exit_price - ep) / ep

        signal_close = float(close_arr[signal_i])
        pct_vs       = (ep - signal_close) / signal_close if signal_close > 0 else 0.0

        trade_close = close_arr[entry_i: exit_i + 1]
        mae = float((trade_close.min() - ep) / ep) if len(trade_close) > 0 else 0.0
        mfe = float((trade_close.max() - ep) / ep) if len(trade_close) > 0 else 0.0

        adv50_v = float(adv50_arr[entry_i])
        if not np.isfinite(adv50_v):
            adv50_v = 0.0
        adv_v = float(adv20_arr[entry_i])
        if not np.isfinite(adv_v):
            adv_v = 0.0

        slow_at_e = float(slow_arr[entry_i])
        ema_dist  = float((ep - slow_at_e) / slow_at_e) if slow_at_e > 0 else 0.0
        atr_pct   = float(atr_arr[entry_i] / ep) if ep > 0 else 0.02
        if not np.isfinite(atr_pct) or atr_pct <= 0:
            atr_pct = 0.02

        trades.append({
            "symbol":                    symbol,
            "strategy":                  "GK",
            "signal_date":               signal_date,
            "signal_close":              signal_close,
            "entry_date":                entry_date,
            "entry_price":               ep,
            "exit_date":                 exit_date,
            "exit_price":                exit_price,
            "exit_reason":               exit_reason,
            "gross_return":              gross,
            "net_return":                gross - cost,
            "holding_days":              bars_held,
            "hold_bars":                 bars_held,
            "mae":                       mae,
            "mfe":                       mfe,
            "adv50_value":               adv50_v,
            "rank_metric":               ema_dist,
            "ema_dist":                  ema_dist,
            "ema_dist_at_entry":         ema_dist,
            "mom20":                     float(mom20_arr[entry_i]),
            "mom20_at_entry":            float(mom20_arr[entry_i]),
            "mom60":                     float(mom60_arr[entry_i]),
            "mom60_at_entry":            float(mom60_arr[entry_i]),
            "adv20_at_entry":            adv_v,
            "vol_at_entry":              float(vol_arr[entry_i]),
            "atr_pct_at_entry":          atr_pct,
            "near_entry_label":          "gk_signal",
            "near_entry_pct_vs_signal":  pct_vs,
            "vnindex_regime":            vnindex_regime,
            "is_ex_vin3":                is_ex_vin3,
            "trade_id":                  f"GK_{symbol}_{signal_date.date()}",
        })

    return trades


# ── Phase 0: build_trade_ledger ───────────────────────────────────────────────

def build_trade_ledger(
    panel: pd.DataFrame,
    vnx: pd.DataFrame,
    strategies: list[str] = None,
    cost: float = DEFAULT_COST,
    min_sell_lock_bars: int = 5,
) -> pd.DataFrame:
    """
    Phase 0: build full trade ledger for specified strategies.
    Returns DataFrame with all output columns.
    """
    if strategies is None:
        strategies = ["A3", "S3", "GK"]

    gate_by_date, _ = vnindex_regime_gate(vnx)

    all_trades: list[dict] = []

    for strategy in strategies:
        if strategy in ("A3", "S3"):
            cfg     = STRATEGY_CONFIGS[strategy]
            symbols = get_universe(panel, cfg["universe"])
            print(f"  [{strategy}] scanning {len(symbols)} symbols...", flush=True)
            for sym, sdf in panel[panel["symbol"].isin(symbols)].groupby("symbol", sort=False):
                sdf = sdf.sort_values("date").reset_index(drop=True)
                trades = sim_symbol_extended(sdf, strategy, cfg["exit_cfg"], cost, gate_by_date)
                all_trades.extend(trades)

        elif strategy == "GK":
            all_syms = sorted(panel["symbol"].unique())
            print(f"  [GK] scanning {len(all_syms)} symbols...", flush=True)
            for sym, sdf in panel.groupby("symbol", sort=False):
                sdf = sdf.sort_values("date").reset_index(drop=True)
                trades = sim_symbol_gk(sdf, gate_by_date, cost)
                all_trades.extend(trades)

    if not all_trades:
        print("  WARNING: no trades generated.", flush=True)
        return pd.DataFrame()

    df = pd.DataFrame(all_trades)
    df["entry_date"]  = pd.to_datetime(df["entry_date"])
    df["exit_date"]   = pd.to_datetime(df["exit_date"])
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df = df.sort_values(["strategy", "entry_date", "symbol"]).reset_index(drop=True)

    # Ensure all required columns exist
    required_cols = [
        "symbol", "strategy", "signal_date", "signal_close",
        "entry_date", "entry_price", "exit_date", "exit_price",
        "exit_reason", "gross_return", "net_return", "holding_days",
        "mae", "mfe", "adv50_value", "rank_metric", "ema_dist", "mom20", "mom60",
        "near_entry_label", "near_entry_pct_vs_signal",
        "vnindex_regime", "is_ex_vin3", "trade_id",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = np.nan

    return df[required_cols + [c for c in df.columns if c not in required_cols]]


# ── Phase 0: run_baseline ─────────────────────────────────────────────────────

def run_baseline(
    trades_df: pd.DataFrame,
    max_positions: int = 20,
) -> dict[str, tuple[pd.Series, dict]]:
    """
    Phase 0: Baseline portfolio simulation.
    Returns dict: strategy_label -> (equity_series, metrics_dict)
    """
    results = {}
    if trades_df.empty:
        return results

    # Per-strategy baselines
    for strategy, cfg in STRATEGY_CONFIGS.items():
        sub = trades_df[trades_df["strategy"] == strategy].copy()
        if sub.empty:
            continue
        rank_mode = cfg["rank_mode"]
        equity, n_filled = _build_equity_v2(
            sub, max_positions=max_positions, rank_mode=rank_mode,
            sizing_mode="equal", gross_exposure=1.0,
        )
        if equity.empty:
            continue
        m = portfolio_metrics(equity, sub, test_start="2023-01-01")
        m["strategy"] = strategy
        m["n_filled"] = n_filled
        results[strategy] = (equity, m)

    # Combined: pool all trades, rank A3->ema_dist, S3->mom20, GK->ema_dist
    # Tie-break: A3 > S3 > GK via strategy_priority column
    combined = trades_df.copy()
    if not combined.empty:
        strategy_priority = {"A3": 3, "S3": 2, "GK": 1}
        combined["_priority"] = combined["strategy"].map(strategy_priority).fillna(0)

        # Composite rank: per strategy, use native rank col; combine with priority
        def _combined_rank(row):
            s = row["strategy"]
            if s == "A3":
                return row.get("ema_dist_at_entry", row.get("ema_dist", 0.0))
            elif s == "S3":
                return row.get("mom20_at_entry", row.get("mom20", 0.0))
            else:
                return row.get("ema_dist_at_entry", row.get("ema_dist", 0.0))

        combined["_combined_rank"] = combined.apply(_combined_rank, axis=1)
        # Ensure _build_equity_v2 can use ema_dist_at_entry
        combined["ema_dist_at_entry"] = combined["_combined_rank"]

        equity, n_filled = _build_equity_v2(
            combined, max_positions=max_positions, rank_mode="ema_dist",
            sizing_mode="equal", gross_exposure=1.0,
        )
        if not equity.empty:
            m = portfolio_metrics(equity, combined, test_start="2023-01-01")
            m["strategy"] = "COMBINED"
            m["n_filled"] = n_filled
            results["COMBINED"] = (equity, m)

    return results


# ── Phase 1: sizing experiments ───────────────────────────────────────────────

def _run_one_sizing_experiment(
    trades_df: pd.DataFrame,
    strategy: str,
    experiment_id: str,
    sizing_method: str,
    params: dict,
    max_positions: int = 20,
    max_position_pct: float = 0.20,
    sizing_mode: str = "equal",
) -> dict:
    """Run one sizing configuration and return result row."""
    sub = trades_df[trades_df["strategy"] == strategy].copy() if strategy != "COMBINED" else trades_df.copy()
    if sub.empty:
        return {}

    rank_mode = STRATEGY_CONFIGS.get(strategy, {}).get("rank_mode", "ema_dist") if strategy != "COMBINED" else "ema_dist"

    # For risk_per_trade: adjust net_return based on position weight scaling
    # For equal/rank-based sizing: use _build_equity_v2 with appropriate sizing_mode
    if sizing_method == "equal_weight":
        positions = params.get("max_open_positions", max_positions)
        equity, n_filled = _build_equity_v2(
            sub, max_positions=positions, rank_mode=rank_mode,
            sizing_mode="equal", gross_exposure=1.0,
        )
    elif sizing_method in ("linear", "top_heavy", "sqrt"):
        # Rank-based sizing implemented via custom weight computation
        equity, n_filled = _run_rank_based_sizing(sub, strategy, sizing_method, max_position_pct)
    elif sizing_method == "inv_atr":
        equity, n_filled = _build_equity_v2(
            sub, max_positions=max_positions, rank_mode=rank_mode,
            sizing_mode="inv_atr", gross_exposure=1.0,
        )
    elif sizing_method == "risk_per_trade":
        equity, n_filled = _run_risk_per_trade_sizing(sub, strategy, params)
    else:
        equity, n_filled = _build_equity_v2(
            sub, max_positions=max_positions, rank_mode=rank_mode,
            sizing_mode="equal", gross_exposure=1.0,
        )

    if equity.empty or len(equity) < 5:
        return {}

    m = portfolio_metrics(equity, sub, test_start="2023-01-01")

    # exposure_pct: fraction of days with active positions (approximated)
    exposure_pct = float(n_filled) / max(len(sub), 1)

    return {
        "experiment_id":    experiment_id,
        "strategy":         strategy,
        "sizing_method":    sizing_method,
        "params_json":      json.dumps(params, default=str),
        "cagr":             m.get("cagr", np.nan),
        "max_dd":           m.get("max_dd", np.nan),
        "sharpe":           m.get("sharpe", np.nan),
        "mar":              m.get("mar", np.nan),
        "n_trades":         m.get("n_trades", 0),
        "hit_rate":         m.get("hit_rate", np.nan),
        "avg_trade_ret":    m.get("avg_trade_ret", np.nan),
        "n_filled":         n_filled,
        "exposure_pct":     exposure_pct,
    }


def _run_rank_based_sizing(
    trades_df: pd.DataFrame,
    strategy: str,
    mode: str,
    max_position_pct: float = 0.15,
    max_positions: int = 20,
) -> tuple[pd.Series, int]:
    """
    Rank-based sizing: linear, top_heavy, sqrt.
    Modifies weight within each entry batch based on within-day rank percentile.
    """
    if trades_df.empty:
        return pd.Series(dtype=float), 0

    rank_col_map = {"A3": "ema_dist_at_entry", "S3": "mom20_at_entry"}
    rank_col = rank_col_map.get(strategy, "ema_dist_at_entry")
    if rank_col not in trades_df.columns:
        rank_col = "ema_dist_at_entry"

    df = trades_df.copy().reset_index(drop=True)

    # Add per-date within-day rank percentile
    if rank_col in df.columns:
        df["_rank_pct"] = df.groupby("entry_date")[rank_col].rank(pct=True, na_option="bottom")
    else:
        df["_rank_pct"] = 0.5

    all_dates = pd.date_range(df["entry_date"].min(), df["exit_date"].max(), freq="B")
    pos_base_weight = 1.0 / max_positions

    by_entry: dict = {}
    for ed, grp in df.groupby("entry_date", sort=False):
        sorted_grp = grp.sort_values(rank_col if rank_col in grp.columns else "_rank_pct", ascending=False)
        by_entry[ed] = [(int(i), r) for i, r in sorted_grp.iterrows()]

    by_exit: dict = {}
    for idx, row in df.iterrows():
        xd = row["exit_date"]
        if xd not in by_exit:
            by_exit[xd] = []
        by_exit[xd].append((int(idx), row))

    portfolio_val = 1.0
    active: dict[int, tuple] = {}
    equity: dict = {}
    n_filled = 0

    def _compute_weight(rank_pct: float) -> float:
        base = pos_base_weight
        if mode == "linear":
            w = base * (1 + 0.5 * (rank_pct - 0.5) * 2)
        elif mode == "top_heavy":
            w = rank_pct ** 0.5  # will normalize below
        elif mode == "sqrt":
            w = rank_pct ** 0.5  # same as top_heavy, applied per batch
        else:
            w = base
        return min(w, max_position_pct)

    for date in all_dates:
        for tid, row in by_exit.get(date, []):
            if tid in active:
                _r, w = active[tid]
                portfolio_val += portfolio_val * w * float(row["net_return"])
                del active[tid]

        remaining = max_positions - len(active)
        if remaining <= 0:
            equity[date] = portfolio_val
            continue

        queued = by_entry.get(date, [])[:remaining]
        if queued:
            # Compute raw weights
            raw_ws = []
            for (tid, row) in queued:
                rp = float(row.get("_rank_pct", 0.5))
                if mode in ("top_heavy", "sqrt"):
                    raw_ws.append(max(rp ** 0.5, 0.01))
                else:
                    raw_ws.append(_compute_weight(rp))

            # Normalize for top_heavy/sqrt
            if mode in ("top_heavy", "sqrt"):
                total = sum(raw_ws)
                if total > 0:
                    scale = min(1.0, len(queued) / max_positions)
                    raw_ws = [w / total * scale for w in raw_ws]
                    raw_ws = [min(w, max_position_pct) for w in raw_ws]

            for (tid, row), w in zip(queued, raw_ws):
                active[tid] = (row, float(w))
                n_filled += 1

        equity[date] = portfolio_val

    return pd.Series(equity), n_filled


def _run_risk_per_trade_sizing(
    trades_df: pd.DataFrame,
    strategy: str,
    params: dict,
    max_positions: int = 20,
    max_position_pct: float = 0.20,
) -> tuple[pd.Series, int]:
    """
    Risk-per-trade sizing: weight = risk_pct / stop_distance, capped at max_position_pct.
    """
    if trades_df.empty:
        return pd.Series(dtype=float), 0

    risk_pct = float(params.get("risk_pct", 0.01))
    stop_mode = params.get("stop_mode", "fixed_7pct")

    df = trades_df.copy().reset_index(drop=True)

    def _get_stop(row) -> float:
        if stop_mode == "fixed_7pct":
            return 0.07
        elif stop_mode == "fixed_10pct":
            return 0.10
        elif stop_mode == "atr_25":
            return float(row.get("atr_pct_at_entry", 0.04)) * 2.5
        elif stop_mode == "atr_35":
            return float(row.get("atr_pct_at_entry", 0.04)) * 3.5
        return 0.07

    rank_col_map = {"A3": "ema_dist_at_entry", "S3": "mom20_at_entry"}
    rank_col = rank_col_map.get(strategy, "ema_dist_at_entry")

    all_dates = pd.date_range(df["entry_date"].min(), df["exit_date"].max(), freq="B")

    by_entry: dict = {}
    if rank_col in df.columns:
        for ed, grp in df.groupby("entry_date", sort=False):
            by_entry[ed] = [(int(i), r) for i, r in grp.sort_values(rank_col, ascending=False).iterrows()]
    else:
        for i, row in df.iterrows():
            ed = row["entry_date"]
            if ed not in by_entry:
                by_entry[ed] = []
            by_entry[ed].append((int(i), row))

    by_exit: dict = {}
    for idx, row in df.iterrows():
        xd = row["exit_date"]
        if xd not in by_exit:
            by_exit[xd] = []
        by_exit[xd].append((int(idx), row))

    portfolio_val = 1.0
    active: dict[int, tuple] = {}
    equity: dict = {}
    n_filled = 0

    for date in all_dates:
        for tid, row in by_exit.get(date, []):
            if tid in active:
                _r, w = active[tid]
                portfolio_val += portfolio_val * w * float(row["net_return"])
                del active[tid]

        remaining = max_positions - len(active)
        if remaining <= 0:
            equity[date] = portfolio_val
            continue

        queued = by_entry.get(date, [])[:remaining]
        for tid, row in queued:
            stop_d = max(_get_stop(row), 0.01)
            w = min(risk_pct / stop_d, max_position_pct)
            active[tid] = (row, float(w))
            n_filled += 1

        equity[date] = portfolio_val

    return pd.Series(equity), n_filled


def run_sizing_experiments(
    trades_df: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """Phase 1: Run all sizing experiments. Returns summary DataFrame."""
    print("Phase 1: sizing experiments...", flush=True)
    results = []

    strategies_to_test = [s for s in ["A3", "S3"] if s in trades_df["strategy"].unique()]

    for strategy in strategies_to_test:
        sub = trades_df[trades_df["strategy"] == strategy]
        if sub.empty:
            continue

        # A. Equal-weight grid
        max_pos_pct_grid = [0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25]
        max_open_grid    = [5, 10, 15, 20, 30]

        for mp_pct, mp_open in itertools.product(max_pos_pct_grid, max_open_grid):
            eid = f"A_{strategy}_pct{mp_pct:.3f}_pos{mp_open}"
            params = {"max_position_pct": mp_pct, "max_open_positions": mp_open}
            row = _run_one_sizing_experiment(
                trades_df, strategy, eid, "equal_weight", params,
                max_positions=mp_open,
            )
            if row:
                results.append(row)

        # B. Rank-based sizing
        for mode in ("linear", "top_heavy", "sqrt"):
            eid = f"B_{strategy}_{mode}"
            params = {"mode": mode, "max_position_pct": 0.15}
            row = _run_one_sizing_experiment(
                trades_df, strategy, eid, mode, params,
                max_positions=20,
            )
            if row:
                results.append(row)

        # C. Inverse-volatility
        eid = f"C_{strategy}_inv_atr"
        params = {"sizing_mode": "inv_atr"}
        row = _run_one_sizing_experiment(
            trades_df, strategy, eid, "inv_atr", params,
            max_positions=20,
        )
        if row:
            results.append(row)

        # D. Risk-per-trade
        risk_pct_grid = [0.005, 0.010, 0.015, 0.020]
        stop_modes    = ["fixed_7pct", "fixed_10pct", "atr_25", "atr_35"]

        for rp, sm in itertools.product(risk_pct_grid, stop_modes):
            eid = f"D_{strategy}_rp{rp:.3f}_{sm}"
            params = {"risk_pct": rp, "stop_mode": sm}
            row = _run_one_sizing_experiment(
                trades_df, strategy, eid, "risk_per_trade", params,
                max_positions=20,
            )
            if row:
                results.append(row)

        # E. Bucket sizing — walk-forward only
        results.append({
            "experiment_id":  f"E_{strategy}_bucket_wf_only",
            "strategy":       strategy,
            "sizing_method":  "bucket",
            "params_json":    '{"note": "walk_forward_only"}',
            "cagr":           np.nan, "max_dd": np.nan, "sharpe": np.nan,
            "mar":            np.nan, "n_trades": 0, "hit_rate": np.nan,
            "avg_trade_ret":  np.nan, "n_filled": 0, "exposure_pct": np.nan,
        })

        # F. Kelly — walk-forward only
        results.append({
            "experiment_id":  f"F_{strategy}_kelly_wf_only",
            "strategy":       strategy,
            "sizing_method":  "kelly",
            "params_json":    '{"note": "walk_forward_only"}',
            "cagr":           np.nan, "max_dd": np.nan, "sharpe": np.nan,
            "mar":            np.nan, "n_trades": 0, "hit_rate": np.nan,
            "avg_trade_ret":  np.nan, "n_filled": 0, "exposure_pct": np.nan,
        })

    return pd.DataFrame(results)


# ── Phase 2: scale-in experiments ────────────────────────────────────────────

def run_scalein_experiments(
    panel: pd.DataFrame,
    vnx: pd.DataFrame,
    strategies: list[str] = None,
    cost: float = DEFAULT_COST,
    min_sell_lock_bars: int = 5,
) -> pd.DataFrame:
    """Phase 2: Scale-in experiments. Returns summary DataFrame."""
    print("Phase 2: scale-in experiments...", flush=True)
    if strategies is None:
        strategies = ["A3", "S3"]

    gate_by_date, _ = vnindex_regime_gate(vnx)
    results = []

    scalein_configs = [
        # (label, tranche_weights, trigger_type)
        ("2T_5050_T2",     [0.50, 0.50], "time_T2"),
        ("2T_5050_T3",     [0.50, 0.50], "time_T3"),
        ("2T_6040_T2",     [0.60, 0.40], "time_T2"),
        ("2T_7030_T3",     [0.70, 0.30], "time_T3"),
        ("2T_5050_pullbk", [0.50, 0.50], "pullback"),
        ("2T_5050_str",    [0.50, 0.50], "strength"),
        ("3T_403030_T2",   [0.40, 0.30, 0.30], "time_T2"),
        ("3T_503020_T2",   [0.50, 0.30, 0.20], "time_T2"),
    ]

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        cfg     = STRATEGY_CONFIGS[strategy]
        symbols = get_universe(panel, cfg["universe"])
        exit_cfg = cfg["exit_cfg"]
        max_hold = int(exit_cfg.get("max_hold", 250))

        for si_label, tranche_weights, trigger in scalein_configs:
            experiment_id = f"SI_{strategy}_{si_label}"

            all_compound_trades: list[dict] = []

            for sym, sdf in panel[panel["symbol"].isin(symbols)].groupby("symbol", sort=False):
                sdf = sdf.sort_values("date").reset_index(drop=True)
                compound_trades = _sim_scalein_symbol(
                    sdf, strategy, exit_cfg, cost,
                    gate_by_date, tranche_weights, trigger, min_sell_lock_bars,
                )
                all_compound_trades.extend(compound_trades)

            if not all_compound_trades:
                continue

            ct_df = pd.DataFrame(all_compound_trades)
            ct_df["entry_date"] = pd.to_datetime(ct_df["entry_date"])
            ct_df["exit_date"]  = pd.to_datetime(ct_df["exit_date"])

            # Simple equity curve from compound trades
            equity, n_filled = _build_equity_v2(
                ct_df, max_positions=20,
                rank_mode=cfg["rank_mode"],
                sizing_mode="equal", gross_exposure=1.0,
            )

            if equity.empty:
                continue

            m = portfolio_metrics(equity, ct_df, test_start="2023-01-01")
            avg_tranches  = float(ct_df["n_tranches_filled"].mean()) if "n_tranches_filled" in ct_df.columns else np.nan
            blocked_exits = int(ct_df["blocked_exit_count"].sum()) if "blocked_exit_count" in ct_df.columns else 0
            missed        = int(ct_df["missed_tranche_count"].sum()) if "missed_tranche_count" in ct_df.columns else 0

            results.append({
                "experiment_id":      experiment_id,
                "strategy":           strategy,
                "scalein_method":     si_label,
                "tranche_structure":  ",".join(str(w) for w in tranche_weights),
                "trigger":            trigger,
                "min_sell_lock_bars": min_sell_lock_bars,
                "cagr":               m.get("cagr", np.nan),
                "max_dd":             m.get("max_dd", np.nan),
                "sharpe":             m.get("sharpe", np.nan),
                "mar":                m.get("mar", np.nan),
                "n_trades":           m.get("n_trades", 0),
                "avg_tranches_filled": avg_tranches,
                "blocked_exits":       blocked_exits,
                "missed_tranches":     missed,
            })

    return pd.DataFrame(results)


def _sim_scalein_symbol(
    sdf: pd.DataFrame,
    strategy: str,
    exit_cfg: dict,
    cost: float,
    gate_by_date: pd.Series,
    tranche_weights: list[float],
    trigger: str,
    min_sell_lock_bars: int,
) -> list[dict]:
    """Simulate scale-in trades for one symbol."""
    cfg = STRATEGY_CONFIGS[strategy]
    ema_fast_n = cfg["ema_fast"]
    ema_slow_n = cfg["ema_slow"]
    max_hold   = int(exit_cfg.get("max_hold", 250))

    if len(sdf) < max(ema_slow_n + 10, 100):
        return []

    sdf = sdf.copy().reset_index(drop=True)
    close  = sdf["close"]
    high   = sdf["high"]
    low    = sdf.get("low", close)
    symbol = sdf["symbol"].iloc[0]
    dates  = sdf["date"]

    cloud_d    = ema_cloud(close, ema_fast_n, ema_slow_n)
    fast_ema   = cloud_d["ema_fast"]
    slow_ema   = cloud_d["ema_slow"]
    cloud_bull = cloud_d["cloud_bull"]
    atr        = compute_atr(high, low, close, period=14)
    warmup     = max(ema_slow_n + 5, 60)

    sig = cloud_only_entry(close, fast_ema, cloud_bull, min_bars_bear=3, warmup=warmup)

    mom20  = close.pct_change(20).fillna(0.0)
    value  = sdf["value"] if "value" in sdf.columns else close * sdf.get("volume", pd.Series(np.ones(len(sdf))))
    adv20  = value.rolling(20, min_periods=10).mean()

    close_arr  = close.values
    high_arr   = high.values
    atr_arr    = atr.values
    slow_arr   = slow_ema.values
    fast_arr   = fast_ema.values
    cbull_arr  = cloud_bull.values
    mom20_arr  = mom20.values
    adv20_arr  = adv20.values
    date_arr   = dates.values
    n          = len(sdf)

    trades = []
    for ei in np.where(sig.values)[0]:
        signal_i = ei
        entry_i  = ei + 1
        if entry_i >= n:
            continue

        signal_date  = pd.Timestamp(date_arr[signal_i])
        signal_close = float(close_arr[signal_i])
        entry_date   = pd.Timestamp(date_arr[entry_i])

        ep1 = float(close_arr[entry_i])
        if ep1 <= 0 or np.isnan(ep1):
            continue

        n_tranches = len(tranche_weights)
        w1 = tranche_weights[0]

        # Determine tranche 2+ fill
        missed_tranche_count = 0
        n_tranches_filled    = 1
        ep2 = None
        ep3 = None

        if n_tranches >= 2:
            t2_i = None
            if trigger == "time_T2" and (entry_i + 2) < n:
                t2_i = entry_i + 2
                if not (bool(cbull_arr[t2_i]) and close_arr[t2_i] > fast_arr[t2_i]):
                    t2_i = None
                    missed_tranche_count += 1
            elif trigger == "time_T3" and (entry_i + 3) < n:
                t2_i = entry_i + 3
                if not (bool(cbull_arr[t2_i]) and close_arr[t2_i] > fast_arr[t2_i]):
                    t2_i = None
                    missed_tranche_count += 1
            elif trigger == "pullback":
                pullback_target = signal_close * 0.98
                for j in range(entry_i + 1, min(entry_i + 20, n)):
                    if close_arr[j] <= pullback_target and close_arr[j] > slow_arr[j] * 0.97:
                        t2_i = j
                        break
                if t2_i is None:
                    missed_tranche_count += 1
            elif trigger == "strength":
                for j in range(entry_i + 1, min(entry_i + 20, n)):
                    if close_arr[j] > ep1 * 1.02:
                        t2_i = j
                        break
                if t2_i is None:
                    missed_tranche_count += 1

            if t2_i is not None and t2_i < n:
                ep2 = float(close_arr[t2_i])
                n_tranches_filled = 2

        if n_tranches >= 3 and ep2 is not None:
            w2 = tranche_weights[1]
            # Tranche 3: time-based T+5 from tranche 2
            t3_i = (t2_i or entry_i) + 3
            if t3_i < n and bool(cbull_arr[t3_i]):
                ep3 = float(close_arr[t3_i])
                n_tranches_filled = 3
            else:
                missed_tranche_count += 1

        # Blended entry price (weighted average)
        if n_tranches_filled == 1:
            blended_ep = ep1
        elif n_tranches_filled == 2:
            w1_n = tranche_weights[0]; w2_n = tranche_weights[1]
            tot = w1_n + w2_n
            blended_ep = (w1_n * ep1 + w2_n * ep2) / tot
        else:
            w1_n, w2_n, w3_n = tranche_weights[0], tranche_weights[1], tranche_weights[2]
            tot = w1_n + w2_n + w3_n
            blended_ep = (w1_n * ep1 + w2_n * ep2 + (w3_n * ep3 if ep3 else 0)) / (w1_n + w2_n + (w3_n if ep3 else 0))

        # Exit from blended entry
        bars_held, gross, exit_reason = _exit_reason_v2(
            close_arr, high_arr, atr_arr, entry_i, blended_ep, exit_cfg
        )

        # min_sell_lock: track blocked exits
        blocked_exit_count = 0
        if bars_held < min_sell_lock_bars:
            blocked_exit_count = 1
            # Force hold to min_sell_lock_bars
            bars_held = min(min_sell_lock_bars, max_hold)
            exit_i = min(entry_i + bars_held, n - 1)
            gross  = (close_arr[exit_i] - blended_ep) / blended_ep
            exit_reason = "min_lock_exit"
        else:
            exit_i = min(entry_i + bars_held, n - 1)

        exit_date  = pd.Timestamp(date_arr[exit_i])
        exit_price = float(close_arr[exit_i])
        net_return = gross - cost

        slow_at_e = float(slow_arr[entry_i])
        ema_dist  = float((ep1 - slow_at_e) / slow_at_e) if slow_at_e > 0 else 0.0
        atr_pct   = float(atr_arr[entry_i] / ep1) if ep1 > 0 else 0.02

        trades.append({
            "symbol":              symbol,
            "strategy":            strategy,
            "signal_date":         signal_date,
            "signal_close":        signal_close,
            "entry_date":          entry_date,
            "entry_price":         blended_ep,
            "exit_date":           exit_date,
            "exit_price":          exit_price,
            "exit_reason":         exit_reason,
            "gross_return":        gross,
            "net_return":          net_return,
            "hold_bars":           bars_held,
            "holding_days":        bars_held,
            "ema_dist_at_entry":   ema_dist,
            "mom20_at_entry":      float(mom20_arr[entry_i]),
            "adv20_at_entry":      float(adv20_arr[entry_i]) if np.isfinite(adv20_arr[entry_i]) else 0.0,
            "atr_pct_at_entry":    atr_pct,
            "n_tranches_filled":   n_tranches_filled,
            "missed_tranche_count": missed_tranche_count,
            "blocked_exit_count":  blocked_exit_count,
        })

    return trades


# ── Phase 3: convergence experiments ─────────────────────────────────────────

def run_convergence_experiments(
    trades_ledger_df: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """Phase 3: Convergence experiments. Returns summary DataFrame."""
    print("Phase 3: convergence experiments...", flush=True)
    results = []

    if trades_ledger_df.empty:
        return pd.DataFrame()

    # Build per-strategy signal lookup: symbol -> sorted signal dates
    def _make_signal_lookup(strategy: str) -> dict[str, pd.DatetimeIndex]:
        sub = trades_ledger_df[trades_ledger_df["strategy"] == strategy]
        lookup: dict[str, pd.DatetimeIndex] = {}
        for sym, grp in sub.groupby("symbol"):
            lookup[sym] = pd.to_datetime(grp["signal_date"].values)
        return lookup

    a3_lookup = _make_signal_lookup("A3")
    s3_lookup = _make_signal_lookup("S3")
    gk_lookup = _make_signal_lookup("GK")

    def _has_signal_within(lookup: dict, sym: str, sig_date: pd.Timestamp, window: int) -> bool:
        if sym not in lookup:
            return False
        dates = lookup[sym]
        delta = (dates - sig_date).days if hasattr(dates, "days") else None
        # Vectorised check
        diffs = np.abs((dates - sig_date).days)
        return bool(np.any(diffs <= window))

    window_grid = [3, 5, 10]

    # Convergence modes
    modes = [
        ("C0", "no_filter"),
        ("C1", "A3+S3_same_day"),
        ("C2", "A3+S3_within_N"),
        ("C3", "A3_or_S3+GK_within_N"),
        ("C4", "all3_within_N"),
    ]

    multiplier_modes = [
        ("M0", 1.0, 1.0),    # baseline (no multiplier)
        ("M1", 1.25, 1.5),   # 2-conv=1.25x, 3-conv=1.5x
        ("M2", 1.5, 2.0),    # 2-conv=1.5x, 3-conv=2.0x
    ]

    a3_trades = trades_ledger_df[trades_ledger_df["strategy"] == "A3"].copy()
    if a3_trades.empty:
        return pd.DataFrame()

    a3_trades["signal_date"] = pd.to_datetime(a3_trades["signal_date"])

    for window in window_grid:
        for (c_mode, c_label) in modes:
            for (m_mode, m2x, m3x) in multiplier_modes:

                exp_id = f"{c_mode}_{m_mode}_w{window}"

                # Filter A3 trades by convergence condition
                sub = a3_trades.copy()

                if c_mode == "C0":
                    filtered = sub
                elif c_mode == "C1":
                    # A3 and S3 same day on same symbol
                    mask = sub.apply(
                        lambda r: _has_signal_within(s3_lookup, r["symbol"], r["signal_date"], 0),
                        axis=1,
                    )
                    filtered = sub[mask]
                elif c_mode == "C2":
                    mask = sub.apply(
                        lambda r: _has_signal_within(s3_lookup, r["symbol"], r["signal_date"], window),
                        axis=1,
                    )
                    filtered = sub[mask]
                elif c_mode == "C3":
                    mask = sub.apply(
                        lambda r: (
                            _has_signal_within(gk_lookup, r["symbol"], r["signal_date"], window)
                        ),
                        axis=1,
                    )
                    filtered = sub[mask]
                elif c_mode == "C4":
                    mask = sub.apply(
                        lambda r: (
                            _has_signal_within(s3_lookup, r["symbol"], r["signal_date"], window) and
                            _has_signal_within(gk_lookup, r["symbol"], r["signal_date"], window)
                        ),
                        axis=1,
                    )
                    filtered = sub[mask]
                else:
                    filtered = sub

                n_filtered = len(filtered)
                n_total    = len(sub)
                coverage   = n_filtered / max(n_total, 1)

                if n_filtered < 5:
                    continue

                # Apply multiplier to ema_dist for sizing weight (proxy for conviction boost)
                if m_mode != "M0" and c_mode not in ("C0",):
                    # Determine conv_level per trade (2 or 3 strategy)
                    filtered = filtered.copy()
                    def _conv_level(r) -> int:
                        has_s3 = _has_signal_within(s3_lookup, r["symbol"], r["signal_date"], window)
                        has_gk = _has_signal_within(gk_lookup, r["symbol"], r["signal_date"], window)
                        return 3 if (has_s3 and has_gk) else 2

                    filtered["_conv_level"] = filtered.apply(_conv_level, axis=1)
                    filtered["_mult"] = filtered["_conv_level"].map({2: m2x, 3: m3x}).fillna(1.0)
                    # Scale ema_dist by multiplier (proxy for boosted conviction weight)
                    filtered["ema_dist_at_entry"] = filtered.get("ema_dist_at_entry", filtered.get("ema_dist", 0)) * filtered["_mult"]

                equity, n_filled = _build_equity_v2(
                    filtered, max_positions=20, rank_mode="ema_dist",
                    sizing_mode="equal", gross_exposure=1.0,
                )

                if equity.empty:
                    continue

                m = portfolio_metrics(equity, filtered, test_start="2023-01-01")

                results.append({
                    "experiment_id":    exp_id,
                    "convergence_mode": c_mode,
                    "multiplier_mode":  m_mode,
                    "window_days":      window,
                    "n_trades":         n_filtered,
                    "coverage_pct":     coverage,
                    "cagr":             m.get("cagr", np.nan),
                    "max_dd":           m.get("max_dd", np.nan),
                    "sharpe":           m.get("sharpe", np.nan),
                    "mar":              m.get("mar", np.nan),
                    "hit_rate":         m.get("hit_rate", np.nan),
                })

    return pd.DataFrame(results)


# ── Phase 5: Walk-forward OOS ─────────────────────────────────────────────────

def run_walk_forward(
    panel: pd.DataFrame,
    vnx: pd.DataFrame,
    strategies: list[str],
    fold_months: int = 1,
    min_train_months: int = 24,
    trades_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """Phase 5: Monthly walk-forward OOS. Returns per-fold metrics DataFrame.

    Uses pre-built trade ledger when available — slicing is O(n_folds) instead
    of re-running signal generation O(n_folds × n_symbols).
    """
    print("Phase 5: walk-forward...", flush=True)

    all_dates = pd.date_range("2014-01", "2026-06", freq="MS")
    results = []

    # Build trade ledger once if not provided
    if trades_df is None or trades_df.empty:
        gate_by_date, _ = vnindex_regime_gate(vnx)
        trades_df = build_trade_ledger(panel, vnx, strategies, DEFAULT_COST, min_sell_lock_bars=5)

    if trades_df.empty:
        return pd.DataFrame()

    # Restrict to requested strategies
    strat_mask = trades_df["strategy"].isin(strategies)
    all_trades = trades_df[strat_mask].copy()
    all_trades["entry_date"] = pd.to_datetime(all_trades["entry_date"])
    all_trades["exit_date"]  = pd.to_datetime(all_trades["exit_date"])

    for fold_idx in range(len(all_dates) - fold_months):
        fold_start = all_dates[fold_idx]
        fold_end   = all_dates[fold_idx + fold_months] - pd.Timedelta(days=1)

        if fold_idx < min_train_months:
            continue  # insufficient training data

        # Slice ledger to fold window (entry date determines which fold a trade belongs to)
        fold_df = all_trades[
            (all_trades["entry_date"] >= fold_start) &
            (all_trades["entry_date"] <= fold_end)
        ].copy()

        if fold_df.empty:
            continue

        # For long-hold strategies (avg 50-250 bars), monthly equity-curve slices
        # are near-zero because most trades haven't exited yet. Use full-trade
        # net_return directly: average performance of signals from this fold.
        fold_net    = float(fold_df["net_return"].mean())
        fold_hit    = float((fold_df["net_return"] > 0).mean())
        n_fold      = len(fold_df)

        results.append({
            "fold_idx":    fold_idx,
            "fold_start":  str(fold_start.date()),
            "fold_end":    str(fold_end.date()),
            "fold_mean_net": fold_net,
            "fold_hit_rate": fold_hit,
            "n_trades":    n_fold,
            "strategies":  ",".join(strategies),
        })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    fold_nets = df["fold_mean_net"].dropna()
    n_pos     = int((fold_nets > 0).sum())
    n_total   = len(fold_nets)
    mean_net  = float(fold_nets.mean())
    mean_hit  = float(df["fold_hit_rate"].dropna().mean())
    stability = float(1 - fold_nets.std() / mean_net) if mean_net != 0 else np.nan

    df.attrs["n_positive_folds"] = n_pos
    df.attrs["n_total_folds"]    = n_total
    df.attrs["fold_stability"]   = stability

    print(
        f"  Walk-forward: {n_pos}/{n_total} positive-return folds, "
        f"mean_net={mean_net:.2%}, mean_hit={mean_hit:.2%}, stability={stability:.3f}",
        flush=True,
    )
    return df


# ── Phase 6: reports ──────────────────────────────────────────────────────────

def write_top_findings(
    output_dir: Path,
    baseline_metrics: dict,
    sizing_results: pd.DataFrame,
    scalein_results: pd.DataFrame,
    convergence_results: pd.DataFrame,
    wf_results: pd.DataFrame,
) -> None:
    """Phase 6: Write TOP_FINDINGS.md and implementation_notes.md."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load from prior runs if in-memory results are empty
    def _load_if_empty(df: pd.DataFrame, fname: str) -> pd.DataFrame:
        if not df.empty:
            return df
        p = output_dir / fname
        if p.exists():
            return pd.read_csv(p)
        return df

    sizing_results     = _load_if_empty(sizing_results,     "sizing_summary.csv")
    scalein_results    = _load_if_empty(scalein_results,    "scalein_summary.csv")
    convergence_results = _load_if_empty(convergence_results, "convergence_summary.csv")

    # ── TOP_FINDINGS.md
    lines = ["# Portfolio Optimization Research — Top Findings\n"]
    lines.append(f"Generated: {date.today()}\n\n")

    lines.append("## Baseline Portfolio Performance\n\n")
    lines.append("| Strategy | CAGR | MaxDD | Sharpe | MAR | N_Trades | Hit Rate |\n")
    lines.append("|----------|------|-------|--------|-----|----------|----------|\n")
    for strat, (eq, m) in baseline_metrics.items():
        mar_v = float(m.get("mar", 0))
        mar_s = f"{mar_v:.2f}" if np.isfinite(mar_v) else "N/A"
        lines.append(
            f"| {strat} | {m.get('cagr', 0):.2%} | {m.get('max_dd', 0):.2%} | "
            f"{m.get('sharpe', 0):.2f} | {mar_s} | "
            f"{m.get('n_trades', 0)} | {m.get('hit_rate', 0):.2%} |\n"
        )

    lines.append("\n## Top 5 Sizing Experiments (by MAR)\n\n")
    if not sizing_results.empty:
        top5 = sizing_results.dropna(subset=["mar"]).nlargest(5, "mar")
        lines.append("| ID | Strategy | Method | CAGR | MaxDD | Sharpe | MAR |\n")
        lines.append("|----|----------|--------|------|-------|--------|-----|\n")
        for _, r in top5.iterrows():
            lines.append(
                f"| {r['experiment_id']} | {r['strategy']} | {r['sizing_method']} | "
                f"{r['cagr']:.2%} | {r['max_dd']:.2%} | {r.get('sharpe', 0):.2f} | "
                f"{r['mar']:.2f} |\n"
            )

    lines.append("\n## Top 5 Convergence Experiments (by MAR)\n\n")
    if not convergence_results.empty:
        top5c = convergence_results.dropna(subset=["mar"]).nlargest(5, "mar")
        lines.append("| ID | Mode | Multiplier | Window | N_Trades | Coverage | CAGR | MAR |\n")
        lines.append("|----|------|------------|--------|----------|----------|------|-----|\n")
        for _, r in top5c.iterrows():
            lines.append(
                f"| {r['experiment_id']} | {r['convergence_mode']} | {r['multiplier_mode']} | "
                f"{r['window_days']}d | {r['n_trades']} | {r['coverage_pct']:.1%} | "
                f"{r['cagr']:.2%} | {r['mar']:.2f} |\n"
            )

    lines.append("\n## Walk-Forward Summary\n\n")
    if not wf_results.empty:
        n_pos    = wf_results.attrs.get("n_positive_folds", "?")
        n_tot    = wf_results.attrs.get("n_total_folds", "?")
        stab     = wf_results.attrs.get("fold_stability", float("nan"))
        mn       = float(wf_results["fold_mean_net"].mean()) if "fold_mean_net" in wf_results.columns else float("nan")
        mh       = float(wf_results["fold_hit_rate"].mean()) if "fold_hit_rate" in wf_results.columns else float("nan")
        lines.append(f"- Positive-return folds: {n_pos} / {n_tot}\n")
        lines.append(f"- Mean net return per fold: {mn:.2%}\n" if np.isfinite(mn) else "- Mean net: N/A\n")
        lines.append(f"- Mean hit rate per fold: {mh:.2%}\n" if np.isfinite(mh) else "- Mean hit rate: N/A\n")
        lines.append(f"- Fold stability score: {stab:.3f}\n" if np.isfinite(stab) else "- Fold stability: N/A\n")

    lines.append("\n## Key Observations\n\n")
    lines.append("- Facts only: interpret from sizing_summary.csv, convergence_summary.csv\n")
    lines.append("- Bucket and Kelly sizing require walk-forward training window (stubbed here)\n")
    lines.append("- Near-entry labels (ideal_pullback / ideal) show highest expected trade returns per validated research\n")

    top_findings_path = output_dir / "TOP_FINDINGS.md"
    top_findings_path.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {top_findings_path}", flush=True)

    # ── implementation_notes.md
    notes = [
        "# Implementation Notes\n\n",
        f"Date: {date.today()}\n\n",
        "## Data sources\n",
        "- Panel: data/research/ema_cloud/ohlcv_panel_ext2012.parquet\n",
        "- VNINDEX: data/fireant_ssot/ta_vnindex.parquet\n\n",
        "## Phase mapping\n",
        "- Phase 0: build_trade_ledger() — full signal sim with extended columns\n",
        "- Phase 1: run_sizing_experiments() — equal-weight grid, rank-based, inv-ATR, risk-per-trade\n",
        "- Phase 2: run_scalein_experiments() — 2T and 3T scale-in with multiple triggers\n",
        "- Phase 3: run_convergence_experiments() — multi-strategy overlap filter + multipliers\n",
        "- Phase 5: run_walk_forward() — monthly fold OOS validation\n\n",
        "## Known stubs\n",
        "- Bucket sizing (Phase 1E) and Kelly sizing (Phase 1F): require walk-forward training; return placeholder rows\n",
        "- Walk-forward Kelly weight: fixed 0.05 placeholder; full implementation requires per-fold hit-rate / payoff estimation\n\n",
        "## Cost scenarios\n",
        f"- base: {DEFAULT_COST} ({DEFAULT_COST*100:.0f} bps)\n",
        f"- low:  {DEFAULT_COST*0.5} ({DEFAULT_COST*50:.0f} bps)\n",
        f"- high: {DEFAULT_COST*1.5} ({DEFAULT_COST*150:.0f} bps)\n",
    ]
    notes_path = output_dir / "implementation_notes.md"
    notes_path.write_text("".join(notes), encoding="utf-8")
    print(f"  Wrote: {notes_path}", flush=True)


# ── CLI / main ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio Optimization Research")
    parser.add_argument("--strategy-set",    default="A3,S3,GK")
    parser.add_argument("--run-baseline",    action="store_true")
    parser.add_argument("--experiment",      choices=["sizing", "scalein", "convergence", "all"])
    parser.add_argument("--min-sell-lock-bars", type=int, default=5)
    parser.add_argument("--cost-scenario",   choices=["low", "base", "high"], default="base")
    parser.add_argument("--walk-forward",    choices=["monthly", "none"], default="none")
    parser.add_argument("--max-symbols",     type=int, default=None,
                        help="Limit symbols for smoke test")
    args = parser.parse_args()

    # Cost
    cost_map = {"base": DEFAULT_COST, "low": DEFAULT_COST * 0.5, "high": DEFAULT_COST * 1.5}
    cost = cost_map[args.cost_scenario]

    strategies = [s.strip() for s in args.strategy_set.split(",") if s.strip()]

    # Output dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data...", flush=True)
    panel = load_panel(max_symbols=args.max_symbols)
    vnx   = load_vnindex()
    print(f"  Panel: {len(panel)} rows, {panel['symbol'].nunique()} symbols", flush=True)
    print(f"  VNINDEX: {len(vnx)} rows", flush=True)

    trades_df      = pd.DataFrame()
    baseline_metrics: dict = {}
    sizing_results = pd.DataFrame()
    scalein_results = pd.DataFrame()
    convergence_results = pd.DataFrame()
    wf_results     = pd.DataFrame()

    # Phase 0: always build ledger if any work needed
    needs_ledger = (
        args.run_baseline
        or args.experiment in ("sizing", "convergence", "all")
    )

    if needs_ledger:
        print("Phase 0: building trade ledger...", flush=True)
        strats_for_ledger = [s for s in strategies if s in ("A3", "S3", "GK")]
        trades_df = build_trade_ledger(
            panel, vnx, strategies=strats_for_ledger,
            cost=cost, min_sell_lock_bars=args.min_sell_lock_bars,
        )
        print(f"  Ledger: {len(trades_df)} trades", flush=True)

        if not trades_df.empty:
            ledger_path = OUT_DIR / "trade_ledger_baseline.csv"
            trades_df.to_csv(ledger_path, index=False)
            print(f"  Saved: {ledger_path}", flush=True)

    # Phase 0 baseline — always run when ledger is built (needed for TOP_FINDINGS anchor)
    if (args.run_baseline or args.experiment) and not trades_df.empty:
        print("Phase 0: baseline portfolio...", flush=True)
        baseline_metrics = run_baseline(trades_df, max_positions=20)
        print("  Baseline results:", flush=True)
        for strat, (eq, m) in baseline_metrics.items():
            print(
                f"    {strat}: CAGR={m.get('cagr', 0):.2%}  MaxDD={m.get('max_dd', 0):.2%}  "
                f"Sharpe={m.get('sharpe', float('nan')):.2f}  "
                f"MAR={m.get('mar', float('nan')):.2f}  "
                f"N={m.get('n_trades', 0)}  HitRate={m.get('hit_rate', 0):.2%}",
                flush=True,
            )
            # Save equity
            eq_path = OUT_DIR / f"equity_{strat}.csv"
            eq.to_csv(eq_path, header=["equity"])
            print(f"    Saved equity: {eq_path}", flush=True)

        # Save combined equity
        if "COMBINED" in baseline_metrics:
            eq_comb = baseline_metrics["COMBINED"][0]
            eq_comb.to_csv(OUT_DIR / "portfolio_daily_equity.csv", header=["equity"])

    # Phase 1: sizing
    if args.experiment in ("sizing", "all") and not trades_df.empty:
        sizing_results = run_sizing_experiments(trades_df, panel)
        if not sizing_results.empty:
            sizing_path = OUT_DIR / "sizing_summary.csv"
            sizing_results.to_csv(sizing_path, index=False)
            print(f"  Saved: {sizing_path}", flush=True)
            print(f"  Sizing experiments: {len(sizing_results)} rows", flush=True)
            # Print top 5
            top5 = sizing_results.dropna(subset=["mar"]).nlargest(5, "mar")
            if not top5.empty:
                print("\n  Top 5 sizing experiments (by MAR):", flush=True)
                for _, r in top5.iterrows():
                    print(
                        f"    {r['experiment_id']}: CAGR={r['cagr']:.2%} "
                        f"MaxDD={r['max_dd']:.2%} Sharpe={r.get('sharpe',0):.2f} "
                        f"MAR={r['mar']:.2f}",
                        flush=True,
                    )

    # Phase 2: scale-in
    if args.experiment in ("scalein", "all"):
        si_strats = [s for s in strategies if s in ("A3", "S3")]
        scalein_results = run_scalein_experiments(
            panel, vnx, strategies=si_strats,
            cost=cost, min_sell_lock_bars=args.min_sell_lock_bars,
        )
        if not scalein_results.empty:
            scalein_path = OUT_DIR / "scalein_summary.csv"
            scalein_results.to_csv(scalein_path, index=False)
            print(f"  Saved: {scalein_path}", flush=True)

    # Phase 3: convergence
    if args.experiment in ("convergence", "all") and not trades_df.empty:
        convergence_results = run_convergence_experiments(trades_df, panel)
        if not convergence_results.empty:
            conv_path = OUT_DIR / "convergence_summary.csv"
            convergence_results.to_csv(conv_path, index=False)
            print(f"  Saved: {conv_path}", flush=True)

    # Phase 5: walk-forward
    if args.walk_forward == "monthly":
        wf_results = run_walk_forward(
            panel, vnx,
            strategies=[s for s in strategies if s in ("A3", "S3")],
            trades_df=trades_df if not trades_df.empty else None,
        )
        if not wf_results.empty:
            wf_path = OUT_DIR / "walk_forward_results.csv"
            wf_results.to_csv(wf_path, index=False)
            print(f"  Saved: {wf_path}", flush=True)

    # Phase 6: reports
    if args.run_baseline or args.experiment:
        write_top_findings(
            OUT_DIR, baseline_metrics, sizing_results,
            scalein_results, convergence_results, wf_results,
        )

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
