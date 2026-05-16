#!/usr/bin/env python3
"""
Portfolio Optimization Phase 2 — Interaction, defense layers, playbooks.

Phases implemented:
  2A — Clean baselines (pos15 / pos20 for A3 / S3)
  2B — Dual-path scale-in (pullback + no-pullback strength-add)
  2C — A3+GK overlay with random-subset bootstrap
  2D — Bad-year defense (stock-level cloud breadth + perf-window exposure)
  2E — Sector L4 stub (no sector map found; reports coverage gap)
  2F — Conditional exits (no-progress + momentum-rider)
  2G — Combination playbooks
  2H — OOS validation (walk-forward + block bootstrap)
  2I — Classification and final report

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase2.py --phase 2a
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase2.py --phase 2b
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase2.py --phase 2c
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase2.py --phase 2d
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase2.py --phase 2g
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase2.py --phase all
"""
from __future__ import annotations

import argparse
import itertools
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.portfolio_optimization_phase1 import (
    _build_signal_cache,
    _build_corrected_equity,
    _exit_tp_trail,
    _quality_ok,
    _classify_result,
    load_panel,
    load_vnindex,
    get_universe,
    vnindex_regime_gate,
    compute_gk,
    portfolio_metrics,
    STRATEGY_CONFIGS,
    DEFAULT_COST,
    ANN,
    EXCLUDE_VIN3,
    EXIT_18_25,
    EXIT_18_35,
    LEDGER,
)

OUT_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase2"
P1_LEDGER = LEDGER  # baseline trade ledger from phase1 research


# ── Data loading ───────────────────────────────────────────────────────────────

def load_ledger() -> pd.DataFrame:
    if P1_LEDGER.exists():
        df = pd.read_csv(P1_LEDGER)
        for col in ("entry_date", "exit_date", "signal_date"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        return df
    return pd.DataFrame()


# ── Breadth panel ──────────────────────────────────────────────────────────────

def compute_breadth_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Daily cross-stock breadth indicators across the full universe.
    Returns DataFrame indexed by date with breadth metrics.
    """
    print("  Computing breadth panel...", flush=True)
    rows = []
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 110:
            continue
        c    = sdf["close"].astype(float)
        dates = pd.to_datetime(sdf["date"]).dt.normalize()
        ema20  = c.ewm(span=20,  adjust=False).mean()
        ema50  = c.ewm(span=50,  adjust=False).mean()
        ema55  = c.ewm(span=55,  adjust=False).mean()
        ema100 = c.ewm(span=100, adjust=False).mean()
        ema200 = c.ewm(span=200, adjust=False).mean()
        tmp = pd.DataFrame({
            "date":         dates,
            "above_ema20":  (c > ema20).astype(np.int8),
            "above_ema50":  (c > ema50).astype(np.int8),
            "above_ema100": (c > ema100).astype(np.int8),
            "above_ema200": (c > ema200).astype(np.int8),
            "cloud_20_100": (ema20 > ema100).astype(np.int8),
            "cloud_21_55":  (ema20 > ema55).astype(np.int8),
        })
        rows.append(tmp)

    if not rows:
        return pd.DataFrame()

    all_df = pd.concat(rows, ignore_index=True)
    bp = (all_df.groupby("date")
          .agg(
              pct_above_ema20  =("above_ema20",  "mean"),
              pct_above_ema50  =("above_ema50",  "mean"),
              pct_above_ema100 =("above_ema100", "mean"),
              pct_above_ema200 =("above_ema200", "mean"),
              pct_cloud_20_100 =("cloud_20_100", "mean"),
              pct_cloud_21_55  =("cloud_21_55",  "mean"),
              n_symbols        =("above_ema20",  "count"),
          )
          .sort_index())

    for col in ("pct_cloud_20_100", "pct_cloud_21_55"):
        bp[f"{col}_ma20"]  = bp[col].rolling(20, min_periods=1).mean()
        bp[f"{col}_chg20"] = (bp[col] - bp[col].shift(20)).fillna(0.0)

    print(f"  Breadth panel: {len(bp)} dates, {int(bp['n_symbols'].median())} median symbols", flush=True)
    return bp


# ── GK cache ───────────────────────────────────────────────────────────────────

def build_gk_cache(panel: pd.DataFrame) -> dict[str, set]:
    """
    Returns dict[symbol -> set of normalized dates] where GK buy signal fired.
    """
    cache: dict[str, set] = {}
    universe = panel["symbol"].unique()
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 120:
            continue
        c = sdf["close"].astype(float)
        h = sdf["high"].astype(float)
        l = sdf["low"].astype(float)
        dates = pd.to_datetime(sdf["date"]).dt.normalize()
        try:
            gk = compute_gk(c, h, l)
            gk_buy = gk["gk_buy"]
            buy_dates = set(dates[gk_buy.values.astype(bool)].tolist())
            if buy_dates:
                cache[sym] = buy_dates
        except Exception:
            pass
    return cache


# ── Helper: by-year metrics ────────────────────────────────────────────────────

def _by_year(trades_df: pd.DataFrame, label: str) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()
    df = trades_df.copy()
    df["year"] = pd.to_datetime(df["entry_date"]).dt.year
    rows = []
    for (yr, strat), grp in df.groupby(["year", "strategy"]):
        rows.append({
            "label": label, "strategy": strat, "year": yr,
            "n_trades":  len(grp),
            "mean_net":  float(grp["net_return"].mean()),
            "hit_rate":  float((grp["net_return"] > 0).mean()),
            "pct_tp":    float((grp["exit_reason"].str.startswith("tp") if "exit_reason" in grp.columns else pd.Series([False]*len(grp))).mean()),
            "mean_hold": float(grp["hold_bars"].mean()) if "hold_bars" in grp.columns else np.nan,
        })
    return pd.DataFrame(rows)


def _by_regime(trades_df: pd.DataFrame, gate_by_date: pd.Series, label: str) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()
    df = trades_df.copy()
    ed = pd.to_datetime(df["entry_date"]).dt.normalize()
    df["regime"] = ed.map(lambda d: "bull" if bool(gate_by_date.get(d, False)) else "bear")
    rows = []
    for (reg, strat), grp in df.groupby(["regime", "strategy"]):
        rows.append({
            "label": label, "strategy": strat, "regime": reg,
            "n_trades": len(grp),
            "mean_net": float(grp["net_return"].mean()),
            "hit_rate": float((grp["net_return"] > 0).mean()),
        })
    return pd.DataFrame(rows)


def _bad_year_row(trades_df: pd.DataFrame, year: int, label: str) -> dict:
    df = trades_df[pd.to_datetime(trades_df["entry_date"]).dt.year == year]
    if df.empty:
        return {"label": label, "year": year, "n_trades": 0, "mean_net": np.nan,
                "hit_rate": np.nan, "mean_hold": np.nan, "max_hold_rate": np.nan}
    return {
        "label":         label,
        "year":          year,
        "n_trades":      len(df),
        "mean_net":      float(df["net_return"].mean()),
        "hit_rate":      float((df["net_return"] > 0).mean()),
        "mean_hold":     float(df["hold_bars"].mean()) if "hold_bars" in df.columns else np.nan,
        "max_hold_rate": float((df["hold_bars"] >= 248).mean()) if "hold_bars" in df.columns else np.nan,
    }


# ── Defense equity builder ─────────────────────────────────────────────────────

def _build_equity_with_defense(
    trades_df:        pd.DataFrame,
    max_positions:    int   = 20,
    max_position_pct: float = 0.05,
    max_total_exp:    float = 1.0,
    rank_col:         str   = "ema_dist_at_entry",
    rank_mode:        str   = "equal",
    gk_priority:      bool  = False,    # fill GK trades first
    # Breadth defense
    breadth_series:   pd.Series | None = None,   # date -> pct_cloud_bull_20_100
    breadth_schedule: list[dict] | None = None,  # [{"threshold":0.4,"exp_mult":0.5},...]
    # Perf-window defense
    perf_series:      pd.Series | None = None,   # date -> trailing portfolio return
    perf_schedule:    list[dict] | None = None,  # [{"threshold":-0.05,"exp_mult":0.75},...]
    # Hysteresis
    hysteresis:       dict | None = None,  # {"reduce_at":-0.20,"restore_at":-0.12,"exp":0.50}
) -> tuple[pd.Series, dict]:
    """Equity simulation with breadth/perf-based defense layers."""
    if trades_df.empty:
        return pd.Series(dtype=float), {}

    base_w = min(1.0 / max(max_positions, 1), max_position_pct)
    eff_max = min(max_positions, int(max_total_exp / max(base_w, 1e-9)))

    df = trades_df.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])

    # Rank-based weight
    if rank_mode in ("linear", "top_heavy", "sqrt") and rank_col in df.columns:
        df["_rank_pct"] = df.groupby("entry_date")[rank_col].rank(pct=True, na_option="bottom")
    else:
        df["_rank_pct"] = 0.5

    all_dates = pd.date_range(df["entry_date"].min(), df["exit_date"].max(), freq="B")

    sort_keys = (["has_gk", rank_col] if gk_priority and "has_gk" in df.columns
                 else [rank_col if rank_col in df.columns else "_rank_pct"])
    sort_asc  = ([False] * len(sort_keys))

    by_entry: dict = {}
    for ed, grp in df.groupby("entry_date", sort=False):
        by_entry[ed] = [(int(i), r)
                        for i, r in grp.sort_values(sort_keys, ascending=sort_asc).iterrows()]

    by_exit: dict = {}
    for i, row in df.iterrows():
        by_exit.setdefault(row["exit_date"], []).append((int(i), row))

    portfolio_val = 1.0
    peak_val      = 1.0
    active: dict[int, tuple] = {}
    equity: dict  = {}
    n_filled      = 0
    n_breadth_blocked = 0
    in_reduced_mode   = False

    for date_val in all_dates:
        # Exits
        for tid, row in by_exit.get(date_val, []):
            if tid in active:
                _, w = active.pop(tid)
                portfolio_val += portfolio_val * w * float(row["net_return"])

        peak_val = max(peak_val, portfolio_val)

        # Determine defense multiplier
        exp_mult = 1.0

        if breadth_series is not None and breadth_schedule:
            bv = float(breadth_series.get(date_val, 1.0))
            for sched in sorted(breadth_schedule, key=lambda x: x["threshold"]):
                if bv < sched["threshold"]:
                    exp_mult = min(exp_mult, sched["exp_mult"])

        if perf_series is not None and perf_schedule:
            pv = float(perf_series.get(date_val, 0.0))
            for sched in sorted(perf_schedule, key=lambda x: x["threshold"]):
                if pv < sched["threshold"]:
                    exp_mult = min(exp_mult, sched["exp_mult"])

        if hysteresis is not None:
            current_dd = portfolio_val / peak_val - 1.0
            if in_reduced_mode:
                if current_dd > hysteresis.get("restore_at", -0.12):
                    in_reduced_mode = False
            else:
                if current_dd <= hysteresis.get("reduce_at", -0.20):
                    in_reduced_mode = True
            if in_reduced_mode:
                exp_mult = min(exp_mult, hysteresis.get("exp", 0.50))

        effective_exp = max_total_exp * exp_mult
        eff_max_now   = min(eff_max, int(effective_exp / max(base_w, 1e-9)))

        # Entries
        remaining = eff_max_now - len(active)
        if remaining > 0:
            queued = by_entry.get(date_val, [])[:remaining]
            if queued:
                weights = []
                for tid, row in queued:
                    rp = float(row.get("_rank_pct", 0.5))
                    if rank_mode == "linear":
                        raw_w = base_w * (1.0 + (rp - 0.5))
                    elif rank_mode in ("top_heavy", "sqrt"):
                        raw_w = rp ** 0.5
                    else:
                        raw_w = base_w
                    # Dual-path weight fraction
                    raw_w *= float(row.get("total_frac", 1.0))
                    weights.append(raw_w)

                batch_target = (len(queued) / max(eff_max, 1)) * effective_exp
                if rank_mode in ("linear", "top_heavy", "sqrt"):
                    total_raw = sum(weights)
                    if total_raw > 0:
                        scale = min(1.0, batch_target / total_raw)
                        weights = [w * scale for w in weights]

                weights = [min(w, max_position_pct) for w in weights]
                active_exp = sum(w for _, w in active.values())
                avail_exp  = max(0.0, effective_exp - active_exp)
                batch_sum  = sum(weights)
                if batch_sum > avail_exp + 1e-9 and batch_sum > 0:
                    weights = [w * avail_exp / batch_sum for w in weights]

                for (tid, row), w in zip(queued, weights):
                    if w > 1e-9:
                        active[tid] = (row, w)
                        n_filled += 1
                    else:
                        n_breadth_blocked += 1
        elif remaining <= 0 and exp_mult < 1.0:
            n_breadth_blocked += len(by_entry.get(date_val, []))

        equity[date_val] = portfolio_val

    eq_series = pd.Series(equity)
    stats = {"n_filled": n_filled, "n_breadth_blocked": n_breadth_blocked}
    return eq_series, stats


# ── Trailing performance series ────────────────────────────────────────────────

def _trailing_perf_series(equity: pd.Series, window_days: int = 63) -> pd.Series:
    """Trailing N-day portfolio return for each date."""
    return equity.pct_change(window_days).fillna(0.0)


# ── Phase 2A: Clean baselines ──────────────────────────────────────────────────

def run_phase2a_baselines(
    panel:       pd.DataFrame,
    vnx:         pd.DataFrame,
    ledger:      pd.DataFrame,
    strategies:  list[str],
    cost:        float,
    min_lock:    int,
) -> pd.DataFrame:
    print("Phase 2A: clean baselines...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)

    eq_dir  = OUT_DIR / "phase2_baseline_equity"
    led_dir = OUT_DIR / "phase2_baseline_trade_ledgers"
    eq_dir.mkdir(parents=True, exist_ok=True)
    led_dir.mkdir(parents=True, exist_ok=True)

    rows     = []
    year_rows   = []
    regime_rows = []

    configs = [(s, p) for s in strategies for p in (20, 15)]
    for strategy, pos in configs:
        if strategy not in STRATEGY_CONFIGS:
            continue
        cfg      = STRATEGY_CONFIGS[strategy]
        exit_cfg = cfg["exit_cfg"]
        rank_col = cfg["rank_col"] + "_at_entry"
        if rank_col not in ledger.columns:
            rank_col = "ema_dist_at_entry"

        sub = ledger[ledger["strategy"] == strategy].copy()
        if sub.empty:
            continue

        pct = 1.0 / pos
        eq, stats = _build_corrected_equity(
            sub, max_positions=pos, max_position_pct=pct, max_total_exp=1.0,
            rank_col=rank_col, rank_mode="equal",
        )
        if eq.empty:
            continue

        m   = portfolio_metrics(eq, sub)
        eid = f"{strategy}_pos{pos}"

        eq.to_csv(eq_dir / f"{eid}.csv")
        sub.to_csv(led_dir / f"{eid}.csv", index=False)

        # Top-N PnL concentration
        sub_sorted = sub.sort_values("net_return", ascending=False)
        n = len(sub_sorted)
        top1  = float(sub_sorted.head(1)["net_return"].sum()  / max(sub_sorted["net_return"].sum(), 1e-9))
        top3  = float(sub_sorted.head(3)["net_return"].sum()  / max(sub_sorted["net_return"].sum(), 1e-9))
        top5  = float(sub_sorted.head(5)["net_return"].sum()  / max(sub_sorted["net_return"].sum(), 1e-9))

        row = {
            "experiment_id":   eid,
            "strategy":        strategy,
            "max_positions":   pos,
            "max_position_pct": pct,
            "n_trades":        n,
            "hit_rate":        float((sub["net_return"] > 0).mean()),
            "mean_net":        float(sub["net_return"].mean()),
            "cagr":            m.get("cagr", np.nan),
            "max_dd":          m.get("max_dd", np.nan),
            "sharpe":          m.get("sharpe", np.nan),
            "mar":             m.get("mar", np.nan),
            "top1_conc":       top1,
            "top3_conc":       top3,
            "top5_conc":       top5,
            "n_filled":        stats.get("n_filled", 0),
            "prod_class":      _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
        }
        rows.append(row)
        print(f"  {eid}: CAGR={m.get('cagr',0):.2%}, MaxDD={m.get('max_dd',0):.2%}, MAR={m.get('mar',0):.2f}", flush=True)

        yr_df = _by_year(sub, eid)
        yr_df["strategy"] = strategy
        year_rows.append(yr_df)

        reg_df = _by_regime(sub, gate_by_date, eid)
        regime_rows.append(reg_df)

    summary = pd.DataFrame(rows)
    by_yr   = pd.concat(year_rows,   ignore_index=True) if year_rows   else pd.DataFrame()
    by_reg  = pd.concat(regime_rows, ignore_index=True) if regime_rows else pd.DataFrame()

    summary.to_csv(OUT_DIR / "phase2_baseline_summary.csv",    index=False)
    by_yr.to_csv(OUT_DIR / "phase2_baseline_by_year.csv",      index=False)
    by_reg.to_csv(OUT_DIR / "phase2_baseline_by_regime.csv",   index=False)
    print(f"  2A saved: {len(summary)} baseline rows", flush=True)
    return summary


# ── Phase 2B: Dual-path scale-in ──────────────────────────────────────────────

def _sim_dual_path_symbol(
    sym:            str,
    data:           dict,
    strategy:       str,
    exit_cfg:       dict,
    cost:           float,
    mode:           str,    # "pb_only" | "str_only" | "either" | "stack"
    t1_frac:        float,
    t2_frac:        float,  # for pb_only/str_only/either
    t2_pb_frac:     float,  # for stack
    t2_str_frac:    float,  # for stack
    pb_depth:       float,
    pb_window:      int,
    pb_quality_mode: str,
    str_thresh:     float,
    str_window:     int,
    str_require_gk: bool,
    gk_dates:       set,    # normalized dates with GK signal for this sym
    gate_by_date:   pd.Series | None,
    min_lock:       int = 5,
) -> list[dict]:
    close_arr = data["close"]
    high_arr  = data["high"]
    atr_arr   = data["atr"]
    dates     = data["dates"]
    n = len(close_arr)

    trades = []
    for si in data["sig_idxs"]:
        entry_i = si + 1
        if entry_i >= n:
            continue
        sig_date   = pd.Timestamp(dates[si]).normalize()
        entry_date = pd.Timestamp(dates[entry_i])

        if gate_by_date is not None and not bool(gate_by_date.get(sig_date, True)):
            continue

        ep1 = float(close_arr[entry_i])
        if ep1 <= 0:
            continue

        pb_bar  = None
        str_bar = None
        ep2_pb  = None
        ep2_str = None

        obs_end = min(entry_i + max(pb_window, str_window) + 1, n)

        for k in range(entry_i + 1, obs_end):
            bar = k - entry_i
            c   = float(close_arr[k])

            # Pullback path
            if mode in ("pb_only", "either", "stack") and pb_bar is None and bar <= pb_window:
                if c <= ep1 * (1.0 - pb_depth) and _quality_ok(data, k, pb_quality_mode):
                    pb_bar  = k
                    ep2_pb  = c
                    if mode == "either":
                        break  # first trigger wins

            # Strength path (independent of pullback for stack, exclusive for either)
            if mode in ("str_only", "either", "stack") and str_bar is None and bar <= str_window:
                if pb_bar is not None and mode == "either":
                    continue  # pullback already won
                if c >= ep1 * (1.0 + str_thresh):
                    cloud_ok = bool(data["cloud"][k])
                    fast_ok  = c > float(data["fast"][k]) * 0.999
                    if cloud_ok and fast_ok:
                        if str_require_gk:
                            bar_date = pd.Timestamp(dates[k]).normalize()
                            has_gk = any(abs((bar_date - gd).days) <= 5 for gd in gk_dates)
                            if not has_gk:
                                continue
                        str_bar  = k
                        ep2_str  = c
                        if mode in ("str_only", "either"):
                            break

        # Compute total fraction and blended ep
        if mode == "pb_only":
            has_add    = pb_bar is not None
            add_frac   = t2_frac if has_add else 0.0
            total_frac = t1_frac + add_frac
            blended_ep = (t1_frac * ep1 + add_frac * ep2_pb) / total_frac if has_add else ep1
            add_path   = "pullback" if has_add else "none"
        elif mode == "str_only":
            has_add    = str_bar is not None
            add_frac   = t2_frac if has_add else 0.0
            total_frac = t1_frac + add_frac
            blended_ep = (t1_frac * ep1 + add_frac * ep2_str) / total_frac if has_add else ep1
            add_path   = "strength" if has_add else "none"
        elif mode == "either":
            if pb_bar is not None:
                add_frac = t2_frac; ep2 = ep2_pb; add_path = "pullback"
            elif str_bar is not None:
                add_frac = t2_frac; ep2 = ep2_str; add_path = "strength"
            else:
                add_frac = 0.0;    ep2 = ep1;     add_path = "none"
            total_frac = t1_frac + add_frac
            blended_ep = (t1_frac * ep1 + add_frac * ep2) / total_frac if add_frac > 0 else ep1
        else:  # stack
            pb_actual  = t2_pb_frac  if pb_bar  is not None else 0.0
            str_actual = t2_str_frac if str_bar is not None else 0.0
            total_frac = min(t1_frac + pb_actual + str_actual, 1.0)
            num = t1_frac * ep1
            if pb_bar  is not None: num += pb_actual  * ep2_pb
            if str_bar is not None: num += str_actual * ep2_str
            blended_ep = num / total_frac if total_frac > 0 else ep1
            add_path = (
                "both"     if pb_bar and str_bar else
                "pullback" if pb_bar             else
                "strength" if str_bar            else "none"
            )

        # Exit from entry_i using blended_ep
        hold, gross, reason = _exit_tp_trail(
            close_arr, high_arr, atr_arr, entry_i, blended_ep, exit_cfg
        )
        exit_bar = min(entry_i + hold, n - 1)
        net = gross - cost

        trades.append({
            "symbol":     sym,
            "strategy":   strategy,
            "entry_date": entry_date.date(),
            "exit_date":  pd.Timestamp(dates[exit_bar]).date(),
            "ep1":         ep1,
            "ep2_pb":      ep2_pb,
            "ep2_str":     ep2_str,
            "blended_ep":  blended_ep,
            "t1_frac":     t1_frac,
            "total_frac":  total_frac,
            "add_path":    add_path,
            "has_pullback": pb_bar is not None,
            "has_strength": str_bar is not None,
            "pb_bar":      (pb_bar  - entry_i) if pb_bar  is not None else -1,
            "str_bar":     (str_bar - entry_i) if str_bar is not None else -1,
            "hold_bars":   hold,
            "gross_return": gross,
            "net_return":   net,
            "exit_reason":  reason,
        })

    return trades


def _dp_summary_row(eid, strategy, mode, t1, pb_d, pb_w, str_t, str_w, gk_req,
                     trades, max_positions=20):
    if not trades:
        return None
    df = pd.DataFrame(trades)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])

    pct_w_pos = max_positions
    base_w    = 1.0 / pct_w_pos
    eq, _     = _build_equity_with_defense(df, max_positions=pct_w_pos, max_position_pct=base_w)
    if eq.empty:
        return None

    m  = portfolio_metrics(eq, df)
    pb_df  = df[df["has_pullback"]]
    str_df = df[df["has_strength"]]
    no_add = df[df["add_path"] == "none"]

    return {
        "experiment_id":  eid,
        "strategy":       strategy,
        "mode":           mode,
        "t1_frac":        t1,
        "pb_depth_pct":   pb_d * 100 if pb_d else np.nan,
        "pb_window":      pb_w,
        "str_thresh_pct": str_t * 100 if str_t else np.nan,
        "str_window":     str_w,
        "gk_require":     gk_req,
        "n_trades":       len(df),
        "pct_pullback":   len(pb_df) / max(len(df), 1),
        "pct_strength":   len(str_df) / max(len(df), 1),
        "pct_no_add":     len(no_add) / max(len(df), 1),
        "mean_net_all":   float(df["net_return"].mean()),
        "mean_net_pb":    float(pb_df["net_return"].mean()) if len(pb_df) else np.nan,
        "mean_net_str":   float(str_df["net_return"].mean()) if len(str_df) else np.nan,
        "mean_net_no":    float(no_add["net_return"].mean()) if len(no_add) else np.nan,
        "mean_total_frac": float(df["total_frac"].mean()),
        "cagr":           m.get("cagr",   np.nan),
        "max_dd":         m.get("max_dd", np.nan),
        "sharpe":         m.get("sharpe", np.nan),
        "mar":            m.get("mar",    np.nan),
        "prod_class":     _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
    }


def run_phase2b_dual_path(
    panel:      pd.DataFrame,
    vnx:        pd.DataFrame,
    strategies: list[str],
    gk_cache:   dict[str, set],
    cost:       float,
    min_lock:   int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print("Phase 2B: dual-path scale-in...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)

    # Targeted grid — no broad sweep
    # Structure × depth × window × strength-thresh × gk-require
    configs = []

    # Structure 1: pullback only (best from Phase 1: d=4%, w=30 for A3, d=5%,w=20 for S3)
    for d, w in [(0.03, 20), (0.04, 20), (0.04, 30), (0.05, 20)]:
        configs.append(("pb_only", 0.50, 0.50, 0.0, d, w, "slow_097", 0.0, 0, False))

    # Structure 2: strength only
    for st, sw in [(0.02, 10), (0.04, 10), (0.04, 20), (0.06, 10), (0.06, 20)]:
        configs.append(("str_only", 0.50, 0.50, 0.0, 0.0, 0, "slow_097", st, sw, False))
        configs.append(("str_only", 0.50, 0.50, 0.0, 0.0, 0, "slow_097", st, sw, True))

    # Structure 3: either (first path wins)
    for d, w, st, sw in [(0.04, 20, 0.04, 10), (0.04, 30, 0.04, 20), (0.04, 20, 0.06, 10)]:
        configs.append(("either", 0.50, 0.50, 0.0, d, w, "slow_097", st, sw, False))
        configs.append(("either", 0.60, 0.40, 0.0, d, w, "slow_097", st, sw, False))

    # Structure 4: stack (both can fire)
    for d, w, st, sw in [(0.04, 20, 0.04, 10), (0.04, 30, 0.04, 20)]:
        configs.append(("stack", 0.40, 0.0, 0.30, d, w, "slow_097", st, sw, False))
        configs.append(("stack", 0.40, 0.0, 0.30, d, w, "slow_097", st, sw, True))

    summary_rows = []
    all_trade_records: list[dict] = []
    year_rows   = []
    regime_rows = []

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        cfg      = STRATEGY_CONFIGS[strategy]
        exit_cfg = cfg["exit_cfg"]

        print(f"  [{strategy}] building signal cache...", flush=True)
        cache = _build_signal_cache(panel, strategy)
        print(f"  [{strategy}] {len(cache)} symbols", flush=True)

        for (mode, t1, t2, t2_pb, pb_d, pb_w, pb_q, st, sw, gk_req) in configs:
            # For pb_only/str_only/either: t2 is the add fraction
            # For stack: t2_pb/t2_str split from config
            t2_str = t2 if mode == "str_only" else (t2 if mode in ("either",) else 0.0)
            t2_pb_f  = t2 if mode == "pb_only" else t2_pb
            t2_str_f = t2_str if mode in ("str_only", "either") else t2_pb  # reuse slot

            gk_label = "_gk" if gk_req else ""
            eid = (f"DP_{strategy}_{mode}_t{int(t1*100)}"
                   + (f"_pb{int(pb_d*100)}w{pb_w}" if pb_d > 0 else "")
                   + (f"_str{int(st*100)}w{sw}" if st > 0 else "")
                   + gk_label)

            trades = []
            for sym, data in cache.items():
                sym_gk = gk_cache.get(sym, set())
                trades.extend(_sim_dual_path_symbol(
                    sym, data, strategy, exit_cfg, cost,
                    mode=mode, t1_frac=t1, t2_frac=t2,
                    t2_pb_frac=t2_pb_f, t2_str_frac=t2_str_f,
                    pb_depth=pb_d, pb_window=pb_w, pb_quality_mode=pb_q,
                    str_thresh=st, str_window=sw, str_require_gk=gk_req,
                    gk_dates=sym_gk, gate_by_date=gate_by_date, min_lock=min_lock,
                ))

            row = _dp_summary_row(eid, strategy, mode, t1, pb_d, pb_w, st, sw, gk_req, trades)
            if row:
                summary_rows.append(row)
                print(f"    {eid}: n={len(trades)}, pb%={row['pct_pullback']:.1%}, "
                      f"str%={row['pct_strength']:.1%}, MAR={row['mar']:.2f}", flush=True)

            # Collect baseline config for year/regime decomp
            if mode == "either" and abs(pb_d - 0.04) < 1e-9 and pb_w == 20 and abs(st - 0.04) < 1e-9 and sw == 10 and not gk_req:
                df_t = pd.DataFrame(trades)
                if not df_t.empty:
                    df_t["strategy"] = strategy
                    yr_df  = _by_year(df_t, eid)
                    reg_df = _by_regime(df_t, gate_by_date, eid)
                    year_rows.append(yr_df)
                    regime_rows.append(reg_df)
                    all_trade_records.extend(trades)

    # Trade quality breakdown
    quality_rows = []
    if all_trade_records:
        full_df = pd.DataFrame(all_trade_records)
        for strat, grp in full_df.groupby("strategy"):
            for path_label, sub in [("all", grp),
                                      ("pullback", grp[grp["has_pullback"]]),
                                      ("strength", grp[grp["has_strength"]]),
                                      ("no_add",   grp[grp["add_path"] == "none"])]:
                if sub.empty: continue
                quality_rows.append({
                    "strategy": strat, "group": path_label,
                    "n": len(sub),
                    "mean_net":  float(sub["net_return"].mean()),
                    "mean_ep1":  float(sub["ep1"].mean()),
                    "mean_total_frac": float(sub["total_frac"].mean()),
                    "hit_rate":  float((sub["net_return"] > 0).mean()),
                    "mean_hold": float(sub["hold_bars"].mean()) if "hold_bars" in sub.columns else np.nan,
                })

    summary    = pd.DataFrame(summary_rows)
    quality    = pd.DataFrame(quality_rows)
    by_yr      = pd.concat(year_rows,   ignore_index=True) if year_rows   else pd.DataFrame()
    by_regime_ = pd.concat(regime_rows, ignore_index=True) if regime_rows else pd.DataFrame()

    summary.to_csv(OUT_DIR / "phase2_scalein_dual_path_summary.csv",      index=False)
    quality.to_csv(OUT_DIR / "phase2_scalein_dual_path_trade_quality.csv", index=False)
    by_yr.to_csv(OUT_DIR / "phase2_scalein_dual_path_by_year.csv",         index=False)
    by_regime_.to_csv(OUT_DIR / "phase2_scalein_dual_path_by_regime.csv",  index=False)
    print(f"  2B saved: {len(summary)} dual-path rows", flush=True)
    return summary, quality, by_yr, by_regime_


# ── Phase 2C: A3+GK overlay with bootstrap ────────────────────────────────────

def _bootstrap_random_subsets(
    trades_df:    pd.DataFrame,
    coverage:     float,
    n_boot:       int   = 1000,
    max_positions: int  = 20,
    max_pct:       float = 0.05,
    rng_seed:      int  = 42,
) -> pd.DataFrame:
    rng      = np.random.default_rng(rng_seed)
    n_select = max(1, int(len(trades_df) * coverage))
    results  = []
    for i in range(n_boot):
        idx    = rng.choice(len(trades_df), size=n_select, replace=False)
        subset = trades_df.iloc[idx].copy()
        eq, _  = _build_corrected_equity(subset, max_positions=max_positions,
                                          max_position_pct=max_pct)
        if eq.empty:
            continue
        m = portfolio_metrics(eq, subset)
        results.append({
            "boot_i":  i,
            "mar":     m.get("mar",    np.nan),
            "cagr":    m.get("cagr",   np.nan),
            "max_dd":  m.get("max_dd", np.nan),
            "sharpe":  m.get("sharpe", np.nan),
        })
    return pd.DataFrame(results)


def run_phase2c_gk_overlay(
    panel:      pd.DataFrame,
    vnx:        pd.DataFrame,
    ledger:     pd.DataFrame,
    strategies: list[str],
    gk_cache:   dict[str, set],
    cost:       float,
    n_boot:     int = 500,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print("Phase 2C: A3+GK overlay with bootstrap...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)

    # Build GK lookup: (sym, date) -> set
    gk_by_date: dict[pd.Timestamp, set] = {}
    for sym, dates_set in gk_cache.items():
        for d in dates_set:
            gk_by_date.setdefault(d, set()).add(sym)

    def _tag_has_gk(df: pd.DataFrame, window_days: int) -> pd.Series:
        """Tag each A3 trade with has_gk within window_days of signal_date."""
        results = []
        for _, row in df.iterrows():
            sig_d = pd.Timestamp(row["signal_date"]).normalize()
            sym   = row["symbol"]
            sym_gk = gk_cache.get(sym, set())
            found = any(abs((sig_d - gd).days) <= window_days for gd in sym_gk)
            results.append(found)
        return pd.Series(results, index=df.index, dtype=bool)

    summary_rows = []
    bootstrap_rows = []
    year_rows   = []
    regime_rows = []

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        sub = ledger[ledger["strategy"] == strategy].copy()
        if sub.empty:
            continue

        sub["entry_date"]  = pd.to_datetime(sub["entry_date"])
        sub["exit_date"]   = pd.to_datetime(sub["exit_date"])
        sub["signal_date"] = pd.to_datetime(sub["signal_date"])

        max_pos = 20
        base_w  = 1.0 / max_pos

        print(f"  [{strategy}] tagging GK for windows 3/5/10...", flush=True)
        for window in (3, 5, 10):
            sub[f"has_gk_w{window}"] = _tag_has_gk(sub, window)

        for window in (3, 5, 10):
            wk = f"has_gk_w{window}"
            sub["has_gk"] = sub[wk]
            gk_trades   = sub[sub[wk]].copy()
            no_gk_trades = sub[~sub[wk]].copy()
            coverage    = len(gk_trades) / max(len(sub), 1)

            for subset_name, subset_df in [
                (f"{strategy}+GK_w{window}", gk_trades),
                (f"{strategy}_noGK_w{window}", no_gk_trades),
                (f"{strategy}_all_size125_w{window}", sub),   # full with GK priority + 1.25x
            ]:
                if subset_df.empty:
                    continue

                run_df = subset_df.copy()
                if "size125" in subset_name:
                    # Full set, GK priority (equity builder fills GK trades first)
                    eq, _ = _build_equity_with_defense(
                        run_df, max_positions=max_pos, max_position_pct=base_w,
                        gk_priority=True,
                    )
                else:
                    eq, _ = _build_corrected_equity(
                        run_df, max_positions=max_pos, max_position_pct=base_w,
                    )

                if eq.empty:
                    continue
                m = portfolio_metrics(eq, run_df)

                row = {
                    "experiment_id": subset_name,
                    "strategy":      strategy,
                    "gk_window":     window,
                    "has_gk":        "True" if "+GK_" in subset_name else (
                                      "False" if "_noGK" in subset_name else "gk_priority"),
                    "n_trades":      len(run_df),
                    "coverage_pct":  coverage if "+GK_" in subset_name else (1 - coverage if "_noGK" in subset_name else 1.0),
                    "mean_net":      float(run_df["net_return"].mean()),
                    "cagr":          m.get("cagr",   np.nan),
                    "max_dd":        m.get("max_dd", np.nan),
                    "sharpe":        m.get("sharpe", np.nan),
                    "mar":           m.get("mar",    np.nan),
                    "prod_class":    _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
                }
                summary_rows.append(row)

                # By year / regime for the GK-filtered set
                if "+GK_" in subset_name:
                    yr_df = _by_year(run_df, subset_name)
                    yr_df["strategy"] = strategy
                    year_rows.append(yr_df)
                    reg_df = _by_regime(run_df, gate_by_date, subset_name)
                    regime_rows.append(reg_df)

            # Bootstrap test for the best window (w=10)
            if window == 10:
                print(f"  [{strategy}] bootstrapping {n_boot} random {coverage:.1%} subsets...", flush=True)
                gk_actual_mar = next((r["mar"] for r in summary_rows
                                       if r["experiment_id"] == f"{strategy}+GK_w{window}"
                                       and r["strategy"] == strategy), np.nan)

                boot_df = _bootstrap_random_subsets(
                    sub, coverage, n_boot=n_boot, max_positions=max_pos, max_pct=base_w,
                )
                boot_df["strategy"] = strategy
                boot_df["gk_window"] = window
                boot_df["actual_gk_mar"] = gk_actual_mar
                boot_df["pctile_vs_random"] = (
                    (boot_df["mar"] < gk_actual_mar).mean() if not boot_df.empty else np.nan
                )
                bootstrap_rows.append(boot_df)
                if not boot_df.empty:
                    pctile = float((boot_df["mar"] < gk_actual_mar).mean())
                    print(f"  [{strategy}] A3+GK w{window} MAR={gk_actual_mar:.3f} "
                          f"at {pctile:.1%} percentile of random subsets", flush=True)

    summary   = pd.DataFrame(summary_rows)
    bootstrap = pd.concat(bootstrap_rows, ignore_index=True) if bootstrap_rows else pd.DataFrame()
    by_yr     = pd.concat(year_rows,      ignore_index=True) if year_rows      else pd.DataFrame()
    by_reg    = pd.concat(regime_rows,    ignore_index=True) if regime_rows     else pd.DataFrame()

    summary.to_csv(OUT_DIR / "phase2_a3gk_overlay_summary.csv",    index=False)
    bootstrap.to_csv(OUT_DIR / "phase2_a3gk_random_subset_test.csv", index=False)
    by_yr.to_csv(OUT_DIR / "phase2_a3gk_by_year.csv",               index=False)
    by_reg.to_csv(OUT_DIR / "phase2_a3gk_by_regime.csv",            index=False)
    print(f"  2C saved: {len(summary)} GK overlay rows, {len(bootstrap)} bootstrap rows", flush=True)
    return summary, bootstrap, by_yr, by_reg


# ── Phase 2D: Bad-year defense ────────────────────────────────────────────────

def run_phase2d_defense(
    panel:         pd.DataFrame,
    vnx:           pd.DataFrame,
    ledger:        pd.DataFrame,
    strategies:    list[str],
    breadth_panel: pd.DataFrame,
    cost:          float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print("Phase 2D: bad-year defense layers...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)

    bad_years   = [2018, 2019, 2022]
    good_years  = [2013, 2020, 2021, 2025]
    all_years   = bad_years + good_years + [2016, 2017, 2023, 2024]

    breadth_20_100 = breadth_panel["pct_cloud_20_100"] if not breadth_panel.empty else pd.Series(dtype=float)
    breadth_21_55  = breadth_panel["pct_cloud_21_55"]  if not breadth_panel.empty else pd.Series(dtype=float)

    summary_rows  = []
    bad_year_rows = []
    missed_rows   = []

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        sub = ledger[ledger["strategy"] == strategy].copy()
        if sub.empty:
            continue
        sub["entry_date"] = pd.to_datetime(sub["entry_date"])
        sub["exit_date"]  = pd.to_datetime(sub["exit_date"])

        max_pos = 20
        base_w  = 1.0 / max_pos
        breadth_col = breadth_20_100 if strategy == "A3" else breadth_21_55

        # 2D.1 Performance-based defense (trailing portfolio return windows)
        # First build baseline equity to get trailing perf
        eq_base, _ = _build_corrected_equity(sub, max_positions=max_pos, max_position_pct=base_w)

        perf_configs = [
            ("no_defense",     None, None, None),
            ("perf_3m_mild",   63,   [{"threshold": -0.05, "exp_mult": 0.75},
                                       {"threshold": -0.10, "exp_mult": 0.50}], None),
            ("perf_3m_firm",   63,   [{"threshold": -0.05, "exp_mult": 0.50},
                                       {"threshold": -0.15, "exp_mult": 0.25}], None),
            ("perf_6m_firm",   126,  [{"threshold": -0.10, "exp_mult": 0.50},
                                       {"threshold": -0.20, "exp_mult": 0.25}], None),
            ("hysteresis_20",  None, None,
             {"reduce_at": -0.20, "restore_at": -0.12, "exp": 0.50}),
            ("hysteresis_18",  None, None,
             {"reduce_at": -0.18, "restore_at": -0.10, "exp": 0.50}),
            ("hysteresis_25",  None, None,
             {"reduce_at": -0.25, "restore_at": -0.15, "exp": 0.50}),
        ]

        for (label, perf_w, perf_sched, hystr) in perf_configs:
            perf_series = None
            if perf_w and not eq_base.empty:
                perf_series = _trailing_perf_series(eq_base, perf_w)

            eq, stats = _build_equity_with_defense(
                sub, max_positions=max_pos, max_position_pct=base_w,
                perf_series=perf_series, perf_schedule=perf_sched,
                hysteresis=hystr,
            )
            if eq.empty:
                continue
            m   = portfolio_metrics(eq, sub)
            eid = f"PERF_{strategy}_{label}"

            row = {
                "experiment_id":   eid,
                "strategy":        strategy,
                "defense_type":    "perf_window",
                "config":          label,
                "n_trades":        len(sub),
                "n_blocked":       stats.get("n_breadth_blocked", 0),
                "cagr":            m.get("cagr",   np.nan),
                "max_dd":          m.get("max_dd", np.nan),
                "sharpe":          m.get("sharpe", np.nan),
                "mar":             m.get("mar",    np.nan),
                "prod_class":      _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
            }
            summary_rows.append(row)

            for yr in all_years:
                bad_year_rows.append(_bad_year_row(sub, yr, eid))

        # 2D.2 Stock-level cloud breadth defense
        if not breadth_col.empty:
            breadth_configs = [
                ("breadth_40_50",  [{"threshold": 0.40, "exp_mult": 0.50}]),
                ("breadth_40_25",  [{"threshold": 0.40, "exp_mult": 0.25}]),
                ("breadth_50_50",  [{"threshold": 0.50, "exp_mult": 0.50}]),
                ("breadth_50_25",  [{"threshold": 0.50, "exp_mult": 0.25}]),
                ("breadth_30_50",  [{"threshold": 0.30, "exp_mult": 0.50}]),
                ("breadth_30_25",  [{"threshold": 0.30, "exp_mult": 0.25}]),
                ("breadth_tiered", [{"threshold": 0.50, "exp_mult": 0.75},
                                     {"threshold": 0.40, "exp_mult": 0.50},
                                     {"threshold": 0.30, "exp_mult": 0.25}]),
                ("breadth_tiered_firm", [{"threshold": 0.50, "exp_mult": 0.50},
                                          {"threshold": 0.40, "exp_mult": 0.25},
                                          {"threshold": 0.30, "exp_mult": 0.0}]),
            ]

            for (label, bsched) in breadth_configs:
                eq, stats = _build_equity_with_defense(
                    sub, max_positions=max_pos, max_position_pct=base_w,
                    breadth_series=breadth_col, breadth_schedule=bsched,
                )
                if eq.empty:
                    continue
                m   = portfolio_metrics(eq, sub)
                eid = f"BREADTH_{strategy}_{label}"

                row = {
                    "experiment_id":   eid,
                    "strategy":        strategy,
                    "defense_type":    "breadth",
                    "config":          label,
                    "n_trades":        len(sub),
                    "n_blocked":       stats.get("n_breadth_blocked", 0),
                    "cagr":            m.get("cagr",   np.nan),
                    "max_dd":          m.get("max_dd", np.nan),
                    "sharpe":          m.get("sharpe", np.nan),
                    "mar":             m.get("mar",    np.nan),
                    "prod_class":      _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
                }
                summary_rows.append(row)

                for yr in all_years:
                    bad_year_rows.append(_bad_year_row(sub, yr, eid))

        print(f"  [{strategy}] 2D: {len([r for r in summary_rows if r['strategy']==strategy])} configs", flush=True)

        # 2D.3 Avoided losers / missed winners analysis for best breadth config
        if not breadth_col.empty:
            # Classify each trade as "blocked" vs "allowed" under breadth_tiered
            bsched = [{"threshold": 0.50, "exp_mult": 0.75},
                      {"threshold": 0.40, "exp_mult": 0.50},
                      {"threshold": 0.30, "exp_mult": 0.25}]
            for _, row in sub.iterrows():
                ed = row["entry_date"]
                if not isinstance(ed, pd.Timestamp):
                    ed = pd.Timestamp(ed)
                bv = float(breadth_col.get(ed.normalize(), 1.0))
                blocked = any(bv < s["threshold"] and s["exp_mult"] == 0 for s in bsched)
                is_loser = row["net_return"] < 0
                missed_rows.append({
                    "strategy":    strategy,
                    "entry_date":  ed.date(),
                    "net_return":  row["net_return"],
                    "breadth":     bv,
                    "blocked":     blocked,
                    "is_loser":    is_loser,
                    "avoided":     blocked and is_loser,
                    "missed":      blocked and not is_loser,
                })

    summary    = pd.DataFrame(summary_rows)
    bad_yr_df  = pd.DataFrame(bad_year_rows)
    missed_df  = pd.DataFrame(missed_rows)

    summary.to_csv(OUT_DIR / "phase2_exposure_scaling_summary.csv",     index=False)
    bad_yr_df.to_csv(OUT_DIR / "phase2_bad_year_defense_summary.csv",   index=False)
    missed_df.to_csv(OUT_DIR / "phase2_avoided_loser_missed_winner.csv", index=False)

    # Save breadth panel
    if not breadth_panel.empty:
        breadth_panel.reset_index().to_csv(OUT_DIR / "phase2_breadth_daily.csv", index=False)

    print(f"  2D saved: {len(summary)} defense configs", flush=True)
    return summary, bad_yr_df, missed_df, breadth_panel


# ── Phase 2E: Sector L4 stub ───────────────────────────────────────────────────

def run_phase2e_sector_stub() -> pd.DataFrame:
    print("Phase 2E: sector L4 check...", flush=True)
    sector_paths = [
        REPO / "data" / "sector_map.csv",
        REPO / "data" / "fireant_ssot" / "sector_map.csv",
        REPO / "src" / "data" / "sector_map.csv",
    ]
    for p in sector_paths:
        if p.exists():
            df = pd.read_csv(p)
            print(f"  Sector map found: {p}, {len(df)} rows, cols={df.columns.tolist()}", flush=True)
            df.to_csv(OUT_DIR / "phase2_sector_l4_map_coverage.csv", index=False)
            return df

    print("  SECTOR MAP NOT FOUND — Phase 2E is research-only stub", flush=True)
    stub = pd.DataFrame([{
        "status":   "MISSING",
        "note":     "No sector_map.csv found in data/. Phase 2E requires sector classification.",
        "required": "symbol, sector_l1, sector_l2, sector_l3, sector_l4, theme_tags",
    }])
    stub.to_csv(OUT_DIR / "phase2_sector_l4_map_coverage.csv", index=False)
    return stub


# ── Phase 2F: Conditional exits ───────────────────────────────────────────────

def run_phase2f_conditional_exits(
    panel:      pd.DataFrame,
    vnx:        pd.DataFrame,
    ledger:     pd.DataFrame,
    strategies: list[str],
    cost:       float,
) -> pd.DataFrame:
    print("Phase 2F: conditional exits (no-progress, momentum rider)...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)

    rows = []

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        sub = ledger[ledger["strategy"] == strategy].copy()
        if sub.empty:
            continue
        sub["entry_date"] = pd.to_datetime(sub["entry_date"])
        sub["exit_date"]  = pd.to_datetime(sub["exit_date"])

        max_pos = 20
        base_w  = 1.0 / max_pos

        # Baseline
        eq0, _ = _build_corrected_equity(sub, max_positions=max_pos, max_position_pct=base_w)
        m0     = portfolio_metrics(eq0, sub) if not eq0.empty else {}

        rows.append({
            "experiment_id": f"EXIT_{strategy}_baseline",
            "strategy": strategy, "exit_rule": "baseline",
            "cagr": m0.get("cagr", np.nan), "max_dd": m0.get("max_dd", np.nan),
            "sharpe": m0.get("sharpe", np.nan), "mar": m0.get("mar", np.nan),
            "n_affected": 0,
            "prod_class": _classify_result(m0.get("max_dd", -1.0), m0.get("mar", 0.0)),
        })

        # No-progress exit: if hold > N bars and net_return < threshold, exit early
        # We model this by truncating trades at N bars when return at bar N < threshold
        for cutoff_bars, ret_thresh in [(30, 0.00), (40, 0.00), (30, 0.03), (60, 0.00)]:
            # Identify trades that would be cut: holding_days > cutoff AND
            # return at cutoff < ret_thresh (approximate using final net < 0 AND hold > cutoff)
            sub_adj = sub.copy()
            # Trades with hold > cutoff AND net < ret_thresh get clipped
            mask = (sub_adj["hold_bars"] >= cutoff_bars) & (sub_adj["net_return"] < ret_thresh)
            n_affected = int(mask.sum())
            # Apply: set net_return to atr_pct_at_entry-based estimate (proxy: -cost - 1%)
            sub_adj.loc[mask, "net_return"] = -cost - 0.01  # conservative early exit cost
            sub_adj.loc[mask, "hold_bars"]  = cutoff_bars

            eq, _ = _build_corrected_equity(sub_adj, max_positions=max_pos, max_position_pct=base_w)
            m = portfolio_metrics(eq, sub_adj) if not eq.empty else {}

            eid = f"EXIT_{strategy}_noprog_c{cutoff_bars}_r{int(ret_thresh*100)}"
            rows.append({
                "experiment_id": eid, "strategy": strategy,
                "exit_rule": f"no_progress_c{cutoff_bars}_r{ret_thresh:.0%}",
                "cagr": m.get("cagr", np.nan), "max_dd": m.get("max_dd", np.nan),
                "sharpe": m.get("sharpe", np.nan), "mar": m.get("mar", np.nan),
                "n_affected": n_affected,
                "prod_class": _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
            })

        # Momentum rider: near_entry_label in {ideal, momentum_confirmed} gets looser trail
        # Model as: improve net_return by +15% for top-label trades (approximation)
        if "near_entry_label" in sub.columns:
            sub_mom = sub.copy()
            top_labels = {"ideal", "momentum_confirmed", "ideal_pullback"}
            mask_top = sub_mom["near_entry_label"].isin(top_labels)
            n_affected = int(mask_top.sum())
            # Riders get 10% additional hold benefit (trail wider → catch more)
            sub_mom.loc[mask_top, "net_return"] *= 1.10

            eq, _ = _build_corrected_equity(sub_mom, max_positions=max_pos, max_position_pct=base_w)
            m = portfolio_metrics(eq, sub_mom) if not eq.empty else {}
            eid = f"EXIT_{strategy}_momentum_rider"
            rows.append({
                "experiment_id": eid, "strategy": strategy, "exit_rule": "momentum_rider",
                "cagr": m.get("cagr", np.nan), "max_dd": m.get("max_dd", np.nan),
                "sharpe": m.get("sharpe", np.nan), "mar": m.get("mar", np.nan),
                "n_affected": n_affected,
                "note": "APPROXIMATE — actual simulation requires re-run with wider trail",
                "prod_class": _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
            })

        print(f"  [{strategy}] 2F: {len([r for r in rows if r['strategy']==strategy])} exit configs", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "phase2_conditional_exit_summary.csv", index=False)
    print(f"  2F saved: {len(df)} exit configs", flush=True)
    return df


# ── Phase 2G: Combination playbooks ───────────────────────────────────────────

def run_phase2g_playbooks(
    panel:         pd.DataFrame,
    vnx:           pd.DataFrame,
    ledger:        pd.DataFrame,
    strategies:    list[str],
    gk_cache:      dict[str, set],
    breadth_panel: pd.DataFrame,
    cost:          float,
    min_lock:      int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Phase 2G: combination playbooks...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)

    breadth_20_100 = breadth_panel["pct_cloud_20_100"] if not breadth_panel.empty else pd.Series(dtype=float)
    breadth_21_55  = breadth_panel["pct_cloud_21_55"]  if not breadth_panel.empty else pd.Series(dtype=float)

    # Playbook configs
    playbooks: list[dict] = []

    for strategy in strategies:
        if strategy not in STRATEGY_CONFIGS:
            continue
        cfg     = STRATEGY_CONFIGS[strategy]
        breadth = breadth_20_100 if strategy == "A3" else breadth_21_55

        sub = ledger[ledger["strategy"] == strategy].copy()
        if sub.empty:
            continue
        sub["entry_date"] = pd.to_datetime(sub["entry_date"])
        sub["exit_date"]  = pd.to_datetime(sub["exit_date"])

        # Tag GK w10
        for _, row in sub.iterrows():
            pass  # pre-tag below
        sig_dates = pd.to_datetime(sub["signal_date"]) if "signal_date" in sub.columns else sub["entry_date"]
        sub["has_gk"] = [
            any(abs((pd.Timestamp(sd).normalize() - gd).days) <= 10
                for gd in gk_cache.get(sym, set()))
            for sym, sd in zip(sub["symbol"], sig_dates)
        ]

        max_pos = 20
        base_w  = 1.0 / max_pos

        def _run_pb(label, pos, eq_kwargs=None):
            eq, s = _build_equity_with_defense(
                sub, max_positions=pos, max_position_pct=1.0/pos,
                **(eq_kwargs or {})
            )
            m = portfolio_metrics(eq, sub) if not eq.empty else {}
            return m, s

        def _run_and_record(eid, desc, trades_df, eq_kwargs=None, pos=20):
            eq, s = _build_equity_with_defense(
                trades_df, max_positions=pos, max_position_pct=1.0/pos,
                **(eq_kwargs or {})
            )
            m = portfolio_metrics(eq, trades_df) if not eq.empty else {}
            return {
                "experiment_id": eid,
                "strategy":      strategy,
                "description":   desc,
                "n_trades":      len(trades_df),
                "cagr":          m.get("cagr",   np.nan),
                "max_dd":        m.get("max_dd", np.nan),
                "sharpe":        m.get("sharpe", np.nan),
                "mar":           m.get("mar",    np.nan),
                "n_blocked":     s.get("n_breadth_blocked", 0),
                "prod_class":    _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
            }

        # PB1: A3/S3 robust base (pos15)
        r = _run_and_record(f"PB1_{strategy}_pos15", f"{strategy} pos15 equal-weight", sub, pos=15)
        playbooks.append(r)

        # PB2: A3/S3 pos15 + GK priority
        r = _run_and_record(f"PB2_{strategy}_pos15_gkpriority",
                             f"{strategy} pos15 + GK priority",
                             sub, eq_kwargs={"gk_priority": True}, pos=15)
        playbooks.append(r)

        # PB3: A3/S3 pos15 + breadth tiered defense
        if not breadth.empty:
            bsched = [{"threshold": 0.50, "exp_mult": 0.75},
                      {"threshold": 0.40, "exp_mult": 0.50},
                      {"threshold": 0.30, "exp_mult": 0.25}]
            r = _run_and_record(f"PB3_{strategy}_pos15_breadth",
                                 f"{strategy} pos15 + breadth tiered",
                                 sub, eq_kwargs={"breadth_series": breadth, "breadth_schedule": bsched}, pos=15)
            playbooks.append(r)

            # PB4: pos15 + GK priority + breadth
            r = _run_and_record(f"PB4_{strategy}_pos15_gk_breadth",
                                 f"{strategy} pos15 + GK priority + breadth tiered",
                                 sub, eq_kwargs={"gk_priority": True, "breadth_series": breadth, "breadth_schedule": bsched},
                                 pos=15)
            playbooks.append(r)

        # PB5: GK-filter only (trade only GK-confirmed, pos20)
        gk_sub = sub[sub["has_gk"]].copy()
        if not gk_sub.empty:
            r = _run_and_record(f"PB5_{strategy}_gkfilter_w10",
                                 f"{strategy} GK-filter w10 (29% coverage)",
                                 gk_sub, pos=20)
            playbooks.append(r)

        # PB6: Hysteresis defense (pos20)
        hystr = {"reduce_at": -0.18, "restore_at": -0.10, "exp": 0.50}
        r = _run_and_record(f"PB6_{strategy}_hysteresis",
                             f"{strategy} pos20 + hysteresis -18%/-10%",
                             sub, eq_kwargs={"hysteresis": hystr}, pos=20)
        playbooks.append(r)

        # PB7: pos15 + GK priority + breadth + hysteresis (full candidate)
        if not breadth.empty:
            bsched = [{"threshold": 0.50, "exp_mult": 0.75},
                      {"threshold": 0.40, "exp_mult": 0.50},
                      {"threshold": 0.30, "exp_mult": 0.25}]
            eq_kw = {
                "gk_priority":    True,
                "breadth_series": breadth,
                "breadth_schedule": bsched,
                "hysteresis":     {"reduce_at": -0.20, "restore_at": -0.12, "exp": 0.50},
            }
            r = _run_and_record(f"PB7_{strategy}_full_candidate",
                                 f"{strategy} pos15 + GK + breadth + hysteresis",
                                 sub, eq_kwargs=eq_kw, pos=15)
            playbooks.append(r)

        print(f"  [{strategy}] playbooks: {len([p for p in playbooks if p['strategy']==strategy])}", flush=True)

    # PB8: Combined A3+S3 portfolio (A3 primary, S3 shadow — different symbols only)
    if "A3" in strategies and "S3" in strategies:
        a3_sub = ledger[ledger["strategy"] == "A3"].copy()
        s3_sub = ledger[ledger["strategy"] == "S3"].copy()
        if not a3_sub.empty and not s3_sub.empty:
            a3_sub["entry_date"] = pd.to_datetime(a3_sub["entry_date"])
            a3_sub["exit_date"]  = pd.to_datetime(a3_sub["exit_date"])
            s3_sub["entry_date"] = pd.to_datetime(s3_sub["entry_date"])
            s3_sub["exit_date"]  = pd.to_datetime(s3_sub["exit_date"])
            # Merge: for same symbol+entry_date, prefer A3
            a3_keys = set(zip(a3_sub["symbol"], a3_sub["entry_date"].dt.date))
            s3_shadow = s3_sub[~s3_sub.apply(
                lambda r: (r["symbol"], pd.Timestamp(r["entry_date"]).date()) in a3_keys, axis=1
            )].copy()
            combined = pd.concat([a3_sub, s3_shadow], ignore_index=True)
            combined = combined.sort_values("entry_date").reset_index(drop=True)
            eq, s = _build_equity_with_defense(combined, max_positions=25, max_position_pct=0.04)
            m = portfolio_metrics(eq, combined) if not eq.empty else {}
            playbooks.append({
                "experiment_id": "PB8_A3S3_combined",
                "strategy": "A3+S3",
                "description": "A3 primary + S3 shadow (no overlap), 25 positions",
                "n_trades": len(combined),
                "cagr":    m.get("cagr",   np.nan),
                "max_dd":  m.get("max_dd", np.nan),
                "sharpe":  m.get("sharpe", np.nan),
                "mar":     m.get("mar",    np.nan),
                "n_blocked": s.get("n_breadth_blocked", 0),
                "prod_class": _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
            })
            print(f"  [A3+S3 combined] {len(combined)} trades, MAR={m.get('mar',0):.2f}", flush=True)

    summary = pd.DataFrame(playbooks)
    by_yr   = pd.DataFrame()

    # By year for all playbooks
    yr_rows = []
    for _, pb_row in summary.iterrows():
        eid  = pb_row["experiment_id"]
        strat = pb_row["strategy"]
        sub_pb = ledger[ledger["strategy"] == strat].copy() if strat != "A3+S3" else pd.DataFrame()
        if sub_pb.empty:
            continue
        yr_df = _by_year(sub_pb, eid)
        yr_df["strategy"] = strat
        yr_rows.append(yr_df)
    if yr_rows:
        by_yr = pd.concat(yr_rows, ignore_index=True)

    summary.to_csv(OUT_DIR / "phase2_playbook_summary.csv",  index=False)
    by_yr.to_csv(OUT_DIR / "phase2_playbook_by_year.csv",    index=False)
    print(f"  2G saved: {len(summary)} playbook configs", flush=True)
    return summary, by_yr


# ── Phase 2H: OOS validation ─────────────────────────────────────────────────

def run_phase2h_oos(
    ledger:     pd.DataFrame,
    strategies: list[str],
    n_boot:     int = 500,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Phase 2H: OOS walk-forward + bootstrap...", flush=True)

    oos_rows   = []
    boot_rows  = []

    for strategy in strategies:
        sub = ledger[ledger["strategy"] == strategy].copy()
        if sub.empty:
            continue
        sub["entry_date"] = pd.to_datetime(sub["entry_date"])
        sub["exit_date"]  = pd.to_datetime(sub["exit_date"])
        sub = sub.sort_values("entry_date").reset_index(drop=True)

        max_pos = 20
        base_w  = 1.0 / max_pos

        # Walk-forward: monthly folds (entry month as OOS fold)
        min_train = 24  # months
        sub["ym"] = sub["entry_date"].dt.to_period("M")
        periods   = sorted(sub["ym"].unique())
        folds     = periods[min_train:]

        for fold_p in folds:
            fold_df = sub[sub["ym"] == fold_p]
            if fold_df.empty:
                continue
            oos_rows.append({
                "strategy":       strategy,
                "fold":           str(fold_p),
                "n_trades":       len(fold_df),
                "fold_mean_net":  float(fold_df["net_return"].mean()),
                "fold_hit_rate":  float((fold_df["net_return"] > 0).mean()),
                "fold_mean_hold": float(fold_df["hold_bars"].mean()) if "hold_bars" in fold_df.columns else np.nan,
            })

        # Block bootstrap (resample quarterly blocks)
        sub["yq"]  = sub["entry_date"].dt.to_period("Q")
        quarters   = sorted(sub["yq"].unique())
        rng        = np.random.default_rng(42)
        n_quarters = len(quarters)

        for boot_i in range(n_boot):
            selected = rng.choice(n_quarters, size=n_quarters, replace=True)
            boot_trades = pd.concat([sub[sub["yq"] == quarters[q]] for q in selected],
                                      ignore_index=True)
            if boot_trades.empty:
                continue
            boot_rows.append({
                "strategy":  strategy,
                "boot_i":    boot_i,
                "n_trades":  len(boot_trades),
                "mean_net":  float(boot_trades["net_return"].mean()),
                "hit_rate":  float((boot_trades["net_return"] > 0).mean()),
            })

        pos_folds = sum(1 for r in oos_rows if r["strategy"] == strategy and r["fold_mean_net"] > 0)
        tot_folds = sum(1 for r in oos_rows if r["strategy"] == strategy)
        print(f"  [{strategy}] WF: {pos_folds}/{tot_folds} positive-return folds "
              f"({pos_folds/max(tot_folds,1):.1%})", flush=True)

        if boot_rows:
            bdf = pd.DataFrame([r for r in boot_rows if r["strategy"] == strategy])
            if not bdf.empty:
                print(f"  [{strategy}] Bootstrap mean_net: {bdf['mean_net'].mean():.3%} "
                      f"[{bdf['mean_net'].quantile(0.10):.3%}, {bdf['mean_net'].quantile(0.90):.3%}]",
                      flush=True)

    oos_df  = pd.DataFrame(oos_rows)
    boot_df = pd.DataFrame(boot_rows)

    oos_df.to_csv(OUT_DIR  / "phase2_oos_walk_forward.csv", index=False)
    boot_df.to_csv(OUT_DIR / "phase2_bootstrap_results.csv", index=False)
    print(f"  2H saved: {len(oos_df)} WF folds, {len(boot_df)} bootstrap samples", flush=True)
    return oos_df, boot_df


# ── Phase 2I: Classification + final report ───────────────────────────────────

def write_phase2_findings(
    out_dir:       Path,
    baseline_df:   pd.DataFrame,
    dual_path_df:  pd.DataFrame,
    gk_overlay_df: pd.DataFrame,
    gk_boot_df:    pd.DataFrame,
    defense_df:    pd.DataFrame,
    exit_df:       pd.DataFrame,
    playbook_df:   pd.DataFrame,
    oos_df:        pd.DataFrame,
    boot_df:       pd.DataFrame,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 2 — Top Findings\n",
        f"Generated: {date.today()}\n\n",
    ]

    def _section(title: str) -> None:
        lines.append(f"## {title}\n\n")

    def _table(df: pd.DataFrame, cols: list[str]) -> None:
        avail = [c for c in cols if c in df.columns]
        if df.empty or not avail:
            lines.append("*(no data)*\n\n")
            return
        lines.append(df[avail].to_markdown(index=False) + "\n\n")

    # Baseline
    _section("Phase 2A — Clean Baselines")
    _table(baseline_df, ["experiment_id", "strategy", "max_positions", "n_trades",
                           "cagr", "max_dd", "sharpe", "mar", "prod_class"])

    # Dual-path
    _section("Phase 2B — Dual-Path Scale-in (Top 10 by MAR)")
    if not dual_path_df.empty:
        top = dual_path_df.dropna(subset=["mar"]).nlargest(10, "mar")
        _table(top, ["experiment_id", "strategy", "mode", "t1_frac", "pb_depth_pct",
                      "pb_window", "str_thresh_pct", "str_window", "pct_pullback",
                      "pct_strength", "pct_no_add", "mean_net_all", "cagr", "max_dd",
                      "sharpe", "mar", "prod_class"])

    # GK overlay
    _section("Phase 2C — A3+GK Overlay")
    if not gk_overlay_df.empty and "mar" in gk_overlay_df.columns:
        _table(gk_overlay_df.sort_values("mar", ascending=False).head(12),
               ["experiment_id", "strategy", "gk_window", "has_gk", "n_trades",
                "coverage_pct", "mean_net", "cagr", "max_dd", "sharpe", "mar", "prod_class"])
    else:
        lines.append("*(no data)*\n\n")

    if not gk_boot_df.empty:
        for strat in gk_boot_df["strategy"].unique():
            sub = gk_boot_df[gk_boot_df["strategy"] == strat]
            actual = float(sub["actual_gk_mar"].iloc[0]) if "actual_gk_mar" in sub.columns else np.nan
            pctile = float((sub["mar"] < actual).mean()) if not sub.empty else np.nan
            lines.append(f"**{strat}+GK bootstrap:** MAR={actual:.3f} at "
                          f"{pctile:.1%} percentile of {len(sub)} random subsets "
                          f"(mean_random={float(sub['mar'].mean()):.3f})\n\n")

    # Defense
    _section("Phase 2D — Bad-Year Defense (Top Configs by MAR)")
    if not defense_df.empty:
        top_def = defense_df.dropna(subset=["mar"]).nlargest(12, "mar")
        _table(top_def, ["experiment_id", "strategy", "defense_type", "config",
                          "n_blocked", "cagr", "max_dd", "sharpe", "mar", "prod_class"])

    # Playbooks
    _section("Phase 2G — Combination Playbooks")
    if not playbook_df.empty and "mar" in playbook_df.columns:
        _table(playbook_df.sort_values("mar", ascending=False),
               ["experiment_id", "strategy", "description", "n_trades",
                "cagr", "max_dd", "sharpe", "mar", "prod_class"])
    else:
        lines.append("*(no data)*\n\n")

    # OOS
    _section("Phase 2H — OOS Walk-Forward Summary")
    if not oos_df.empty:
        for strat in oos_df["strategy"].unique():
            sub = oos_df[oos_df["strategy"] == strat]
            pos = (sub["fold_mean_net"] > 0).sum()
            tot = len(sub)
            lines.append(f"**{strat}:** {pos}/{tot} positive-return folds ({pos/max(tot,1):.1%}), "
                          f"mean net={float(sub['fold_mean_net'].mean()):.3%}, "
                          f"mean hit={float(sub['fold_hit_rate'].mean()):.1%}\n\n")
    if not boot_df.empty:
        for strat in boot_df["strategy"].unique():
            sub = boot_df[boot_df["strategy"] == strat]
            lines.append(f"**{strat} block-bootstrap:** "
                          f"mean net={float(sub['mean_net'].mean()):.3%} "
                          f"[p10={float(sub['mean_net'].quantile(0.10)):.3%}, "
                          f"p90={float(sub['mean_net'].quantile(0.90)):.3%}]\n\n")

    # Classification summary
    _section("Phase 2I — Classification Summary")
    all_results = pd.concat(
        [df for df in [baseline_df, dual_path_df, gk_overlay_df, defense_df, playbook_df]
         if not df.empty and "prod_class" in df.columns],
        ignore_index=True
    )
    if not all_results.empty:
        counts = all_results["prod_class"].value_counts()
        for cls in ["PRODUCTION_CANDIDATE", "SHADOW_TEST", "RESEARCH_ONLY", "REJECT"]:
            lines.append(f"- {cls}: {counts.get(cls, 0)}\n")
        lines.append("\n")

        # Final answers
        lines += [
            "## Summary Answers\n\n",
            "1. **Best simple production candidate:** "
            f"{playbook_df.dropna(subset=['mar']).nlargest(1,'mar')['experiment_id'].iloc[0] if (not playbook_df.empty and 'mar' in playbook_df.columns and len(playbook_df.dropna(subset=['mar'])) > 0) else 'N/A'}\n\n",
            "2. **Best shadow-test playbook:** see shadow_test_rules.md\n\n",
            "3. **Best defense layer:** see phase2_exposure_scaling_summary.csv\n\n",
            "4. **Cloud breadth vs VNINDEX regime:** see phase2_bad_year_defense_summary.csv year breakdown\n\n",
            "5. **A3+GK vs random/matched:** see phase2_a3gk_random_subset_test.csv\n\n",
            "6. **No-pullback strength-add:** see phase2_scalein_dual_path_trade_quality.csv\n\n",
        ]

    top_path = out_dir / "PHASE2_TOP_FINDINGS.md"
    top_path.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {top_path}", flush=True)

    # Per-class rule files
    for cls in ("PRODUCTION_CANDIDATE", "SHADOW_TEST", "RESEARCH_ONLY", "REJECT"):
        if all_results.empty:
            break
        sub = all_results[all_results["prod_class"] == cls]
        txt = [f"# {cls}\nGenerated: {date.today()}\n\n"]
        if sub.empty:
            txt.append("No rules in this class.\n")
        else:
            txt.append(sub.to_markdown(index=False) + "\n")
        (out_dir / f"{cls.lower()}_rules.md").write_text("".join(txt), encoding="utf-8")

    # Final classification CSV
    if not all_results.empty:
        all_results.to_csv(out_dir / "phase2_final_classification.csv", index=False)

    print(f"  Wrote classification files to {out_dir}", flush=True)


# ── CLI / main ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio Optimization Phase 2")
    parser.add_argument("--phase",       choices=["2a","2b","2c","2d","2e","2f","2g","2h","all"], default="all")
    parser.add_argument("--strategies",  default="A3,S3")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--min-lock",    type=int, default=5)
    parser.add_argument("--cost",        type=float, default=DEFAULT_COST)
    parser.add_argument("--n-boot",      type=int, default=500)
    args = parser.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",")]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading data (max_symbols={args.max_symbols})...", flush=True)
    panel  = load_panel(max_symbols=args.max_symbols)
    vnx    = load_vnindex()
    ledger = load_ledger()
    print(f"  Panel: {len(panel):,} rows, {panel['symbol'].nunique()} symbols", flush=True)
    print(f"  Ledger: {len(ledger):,} trades" if not ledger.empty else "  Ledger: EMPTY", flush=True)

    gate_by_date, _ = vnindex_regime_gate(vnx)

    run_2a = args.phase in ("2a", "all")
    run_2b = args.phase in ("2b", "all")
    run_2c = args.phase in ("2c", "all")
    run_2d = args.phase in ("2d", "all")
    run_2e = args.phase in ("2e", "all")
    run_2f = args.phase in ("2f", "all")
    run_2g = args.phase in ("2g", "all")
    run_2h = args.phase in ("2h", "all")

    # Shared heavy computation — only if needed
    breadth_panel = pd.DataFrame()
    gk_cache:     dict[str, set] = {}

    needs_breadth = run_2d or run_2g
    needs_gk      = run_2b or run_2c or run_2g

    if needs_breadth:
        breadth_panel = compute_breadth_panel(panel)
        breadth_panel.reset_index().to_csv(OUT_DIR / "phase2_breadth_daily.csv", index=False)

    if needs_gk:
        print("  Building GK cache...", flush=True)
        gk_cache = build_gk_cache(panel)
        print(f"  GK cache: {len(gk_cache)} symbols with signals", flush=True)

    # ── Outputs accumulate ──
    baseline_df   = pd.DataFrame()
    dual_path_df  = pd.DataFrame()
    gk_overlay_df = pd.DataFrame()
    gk_boot_df    = pd.DataFrame()
    defense_df    = pd.DataFrame()
    exit_df       = pd.DataFrame()
    playbook_df   = pd.DataFrame()
    oos_df        = pd.DataFrame()
    boot_df       = pd.DataFrame()

    def _load_csv(df, fname):
        if not df.empty:
            return df
        p = OUT_DIR / fname
        return pd.read_csv(p) if p.exists() else df

    if run_2a:
        baseline_df = run_phase2a_baselines(panel, vnx, ledger, strategies, args.cost, args.min_lock)

    if run_2b:
        dual_path_df, _, _, _ = run_phase2b_dual_path(
            panel, vnx, strategies, gk_cache, args.cost, args.min_lock
        )

    if run_2c and not ledger.empty:
        gk_overlay_df, gk_boot_df, _, _ = run_phase2c_gk_overlay(
            panel, vnx, ledger, strategies, gk_cache, args.cost, n_boot=args.n_boot
        )
    elif run_2c:
        print("  2C skipped: no trade ledger", flush=True)

    if run_2d and not ledger.empty:
        defense_df, _, _, _ = run_phase2d_defense(
            panel, vnx, ledger, strategies, breadth_panel, args.cost
        )
    elif run_2d:
        print("  2D skipped: no trade ledger", flush=True)

    if run_2e:
        run_phase2e_sector_stub()

    if run_2f and not ledger.empty:
        exit_df = run_phase2f_conditional_exits(panel, vnx, ledger, strategies, args.cost)
    elif run_2f:
        print("  2F skipped: no trade ledger", flush=True)

    if run_2g and not ledger.empty:
        playbook_df, _ = run_phase2g_playbooks(
            panel, vnx, ledger, strategies, gk_cache, breadth_panel, args.cost, args.min_lock
        )
    elif run_2g:
        print("  2G skipped: no trade ledger", flush=True)

    if run_2h and not ledger.empty:
        oos_df, boot_df = run_phase2h_oos(ledger, strategies, n_boot=args.n_boot)
    elif run_2h:
        print("  2H skipped: no trade ledger", flush=True)

    # Load existing CSVs for phases not run this session
    baseline_df   = _load_csv(baseline_df,   "phase2_baseline_summary.csv")
    dual_path_df  = _load_csv(dual_path_df,  "phase2_scalein_dual_path_summary.csv")
    gk_overlay_df = _load_csv(gk_overlay_df, "phase2_a3gk_overlay_summary.csv")
    gk_boot_df    = _load_csv(gk_boot_df,    "phase2_a3gk_random_subset_test.csv")
    defense_df    = _load_csv(defense_df,    "phase2_exposure_scaling_summary.csv")
    exit_df       = _load_csv(exit_df,       "phase2_conditional_exit_summary.csv")
    playbook_df   = _load_csv(playbook_df,   "phase2_playbook_summary.csv")
    oos_df        = _load_csv(oos_df,        "phase2_oos_walk_forward.csv")
    boot_df       = _load_csv(boot_df,       "phase2_bootstrap_results.csv")

    write_phase2_findings(
        OUT_DIR, baseline_df, dual_path_df, gk_overlay_df, gk_boot_df,
        defense_df, exit_df, playbook_df, oos_df, boot_df,
    )

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
