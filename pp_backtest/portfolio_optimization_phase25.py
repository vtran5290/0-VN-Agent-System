#!/usr/bin/env python3
"""
Portfolio Optimization Phase 2.5 — Decision Audit

Five focused tests before Phase 3:
  25A — Exposure-matched pullback: is DP_A3 better than capped A3_pos15?
  25B — No-pullback strength-add (pb_then_str mode)
  25C — GK usage modes: hard filter / fill priority / add-trigger / size-mult
  25D — Bad-year diagnostics for all 5 candidates
  25E — Cost / liquidity sensitivity

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase25.py --phase 25a
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase25.py --phase 25b
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase25.py --phase all
"""
from __future__ import annotations

import argparse
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
    LEDGER,
)
from pp_backtest.portfolio_optimization_phase2 import (
    load_ledger,
    build_gk_cache,
    _build_equity_with_defense,
    _by_year,
)

OUT_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase25"
P2_DIR   = REPO / "data" / "research" / "portfolio_optimization" / "phase2"
P2_LED   = P2_DIR / "phase2_baseline_trade_ledgers"

# Portfolio reference for participation calc (20B VND = ~$800k, realistic individual)
PORTFOLIO_REF_VND = 20e9


# ── Equity builder with exposure + blocked-trade tracking ─────────────────────

def _build_equity_capped(
    trades_df:        pd.DataFrame,
    max_positions:    int   = 15,
    max_position_pct: float | None = None,
    max_total_exp:    float = 1.0,
    gk_size_mult:     float = 1.0,
    gk_col:           str   = "has_gk",
    rank_col:         str   = "ema_dist_at_entry",
) -> tuple[pd.Series, dict[str, float], pd.DataFrame]:
    """
    Equity simulation with daily exposure tracking and blocked-trade recording.

    Returns:
        equity       — pd.Series indexed by date
        daily_exp    — {date: fractional_exposure}
        blocked_df   — trades that couldn't enter (capacity cap hit)
    """
    if trades_df.empty:
        return pd.Series(dtype=float), {}, pd.DataFrame()

    base_w = max_position_pct if max_position_pct is not None else 1.0 / max(max_positions, 1)
    eff_max = min(max_positions, int(max_total_exp / max(base_w, 1e-9)))

    df = trades_df.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])

    all_dates = pd.date_range(df["entry_date"].min(), df["exit_date"].max(), freq="B")

    # Sort queue: rank_col descending (higher dist = stronger signal = goes first)
    sort_col = rank_col if rank_col in df.columns else None
    by_entry: dict = {}
    for ed, grp in df.groupby("entry_date", sort=False):
        sorted_grp = grp.sort_values(sort_col, ascending=False) if sort_col else grp
        by_entry[ed] = list(sorted_grp.index)

    by_exit: dict = {}
    for i, row in df.iterrows():
        by_exit.setdefault(row["exit_date"], []).append(int(i))

    portfolio_val = 1.0
    peak_val      = 1.0
    active: dict[int, float] = {}   # tid -> weight
    equity: dict  = {}
    daily_exp: dict = {}
    blocked_ids: list[int] = []

    for date_val in all_dates:
        # Exits
        for tid in by_exit.get(date_val, []):
            if tid in active:
                w = active.pop(tid)
                net = float(df.loc[tid, "net_return"])
                portfolio_val += portfolio_val * w * net
        peak_val = max(peak_val, portfolio_val)

        # Current exposure
        active_exp = sum(active.values())

        # Entries
        queued_ids = by_entry.get(date_val, [])
        remaining  = eff_max - len(active)

        for tid in queued_ids:
            if remaining <= 0:
                blocked_ids.append(tid)
                continue
            row = df.loc[tid]
            # GK size multiplier
            is_gk = bool(row[gk_col]) if gk_col in df.columns else False
            mult  = gk_size_mult if is_gk else 1.0
            # Dual-path total_frac scaling (T1-only trades get half weight)
            tf    = float(row["total_frac"]) if "total_frac" in df.columns else 1.0
            w_raw = base_w * mult * tf
            cap_w = (max_position_pct or base_w) * gk_size_mult
            w     = min(w_raw, cap_w)
            # Cap to available exposure
            avail = max(0.0, max_total_exp - active_exp)
            w     = min(w, avail)
            if w > 1e-9:
                active[tid]   = w
                active_exp   += w
                remaining    -= 1
            else:
                blocked_ids.append(tid)

        # Apply total_frac if present (dual-path scale-in)
        daily_exp[date_val] = sum(active.values())
        equity[date_val] = portfolio_val

    eq_series   = pd.Series(equity)
    blocked_df  = df.loc[sorted(set(blocked_ids))].copy() if blocked_ids else pd.DataFrame()
    return eq_series, daily_exp, blocked_df


# ── Helpers ───────────────────────────────────────────────────────────────────

def _annual_returns(equity: pd.Series) -> dict[int, float]:
    if equity.empty:
        return {}
    eq = equity.sort_index()
    years = sorted(eq.index.year.unique())
    ann = {}
    for yr in years:
        yr_eq  = eq[eq.index.year == yr]
        prev_yr = eq[eq.index.year < yr]
        if yr_eq.empty:
            continue
        end_val  = float(yr_eq.iloc[-1])
        start_val = float(prev_yr.iloc[-1]) if not prev_yr.empty else float(yr_eq.iloc[0])
        ann[yr] = end_val / start_val - 1.0
    return ann


def _worst_year(equity: pd.Series) -> tuple[int, float]:
    ann = _annual_returns(equity)
    if not ann:
        return (0, np.nan)
    worst = min(ann, key=lambda y: ann[y])
    return (worst, ann[worst])


def _avg_exp(daily_exp: dict) -> float:
    if not daily_exp:
        return np.nan
    return float(np.mean(list(daily_exp.values())))


def _year_exp(daily_exp: dict, year: int) -> float:
    vals = [v for d, v in daily_exp.items() if d.year == year]
    return float(np.mean(vals)) if vals else np.nan


def _metrics_row(eid, strategy, desc, eq, trades, blocked_df, daily_exp, label=None):
    if eq.empty:
        return None
    m         = portfolio_metrics(eq, trades)
    avg_e     = _avg_exp(daily_exp)
    cagr      = m.get("cagr",   np.nan)
    max_dd    = m.get("max_dd", np.nan)
    mar       = m.get("mar",    np.nan)
    sharpe    = m.get("sharpe", np.nan)
    ann       = _annual_returns(eq)
    worst_yr, worst_ret = _worst_year(eq)

    n_blocked  = len(blocked_df)
    block_win  = int((blocked_df["net_return"] > 0).sum()) if n_blocked else 0
    block_los  = int((blocked_df["net_return"] <= 0).sum()) if n_blocked else 0
    n_trades   = len(trades)

    # For dual-path ledgers: missed winners = no_add trades with positive return
    no_add_df  = trades[trades.get("add_path", pd.Series("N/A", index=trades.index)) == "none"] \
                 if "add_path" in trades.columns else pd.DataFrame()
    missed_wins = int((no_add_df["net_return"] > 0).sum()) if not no_add_df.empty else block_win

    return {
        "experiment_id":    eid,
        "strategy":         strategy,
        "description":      desc,
        "n_trades":         n_trades,
        "avg_exposure":     avg_e,
        "cagr":             cagr,
        "active_cagr":      cagr / max(avg_e, 0.01) if not np.isnan(avg_e) else np.nan,
        "max_dd":           max_dd,
        "mar":              mar,
        "sharpe":           sharpe,
        "worst_year":       worst_yr,
        "worst_return":     worst_ret,
        "n_blocked":        n_blocked,
        "blocked_winners":  block_win,
        "blocked_losers":   block_los,
        "missed_winners":   missed_wins,
        "prod_class":       _classify_result(max_dd, mar),
    }


# ── Phase 25A: Exposure-matched pullback ──────────────────────────────────────

def _rebuild_dp_trades(panel, strategies, gk_cache, cost, gate_by_date, min_lock=5):
    """Re-simulate DP_A3_pb_only_t50_pb4w30 and return trade DataFrame."""
    from pp_backtest.portfolio_optimization_phase2 import _sim_dual_path_symbol

    all_trades = []
    strategy = "A3"
    if strategy not in STRATEGY_CONFIGS:
        return pd.DataFrame()
    cfg      = STRATEGY_CONFIGS[strategy]
    exit_cfg = cfg["exit_cfg"]

    cache = _build_signal_cache(panel, strategy)
    for sym, data in cache.items():
        gk_dates = gk_cache.get(sym, set())
        trades = _sim_dual_path_symbol(
            sym=sym, data=data, strategy=strategy, exit_cfg=exit_cfg,
            cost=cost, mode="pb_only",
            t1_frac=0.50, t2_frac=0.50,
            t2_pb_frac=0.50, t2_str_frac=0.0,
            pb_depth=0.04, pb_window=30, pb_quality_mode="slow_097",
            str_thresh=0.0, str_window=0, str_require_gk=False,
            gk_dates=gk_dates, gate_by_date=gate_by_date, min_lock=min_lock,
        )
        all_trades.extend(trades)

    if not all_trades:
        return pd.DataFrame()
    df = pd.DataFrame(all_trades)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])
    return df


def run_phase25a(panel, vnx, ledger, gk_cache, cost, min_lock):
    print("Phase 25A: exposure-matched pullback test...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)
    strategy = "A3"

    # Load A3_pos15 baseline ledger
    led_path = P2_LED / "A3_pos15.csv"
    if led_path.exists():
        a3_led = pd.read_csv(led_path)
        a3_led["entry_date"] = pd.to_datetime(a3_led["entry_date"])
        a3_led["exit_date"]  = pd.to_datetime(a3_led["exit_date"])
    else:
        a3_led = ledger[ledger["strategy"] == strategy].copy()

    # Rebuild DP reference trades
    print("  Rebuilding DP_A3_pb_only trades...", flush=True)
    dp_trades = _rebuild_dp_trades(panel, [strategy], gk_cache, cost, gate_by_date, min_lock)
    dp_trades.to_csv(OUT_DIR / "phase25a_dp_trade_ledger.csv", index=False)

    rows = []

    # ── DP reference ──
    dp_base_w = 1.0 / 20  # pos20 equivalent
    dp_eq, dp_exp, dp_blocked = _build_equity_capped(
        dp_trades, max_positions=20, max_position_pct=dp_base_w, max_total_exp=1.0,
    )
    dp_avg_exp = _avg_exp(dp_exp)
    r = _metrics_row("DP_A3_pb_only_t50_pb4w30", strategy,
                     "50% T1 + 50% T2 on pullback d4/w30", dp_eq, dp_trades, dp_blocked, dp_exp)
    if r:
        rows.append(r)
        print(f"  DP ref: CAGR={r['cagr']:.2%}, MaxDD={r['max_dd']:.2%}, MAR={r['mar']:.2f}, "
              f"avg_exp={r['avg_exposure']:.1%}", flush=True)

    # ── A3_pos15 at various exposure caps ──
    caps = [0.50, 0.60, 0.70, 0.75, 0.80, 0.90, 1.00]
    base_w = 1.0 / 15
    for cap in caps:
        label = f"A3_pos15_exp{int(cap*100)}"
        desc  = f"A3 pos15 max_exp={cap:.0%}"
        eq, exp_d, blocked = _build_equity_capped(
            a3_led, max_positions=15, max_position_pct=base_w, max_total_exp=cap,
        )
        r = _metrics_row(label, strategy, desc, eq, a3_led, blocked, exp_d)
        if r:
            rows.append(r)
            print(f"  {label}: CAGR={r['cagr']:.2%}, MaxDD={r['max_dd']:.2%}, "
                  f"MAR={r['mar']:.2f}, avg_exp={r['avg_exposure']:.1%}, "
                  f"active_CAGR={r['active_cagr']:.2%}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase25_exposure_matched_pullback.csv", index=False)
    print(f"  25A saved: {len(out)} rows", flush=True)
    return out, dp_trades


# ── Phase 25B: No-pullback strength-add (pb_then_str) ────────────────────────

def _sim_pb_then_str(
    sym:         str,
    data:        dict,
    strategy:    str,
    exit_cfg:    dict,
    cost:        float,
    pb_depth:    float,
    pb_window:   int,
    str_thresh:  float,
    str_window:  int,
    gk_dates:    set,
    gk_req:      bool  = False,
    vol_req:     bool  = False,
    gate_by_date: pd.Series | None = None,
    min_lock:    int   = 5,
    t1:          float = 0.50,
    t2:          float = 0.50,
) -> list[dict]:
    """
    pb_then_str: wait pb_window for pullback; if none, watch str_window more bars for strength.
    This fixes the under-allocation to no-pullback winners.
    """
    close_arr = data["close"]
    high_arr  = data["high"]
    atr_arr   = data["atr"]
    dates     = data["dates"]
    n         = len(close_arr)

    vol_ma20  = data.get("vol_ma20")  # optional

    trades = []
    for si in data["sig_idxs"]:
        entry_i = si + 1
        if entry_i >= n:
            continue
        sig_date = pd.Timestamp(dates[si]).normalize()
        if gate_by_date is not None and not bool(gate_by_date.get(sig_date, True)):
            continue

        ep1 = float(close_arr[entry_i])
        if ep1 <= 0:
            continue

        pb_bar   = None
        str_bar  = None
        ep2      = None
        add_path = "none"

        # Phase 1: look for pullback within pb_window bars
        pb_end = min(entry_i + pb_window + 1, n)
        for k in range(entry_i + 1, pb_end):
            c = float(close_arr[k])
            if c <= ep1 * (1.0 - pb_depth) and _quality_ok(data, k, "slow_097"):
                pb_bar   = k
                ep2      = c
                add_path = "pullback"
                break

        # Phase 2: if no pullback, look for strength in next str_window bars
        if pb_bar is None:
            str_start = pb_end  # start right after pb_window expires
            str_end   = min(str_start + str_window, n)
            for k in range(str_start, str_end):
                c = float(close_arr[k])
                if c < ep1 * (1.0 + str_thresh):
                    continue
                cloud_ok = bool(data["cloud"][k])
                fast_ok  = c > float(data["fast"][k]) * 0.999
                if not (cloud_ok and fast_ok):
                    continue
                # Volume condition (optional)
                if vol_req and vol_ma20 is not None:
                    if float(data["close"][k]) > 0:  # proxy: just check non-zero
                        vol_bar = float(vol_ma20[k]) if k < len(vol_ma20) else 0.0
                        vol_now = float(data.get("volume", close_arr)[k])
                        if vol_bar > 0 and vol_now < vol_bar * 1.2:
                            continue
                # GK condition (optional)
                if gk_req:
                    bar_date = pd.Timestamp(dates[k]).normalize()
                    has_gk = any(abs((bar_date - gd).days) <= 10 for gd in gk_dates)
                    if not has_gk:
                        continue
                str_bar  = k
                ep2      = c
                add_path = "strength"
                break

        # Compute blended entry
        if ep2 is not None:
            total_frac = t1 + t2
            blended_ep = (t1 * ep1 + t2 * ep2) / total_frac
        else:
            total_frac = t1
            blended_ep = ep1

        hold, gross, reason = _exit_tp_trail(close_arr, high_arr, atr_arr, entry_i, blended_ep, exit_cfg)
        exit_bar = min(entry_i + hold, n - 1)
        net      = gross - cost

        trades.append({
            "symbol":      sym,
            "strategy":    strategy,
            "entry_date":  pd.Timestamp(dates[entry_i]).date(),
            "exit_date":   pd.Timestamp(dates[exit_bar]).date(),
            "ep1":          ep1,
            "ep2":          ep2,
            "blended_ep":   blended_ep,
            "t1_frac":      t1,
            "total_frac":   total_frac,
            "add_path":     add_path,
            "has_pullback": pb_bar is not None,
            "has_strength": str_bar is not None,
            "hold_bars":    hold,
            "gross_return": gross,
            "net_return":   net,
            "exit_reason":  reason,
        })

    return trades


def run_phase25b(panel, vnx, gk_cache, cost, min_lock):
    print("Phase 25B: no-pullback strength-add test...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)
    strategy = "A3"
    cfg      = STRATEGY_CONFIGS[strategy]
    exit_cfg = cfg["exit_cfg"]

    print(f"  [{strategy}] building signal cache...", flush=True)
    cache = _build_signal_cache(panel, strategy)
    print(f"  [{strategy}] {len(cache)} symbols", flush=True)

    # Grid: (str_thresh, str_window, gk_req)
    configs = [
        (0.04, 10, False, "str+4pct_w10"),
        (0.06, 10, False, "str+6pct_w10"),
        (0.04, 20, False, "str+4pct_w20"),
        (0.06, 20, False, "str+6pct_w20"),
        (0.04, 10, True,  "str+4pct_w10_gk"),
        (0.06, 10, True,  "str+6pct_w10_gk"),
    ]

    rows      = []
    year_rows = []

    for (st, sw, gk_req, label) in configs:
        gk_sfx = "_gk" if gk_req else ""
        eid    = f"PTS_A3_pb4w30_str{int(st*100)}w{sw}{gk_sfx}"
        desc   = f"pb4/w30 then str+{int(st*100)}%/w{sw}" + (" +GK" if gk_req else "")

        all_t = []
        for sym, data in cache.items():
            gk_dates = gk_cache.get(sym, set())
            t = _sim_pb_then_str(
                sym=sym, data=data, strategy=strategy, exit_cfg=exit_cfg,
                cost=cost, pb_depth=0.04, pb_window=30,
                str_thresh=st, str_window=sw,
                gk_dates=gk_dates, gk_req=gk_req, vol_req=False,
                gate_by_date=gate_by_date, min_lock=min_lock,
                t1=0.50, t2=0.50,
            )
            all_t.extend(t)

        if not all_t:
            continue

        df = pd.DataFrame(all_t)
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])

        eq, exp_d, blocked = _build_equity_capped(df, max_positions=20, max_position_pct=0.05)
        if eq.empty:
            continue
        m = portfolio_metrics(eq, df)

        pb_df  = df[df["has_pullback"]]
        str_df = df[df["has_strength"]]
        no_df  = df[df["add_path"] == "none"]

        row = {
            "experiment_id":  eid,
            "strategy":       strategy,
            "description":    desc,
            "str_thresh_pct": st * 100,
            "str_window":     sw,
            "gk_req":         gk_req,
            "n_trades":       len(df),
            "pct_pullback":   len(pb_df) / max(len(df), 1),
            "pct_strength":   len(str_df) / max(len(df), 1),
            "pct_no_add":     len(no_df) / max(len(df), 1),
            "mean_net_pb":    float(pb_df["net_return"].mean()) if len(pb_df) else np.nan,
            "mean_net_str":   float(str_df["net_return"].mean()) if len(str_df) else np.nan,
            "mean_net_no":    float(no_df["net_return"].mean())  if len(no_df) else np.nan,
            "mean_net_all":   float(df["net_return"].mean()),
            "avg_exposure":   _avg_exp(exp_d),
            "cagr":           m.get("cagr",   np.nan),
            "max_dd":         m.get("max_dd", np.nan),
            "sharpe":         m.get("sharpe", np.nan),
            "mar":            m.get("mar",    np.nan),
            "prod_class":     _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
        }
        rows.append(row)
        print(f"  {eid}: n={len(df)}, pb={len(pb_df)/len(df):.1%}, "
              f"str={len(str_df)/len(df):.1%}, no={len(no_df)/len(df):.1%}, "
              f"CAGR={m.get('cagr',0):.2%}, MAR={m.get('mar',0):.2f}", flush=True)

        yr_df = _by_year(df, eid)
        year_rows.append(yr_df)

    out    = pd.DataFrame(rows)
    yr_out = pd.concat(year_rows, ignore_index=True) if year_rows else pd.DataFrame()

    out.to_csv(OUT_DIR / "phase25_dual_path_strength_add.csv", index=False)
    yr_out.to_csv(OUT_DIR / "phase25_strength_add_by_year.csv", index=False)
    print(f"  25B saved: {len(out)} configs", flush=True)
    return out


# ── Phase 25C: GK usage modes ─────────────────────────────────────────────────

def _sim_gk_add_trigger(
    sym:        str,
    data:       dict,
    strategy:   str,
    exit_cfg:   dict,
    cost:       float,
    gk_dates:   set,
    gk_window:  int   = 10,
    gate_by_date: pd.Series | None = None,
    t1:         float = 0.50,
    t2:         float = 0.50,
) -> list[dict]:
    """A3 entry on signal; add second tranche when GK fires within gk_window."""
    close_arr = data["close"]
    high_arr  = data["high"]
    atr_arr   = data["atr"]
    dates     = data["dates"]
    n         = len(close_arr)

    trades = []
    for si in data["sig_idxs"]:
        entry_i = si + 1
        if entry_i >= n:
            continue
        sig_date = pd.Timestamp(dates[si]).normalize()
        if gate_by_date is not None and not bool(gate_by_date.get(sig_date, True)):
            continue

        ep1 = float(close_arr[entry_i])
        if ep1 <= 0:
            continue

        gk_bar   = None
        ep2_gk   = None

        obs_end = min(entry_i + gk_window + 1, n)
        for k in range(entry_i + 1, obs_end):
            bar_date = pd.Timestamp(dates[k]).normalize()
            if bar_date in gk_dates:
                gk_bar = k
                ep2_gk = float(close_arr[k])
                break

        if ep2_gk is not None:
            total_frac = t1 + t2
            blended_ep = (t1 * ep1 + t2 * ep2_gk) / total_frac
            add_path   = "gk_trigger"
        else:
            total_frac = t1
            blended_ep = ep1
            add_path   = "none"

        hold, gross, reason = _exit_tp_trail(close_arr, high_arr, atr_arr, entry_i, blended_ep, exit_cfg)
        exit_bar = min(entry_i + hold, n - 1)
        net      = gross - cost

        trades.append({
            "symbol":      sym,
            "strategy":    strategy,
            "entry_date":  pd.Timestamp(dates[entry_i]).date(),
            "exit_date":   pd.Timestamp(dates[exit_bar]).date(),
            "total_frac":  total_frac,
            "add_path":    add_path,
            "has_gk_add":  gk_bar is not None,
            "hold_bars":   hold,
            "gross_return": gross,
            "net_return":   net,
            "exit_reason":  reason,
        })

    return trades


def run_phase25c(panel, vnx, ledger, gk_cache, cost, min_lock):
    print("Phase 25C: GK usage modes...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)
    strategy = "A3"
    cfg      = STRATEGY_CONFIGS[strategy]
    exit_cfg = cfg["exit_cfg"]

    rows = []

    # Reference: load from Phase 2 outputs
    # Mode 1: hard filter w10 (A3+GK_w10)
    p2_gk = pd.read_csv(P2_DIR / "phase2_a3gk_overlay_summary.csv")
    hw = p2_gk[(p2_gk["strategy"] == "A3") & (p2_gk["experiment_id"] == "A3+GK_w10")]
    if not hw.empty:
        r = hw.iloc[0].to_dict()
        r["description"] = "Hard filter: only GK-confirmed trades w10 (29% coverage)"
        r["experiment_id"] = "GK_hard_filter_w10"
        r["avg_exposure"] = float(r.get("coverage_pct", 0.291)) * 1.0  # approx
        r["active_cagr"]  = float(r.get("cagr", 0)) / max(float(r.get("coverage_pct", 1)), 0.01)
        r["missed_winners"] = int((1 - float(r.get("coverage_pct", 0.291))) * 9030)
        rows.append(r)
        print(f"  GK_hard_filter_w10: CAGR={r['cagr']:.2%}, MAR={r['mar']:.2f} (from Phase2C)", flush=True)

    # Mode 2: fill priority (A3_all_size125_w3 from Phase 2C — best fill-priority result)
    fp = p2_gk[(p2_gk["strategy"] == "A3") & (p2_gk["experiment_id"] == "A3_all_size125_w3")]
    if not fp.empty:
        r = fp.iloc[0].to_dict()
        r["description"] = "GK fill priority w3 (all trades, GK enter first)"
        r["experiment_id"] = "GK_fill_priority_w3"
        r["avg_exposure"] = 1.0
        r["active_cagr"]  = float(r.get("cagr", 0))
        r["missed_winners"] = 0
        rows.append(r)
        print(f"  GK_fill_priority_w3: CAGR={r['cagr']:.2%}, MAR={r['mar']:.2f} (from Phase2C)", flush=True)

    # Mode 3: GK add-trigger (new)
    led_path = P2_LED / "A3_pos15.csv"
    a3_led   = pd.read_csv(led_path) if led_path.exists() else ledger[ledger["strategy"] == strategy]
    a3_led["entry_date"] = pd.to_datetime(a3_led["entry_date"])
    a3_led["exit_date"]  = pd.to_datetime(a3_led["exit_date"])

    print("  Simulating GK add-trigger...", flush=True)
    cache    = _build_signal_cache(panel, strategy)
    add_trades = []
    for sym, data in cache.items():
        gk_dates = gk_cache.get(sym, set())
        t = _sim_gk_add_trigger(
            sym=sym, data=data, strategy=strategy, exit_cfg=exit_cfg,
            cost=cost, gk_dates=gk_dates, gk_window=10,
            gate_by_date=gate_by_date, t1=0.50, t2=0.50,
        )
        add_trades.extend(t)

    if add_trades:
        df_add = pd.DataFrame(add_trades)
        df_add["entry_date"] = pd.to_datetime(df_add["entry_date"])
        df_add["exit_date"]  = pd.to_datetime(df_add["exit_date"])
        eq_add, exp_add, blk_add = _build_equity_capped(df_add, max_positions=20, max_position_pct=0.05)
        m_add = portfolio_metrics(eq_add, df_add) if not eq_add.empty else {}

        gk_add_df = df_add[df_add["has_gk_add"]]
        no_add_df = df_add[~df_add["has_gk_add"]]
        pct_gk = len(gk_add_df) / max(len(df_add), 1)

        r_add = {
            "experiment_id":  "GK_add_trigger_w10",
            "strategy":        strategy,
            "description":    "GK add-trigger: T1=50% on signal, T2=50% when GK fires w10",
            "n_trades":        len(df_add),
            "coverage_pct":   pct_gk,
            "avg_exposure":   _avg_exp(exp_add),
            "active_cagr":    m_add.get("cagr", np.nan) / max(_avg_exp(exp_add), 0.01),
            "cagr":           m_add.get("cagr",   np.nan),
            "max_dd":         m_add.get("max_dd", np.nan),
            "sharpe":         m_add.get("sharpe", np.nan),
            "mar":            m_add.get("mar",    np.nan),
            "mean_net":       float(df_add["net_return"].mean()),
            "missed_winners": int((no_add_df["net_return"] > 0).sum()),
            "prod_class":     _classify_result(m_add.get("max_dd", -1.0), m_add.get("mar", 0.0)),
        }
        rows.append(r_add)
        print(f"  GK_add_trigger_w10: gk_add%={pct_gk:.1%}, "
              f"CAGR={m_add.get('cagr',0):.2%}, MAR={m_add.get('mar',0):.2f}", flush=True)

    # Mode 4: GK size multiplier 1.25x (for has_gk_w10 trades)
    # Tag ledger with has_gk
    sig_dates = pd.to_datetime(a3_led["signal_date"]) if "signal_date" in a3_led.columns \
                else pd.to_datetime(a3_led["entry_date"])
    a3_led["has_gk"] = [
        any(abs((pd.Timestamp(sd).normalize() - gd).days) <= 10
            for gd in gk_cache.get(sym, set()))
        for sym, sd in zip(a3_led["symbol"], sig_dates)
    ]
    pct_gk_full = float(a3_led["has_gk"].mean())

    eq_mult, exp_mult, blk_mult = _build_equity_capped(
        a3_led, max_positions=15, max_position_pct=1.0/15,
        max_total_exp=1.0, gk_size_mult=1.25, gk_col="has_gk",
    )
    m_mult = portfolio_metrics(eq_mult, a3_led) if not eq_mult.empty else {}
    r_mult = {
        "experiment_id":  "GK_size_mult_1p25_w10",
        "strategy":        strategy,
        "description":    "GK size mult 1.25x for has_gk_w10 trades (full universe)",
        "n_trades":        len(a3_led),
        "coverage_pct":   pct_gk_full,
        "avg_exposure":   _avg_exp(exp_mult),
        "active_cagr":    m_mult.get("cagr", np.nan) / max(_avg_exp(exp_mult), 0.01),
        "cagr":           m_mult.get("cagr",   np.nan),
        "max_dd":         m_mult.get("max_dd", np.nan),
        "sharpe":         m_mult.get("sharpe", np.nan),
        "mar":            m_mult.get("mar",    np.nan),
        "mean_net":       float(a3_led["net_return"].mean()),
        "missed_winners": 0,
        "prod_class":     _classify_result(m_mult.get("max_dd", -1.0), m_mult.get("mar", 0.0)),
    }
    rows.append(r_mult)
    print(f"  GK_size_mult_1p25: CAGR={m_mult.get('cagr',0):.2%}, MAR={m_mult.get('mar',0):.2f}", flush=True)

    # Reference: A3_pos15 baseline
    eq_base, exp_base, _ = _build_equity_capped(a3_led, max_positions=15, max_position_pct=1.0/15)
    m_base = portfolio_metrics(eq_base, a3_led) if not eq_base.empty else {}
    rows.append({
        "experiment_id":  "A3_pos15_baseline",
        "strategy":        strategy,
        "description":    "A3 pos15 equal-weight baseline",
        "n_trades":        len(a3_led),
        "coverage_pct":   1.0,
        "avg_exposure":   _avg_exp(exp_base),
        "active_cagr":    m_base.get("cagr", np.nan),
        "cagr":           m_base.get("cagr",   np.nan),
        "max_dd":         m_base.get("max_dd", np.nan),
        "sharpe":         m_base.get("sharpe", np.nan),
        "mar":            m_base.get("mar",    np.nan),
        "mean_net":       float(a3_led["net_return"].mean()),
        "missed_winners": 0,
        "prod_class":     _classify_result(m_base.get("max_dd", -1.0), m_base.get("mar", 0.0)),
    })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase25_gk_usage_comparison.csv", index=False)
    print(f"  25C saved: {len(out)} GK modes", flush=True)
    return out


# ── Phase 25D: Bad-year diagnostics ──────────────────────────────────────────

BAD_YEARS  = [2018, 2019, 2022]
GOOD_YEARS = [2013, 2020, 2021, 2025]
ALL_YEARS  = sorted(set(BAD_YEARS + GOOD_YEARS))


def _year_stats(trades_df: pd.DataFrame, equity: pd.Series, daily_exp: dict, year: int, label: str) -> dict:
    """Full per-year stat block for one candidate."""
    yr_trades = trades_df[pd.to_datetime(trades_df["entry_date"]).dt.year == year]
    ann       = _annual_returns(equity)
    avg_exp_yr = _year_exp(daily_exp, year)

    if yr_trades.empty:
        return {
            "label": label, "year": year,
            "annual_return": ann.get(year, np.nan),
            "n_trades": 0, "hit_rate": np.nan, "tp_trail_rate": np.nan,
            "max_hold_rate": np.nan, "avg_exposure": avg_exp_yr,
            "missed_winners": np.nan, "avoided_losers": np.nan,
            "mean_net": np.nan,
        }

    n       = len(yr_trades)
    hit     = float((yr_trades["net_return"] > 0).mean())
    mean_n  = float(yr_trades["net_return"].mean())

    # TP-trail rate
    if "exit_reason" in yr_trades.columns:
        tp_rate = float(yr_trades["exit_reason"].str.startswith("tp").mean())
    else:
        tp_rate = np.nan

    # Max-hold rate (≥248 bars ≈ 1 year)
    mh_rate = float((yr_trades["hold_bars"] >= 248).mean()) if "hold_bars" in yr_trades.columns else np.nan

    # Missed winners: no_add trades with positive return
    if "add_path" in yr_trades.columns:
        no_add  = yr_trades[yr_trades["add_path"] == "none"]
        missed  = int((no_add["net_return"] > 0).sum())
        avoided = np.nan  # N/A for DP mode
    else:
        missed  = np.nan
        avoided = np.nan

    return {
        "label":          label,
        "year":           year,
        "annual_return":  ann.get(year, np.nan),
        "n_trades":       n,
        "hit_rate":       hit,
        "tp_trail_rate":  tp_rate,
        "max_hold_rate":  mh_rate,
        "avg_exposure":   avg_exp_yr,
        "missed_winners": missed,
        "avoided_losers": avoided,
        "mean_net":       mean_n,
    }


def run_phase25d(ledger, gk_cache, dp_trades: pd.DataFrame):
    print("Phase 25D: bad-year diagnostics...", flush=True)

    a3_led = pd.read_csv(P2_LED / "A3_pos15.csv") if (P2_LED / "A3_pos15.csv").exists() \
             else ledger[ledger["strategy"] == "A3"].copy()
    a3_led["entry_date"] = pd.to_datetime(a3_led["entry_date"])
    a3_led["exit_date"]  = pd.to_datetime(a3_led["exit_date"])

    # Tag GK for A3 ledger
    if "has_gk" not in a3_led.columns:
        sig_dates = pd.to_datetime(a3_led["signal_date"]) if "signal_date" in a3_led.columns \
                    else pd.to_datetime(a3_led["entry_date"])
        a3_led["has_gk"] = [
            any(abs((pd.Timestamp(sd).normalize() - gd).days) <= 10
                for gd in gk_cache.get(sym, set()))
            for sym, sd in zip(a3_led["symbol"], sig_dates)
        ]

    # ── Simulate each candidate and collect trade ledger + equity + daily_exp ──
    candidates: dict[str, tuple[pd.DataFrame, pd.Series, dict]] = {}

    # 1. A3_pos15
    eq1, exp1, _ = _build_equity_capped(a3_led, max_positions=15, max_position_pct=1/15)
    candidates["A3_pos15"] = (a3_led, eq1, exp1)

    # 2. DP_A3_pb_only (from 25A)
    if not dp_trades.empty:
        eq2, exp2, _ = _build_equity_capped(dp_trades, max_positions=20, max_position_pct=0.05)
        candidates["DP_A3_pb_only"] = (dp_trades, eq2, exp2)

    # 3. A3+GK_w10 hard filter
    gk_mask = a3_led["has_gk"]
    a3_gk   = a3_led[gk_mask].copy()
    if not a3_gk.empty:
        eq3, exp3, _ = _build_equity_capped(a3_gk, max_positions=20, max_position_pct=0.05)
        candidates["A3_GK_hardfilter_w10"] = (a3_gk, eq3, exp3)

    # 4. A3_pos15 + GK priority (fill GK first)
    eq4, exp4, _ = _build_equity_capped(
        a3_led, max_positions=15, max_position_pct=1/15,
        gk_size_mult=1.0, gk_col="has_gk",
    )
    # For true GK priority, use _build_equity_with_defense with gk_priority=True
    a3_led_gk_prio = a3_led.copy()
    eq4p, _ = _build_equity_with_defense(
        a3_led_gk_prio, max_positions=15, max_position_pct=1/15,
        gk_priority=True,
    )
    # Use exp4 as proxy (same universe)
    candidates["A3_pos15_gk_priority"] = (a3_led, eq4p, exp4)

    # 5. A3_pos15 at 75% exposure cap (exposure-matched to DP)
    eq5, exp5, _ = _build_equity_capped(a3_led, max_positions=15, max_position_pct=1/15, max_total_exp=0.75)
    candidates["A3_pos15_exp75"] = (a3_led, eq5, exp5)

    rows = []
    for label, (trades_df, eq, exp_d) in candidates.items():
        print(f"  {label}: {len(trades_df)} trades", flush=True)
        for yr in ALL_YEARS:
            r = _year_stats(trades_df, eq, exp_d, yr, label)
            rows.append(r)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase25_bad_year_diagnostics.csv", index=False)
    print(f"  25D saved: {len(out)} rows ({len(candidates)} candidates × {len(ALL_YEARS)} years)", flush=True)
    return out


# ── Phase 25E: Cost / liquidity sensitivity ───────────────────────────────────

def run_phase25e(ledger, gk_cache, panel, vnx):
    print("Phase 25E: cost / liquidity sensitivity...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)

    strategy = "A3"
    led_path = P2_LED / "A3_pos15.csv"
    a3_base  = pd.read_csv(led_path) if led_path.exists() else ledger[ledger["strategy"] == strategy].copy()
    a3_base["entry_date"] = pd.to_datetime(a3_base["entry_date"])
    a3_base["exit_date"]  = pd.to_datetime(a3_base["exit_date"])

    # Cost grid
    costs    = [0.002, 0.004, 0.006]   # 0.2%, 0.4%, 0.6%
    # ADV50 floors (VND)
    adv_floors = [0.0, 2e9, 5e9, 10e9]
    # Participation rates (max pos_size_VND = adv50 * participation)
    participations = [None, 0.05, 0.10, 0.20]  # None = no cap

    pos_size_ref = PORTFOLIO_REF_VND / 15  # ~1.33B VND per position

    rows = []
    for cost in costs:
        for adv_floor in adv_floors:
            for participation in participations:
                # Filter by ADV50 floor
                if adv_floor > 0 and "adv50_value" in a3_base.columns:
                    mask = a3_base["adv50_value"] >= adv_floor
                else:
                    mask = pd.Series(True, index=a3_base.index)

                # Participation filter
                if participation is not None and "adv50_value" in a3_base.columns:
                    max_pos_vnd = a3_base["adv50_value"] * participation
                    part_mask   = max_pos_vnd >= pos_size_ref
                    mask        = mask & part_mask

                sub = a3_base[mask].copy()
                if sub.empty:
                    continue

                # Adjust net_return for new cost
                orig_cost = DEFAULT_COST
                sub["net_return"] = sub["gross_return"] - cost

                n_excluded   = len(a3_base) - len(sub)
                pct_excluded = n_excluded / max(len(a3_base), 1)

                eq, exp_d, _ = _build_equity_capped(sub, max_positions=15, max_position_pct=1/15)
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, sub)

                eid = (f"COST{int(cost*1000)}bps"
                       + (f"_ADV{int(adv_floor/1e9)}B" if adv_floor > 0 else "")
                       + (f"_PART{int(participation*100)}pct" if participation is not None else ""))

                rows.append({
                    "experiment_id":  eid,
                    "strategy":       strategy,
                    "cost_pct":       cost * 100,
                    "adv_floor_B":    adv_floor / 1e9,
                    "participation":  (participation * 100) if participation else np.nan,
                    "n_trades":       len(sub),
                    "n_excluded":     n_excluded,
                    "pct_excluded":   pct_excluded,
                    "cagr":           m.get("cagr",   np.nan),
                    "max_dd":         m.get("max_dd", np.nan),
                    "sharpe":         m.get("sharpe", np.nan),
                    "mar":            m.get("mar",    np.nan),
                    "prod_class":     _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase25_cost_liquidity_sensitivity.csv", index=False)
    print(f"  25E saved: {len(out)} combinations", flush=True)
    return out


# ── Write findings ─────────────────────────────────────────────────────────────

def _fmt(v, fmt=".3f"):
    return f"{v:{fmt}}" if pd.notna(v) else "N/A"


def write_phase25_findings(out_dir, exp_df, str_df, gk_df, bad_df, cost_df):
    lines = [
        "# Phase 2.5 — Decision Audit\n",
        f"Generated: {date.today()}\n\n",
        "**Goal:** Determine whether DP_A3_pb_only, A3+GK, and defense layers earn their "
        "classification or are artifacts of exposure reduction / limited years.\n\n",
    ]

    def _section(title):
        lines.append(f"## {title}\n\n")

    def _table(df, cols):
        if df is None or df.empty:
            lines.append("*(no data)*\n\n")
            return
        avail = [c for c in cols if c in df.columns]
        if not avail:
            lines.append("*(no matching columns)*\n\n")
            return
        lines.append(df[avail].to_markdown(index=False, floatfmt=".4f") + "\n\n")

    # ── 25A ──
    _section("25A — Exposure-Matched Pullback")
    if exp_df is not None and not exp_df.empty:
        lines.append("**Key question:** Is DP_A3 better than a capped A3_pos15 at the same exposure?\n\n")
        _table(exp_df.sort_values("mar", ascending=False),
               ["experiment_id", "description", "avg_exposure", "cagr", "active_cagr",
                "max_dd", "mar", "worst_year", "worst_return",
                "n_blocked", "blocked_winners", "blocked_losers", "prod_class"])

        dp_row  = exp_df[exp_df["experiment_id"] == "DP_A3_pb_only_t50_pb4w30"]
        exp75   = exp_df[exp_df["experiment_id"] == "A3_pos15_exp75"]
        if not dp_row.empty and not exp75.empty:
            dp_mar  = float(dp_row["mar"].iloc[0])
            e75_mar = float(exp75["mar"].iloc[0])
            verdict = "DP wins on MAR even exposure-matched" if dp_mar > e75_mar + 0.02 \
                      else "DP MAR advantage is primarily from exposure reduction"
            lines.append(f"**Verdict:** {verdict} "
                          f"(DP MAR={dp_mar:.3f} vs A3_pos15_exp75 MAR={e75_mar:.3f})\n\n")

    # ── 25B ──
    _section("25B — No-Pullback Strength-Add (pb_then_str mode)")
    if str_df is not None and not str_df.empty:
        lines.append("Does waiting for pb_window then adding on strength fix under-allocation to no-pullback winners?\n\n")
        _table(str_df.sort_values("mar", ascending=False),
               ["experiment_id", "description", "pct_pullback", "pct_strength", "pct_no_add",
                "mean_net_pb", "mean_net_str", "mean_net_no",
                "avg_exposure", "cagr", "max_dd", "mar", "prod_class"])

        best = str_df.dropna(subset=["mar"]).nlargest(1, "mar")
        if not best.empty:
            b = best.iloc[0]
            lines.append(f"**Best:** {b['experiment_id']} MAR={b['mar']:.3f}, "
                          f"str%={b['pct_strength']:.1%}, no_add%={b['pct_no_add']:.1%}\n\n")
            vs_pb_only = 0.720  # DP_A3_pb_only reference MAR
            better = "YES — strength-add helps" if float(b["mar"]) > vs_pb_only \
                     else f"NO — pb_only (MAR={vs_pb_only:.3f}) still wins"
            lines.append(f"**vs DP_A3_pb_only (MAR=0.720):** {better}\n\n")

    # ── 25C ──
    _section("25C — GK Usage Modes")
    if gk_df is not None and not gk_df.empty:
        _table(gk_df.sort_values("mar", ascending=False),
               ["experiment_id", "description", "coverage_pct", "avg_exposure",
                "cagr", "active_cagr", "max_dd", "mar", "missed_winners", "prod_class"])

        best = gk_df.dropna(subset=["mar"]).nlargest(1, "mar")
        if not best.empty:
            lines.append(f"**Best GK mode:** {best.iloc[0]['experiment_id']} "
                          f"MAR={best.iloc[0]['mar']:.3f}\n\n")

    # ── 25D ──
    _section("25D — Bad-Year Diagnostics")
    if bad_df is not None and not bad_df.empty:
        lines.append("### Bad Years (2018, 2019, 2022)\n\n")
        bad = bad_df[bad_df["year"].isin(BAD_YEARS)]
        _table(bad.sort_values(["year", "label"]),
               ["label", "year", "annual_return", "n_trades", "hit_rate",
                "tp_trail_rate", "max_hold_rate", "avg_exposure", "missed_winners"])

        lines.append("### Good / Mixed Years (2013, 2020, 2021, 2025)\n\n")
        good = bad_df[bad_df["year"].isin(GOOD_YEARS)]
        _table(good.sort_values(["year", "label"]),
               ["label", "year", "annual_return", "n_trades", "hit_rate",
                "tp_trail_rate", "avg_exposure", "mean_net"])

    # ── 25E ──
    _section("25E — Cost / Liquidity Sensitivity")
    if cost_df is not None and not cost_df.empty:
        lines.append("### Cost Sensitivity (ADV floor = 0, no participation cap)\n\n")
        cs = cost_df[(cost_df["adv_floor_B"] == 0) & cost_df["participation"].isna()]
        _table(cs, ["experiment_id", "cost_pct", "n_trades", "cagr", "max_dd", "mar", "prod_class"])

        lines.append("### ADV50 Floor Sensitivity (cost = 0.4%, no participation cap)\n\n")
        af = cost_df[(cost_df["cost_pct"] == 0.4) & cost_df["participation"].isna()]
        _table(af, ["experiment_id", "adv_floor_B", "n_trades", "pct_excluded",
                    "cagr", "max_dd", "mar", "prod_class"])

        lines.append("### Participation Cap Sensitivity (cost = 0.4%, ADV floor = 5B)\n\n")
        pc = cost_df[(cost_df["cost_pct"] == 0.4) & (cost_df["adv_floor_B"] == 5.0) &
                     cost_df["participation"].notna()]
        _table(pc, ["experiment_id", "participation", "n_trades", "pct_excluded",
                    "cagr", "max_dd", "mar", "prod_class"])

    # ── Final verdict ──
    _section("Summary Verdicts")
    verdicts = []

    if exp_df is not None and not exp_df.empty:
        dp_row = exp_df[exp_df["experiment_id"] == "DP_A3_pb_only_t50_pb4w30"]
        e75    = exp_df[exp_df["experiment_id"] == "A3_pos15_exp75"]
        if not dp_row.empty and not e75.empty:
            dp_m = float(dp_row["mar"].iloc[0])
            e_m  = float(e75["mar"].iloc[0])
            verdicts.append(
                f"- **DP_A3_pb_only:** MAR {dp_m:.3f} vs capped-A3 (75%) {e_m:.3f}. "
                f"{'GENUINE edge from pullback timing' if dp_m > e_m + 0.02 else 'Exposure artifact — capped A3 matches it'}. "
                f"→ {'PRODUCTION_CANDIDATE' if dp_m > e_m + 0.02 else 'SHADOW_TEST'}"
            )

    if gk_df is not None and not gk_df.empty:
        hf = gk_df[gk_df["experiment_id"] == "GK_hard_filter_w10"]
        base = gk_df[gk_df["experiment_id"] == "A3_pos15_baseline"]
        if not hf.empty and not base.empty:
            hf_m = float(hf["mar"].iloc[0]) if pd.notna(hf["mar"].iloc[0]) else 0
            b_m  = float(base["mar"].iloc[0]) if pd.notna(base["mar"].iloc[0]) else 0
            verdicts.append(
                f"- **GK hard filter:** MAR {hf_m:.3f} vs baseline {b_m:.3f}. "
                f"Coverage 29% — {'maintains full MAR; PRODUCTION_CANDIDATE for concentrated allocation' if hf_m >= b_m - 0.01 else 'loses edge vs baseline'}."
            )

    if cost_df is not None and not cost_df.empty:
        high_cost = cost_df[(cost_df["cost_pct"] == 0.6) & (cost_df["adv_floor_B"] == 0) &
                            cost_df["participation"].isna()]
        if not high_cost.empty:
            hc_mar = float(high_cost["mar"].iloc[0])
            verdicts.append(
                f"- **Cost sensitivity:** At 0.6% cost, MAR={hc_mar:.3f}. "
                f"{'Robust — strategy survives high friction' if hc_mar > 0.35 else 'Sensitive — needs low-cost broker'}."
            )

        adv5 = cost_df[(cost_df["adv_floor_B"] == 5.0) & (cost_df["cost_pct"] == 0.4) &
                       cost_df["participation"].isna()]
        if not adv5.empty:
            pct_ex = float(adv5["pct_excluded"].iloc[0])
            adv5_mar = float(adv5["mar"].iloc[0])
            verdicts.append(
                f"- **ADV5B floor:** excludes {pct_ex:.1%} of trades, MAR={adv5_mar:.3f}. "
                f"{'Universe survives liquidity screen' if pct_ex < 0.55 else 'Heavy exclusion — check liquidity realism'}."
            )

    for v in verdicts:
        lines.append(v + "\n")
    lines.append("\n")

    lines += [
        "## Phase 3 Readiness\n\n",
        "Promote to Phase 3 (live trading simulation / paper trade):\n",
        "- Rules with MAR > 0.50, MaxDD > -30%, positive OOS, no bad-year collapse\n",
        "- Do NOT promote if edge comes from exposure reduction alone\n",
        "- Do NOT promote if MAR drops below 0.40 at 0.4% cost + 5B ADV floor\n\n",
    ]

    top_path = out_dir / "PHASE25_TOP_FINDINGS.md"
    top_path.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {top_path}", flush=True)

    # ── Review prompt ──
    _write_review_prompt(out_dir, exp_df, str_df, gk_df, bad_df, cost_df)


def _write_review_prompt(out_dir, exp_df, str_df, gk_df, bad_df, cost_df):
    """Self-contained briefing for external AI review."""
    lines = [
        "# Phase 2.5 Review Prompt\n",
        f"Date: {date.today()}\n\n",
        "## Context\n\n",
        "Vietnam EMA-cloud strategy (A3) backtested on HOSE 2012-2025.\n",
        "Universe: ~272 stocks, equal-weight pos15, TP-trail exit, T+3 settlement.\n",
        "Baseline (A3_pos15): CAGR=14.1%, MaxDD=-26.2%, MAR=0.54, Sharpe=1.15.\n\n",
        "Phase 1 identified: pullback scale-in (d=4%, w=30) produces MAR=0.72 with CAGR=10.2%.\n",
        "Phase 2 confirmed: A3+GK at 97.8th percentile vs random subsets; "
        "defense layers hurt; OOS 65% positive folds.\n\n",
        "## Phase 2.5 Tests and Results\n\n",
    ]

    def _mini_table(df, cols, n=8):
        if df is None or df.empty:
            return "*(no data)*\n"
        avail = [c for c in cols if c in df.columns]
        return df[avail].head(n).to_markdown(index=False, floatfmt=".4f") + "\n"

    lines.append("### 25A: Exposure-Matched Pullback\n\n")
    if exp_df is not None and not exp_df.empty:
        lines.append(_mini_table(
            exp_df.sort_values("mar", ascending=False),
            ["experiment_id", "avg_exposure", "cagr", "active_cagr", "max_dd", "mar",
             "worst_year", "worst_return", "blocked_winners", "blocked_losers", "prod_class"]
        ))

    lines.append("\n### 25B: No-Pullback Strength-Add\n\n")
    if str_df is not None and not str_df.empty:
        lines.append(_mini_table(
            str_df.sort_values("mar", ascending=False),
            ["experiment_id", "pct_pullback", "pct_strength", "pct_no_add",
             "mean_net_str", "cagr", "max_dd", "mar", "prod_class"]
        ))

    lines.append("\n### 25C: GK Usage Modes\n\n")
    if gk_df is not None and not gk_df.empty:
        lines.append(_mini_table(
            gk_df.sort_values("mar", ascending=False),
            ["experiment_id", "description", "coverage_pct", "cagr", "active_cagr",
             "max_dd", "mar", "prod_class"]
        ))

    lines.append("\n### 25D: Bad-Year Diagnostics\n\n")
    if bad_df is not None and not bad_df.empty:
        lines.append(_mini_table(
            bad_df[bad_df["year"].isin([2018, 2019, 2022])].sort_values(["year", "label"]),
            ["label", "year", "annual_return", "n_trades", "hit_rate",
             "tp_trail_rate", "avg_exposure", "missed_winners"], n=20
        ))

    lines.append("\n### 25E: Cost / Liquidity Sensitivity\n\n")
    if cost_df is not None and not cost_df.empty:
        # Show cost axis only (ADV floor=0, no participation)
        cs = cost_df[(cost_df["adv_floor_B"] == 0) & cost_df["participation"].isna()]
        lines.append(_mini_table(cs, ["experiment_id", "cost_pct", "n_trades", "cagr", "max_dd", "mar", "prod_class"]))

    lines += [
        "\n## Questions for Reviewer\n\n",
        "1. **Exposure test:** Does DP_A3_pb_only earn its MAR beyond mere exposure reduction? "
        "Is active_CAGR (CAGR/avg_exposure) higher for DP than for capped A3?\n\n",
        "2. **Strength-add:** Does the pb_then_str mode close the gap on no-pullback winners "
        "without degrading pullback returns? Best strength threshold: +4% or +6%?\n\n",
        "3. **GK usage:** Which mode gives the best MAR without excessive coverage loss? "
        "Is GK add-trigger better than hard filter?\n\n",
        "4. **Bad years:** Does any candidate collapse in 2018 or 2022? "
        "Do the bad years reflect strategy weakness or Vietnam market structure?\n\n",
        "5. **Liquidity:** At 5B VND ADV floor, what is the MAR delta? "
        "Is the strategy universe realistic for 20B VND portfolio?\n\n",
        "6. **Phase 3 recommendation:** Which 1-2 candidates should enter live paper trade? "
        "State required conditions (min MAR, max drawdown, OOS requirement).\n\n",
        "## Classification criteria\n\n",
        "- PRODUCTION_CANDIDATE: MAR ≥ 0.50, MaxDD ≥ -30%, 65%+ OOS positive folds, "
        "no collapse year, cost/liq robust\n",
        "- SHADOW_TEST: MAR 0.40-0.50, marginal on one dimension\n",
        "- RESEARCH_ONLY: MAR < 0.40 or fails liquidity\n",
        "- REJECT: exposure artifact, one-year driven, or OOS fails\n\n",
    ]

    rp_path = out_dir / "PHASE25_REVIEW_PROMPT.md"
    rp_path.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {rp_path}", flush=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase",    default="all")
    parser.add_argument("--cost",     type=float, default=DEFAULT_COST)
    parser.add_argument("--min_lock", type=int,   default=5)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strategies = ["A3"]  # Phase 2.5 focuses on A3 (primary candidate)

    print("Loading data...", flush=True)
    panel  = load_panel()
    vnx    = load_vnindex()
    ledger = load_ledger()
    print(f"  Panel: {len(panel):,} rows, {panel['symbol'].nunique()} symbols", flush=True)
    print(f"  Ledger: {len(ledger):,} trades", flush=True)

    gate_by_date, _ = vnindex_regime_gate(vnx)

    run_25a = args.phase in ("25a", "all")
    run_25b = args.phase in ("25b", "all")
    run_25c = args.phase in ("25c", "all")
    run_25d = args.phase in ("25d", "all")
    run_25e = args.phase in ("25e", "all")

    needs_gk    = run_25b or run_25c or run_25d
    needs_cache = run_25b or run_25c

    gk_cache: dict[str, set] = {}
    if needs_gk:
        print("  Building GK cache...", flush=True)
        gk_cache = build_gk_cache(panel)
        print(f"  GK cache: {len(gk_cache)} symbols", flush=True)

    exp_df = str_df = gk_df = bad_df = cost_df = pd.DataFrame()
    dp_trades = pd.DataFrame()

    def _load_csv(df, fname):
        if not df.empty:
            return df
        p = OUT_DIR / fname
        return pd.read_csv(p) if p.exists() else df

    if run_25a:
        exp_df, dp_trades = run_phase25a(panel, vnx, ledger, gk_cache, args.cost, args.min_lock)

    if run_25b:
        str_df = run_phase25b(panel, vnx, gk_cache, args.cost, args.min_lock)

    if run_25c:
        gk_df = run_phase25c(panel, vnx, ledger, gk_cache, args.cost, args.min_lock)

    if run_25d:
        # Load dp_trades if 25a wasn't run this session
        if dp_trades.empty:
            dp_path = OUT_DIR / "phase25a_dp_trade_ledger.csv"
            if dp_path.exists():
                dp_trades = pd.read_csv(dp_path)
                dp_trades["entry_date"] = pd.to_datetime(dp_trades["entry_date"])
                dp_trades["exit_date"]  = pd.to_datetime(dp_trades["exit_date"])
        bad_df = run_phase25d(ledger, gk_cache, dp_trades)

    if run_25e:
        cost_df = run_phase25e(ledger, gk_cache, panel, vnx)

    # Load any phases not run this session
    exp_df  = _load_csv(exp_df,  "phase25_exposure_matched_pullback.csv")
    str_df  = _load_csv(str_df,  "phase25_dual_path_strength_add.csv")
    gk_df   = _load_csv(gk_df,   "phase25_gk_usage_comparison.csv")
    bad_df  = _load_csv(bad_df,  "phase25_bad_year_diagnostics.csv")
    cost_df = _load_csv(cost_df, "phase25_cost_liquidity_sensitivity.csv")

    write_phase25_findings(OUT_DIR, exp_df, str_df, gk_df, bad_df, cost_df)
    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
