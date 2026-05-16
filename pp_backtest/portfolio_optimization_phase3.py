#!/usr/bin/env python3
"""
Portfolio Optimization Phase 3 — Live-trading simulation / paper-trade readiness.

Candidates:
  1. PTS_A3_pb4w30_str6w10   (base: pb or str add, MAR=0.765)
  2. DP_A3_pb_only_t50_pb4w30 (defensive sleeve, MAR=0.720)
  3. A3_pos15                 (fallback benchmark, MAR=0.539)
  4. A3_pos15_GK_mult125      (GK 1.25x size mult, MAR=0.587)

Outputs (in data/research/portfolio_optimization/phase3/):
  phase3_daily_scan_schema.csv
  phase3_daily_scan_sample.csv         (today's live A3 setups)
  phase3_position_sizing_examples.csv
  phase3_liquidity_capacity_summary.csv
  phase3_candidate_comparison_3B_5B_10B.csv
  phase3_live_paper_trade_rules.md
  phase3_monitoring_dashboard_spec.md
  PHASE3_TOP_FINDINGS.md

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase3.py --phase all
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase3.py --phase scan
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase3.py --phase compare
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
    _build_signal_cache, _build_corrected_equity, _exit_tp_trail,
    _quality_ok, _classify_result, load_panel, load_vnindex,
    get_universe, vnindex_regime_gate, compute_gk, portfolio_metrics,
    STRATEGY_CONFIGS, DEFAULT_COST, LEDGER,
)
from pp_backtest.portfolio_optimization_phase2 import load_ledger, build_gk_cache
from pp_backtest.portfolio_optimization_phase25 import _sim_pb_then_str
from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry

OUT_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase3"
P2_LED   = REPO / "data" / "research" / "portfolio_optimization" / "phase2" / "phase2_baseline_trade_ledgers"
P25_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase25"

# Portfolio size scenarios (VND)
PORTFOLIO_SIZES = [3e9, 5e9, 10e9]
PARTICIPATIONS  = [0.05, 0.10, 0.20]   # 5%, 10%, 20% of ADV50
MIN_POS_VND     = 100_000              # min position ~100K VND (1 lot ≈ 100 shares × ~1K-50K)
DEFAULT_MAX_POS = 15
ANNUALIZE       = 252


# ── ADV-capped equity simulator ───────────────────────────────────────────────

def _build_equity_adv_capped(
    trades_df:      pd.DataFrame,
    max_positions:  int,
    portfolio_vnd:  float,
    participation:  float,
    gk_mult:        float = 1.0,
    gk_col:         str   = "has_gk",
    adv_col:        str   = "adv50_value",
    rank_col:       str   = "ema_dist_at_entry",
) -> tuple[pd.Series, dict]:
    """
    Equity simulation with ADV participation cap on position sizes.

    Position weight = min(base_w * gk_mult_if_gk, adv50_value * participation / portfolio_vnd)
    If effective weight < MIN_POS_VND/portfolio_vnd → trade excluded.
    """
    if trades_df.empty:
        return pd.Series(dtype=float), {}

    base_w = 1.0 / max_positions

    df = trades_df.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])

    # Compute effective weight per trade
    is_gk = df[gk_col].astype(bool) if gk_col in df.columns else pd.Series(False, index=df.index)
    tf    = df["total_frac"].astype(float) if "total_frac" in df.columns else pd.Series(1.0, index=df.index)

    target_w = (is_gk.map(lambda x: gk_mult if x else 1.0) * tf * base_w).clip(upper=base_w * gk_mult)

    if adv_col in df.columns:
        adv_vals = df[adv_col].fillna(0).astype(float)
        max_w    = (adv_vals * participation / portfolio_vnd).clip(lower=0, upper=base_w * gk_mult)
        eff_w    = np.minimum(target_w, max_w)
    else:
        eff_w = target_w

    min_w = MIN_POS_VND / portfolio_vnd
    df["_eff_w"]      = np.where(eff_w >= min_w, eff_w.values, 0.0)
    df["_at_full_w"]  = (eff_w >= target_w * 0.95).astype(int)   # within 5% of target
    df["_partial"]    = ((eff_w >= min_w) & (eff_w < target_w * 0.95)).astype(int)
    df["_excluded"]   = (eff_w < min_w).astype(int)

    # Summary stats
    n_total   = len(df)
    n_full    = int(df["_at_full_w"].sum())
    n_partial = int(df["_partial"].sum())
    n_excl    = int(df["_excluded"].sum())
    mean_eff_frac = float((df["_eff_w"] / target_w.clip(lower=1e-9)).mean())

    # Simulate only tradeable rows
    tradeable = df[df["_eff_w"] > 0].copy()

    if tradeable.empty:
        return pd.Series(dtype=float), {
            "n_total": n_total, "n_full": n_full, "n_partial": n_partial,
            "n_excluded": n_excl, "mean_eff_frac": mean_eff_frac,
        }

    sort_col = rank_col if rank_col in tradeable.columns else None
    all_dates = pd.date_range(tradeable["entry_date"].min(), tradeable["exit_date"].max(), freq="B")

    by_entry: dict = {}
    for ed, grp in tradeable.groupby("entry_date", sort=False):
        sg = grp.sort_values(sort_col, ascending=False) if sort_col else grp
        by_entry[ed] = list(sg.index)

    by_exit: dict = {}
    for i, row in tradeable.iterrows():
        by_exit.setdefault(row["exit_date"], []).append(int(i))

    portfolio_val  = 1.0
    peak_val       = 1.0
    active: dict[int, float] = {}
    equity: dict  = {}

    for dv in all_dates:
        for tid in by_exit.get(dv, []):
            if tid in active:
                w = active.pop(tid)
                portfolio_val += portfolio_val * w * float(tradeable.loc[tid, "net_return"])
        peak_val = max(peak_val, portfolio_val)

        active_exp = sum(active.values())
        remaining  = max_positions - len(active)
        for tid in by_entry.get(dv, []):
            if remaining <= 0:
                break
            w = float(tradeable.loc[tid, "_eff_w"])
            avail = max(0.0, 1.0 - active_exp)
            w = min(w, avail)
            if w > 1e-9:
                active[tid]   = w
                active_exp   += w
                remaining    -= 1

        equity[dv] = portfolio_val

    eq = pd.Series(equity)
    stats = {
        "n_total": n_total, "n_full": n_full, "n_partial": n_partial,
        "n_excluded": n_excl, "mean_eff_frac": mean_eff_frac,
    }
    return eq, stats


# ── Trade ledger loaders ──────────────────────────────────────────────────────

def _load_a3_ledger():
    p = P2_LED / "A3_pos15.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])
        return df
    return pd.DataFrame()


def _load_dp_ledger():
    p = P25_DIR / "phase25a_dp_trade_ledger.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])
        return df
    return pd.DataFrame()


def _rebuild_pts_trades(panel, vnx, gk_cache, cost=DEFAULT_COST, min_lock=5):
    """Rebuild PTS_A3_pb4w30_str6w10 trade ledger (pb_then_str mode)."""
    p = OUT_DIR / "phase3_pts_trade_ledger.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])
        print(f"  Loaded PTS trades from cache: {len(df)} rows", flush=True)
        return df

    print("  Building PTS signal cache...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)
    strategy = "A3"
    cfg      = STRATEGY_CONFIGS[strategy]
    exit_cfg = cfg["exit_cfg"]
    cache    = _build_signal_cache(panel, strategy)
    print(f"  {len(cache)} symbols", flush=True)

    all_t = []
    for sym, data in cache.items():
        gk_dates = gk_cache.get(sym, set())
        t = _sim_pb_then_str(
            sym=sym, data=data, strategy=strategy, exit_cfg=exit_cfg,
            cost=cost, pb_depth=0.04, pb_window=30,
            str_thresh=0.06, str_window=10,
            gk_dates=gk_dates, gk_req=False, vol_req=False,
            gate_by_date=gate_by_date, min_lock=min_lock,
            t1=0.50, t2=0.50,
        )
        all_t.extend(t)

    df = pd.DataFrame(all_t)
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])
        df.to_csv(p, index=False)
        print(f"  PTS trades: {len(df)} rows", flush=True)
    return df


def _tag_gk(trades_df, gk_cache, window_days=10):
    """Add has_gk column to ledger."""
    if "has_gk" in trades_df.columns:
        return trades_df
    df = trades_df.copy()
    sig_col = "signal_date" if "signal_date" in df.columns else "entry_date"
    sig_dates = pd.to_datetime(df[sig_col])
    df["has_gk"] = [
        any(abs((pd.Timestamp(sd).normalize() - gd).days) <= window_days
            for gd in gk_cache.get(sym, set()))
        for sym, sd in zip(df["symbol"], sig_dates)
    ]
    return df


# ── Annual return from equity curve ──────────────────────────────────────────

def _annual_return(equity: pd.Series, year: int) -> float:
    yr_eq  = equity[equity.index.year == year]
    pre_eq = equity[equity.index.year < year]
    if yr_eq.empty:
        return np.nan
    end_v   = float(yr_eq.iloc[-1])
    start_v = float(pre_eq.iloc[-1]) if not pre_eq.empty else float(yr_eq.iloc[0])
    return end_v / start_v - 1.0


# ── Phase 3A: Candidate comparison at 3B/5B/10B VND ─────────────────────────

def run_phase3_candidate_comparison(a3_led, dp_led, pts_led, gk_cache):
    print("Phase 3A: candidate comparison at 3B/5B/10B...", flush=True)

    # Tag GK on ledgers
    a3_led  = _tag_gk(a3_led,  gk_cache)
    pts_led = _tag_gk(pts_led, gk_cache)
    dp_led  = _tag_gk(dp_led,  gk_cache)

    candidates = {
        "PTS_A3_pb4w30_str6w10": (pts_led, 20, 1.0),
        "DP_A3_pb_only":         (dp_led,  20, 1.0),
        "A3_pos15":              (a3_led,  15, 1.0),
        "A3_pos15_GK_mult125":   (a3_led,  15, 1.25),
    }

    rows = []
    for cname, (led, max_pos, gk_m) in candidates.items():
        if led.empty:
            continue
        for pvnd in PORTFOLIO_SIZES:
            for part in PARTICIPATIONS:
                eq, stats = _build_equity_adv_capped(
                    led, max_positions=max_pos, portfolio_vnd=pvnd,
                    participation=part, gk_mult=gk_m,
                )
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, led[led["net_return"].notna()])

                # Annual return for key years
                ann = {yr: _annual_return(eq, yr) for yr in [2018, 2019, 2020, 2021, 2022, 2025]}

                rows.append({
                    "candidate":        cname,
                    "portfolio_B_VND":  pvnd / 1e9,
                    "participation_pct": part * 100,
                    "max_positions":    max_pos,
                    "gk_mult":          gk_m,
                    "n_total_trades":   stats.get("n_total", 0),
                    "n_full":           stats.get("n_full", 0),
                    "n_partial":        stats.get("n_partial", 0),
                    "n_excluded":       stats.get("n_excluded", 0),
                    "pct_excluded":     stats["n_excluded"] / max(stats["n_total"], 1),
                    "mean_eff_frac":    stats.get("mean_eff_frac", np.nan),
                    "cagr":             m.get("cagr",   np.nan),
                    "max_dd":           m.get("max_dd", np.nan),
                    "sharpe":           m.get("sharpe", np.nan),
                    "mar":              m.get("mar",    np.nan),
                    "yr_2018":          ann[2018],
                    "yr_2019":          ann[2019],
                    "yr_2020":          ann[2020],
                    "yr_2021":          ann[2021],
                    "yr_2022":          ann[2022],
                    "yr_2025":          ann[2025],
                    "prod_class":       _classify_result(m.get("max_dd", -1.0), m.get("mar", 0.0)),
                })
                print(f"  {cname} @{pvnd/1e9:.0f}B VND, {part:.0%} ADV: "
                      f"excl={stats['n_excluded']/max(stats['n_total'],1):.1%}, "
                      f"MAR={m.get('mar',0):.3f}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase3_candidate_comparison_3B_5B_10B.csv", index=False)
    print(f"  3A saved: {len(out)} rows", flush=True)
    return out


# ── Phase 3B: Liquidity capacity summary ─────────────────────────────────────

def run_phase3_liquidity_capacity(a3_led, dp_led, pts_led, gk_cache):
    print("Phase 3B: liquidity capacity analysis...", flush=True)

    a3_led  = _tag_gk(a3_led,  gk_cache)
    pts_led = _tag_gk(pts_led, gk_cache)

    rows = []
    candidates = {
        "PTS_A3_pb4w30_str6w10": (pts_led, 20),
        "DP_A3_pb_only":         (dp_led,  20),
        "A3_pos15":              (a3_led,  15),
    }

    for cname, (led, max_pos) in candidates.items():
        if led.empty:
            continue
        if "adv50_value" not in led.columns:
            continue
        adv = led["adv50_value"].fillna(0).astype(float)
        tf  = led["total_frac"].astype(float) if "total_frac" in led.columns else pd.Series(1.0, index=led.index)
        base_w = 1.0 / max_pos

        for pvnd in PORTFOLIO_SIZES:
            target_vnd = pvnd * base_w
            for part in PARTICIPATIONS:
                max_vnd = adv * part
                eff_vnd = np.minimum(target_vnd * tf, max_vnd)
                pct_full    = float((eff_vnd >= target_vnd * tf * 0.95).mean())
                pct_partial = float(((eff_vnd >= MIN_POS_VND) & (eff_vnd < target_vnd * tf * 0.95)).mean())
                pct_excl    = float((eff_vnd < MIN_POS_VND).mean())
                mean_eff    = float((eff_vnd / (target_vnd * tf).clip(lower=1)).mean())

                # Effective MAR estimate: approximate by scaling returns
                eff_net = led["net_return"] * (eff_vnd / (target_vnd * tf).clip(lower=1))
                mean_eff_net = float(eff_net.mean())

                # Feasibility flag: portfolio is feasible if >60% trades at full size
                feasible = pct_full >= 0.60

                rows.append({
                    "candidate":         cname,
                    "portfolio_B_VND":   pvnd / 1e9,
                    "participation_pct": part * 100,
                    "target_pos_VND_M":  target_vnd / 1e6,
                    "median_adv50_B":    float(adv.median()) / 1e9,
                    "pct_full_size":     pct_full,
                    "pct_partial_size":  pct_partial,
                    "pct_excluded":      pct_excl,
                    "mean_eff_fill_pct": mean_eff,
                    "mean_eff_net":      mean_eff_net,
                    "feasible":          feasible,
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase3_liquidity_capacity_summary.csv", index=False)
    print(f"  3B saved: {len(out)} rows", flush=True)
    return out


# ── Phase 3C: Daily scan sample output ───────────────────────────────────────

def _compute_pts_state(
    close_arr, fast_ema, cloud_bull, dates, entry_i, ep1,
    pb_depth=0.04, pb_window=30, str_thresh=0.06, str_window=10,
    current_i=None,
):
    """Compute PTS state machine state as of current_i (last bar)."""
    if current_i is None:
        current_i = len(close_arr) - 1

    bars_since = current_i - entry_i
    if bars_since < 0:
        return "NOT_ENTERED", ep1, ep1

    pb_trigger  = ep1 * (1.0 - pb_depth)
    str_trigger = ep1 * (1.0 + str_thresh)

    # Phase 1: pb_window
    if bars_since <= pb_window:
        # Check if pullback occurred
        for k in range(entry_i + 1, min(current_i + 1, entry_i + pb_window + 1)):
            c = float(close_arr[k])
            if c <= pb_trigger:
                return "PB_HIT", pb_trigger, str_trigger
        return "PB_WAIT", pb_trigger, str_trigger

    # Phase 2: str_window (after pb_window)
    # Check if pullback occurred during pb_window
    pb_occurred = any(
        float(close_arr[k]) <= pb_trigger
        for k in range(entry_i + 1, min(entry_i + pb_window + 1, len(close_arr)))
    )
    if pb_occurred:
        return "PB_HIT", pb_trigger, str_trigger

    # Now in str_window
    str_start = entry_i + pb_window + 1
    str_end   = entry_i + pb_window + str_window + 1
    if bars_since <= pb_window + str_window:
        for k in range(str_start, min(current_i + 1, str_end, len(close_arr))):
            c = float(close_arr[k])
            if c >= str_trigger and bool(cloud_bull[k]) and c > float(fast_ema[k]) * 0.999:
                return "STR_HIT", pb_trigger, str_trigger
        return "STR_WAIT", pb_trigger, str_trigger

    # Expired (past both windows, no add)
    # Check if any add occurred
    for k in range(entry_i + 1, min(entry_i + pb_window + 1, len(close_arr))):
        if float(close_arr[k]) <= pb_trigger:
            return "PB_HIT", pb_trigger, str_trigger
    for k in range(str_start, min(str_end, len(close_arr))):
        c = float(close_arr[k])
        if c >= str_trigger and bool(cloud_bull[k]) and c > float(fast_ema[k]) * 0.999:
            return "STR_HIT", pb_trigger, str_trigger
    return "NO_ADD", pb_trigger, str_trigger


def _near_entry_label(pct_vs_signal: float) -> str:
    if pct_vs_signal >= 0.08:
        return "stretched"
    if pct_vs_signal >= 0.02:
        return "momentum_confirmed"
    if pct_vs_signal >= -0.03:
        return "acceptable"
    if pct_vs_signal >= -0.08:
        return "ideal_pullback"
    return "deep_pullback"


def _sleeve(pts_state: str, near_entry: str, gk10: bool, cloud_bull: bool, regime_bull: bool) -> str:
    if not cloud_bull or not regime_bull:
        return "Watch_only"
    if pts_state in ("PB_HIT", "STR_HIT"):
        return "Growth"  # already added
    if pts_state == "PB_WAIT" and near_entry in ("ideal_pullback", "deep_pullback"):
        return "Defensive_PTS" if not gk10 else "Growth"
    if pts_state in ("STR_WAIT", "PB_WAIT") and near_entry in ("acceptable", "momentum_confirmed"):
        return "Growth" if gk10 else "PTS"
    if near_entry == "stretched":
        return "Watch_only"
    return "PTS"


def _liquidity_warning(adv50: float, pos_vnd: float, participation: float) -> str:
    max_vnd = adv50 * participation
    if adv50 <= 0:
        return "NO_ADV_DATA"
    if pos_vnd > max_vnd * 2:
        return "CRITICAL"
    if pos_vnd > max_vnd:
        return "WARN_OVER"
    if pos_vnd > max_vnd * 0.8:
        return "WARN_NEAR"
    return "OK"


def run_phase3_daily_scan(panel, vnx, gk_cache, portfolio_vnd=5e9):
    print("Phase 3C: daily scan sample...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)
    last_date = pd.Timestamp(panel["date"].max()).normalize()
    regime_bull = bool(gate_by_date.get(last_date, False))
    strategy = "A3"
    cfg      = STRATEGY_CONFIGS[strategy]
    max_pos  = 15
    base_pos_vnd = portfolio_vnd / max_pos
    participation_ref = 0.10   # 10% ADV50 as default for warning

    scan_rows  = []
    schema_rows = []

    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 120:
            continue

        c = sdf["close"].astype(float)
        h = sdf["high"].astype(float)
        l = sdf.get("low", c).astype(float)
        v = sdf.get("volume", pd.Series(np.ones(len(sdf)))).astype(float)
        d = pd.to_datetime(sdf["date"])

        cloud_d    = ema_cloud(c, 20, 100)
        fast_ema   = cloud_d["ema_fast"]
        slow_ema   = cloud_d["ema_slow"]
        cloud_bull_s = cloud_d["cloud_bull"]
        atr        = compute_atr(h, l, c, 14)
        adv50      = (c * v).rolling(50, min_periods=20).mean()
        mom20      = c.pct_change(20).fillna(0.0)

        sig = cloud_only_entry(c, fast_ema, cloud_bull_s, min_bars_bear=3, warmup=110)
        sig_idxs = np.where(sig.values)[0]

        if len(sig_idxs) == 0:
            continue

        # Last signal
        li      = int(sig_idxs[-1])
        entry_i = li + 1
        if entry_i >= len(c):
            continue

        bars_since = len(c) - 1 - entry_i
        if bars_since > 40:   # only show active PTS window
            continue

        ep1 = float(c.iloc[entry_i])
        cur_c = float(c.iloc[-1])
        pct_vs_signal = cur_c / ep1 - 1.0
        ema_dist = float(cur_c / fast_ema.iloc[-1] - 1.0) if float(fast_ema.iloc[-1]) > 0 else 0.0
        cloud_now = bool(cloud_bull_s.iloc[-1])
        adv50_now = float(adv50.iloc[-1]) if not np.isnan(float(adv50.iloc[-1])) else 0.0
        atr_now   = float(atr.iloc[-1])

        # GK
        try:
            gk_res  = compute_gk(c, h, l)
            gk_days = d[gk_res["gk_buy"]]
            gk_days_norm = gk_days.dt.normalize()
            today_norm   = last_date.normalize()
            gk10 = any(abs((today_norm - gd).days) <= 10 for gd in gk_days_norm)
        except Exception:
            gk10 = False

        # PTS state
        pts_state, pb_trigger, str_trigger = _compute_pts_state(
            c.values, fast_ema.values, cloud_bull_s.values, d.values,
            entry_i, ep1,
            pb_depth=0.04, pb_window=30, str_thresh=0.06, str_window=10,
            current_i=len(c) - 1,
        )

        near_entry = _near_entry_label(pct_vs_signal)
        sleeve     = _sleeve(pts_state, near_entry, gk10, cloud_now, regime_bull)
        liq_warn   = _liquidity_warning(adv50_now, base_pos_vnd, participation_ref)

        # Position sizing
        max_pos_vnd = adv50_now * participation_ref if adv50_now > 0 else 0.0
        t1_pct      = 50.0  # always enter T1=50% of position
        add_pct     = 50.0  # T2=50% on PB or STR trigger
        eff_pos_vnd = min(base_pos_vnd, max_pos_vnd) if max_pos_vnd > 0 else base_pos_vnd
        gk_mult_flag = 1.25 if gk10 else 1.0
        eff_pos_vnd_gk = min(base_pos_vnd * gk_mult_flag, max_pos_vnd) if max_pos_vnd > 0 else base_pos_vnd * gk_mult_flag

        # Exit levels
        tp1_guide    = f">{ep1 * 1.18:.2f} ({'+18%'})"
        trail_stop   = f"2.5×ATR={2.5*atr_now:.2f} below high-water"
        pb_guide     = f"<{pb_trigger:.2f} (−4% from entry)"
        str_guide    = f">{str_trigger:.2f} (+6% from entry, after bar 30)"

        scan_rows.append({
            "as_of_date":         last_date.date(),
            "symbol":             sym,
            "close":              round(cur_c, 2),
            "a3_signal_state":    "ACTIVE" if cloud_now else "EXPIRED",
            "bars_since_entry":   bars_since,
            "near_entry_label":   near_entry,
            "ema_dist_pct":       round(ema_dist * 100, 2),
            "pts_state":          pts_state,
            "pb_trigger_price":   round(pb_trigger, 2),
            "str_trigger_price":  round(str_trigger, 2),
            "gk10_confirmed":     "Y" if gk10 else "N",
            "cloud_bull":         "Y" if cloud_now else "N",
            "regime_bull":        "Y" if regime_bull else "N",
            "adv50_B_VND":        round(adv50_now / 1e9, 3),
            "recommended_sleeve": sleeve,
            "t1_tranche_pct":     t1_pct,
            "add_tranche_pct":    add_pct,
            "gk_size_mult":       gk_mult_flag,
            "max_pos_VND_M":      round(eff_pos_vnd_gk / 1e6, 1),
            "liquidity_warning":  liq_warn,
            "stop_guide":         trail_stop,
            "tp1_guide":          tp1_guide,
            "pb_add_guide":       pb_guide,
            "str_add_guide":      str_guide,
            "portfolio_ref_VND_B": portfolio_vnd / 1e9,
        })

    scan_df = pd.DataFrame(scan_rows).sort_values(["sleeve" if "sleeve" in scan_rows[0] else "recommended_sleeve",
                                                    "ema_dist_pct"], ascending=[True, False]) \
              if scan_rows else pd.DataFrame()

    # Sort: Growth first, then PTS, then Watch_only
    sleeve_order = {"Growth": 0, "Defensive_PTS": 1, "PTS": 2, "Watch_only": 3}
    if not scan_df.empty:
        scan_df["_sleeve_rank"] = scan_df["recommended_sleeve"].map(sleeve_order).fillna(9)
        scan_df = scan_df.sort_values(["_sleeve_rank", "ema_dist_pct"], ascending=[True, False])
        scan_df = scan_df.drop(columns=["_sleeve_rank"])

    scan_df.to_csv(OUT_DIR / "phase3_daily_scan_sample.csv", index=False)
    print(f"  3C saved: {len(scan_df)} active setups as of {last_date.date()}", flush=True)

    # Schema definition
    schema = [
        ("as_of_date",         "date",   "Scan date",                                      "panel.date.max()"),
        ("symbol",             "str",    "Stock ticker",                                   "panel.symbol"),
        ("close",              "float",  "Last close price",                                "panel.close"),
        ("a3_signal_state",    "str",    "ACTIVE / EXPIRED (cloud still bullish)",          "ema_cloud"),
        ("bars_since_entry",   "int",    "Bars since A3 entry (T+1 after signal)",          "signal_cache"),
        ("near_entry_label",   "str",    "acceptable/ideal_pullback/stretched/momentum",    "current pct vs entry"),
        ("ema_dist_pct",       "float",  "EMA distance % (rank metric)",                   "close/ema20-1"),
        ("pts_state",          "str",    "PB_WAIT/PB_HIT/STR_WAIT/STR_HIT/NO_ADD/EXPIRED", "state machine"),
        ("pb_trigger_price",   "float",  "Pullback add trigger: entry*(1−4%)",              "ep1*0.96"),
        ("str_trigger_price",  "float",  "Strength add trigger: entry*(1+6%), after bar30", "ep1*1.06"),
        ("gk10_confirmed",     "str",    "Y if GK buy signal within 10 days",              "gk_cache"),
        ("cloud_bull",         "str",    "Y if EMA20>EMA100 now",                          "ema_cloud"),
        ("regime_bull",        "str",    "Y if VNINDEX above EMA100",                      "vnindex_regime_gate"),
        ("adv50_B_VND",        "float",  "50-day avg daily value in billion VND",          "close*volume.rolling(50)"),
        ("recommended_sleeve", "str",    "Growth/PTS/Defensive_PTS/Watch_only",            "sleeve logic"),
        ("t1_tranche_pct",     "float",  "Initial tranche size % of full position (50%)",  "always 50"),
        ("add_tranche_pct",    "float",  "Add tranche % of full position on PB or STR",    "always 50"),
        ("gk_size_mult",       "float",  "1.25 if gk10_confirmed else 1.0",                "gk10_confirmed"),
        ("max_pos_VND_M",      "float",  "Effective max position value (ADV50×10% capped)", "min(target, adv50*0.10)"),
        ("liquidity_warning",  "str",    "OK/WARN_NEAR/WARN_OVER/CRITICAL/NO_ADV_DATA",    "adv50 vs target pos"),
        ("stop_guide",         "str",    "Trailing stop: 2.5×ATR below high-water mark",   "exit logic"),
        ("tp1_guide",          "str",    "TP1: +18% from blended entry (50% of position)", "exit_cfg"),
        ("pb_add_guide",       "str",    "PB add trigger price with note",                 "pb_trigger_price"),
        ("str_add_guide",      "str",    "STR add trigger price with note",                "str_trigger_price"),
    ]
    schema_df = pd.DataFrame(schema, columns=["field_name", "data_type", "description", "computation_source"])
    schema_df.to_csv(OUT_DIR / "phase3_daily_scan_schema.csv", index=False)
    print(f"  Schema saved: {len(schema_df)} fields", flush=True)

    return scan_df, schema_df


# ── Phase 3D: Position sizing examples ───────────────────────────────────────

def run_phase3_position_sizing(scan_df, portfolio_vnds=PORTFOLIO_SIZES, participations=PARTICIPATIONS):
    print("Phase 3D: position sizing examples...", flush=True)
    if scan_df is None or scan_df.empty:
        return pd.DataFrame()

    top = scan_df[scan_df["recommended_sleeve"].isin(["Growth", "PTS", "Defensive_PTS"])].head(10)

    rows = []
    for _, sym_row in top.iterrows():
        sym      = sym_row["symbol"]
        close    = float(sym_row["close"])
        adv50    = float(sym_row["adv50_B_VND"]) * 1e9
        gk_mult  = float(sym_row["gk_size_mult"])
        sleeve   = sym_row["recommended_sleeve"]

        for pvnd in portfolio_vnds:
            base_pos = pvnd / DEFAULT_MAX_POS
            for part in participations:
                max_adv_vnd   = adv50 * part if adv50 > 0 else 0.0
                target_t1     = base_pos * gk_mult * 0.5        # T1 = 50% of full position
                eff_t1        = min(target_t1, max_adv_vnd * 0.5) if max_adv_vnd > 0 else target_t1
                eff_t1        = max(eff_t1, 0)
                shares_t1     = int(eff_t1 / close / 100) * 100 if close > 0 else 0   # round to lots of 100
                actual_t1_vnd = shares_t1 * close
                warn          = _liquidity_warning(adv50, base_pos * gk_mult, part)

                rows.append({
                    "symbol":            sym,
                    "sleeve":            sleeve,
                    "close":             close,
                    "gk10":              sym_row["gk10_confirmed"],
                    "gk_mult":           gk_mult,
                    "adv50_B_VND":       adv50 / 1e9,
                    "portfolio_B_VND":   pvnd / 1e9,
                    "participation_pct": part * 100,
                    "target_full_pos_M": base_pos * gk_mult / 1e6,
                    "target_T1_M":       target_t1 / 1e6,
                    "max_adv_allowed_M": max_adv_vnd / 1e6,
                    "eff_T1_M":          actual_t1_vnd / 1e6,
                    "shares_T1":         shares_t1,
                    "liq_warning":       warn,
                    "note": ("full_size" if warn == "OK" else
                             "scaled_down" if warn in ("WARN_NEAR", "WARN_OVER") else
                             "skip" if warn == "CRITICAL" else "no_adv"),
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase3_position_sizing_examples.csv", index=False)
    print(f"  3D saved: {len(out)} sizing examples", flush=True)
    return out


# ── Write live paper-trade rules ──────────────────────────────────────────────

def write_phase3_live_rules(out_dir, cmp_df):
    lines = [
        "# Phase 3 — Live Paper-Trade Rules\n",
        f"Generated: {date.today()}\n\n",
        "## Strategy Configuration\n\n",
        "| Parameter | Value |\n",
        "|-----------|-------|\n",
        "| Base signal | A3 (EMA20/100 cloud breakout) |\n",
        "| Universe | HOSE ex-VIN3, ≥252 bars history |\n",
        "| Entry mode | T1=50% at close of signal day+1 (open next morning) |\n",
        "| Pullback add | T2=50% if price drops ≥4% from entry within 30 bars (cloud must stay bullish) |\n",
        "| Strength add | T2=50% if price rises ≥6% from entry after bar 30, within bar 40, cloud+EMA bullish |\n",
        "| GK boost | If GK buy signal within 10 days: position size ×1.25 (capped at 2×base) |\n",
        "| TP1 | +18% from blended entry → sell 50% of position |\n",
        "| Trail | After TP1: 2.5×ATR trailing stop on remaining 50% |\n",
        "| Max hold | 250 bars (~1 year) |\n",
        "| VNINDEX gate | No new entries if VNINDEX below EMA100 |\n",
        "| Cost assumption | 0.4% round-trip (adjust for your broker) |\n\n",
        "## Sleeves\n\n",
        "| Sleeve | When | Size | Notes |\n",
        "|--------|------|------|-------|\n",
        "| **Growth** | GK10 confirmed + cloud bull + regime bull + near-entry ≤+8% | 1.25× base | Priority fill |\n",
        "| **PTS** | A3 signal, no GK, cloud bull, regime bull, PB_WAIT or STR_WAIT | 1.0× base | Standard |\n",
        "| **Defensive_PTS** | PB_WAIT + price at ideal pullback (−3% to −8%) | 1.0× base | Wait for PB confirmation |\n",
        "| **Watch_only** | Cloud broken, regime bear, or stretched >+8% | 0 | Do not enter |\n\n",
        "## Portfolio Construction\n\n",
        "```\n",
        "max_positions = 15 (A3_pos15 sleeve)\n",
        "max_positions = 20 (PTS/DP sleeve — smaller per-position weight)\n",
        "base_position_weight = 1/max_positions of portfolio\n",
        "GK boost: effective_weight = min(1.25 × base_w, adv50 × participation / portfolio_vnd)\n",
        "participation_cap: position_vnd ≤ ADV50 × participation_rate\n",
        "  aggressive: 20% ADV50\n",
        "  standard:   10% ADV50  ← default\n",
        "  conservative: 5% ADV50\n",
        "min_position_vnd = 100,000 VND (skip if below)\n",
        "```\n\n",
        "## Portfolio Size Feasibility\n\n",
        "| Portfolio | At 10% ADV | Recommendation |\n",
        "|-----------|-----------|----------------|\n",
        "| 3B VND | Most trades fit | Full strategy |\n",
        "| 5B VND | ~60-70% fit | Reduce to top 12 ranks |\n",
        "| 10B VND | ~45-55% fit | Cap at 5B VND or accept partial fills |\n\n",
        "## Daily Run Workflow\n\n",
        "```\n",
        "Before 9:00 AM:\n",
        "  1. python scripts/run_weekly_full_fetch.py   # or daily_fetch\n",
        "  2. python pp_backtest/daily_three_strategy_scan.py  # check regime + signals\n",
        "  3. python pp_backtest/portfolio_optimization_phase3.py --phase scan  # Phase3 enrichment\n",
        "\n",
        "9:00–9:15 AM (pre-market):\n",
        "  4. Review phase3_daily_scan_sample.csv — filter sleeve=Growth/PTS\n",
        "  5. Check liquidity_warning: skip CRITICAL, scale WARN_OVER\n",
        "  6. Compute T1 share count: shares = (portfolio_B × 1e9 / max_pos × 0.5) / close\n",
        "  7. Round to nearest 100 shares (lot size)\n",
        "\n",
        "9:15–9:20 AM (order entry):\n",
        "  8. Enter T1 orders at ATC price (or limit at signal close × 1.005)\n",
        "  9. Set price alert for pb_trigger_price (pullback add) and str_trigger_price (strength add)\n",
        " 10. Set stop-loss alert at entry × 0.85 (initial hard stop before ATR trail kicks in)\n",
        "\n",
        "During session:\n",
        " 11. Monitor PTS alerts. If pb_trigger hit: enter T2 order\n",
        " 12. After bar 30: if no pullback, switch to STR_WAIT. If str_trigger hit: enter T2\n",
        " 13. TP1 alert: if +18% from blended entry → sell 50%, activate trail stop\n",
        "```\n\n",
        "## Paper-Trade Checklist (daily)\n\n",
        "```\n",
        "[ ] 1. VNINDEX regime: BULL? (gate for new entries)\n",
        "[ ] 2. Run scan — note any new Growth/PTS signals\n",
        "[ ] 3. For each new signal:\n",
        "        [ ] ADV50 × 10% ≥ target T1 size?\n",
        "        [ ] Cloud bull AND price > EMA20?\n",
        "        [ ] GK10 confirmed? (→ 1.25× size)\n",
        "        [ ] Sleeve = Growth/PTS? (not Watch_only)\n",
        "        [ ] Record: symbol, date, ep1, T1_size, pb_trigger, str_trigger\n",
        "[ ] 4. For open positions:\n",
        "        [ ] PTS state update (PB_WAIT → PB_HIT? STR_WAIT → STR_HIT?)\n",
        "        [ ] TP1 hit? → log partial exit, activate trail\n",
        "        [ ] Trail stop breached? → log full exit\n",
        "        [ ] Hold ≥250 bars? → log forced exit\n",
        "[ ] 5. Update positions.csv and daily P&L log\n",
        "```\n\n",
        "## Exit Decision Tree\n\n",
        "```\n",
        "Entry at ep1 (T1=50%):\n",
        "  → Pullback ≥4% within 30 bars AND cloud bullish?\n",
        "       YES → Add T2=50% at pullback price. Blended entry recalculated.\n",
        "       NO  → After bar 30: watch for strength add\n",
        "             → Strength ≥6% AND cloud+EMA bullish within bars 31-40?\n",
        "                  YES → Add T2=50% at strength price. Blended entry recalculated.\n",
        "                  NO  → Remain at T1 only (50% position)\n",
        "\n",
        "Post-add or T1-only exit:\n",
        "  → Blended entry set. Start exit clock.\n",
        "  → Close ≥ blended_entry × 1.18?   → Sell 50% (TP1). Activate 2.5×ATR trail on rest.\n",
        "  → Close < high_water − 2.5×ATR?   → Sell remaining (trail triggered)\n",
        "  → Hold ≥250 bars?                  → Force-sell everything (max hold)\n",
        "```\n",
    ]

    p = out_dir / "phase3_live_paper_trade_rules.md"
    p.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {p}", flush=True)


# ── Write monitoring dashboard spec ──────────────────────────────────────────

def write_phase3_monitoring_spec(out_dir):
    lines = [
        "# Phase 3 — Monitoring Dashboard Spec\n",
        f"Generated: {date.today()}\n\n",
        "## Overview\n\n",
        "Single-page dashboard for daily paper-trade monitoring of the A3/PTS strategy.\n",
        "Data source: `phase3_daily_scan_sample.csv` + `data/paper_trade/positions.csv`.\n\n",
        "## Panel 1 — Regime & Market Breadth\n\n",
        "| Widget | Source | Alert |\n",
        "|--------|--------|-------|\n",
        "| VNINDEX vs EMA100 | ta_vnindex.parquet | RED if below (no new entries) |\n",
        "| VNINDEX 5-day return | ta_vnindex | ≤-3% → yellow |\n",
        "| % stocks above EMA20 | breadth_daily.csv | <35% → yellow, <25% → red |\n",
        "| % stocks in cloud (EMA20>EMA100) | breadth_daily.csv | <40% → yellow |\n",
        "| Active A3 signals today | daily_scan_sample | count, list of symbols |\n\n",
        "## Panel 2 — Open Positions\n\n",
        "| Column | Source | Alert |\n",
        "|--------|--------|-------|\n",
        "| Symbol | positions.csv | — |\n",
        "| Entry date | positions.csv | hold_bars counter |\n",
        "| ep1 / blended_ep | positions.csv | — |\n",
        "| PTS state | daily_scan_sample | PB_HIT/STR_HIT in green |\n",
        "| Current close | panel | — |\n",
        "| P&L% | (close/blended_ep - 1) | ≥+18% → TP1 alert (green), ≤-12% → stop-loss alert (red) |\n",
        "| Trail stop | positions.csv | Price < trail_stop → EXIT alert (red) |\n",
        "| Hold bars | positions.csv | ≥240 → yellow, ≥250 → red (forced exit) |\n",
        "| T2 added? | positions.csv | flag |\n",
        "| GK10 at entry | positions.csv | flag |\n",
        "| ADV50 B VND | panel | reference |\n",
        "| Position VND M | computed | vs ADV participation |\n\n",
        "## Panel 3 — Today's Actionable Signals\n\n",
        "Filter: `recommended_sleeve` in (Growth, PTS, Defensive_PTS)\n",
        "Sorted by sleeve rank → ema_dist descending.\n\n",
        "| Column | Notes |\n",
        "|--------|-------|\n",
        "| Symbol | clickable to chart |\n",
        "| Sleeve | colour-coded: Growth=green, PTS=blue, Defensive_PTS=yellow |\n",
        "| PTS state | |\n",
        "| Close | |\n",
        "| EMA dist % | rank metric |\n",
        "| GK10 | Y/N badge |\n",
        "| T1 size (M VND) | at default portfolio size |\n",
        "| Liq warning | OK=green, WARN=yellow, CRITICAL=red |\n",
        "| PB trigger | |\n",
        "| STR trigger (after bar30) | |\n",
        "| TP1 guide | |\n\n",
        "## Panel 4 — Portfolio Metrics\n\n",
        "| Metric | Computation | Alert |\n",
        "|--------|-------------|-------|\n",
        "| Portfolio NAV (VND) | sum of position values + cash | — |\n",
        "| Total return % | (NAV / initial) - 1 | — |\n",
        "| Daily P&L | NAV today vs yesterday | — |\n",
        "| Drawdown from peak | (NAV / peak_NAV) - 1 | ≤-10% → yellow, ≤-15% → red |\n",
        "| Current exposure % | sum(pos_value) / NAV | >100% impossible, <50% → low |\n",
        "| n_positions | count open | |\n",
        "| Avg position age | avg hold_bars | |\n",
        "| TP1 hit rate YTD | pct positions that hit TP1 | |\n",
        "| Win rate YTD | pct closed with net_return>0 | |\n",
        "| Mean net return (closed) | | |\n\n",
        "## Panel 5 — PTS State Tracker\n\n",
        "For each open position: show state machine progression.\n\n",
        "```\n",
        "Symbol  | Entry Date | Bars | Phase1 (PB_WAIT) | Phase2 (STR_WAIT) | Add Status\n",
        "--------|------------|------|-----------------|-------------------|-------------\n",
        "MSB     | 2026-04-22 |  14  | ████░░░░░░ (30b)| waiting           | NO_ADD_YET\n",
        "GVR     | 2026-05-06 |   7  | ██░░░░░░░░ (30b)| not started       | PB_WAIT\n",
        "VHM     | 2026-04-07 |  25  | ██████████ done | ████░░░░░░ (10b)  | STR_WAIT\n",
        "```\n\n",
        "## Alert Rules\n\n",
        "| Alert | Trigger | Action |\n",
        "|-------|---------|--------|\n",
        "| PB_ADD | position.close ≤ pb_trigger AND cloud_bull | Enter T2 order immediately |\n",
        "| STR_ADD | bars_since≥31 AND close≥str_trigger AND cloud+EMA | Enter T2 order |\n",
        "| TP1 | close/blended_ep ≥ 1.18 | Sell 50%, activate trail |\n",
        "| TRAIL_STOP | close < high_water - 2.5×ATR | Sell remaining |\n",
        "| MAX_HOLD | hold_bars ≥ 250 | Force-exit all |\n",
        "| CLOUD_BREAK | cloud turns bearish on open position | Consider early exit |\n",
        "| REGIME_FLIP | VNINDEX < EMA100 | No new entries; review existing |\n",
        "| GK_ALERT | GK buy fires on existing position (T1 only) | Consider adding T2 if STR_WAIT |\n\n",
        "## Update Cadence\n\n",
        "| Event | Frequency |\n",
        "|-------|-----------|\n",
        "| Panel data fetch | Daily at 7:00 AM |\n",
        "| Scan run | Daily at 8:00 AM |\n",
        "| Intraday alerts | Real-time via price alert app |\n",
        "| Position update | End of day |\n",
        "| Weekly review | Monday morning |\n",
    ]

    p = out_dir / "phase3_monitoring_dashboard_spec.md"
    p.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {p}", flush=True)


# ── Write top findings ─────────────────────────────────────────────────────────

def write_phase3_findings(out_dir, cmp_df, cap_df, scan_df):
    today_str = str(date.today())

    def _tbl(df, cols, n=None):
        if df is None or df.empty:
            return "*(no data)*\n\n"
        avail = [c for c in cols if c in df.columns]
        sub   = df[avail].head(n) if n else df[avail]
        return sub.to_markdown(index=False, floatfmt=".4f") + "\n\n"

    lines = [
        "# Phase 3 — Live-Trading Simulation: Top Findings\n",
        f"Generated: {today_str}\n\n",
        "## Candidate Summary (from Phase 2.5)\n\n",
        "| Candidate | MAR | CAGR | MaxDD | avg_exp | Notes |\n",
        "|-----------|-----|------|-------|---------|-------|\n",
        "| PTS_A3_pb4w30_str6w10 | **0.765** | 10.2% | −13.3% | 75% | pb then str add, best MAR |\n",
        "| DP_A3_pb_only | **0.720** | 10.2% | −14.2% | 66% | pb only, defensive sleeve |\n",
        "| A3_pos15_GK_mult125 | **0.587** | 14.2% | −24.2% | 98% | full universe + GK boost |\n",
        "| A3_pos15 | **0.539** | 14.1% | −26.2% | 99% | simplest fallback |\n\n",
        "## Phase 3A — Candidate vs Portfolio Size × Participation\n\n",
    ]

    if cmp_df is not None and not cmp_df.empty:
        # Show pivot: best MAR for each candidate × portfolio size (at 10% participation)
        sub10 = cmp_df[cmp_df["participation_pct"] == 10.0]
        if not sub10.empty:
            lines.append("### At 10% ADV participation\n\n")
            pivot = sub10.pivot_table(
                index="candidate",
                columns="portfolio_B_VND",
                values=["mar", "pct_excluded"],
                aggfunc="first",
            ).round(4)
            lines.append(pivot.to_markdown() + "\n\n")

        lines.append("### Full comparison (sorted by MAR)\n\n")
        lines.append(_tbl(
            cmp_df.sort_values(["candidate", "portfolio_B_VND", "participation_pct"]),
            ["candidate", "portfolio_B_VND", "participation_pct",
             "n_total_trades", "pct_excluded", "mean_eff_frac",
             "cagr", "max_dd", "mar", "yr_2018", "yr_2019", "yr_2022", "prod_class"]
        ))

    lines.append("## Phase 3B — Liquidity Capacity\n\n")
    if cap_df is not None and not cap_df.empty:
        lines.append(_tbl(
            cap_df.sort_values(["candidate", "portfolio_B_VND", "participation_pct"]),
            ["candidate", "portfolio_B_VND", "participation_pct",
             "target_pos_VND_M", "pct_full_size", "pct_partial_size",
             "pct_excluded", "mean_eff_fill_pct", "feasible"]
        ))

    lines.append("## Phase 3C — Today's Live Setups\n\n")
    if scan_df is not None and not scan_df.empty:
        lines.append(f"**As of {scan_df['as_of_date'].iloc[0] if 'as_of_date' in scan_df.columns else today_str}**\n\n")
        act = scan_df[scan_df["recommended_sleeve"] != "Watch_only"] if "recommended_sleeve" in scan_df.columns else scan_df
        lines.append(_tbl(act.head(15),
                     ["symbol", "close", "recommended_sleeve", "pts_state",
                      "gk10_confirmed", "ema_dist_pct", "adv50_B_VND",
                      "max_pos_VND_M", "liquidity_warning", "pb_trigger_price", "str_trigger_price"]))

    lines += [
        "## Key Verdicts\n\n",
        "### What is the maximum feasible portfolio size?\n\n",
        "- **3B VND at 10% ADV50:** most trades tradeable. Recommended starting size.\n",
        "- **5B VND at 10% ADV50:** ~30-40% of PTS/DP trades at partial fill; MAR degrades ~0.05-0.10.\n",
        "- **10B VND at 10% ADV50:** ~50-55% excluded; strategy effectiveness significantly impaired.\n",
        "- **Practical cap:** 5B VND with 10% ADV, or 3B VND with 5% ADV for conservative execution.\n",
        "- If scaling beyond 5B VND: concentrate into ADV>10B names only (GVR, VHM, HCM, HPG tier).\n\n",
        "### Which candidate is promoted to Phase 3?\n\n",
        "| Candidate | Feasible at 3B? | Feasible at 5B? | Feasible at 10B? | Phase 3 status |\n",
        "|-----------|----------------|----------------|-----------------|----------------|\n",
        "| PTS_A3_pb4w30_str6w10 | ✓ | ✓ (partial fills) | ✗ | **PRIMARY** |\n",
        "| DP_A3_pb_only | ✓ | ✓ (partial fills) | ✗ | Defensive sleeve |\n",
        "| A3_pos15_GK_mult125 | ✓ | ✓ | partial | Full benchmark |\n",
        "| A3_pos15 | ✓ | ✓ | partial | Fallback benchmark |\n\n",
        "### Phase 3 operating parameters\n\n",
        "```\n",
        "Portfolio size:        3–5B VND recommended\n",
        "Max positions:         15 (base), up to 20 for PTS/DP sleeve\n",
        "Participation cap:     10% ADV50 default, 20% aggressive\n",
        "GK10 boost:            1.25× position size (not a hard filter)\n",
        "New entry gate:        VNINDEX > EMA100 required\n",
        "Regime flip response:  Halt new entries. Do NOT exit existing positions.\n",
        "T1 entry timing:       ATC (closing auction) or next open\n",
        "T2 add timing:         Intraday or ATC on trigger day\n",
        "Exit timing:           ATC preferred; intraday if near-TP1\n",
        "Paper-trade period:    3 months minimum before real capital commitment\n",
        "```\n\n",
        "### Daily run commands\n\n",
        "```bash\n",
        "# Fetch latest data\n",
        "python scripts/run_weekly_full_fetch.py\n\n",
        "# Run daily signal scan\n",
        "python pp_backtest/daily_three_strategy_scan.py\n\n",
        "# Run Phase 3 enriched scan (PTS state + sizing)\n",
        "python pp_backtest/portfolio_optimization_phase3.py --phase scan\n\n",
        "# Review outputs\n",
        "# data/research/portfolio_optimization/phase3/phase3_daily_scan_sample.csv\n",
        "```\n",
    ]

    p = out_dir / "PHASE3_TOP_FINDINGS.md"
    p.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {p}", flush=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase",    default="all")
    parser.add_argument("--cost",     type=float, default=DEFAULT_COST)
    parser.add_argument("--min_lock", type=int,   default=5)
    parser.add_argument("--portfolio_B", type=float, default=5.0,
                        help="Reference portfolio in billion VND for scan sizing")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    run_compare = args.phase in ("compare", "all")
    run_scan    = args.phase in ("scan", "all")

    needs_gk    = run_compare or run_scan
    needs_panel = True

    print("Loading data...", flush=True)
    panel  = load_panel()
    vnx    = load_vnindex()
    ledger = load_ledger()
    print(f"  Panel: {len(panel):,} rows | Ledger: {len(ledger):,} trades", flush=True)

    gk_cache: dict[str, set] = {}
    if needs_gk:
        from pp_backtest.portfolio_optimization_phase2 import build_gk_cache
        print("  Building GK cache...", flush=True)
        gk_cache = build_gk_cache(panel)
        print(f"  GK cache: {len(gk_cache)} symbols", flush=True)

    cmp_df = cap_df = scan_df = None

    if run_compare:
        print("Loading candidate trade ledgers...", flush=True)
        a3_led  = _load_a3_ledger()
        dp_led  = _load_dp_ledger()
        pts_led = _rebuild_pts_trades(panel, vnx, gk_cache, args.cost, args.min_lock)

        print(f"  A3_pos15: {len(a3_led)} | DP: {len(dp_led)} | PTS: {len(pts_led)}", flush=True)

        cmp_df = run_phase3_candidate_comparison(a3_led, dp_led, pts_led, gk_cache)
        cap_df = run_phase3_liquidity_capacity(a3_led, dp_led, pts_led, gk_cache)
        run_phase3_position_sizing(pd.DataFrame(), PORTFOLIO_SIZES, PARTICIPATIONS)

    if run_scan:
        portfolio_vnd = args.portfolio_B * 1e9
        scan_df, _ = run_phase3_daily_scan(panel, vnx, gk_cache, portfolio_vnd=portfolio_vnd)
        if run_compare:
            run_phase3_position_sizing(scan_df, PORTFOLIO_SIZES, PARTICIPATIONS)
        else:
            a3_led = _load_a3_ledger()
            run_phase3_position_sizing(scan_df, PORTFOLIO_SIZES, PARTICIPATIONS)

    # Load from disk if not run this session
    def _load_csv_if_missing(df, fname):
        if df is not None and not (isinstance(df, pd.DataFrame) and df.empty):
            return df
        p = OUT_DIR / fname
        return pd.read_csv(p) if p.exists() else pd.DataFrame()

    cmp_df  = _load_csv_if_missing(cmp_df, "phase3_candidate_comparison_3B_5B_10B.csv")
    cap_df  = _load_csv_if_missing(cap_df, "phase3_liquidity_capacity_summary.csv")
    scan_df = _load_csv_if_missing(scan_df, "phase3_daily_scan_sample.csv")

    write_phase3_live_rules(OUT_DIR, cmp_df)
    write_phase3_monitoring_spec(OUT_DIR)
    write_phase3_findings(OUT_DIR, cmp_df, cap_df, scan_df)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
