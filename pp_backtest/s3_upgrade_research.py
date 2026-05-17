#!/usr/bin/env python3
"""
S3 EMA21/55 Upgrade Research — 6 Tests.

Tests whether S3 can move beyond RESEARCH_ONLY.
Corrected liquidity throughout: adv50_VND = close_kVND * volume * 1000.
A3 is not touched. All gates evidence-based.

Usage:
  .venv\\Scripts\\python.exe pp_backtest/s3_upgrade_research.py --test all
  .venv\\Scripts\\python.exe pp_backtest/s3_upgrade_research.py --test 1
  .venv\\Scripts\\python.exe pp_backtest/s3_upgrade_research.py --test 2
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.portfolio_optimization_phase1 import (
    _build_signal_cache, _exit_tp_trail,
    load_panel, load_vnindex, get_universe,
    compute_gk, portfolio_metrics,
    STRATEGY_CONFIGS, DEFAULT_COST, EXCLUDE_VIN3,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2,
    _annual_return,
)
from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr

OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "missing_work"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Constants
ANN           = 252
PORTFOLIO_VND = 5e9
MAX_SLOTS     = 20
PARTICIPATION = 0.10
COST          = DEFAULT_COST
MIN_LOCK      = 5

EXIT_A3 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5, "max_hold": 250}
EXIT_S3 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": 250}


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def _regime_gate_100(vnx: pd.DataFrame) -> pd.Series:
    """VNINDEX EMA20 > EMA100 — the documented A3 hard block."""
    w = vnx.sort_values("date").reset_index(drop=True)
    c = w["close"].astype(float)
    ema20  = c.ewm(span=20,  adjust=False).mean()
    ema100 = c.ewm(span=100, adjust=False).mean()
    gate   = ema20 > ema100
    idx    = pd.to_datetime(w["date"]).dt.normalize()
    return pd.Series(gate.values, index=idx)


def _build_breadth_series(panel: pd.DataFrame, universe: list[str],
                           ema_fast: int, ema_slow: int) -> pd.Series:
    """Pct of universe symbols with bull cloud at each date."""
    print("  Building breadth series...", flush=True)
    records = []
    for sym, sdf in panel[panel["symbol"].isin(universe)].groupby("symbol", sort=False):
        sdf  = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < ema_slow + 5:
            continue
        c    = sdf["close"].astype(float)
        cd   = ema_cloud(c, ema_fast, ema_slow)
        bull = cd["cloud_bull"].values.astype(bool)
        dates = pd.to_datetime(sdf["date"]).dt.normalize().values
        for d, b in zip(dates, bull):
            records.append({"date": d, "bull": int(b)})
    df  = pd.DataFrame(records)
    if df.empty:
        return pd.Series(dtype=float)
    grp = df.groupby("date").agg(n_bull=("bull", "sum"), n_total=("bull", "count"))
    return (grp["n_bull"] / grp["n_total"].clip(lower=1)).rename("breadth")


# ─────────────────────────────────────────────────────────────────────────────
# Core trade builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_trades(
    cache: dict,
    exit_cfg: dict,
    gate_by_date: pd.Series | None = None,
    gk_cache: dict | None = None,
    gk_window: int | None = None,
    breadth: pd.Series | None = None,
    breadth_floor: float | None = None,
    adv_floor_vnd: float | None = None,
    adv50_map: dict | None = None,
    s3_cache: dict | None = None,
    s3_lead_window: int | None = None,
    max_hold_override: int | None = None,
    tp_pct_override: float | None = None,
    trail_mult_override: float | None = None,
    no_progress_pct: float | None = None,
    no_progress_bars: int | None = None,
    cloud_loss_bars: int | None = None,
    slow_ema_cache: dict | None = None,
) -> pd.DataFrame:
    """
    Build per-trade ledger from signal cache with optional filters.
    Returns DataFrame with all raw trades.
    """
    rows = []
    cfg = dict(exit_cfg)
    if max_hold_override is not None:
        cfg["max_hold"] = max_hold_override
    if tp_pct_override is not None:
        cfg["tp_pct"] = tp_pct_override
    if trail_mult_override is not None:
        cfg["trail_mult"] = trail_mult_override

    for sym, data in cache.items():
        close_arr = data["close"]
        high_arr  = data["high"]
        atr_arr   = data["atr"]
        dates     = data["dates"]
        n         = len(close_arr)
        slow_arr  = data["slow"]

        for si in data["sig_idxs"]:
            entry_i = si + 1
            if entry_i >= n:
                continue

            sig_date   = pd.Timestamp(dates[si]).normalize()
            entry_date = pd.Timestamp(dates[entry_i]).normalize()

            # Regime gate
            if gate_by_date is not None:
                if not bool(gate_by_date.get(sig_date, True)):
                    continue

            # Breadth filter
            if breadth is not None and breadth_floor is not None:
                b_val = breadth.get(sig_date, np.nan)
                if np.isnan(b_val) or b_val < breadth_floor:
                    continue

            # GK filter
            has_gk = False
            if gk_cache is not None:
                gk_dates = gk_cache.get(sym, set())
                if gk_window is not None:
                    has_gk = any(
                        abs((sig_date - gd).days) <= gk_window
                        for gd in gk_dates
                    )

            if gk_cache is not None and gk_window is not None and not has_gk:
                continue

            # S3 lead check
            has_s3_lead = False
            s3_lead_bars = None
            if s3_cache is not None and s3_lead_window is not None:
                s3_data = s3_cache.get(sym)
                if s3_data is not None:
                    s3_dates = [pd.Timestamp(s3_data["dates"][k]).normalize()
                                for k in s3_data["sig_idxs"]]
                    for sd in s3_dates:
                        diff = (sig_date - sd).days
                        if 0 < diff <= s3_lead_window * 2:
                            has_s3_lead = True
                            s3_lead_bars = diff
                            break

            entry_price = close_arr[entry_i]
            if entry_price <= 0:
                continue

            # Custom exit with cloud-loss or no-progress rules
            if cloud_loss_bars is not None or no_progress_pct is not None:
                hold_bars, gross, exit_reason = _exit_custom(
                    close_arr, high_arr, atr_arr, slow_arr,
                    entry_i, entry_price, cfg,
                    cloud_loss_bars=cloud_loss_bars,
                    no_progress_pct=no_progress_pct,
                    no_progress_bars=no_progress_bars,
                )
            else:
                hold_bars, gross, exit_reason = _exit_tp_trail(
                    close_arr, high_arr, atr_arr, entry_i, entry_price, cfg
                )

            exit_i    = min(entry_i + hold_bars, n - 1)
            exit_date = pd.Timestamp(dates[exit_i]).normalize()
            net       = gross - COST

            # ADV50 at entry
            adv50_val = 0.0
            if adv50_map is not None:
                s = adv50_map.get(sym)
                if s is not None:
                    valid = s[s.index <= entry_date].dropna()
                    if not valid.empty:
                        adv50_val = float(valid.iloc[-1])

            if adv_floor_vnd is not None and adv50_val < adv_floor_vnd:
                continue

            rows.append({
                "symbol":            sym,
                "signal_date":       sig_date,
                "entry_date":        entry_date,
                "exit_date":         exit_date,
                "entry_price":       round(entry_price, 4),
                "exit_price":        round(close_arr[exit_i], 4),
                "gross_return":      round(gross, 6),
                "net_return":        round(net, 6),
                "hold_bars":         hold_bars,
                "exit_reason":       exit_reason,
                "has_gk":            has_gk,
                "has_s3_lead":       has_s3_lead,
                "s3_lead_bars":      s3_lead_bars,
                "adv50_value":       adv50_val,
                "ema_dist_at_entry": round(
                    (entry_price - data["slow"][entry_i]) / max(data["slow"][entry_i], 1e-9), 4
                ),
                "mom20_at_entry":    round(data["mom20"][entry_i], 4),
                "t1_frac":           0.5,
                "total_frac":        1.0,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"]  = pd.to_datetime(df["exit_date"])
        df["signal_date"] = pd.to_datetime(df["signal_date"])
    return df


def _exit_custom(
    close_arr, high_arr, atr_arr, slow_arr,
    start, entry_price, cfg,
    cloud_loss_bars=None, no_progress_pct=None, no_progress_bars=None,
):
    """Extended exit with cloud-loss and no-progress rules on top of TP/trail."""
    tp_pct     = float(cfg.get("tp_pct", 0.18))
    tp_frac    = float(cfg.get("tp_frac", 0.50))
    trail_mult = float(cfg.get("trail_mult", 3.5))
    max_hold   = int(cfg.get("max_hold", 250))
    tp_price   = entry_price * (1.0 + tp_pct)
    tp_hit     = False
    high_water = entry_price
    below_slow_count = 0
    n = len(close_arr)

    for k in range(start + 1, min(start + max_hold + 1, n)):
        c   = close_arr[k]
        atr = atr_arr[k]
        bar = k - start

        # Cloud-loss exit (below slow EMA for N bars)
        if cloud_loss_bars is not None:
            if c < slow_arr[k]:
                below_slow_count += 1
                if below_slow_count >= cloud_loss_bars and bar >= MIN_LOCK:
                    gross = (tp_frac * tp_pct + (1 - tp_frac) * (c / entry_price - 1)) if tp_hit else (c / entry_price - 1)
                    return bar, gross, "cloud_loss"
            else:
                below_slow_count = 0

        # No-progress exit
        if (no_progress_pct is not None and no_progress_bars is not None
                and bar == no_progress_bars and not tp_hit):
            peak = max(close_arr[start:k + 1])
            if (peak / entry_price - 1) < no_progress_pct:
                gross = c / entry_price - 1
                return bar, gross, "no_progress"

        if not tp_hit:
            if high_arr[k] >= tp_price:
                tp_hit = True
                high_water = max(c, tp_price)
        if tp_hit:
            high_water = max(high_water, c)
            if c <= high_water - trail_mult * atr:
                gross = tp_frac * tp_pct + (1 - tp_frac) * (c / entry_price - 1)
                return bar, gross, "tp_trail"

    c     = close_arr[min(start + max_hold, n - 1)]
    gross = (tp_frac * tp_pct + (1 - tp_frac) * (c / entry_price - 1)) if tp_hit else (c / entry_price - 1)
    return min(max_hold, n - 1 - start), gross, "max_hold"


def _metrics(trades_df: pd.DataFrame, adv50_map: dict) -> dict:
    """Tag ADV, simulate equity, compute portfolio_metrics."""
    if trades_df.empty:
        return {}
    df = _tag_adv50(trades_df, adv50_map) if "adv50_value" not in trades_df.columns or (trades_df["adv50_value"] == 0).all() else trades_df.copy()
    eq, _ = _build_equity_adv_capped_v2(
        df, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION,
        rank_col="ema_dist_at_entry",
    )
    if eq.empty:
        return {}
    m = portfolio_metrics(eq, df[df["net_return"].notna()])
    # Annual returns
    for yr in range(2014, 2027):
        m[f"yr_{yr}"] = _annual_return(eq, yr)
    return m


def _by_year_stability(trades_df: pd.DataFrame, adv50_map: dict) -> pd.DataFrame:
    """Annual MAR and returns from full equity simulation."""
    m = _metrics(trades_df, adv50_map)
    rows = []
    for yr in range(2014, 2027):
        ret = m.get(f"yr_{yr}", np.nan)
        if not np.isnan(ret):
            rows.append({"year": yr, "annual_return": round(ret, 4)})
    return pd.DataFrame(rows)


def _tp_rate(trades_df: pd.DataFrame) -> float:
    if trades_df.empty:
        return np.nan
    return float((trades_df["exit_reason"] == "tp_trail").mean())


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — S3 as A3 lead indicator
# ─────────────────────────────────────────────────────────────────────────────

def run_test1(a3_trades: pd.DataFrame, s3_cache: dict, adv50_map: dict):
    print("\n=== TEST 1: S3 as A3 lead indicator ===", flush=True)

    a3 = a3_trades.copy()
    a3["signal_date"] = pd.to_datetime(a3["signal_date"])

    # Build s3 signal date lookup: sym -> sorted list of signal dates
    s3_sigs: dict[str, list] = {}
    for sym, data in s3_cache.items():
        s3_sigs[sym] = sorted(
            pd.Timestamp(data["dates"][k]).normalize()
            for k in data["sig_idxs"]
        )

    rows = []
    for window in [5, 10, 20, 30]:
        a3_copy = a3.copy()
        def has_lead(sym, sig_date, w=window):
            for sd in s3_sigs.get(sym, []):
                diff = (sig_date - sd).days
                if 0 < diff <= w * 2:
                    return True
            return False

        a3_copy["has_s3_lead"] = [
            has_lead(sym, sd)
            for sym, sd in zip(a3_copy["symbol"], a3_copy["signal_date"])
        ]

        with_s3    = a3_copy[a3_copy["has_s3_lead"]]
        without_s3 = a3_copy[~a3_copy["has_s3_lead"]]

        for label, sub in [("with_s3", with_s3), ("without_s3", without_s3)]:
            if sub.empty:
                continue
            m = _metrics(sub, adv50_map)
            rows.append({
                "s3_lead_window_bars": window,
                "group":              label,
                "n_trades":           len(sub),
                "n_with_s3_lead":     int(sub["has_s3_lead"].sum()) if label == "with_s3" else 0,
                "pct_a3_has_lead":    round(a3_copy["has_s3_lead"].mean(), 4),
                "mar":                round(m.get("mar", np.nan), 4),
                "cagr":               round(m.get("cagr", np.nan), 4),
                "max_dd":             round(m.get("max_dd", np.nan), 4),
                "avg_net_ret":        round(sub["net_return"].mean(), 4),
                "hit_rate":           round((sub["net_return"] > 0).mean(), 4),
                "tp1_rate":           round(_tp_rate(sub), 4),
                "avg_hold_bars":      round(sub["hold_bars"].mean(), 1),
                "pct_adv_capped":     round((sub["adv50_value"] > 0).mean(), 4),
            })
        print(f"  window={window}: with_s3={len(with_s3)}, without_s3={len(without_s3)}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "s3_lead_a3_analysis.csv", index=False)
    print(f"  Saved s3_lead_a3_analysis.csv ({len(out)} rows)", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — S3 as scout before A3
# ─────────────────────────────────────────────────────────────────────────────

def run_test2(s3_cache: dict, a3_cache: dict, adv50_map: dict, regime: pd.Series):
    print("\n=== TEST 2: S3 scout before A3 ===", flush=True)

    # Build A3 signal lookup: sym -> sorted list of (sig_date, entry_i)
    a3_sigs: dict[str, list] = {}
    for sym, data in a3_cache.items():
        a3_sigs[sym] = sorted(
            pd.Timestamp(data["dates"][k]).normalize()
            for k in data["sig_idxs"]
        )

    rows = []
    for scout_pct in [0.10, 0.20, 0.25, 0.33]:
        for confirm_window in [10, 20, 30]:
            for no_confirm_exit in [20, 30, 40]:
                scouts_all, scouts_conv, scouts_noconv = [], [], []

                for sym, data in s3_cache.items():
                    close_arr = data["close"]
                    high_arr  = data["high"]
                    atr_arr   = data["atr"]
                    slow_arr  = data["slow"]
                    dates     = data["dates"]
                    n         = len(close_arr)

                    a3_sym_sigs = a3_sigs.get(sym, [])

                    for si in data["sig_idxs"]:
                        entry_i    = si + 1
                        if entry_i >= n:
                            continue
                        sig_date   = pd.Timestamp(dates[si]).normalize()
                        entry_date = pd.Timestamp(dates[entry_i]).normalize()
                        if not bool(regime.get(sig_date, True)):
                            continue

                        entry_price = close_arr[entry_i]
                        if entry_price <= 0:
                            continue

                        # Check if A3 confirms within window
                        a3_confirm_date = None
                        for asd in a3_sym_sigs:
                            diff_bars = int((asd - sig_date).days * 5 / 7)
                            if 0 < diff_bars <= confirm_window:
                                a3_confirm_date = asd
                                break

                        converted = a3_confirm_date is not None

                        # Simulate scout exit
                        max_hold = confirm_window + 5 if converted else no_confirm_exit
                        # EMA55 loss check (cloud_loss_bars=2 if no A3 confirm)
                        cl_bars = None if converted else 2
                        hold_bars, gross, exit_reason = _exit_custom(
                            close_arr, high_arr, atr_arr, slow_arr,
                            entry_i, entry_price,
                            {"tp_pct": 0.18, "tp_frac": 0.5, "trail_mult": 3.5, "max_hold": max_hold},
                            cloud_loss_bars=cl_bars,
                        )
                        exit_i    = min(entry_i + hold_bars, n - 1)
                        exit_date = pd.Timestamp(dates[exit_i]).normalize()
                        net       = gross - COST

                        adv50_val = 0.0
                        s = adv50_map.get(sym)
                        if s is not None:
                            valid = s[s.index <= entry_date].dropna()
                            if not valid.empty:
                                adv50_val = float(valid.iloc[-1])

                        rec = {
                            "symbol":      sym,
                            "signal_date": sig_date,
                            "entry_date":  entry_date,
                            "exit_date":   exit_date,
                            "gross_return": round(gross, 6),
                            "net_return":   round(net * scout_pct, 6),
                            "hold_bars":    hold_bars,
                            "exit_reason":  exit_reason,
                            "converted":    converted,
                            "adv50_value":  adv50_val,
                            "has_gk":       False,
                            "ema_dist_at_entry": round(
                                (entry_price - data["slow"][entry_i]) / max(data["slow"][entry_i], 1e-9), 4),
                            "mom20_at_entry": round(data["mom20"][entry_i], 4),
                            "t1_frac": 0.5, "total_frac": scout_pct,
                        }
                        scouts_all.append(rec)
                        (scouts_conv if converted else scouts_noconv).append(rec)

                df_all  = pd.DataFrame(scouts_all)
                df_conv = pd.DataFrame(scouts_conv)
                df_nc   = pd.DataFrame(scouts_noconv)

                if df_all.empty:
                    continue

                for d in [df_all, df_conv, df_nc]:
                    if not d.empty:
                        d["entry_date"]  = pd.to_datetime(d["entry_date"])
                        d["exit_date"]   = pd.to_datetime(d["exit_date"])
                        d["signal_date"] = pd.to_datetime(d["signal_date"])

                m_all  = _metrics(df_all,  adv50_map) if not df_all.empty  else {}
                m_conv = _metrics(df_conv, adv50_map) if not df_conv.empty else {}
                m_nc   = _metrics(df_nc,   adv50_map) if not df_nc.empty   else {}

                conv_rate = len(df_conv) / max(len(df_all), 1)

                rows.append({
                    "scout_pct":         scout_pct,
                    "confirm_window":    confirm_window,
                    "no_confirm_exit":   no_confirm_exit,
                    "n_scouts":          len(df_all),
                    "n_converted":       len(df_conv),
                    "n_no_convert":      len(df_nc),
                    "conversion_rate":   round(conv_rate, 4),
                    "mar_all":           round(m_all.get("mar",  np.nan), 4),
                    "cagr_all":          round(m_all.get("cagr", np.nan), 4),
                    "max_dd_all":        round(m_all.get("max_dd", np.nan), 4),
                    "avg_ret_converted": round(df_conv["net_return"].mean(), 4) if not df_conv.empty else np.nan,
                    "avg_ret_noconvert": round(df_nc["net_return"].mean(),   4) if not df_nc.empty   else np.nan,
                    "hit_rate_conv":     round((df_conv["net_return"] > 0).mean(), 4) if not df_conv.empty else np.nan,
                    "hit_rate_nc":       round((df_nc["net_return"]   > 0).mean(), 4) if not df_nc.empty   else np.nan,
                    "false_scout_loss":  round(df_nc["net_return"].clip(upper=0).mean(), 4) if not df_nc.empty else np.nan,
                })
                print(f"  scout={scout_pct} confirm={confirm_window} nc_exit={no_confirm_exit}: "
                      f"n={len(df_all)} conv={conv_rate:.1%}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "s3_scout_to_a3_tests.csv", index=False)
    print(f"  Saved s3_scout_to_a3_tests.csv ({len(out)} rows)", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — S3 with GK confirmation
# ─────────────────────────────────────────────────────────────────────────────

def run_test3(s3_base: pd.DataFrame, gk_cache_s: dict, adv50_map: dict):
    print("\n=== TEST 3: S3 + GK confirmation ===", flush=True)
    rows = []

    df = s3_base.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])

    def tag_gk(df, window):
        def check(sym, sd):
            gk_dates = gk_cache_s.get(sym, set())
            return any(abs((sd - gd).days) <= window for gd in gk_dates)
        return df.apply(lambda r: check(r["symbol"], r["signal_date"]), axis=1)

    # Baseline (no GK filter)
    m0 = _metrics(df, adv50_map)
    rows.append({
        "variant": "no_gk_filter",
        "gk_window": None,
        "n_trades": len(df),
        "pct_with_gk": np.nan,
        "missed_winners": np.nan,
        "avoided_losers": np.nan,
        "mar": round(m0.get("mar", np.nan), 4),
        "cagr": round(m0.get("cagr", np.nan), 4),
        "max_dd": round(m0.get("max_dd", np.nan), 4),
        "hit_rate": round((df["net_return"] > 0).mean(), 4),
        "tp1_rate": round(_tp_rate(df), 4),
    })

    for window in [3, 5, 10]:
        df["has_gk"] = tag_gk(df, window)
        gk_only  = df[df["has_gk"]]
        no_gk    = df[~df["has_gk"]]

        pct_gk = df["has_gk"].mean()
        missed_w = int((no_gk["net_return"] > 0).sum())
        avoided_l = int((no_gk["net_return"] < 0).sum())

        m = _metrics(gk_only, adv50_map)
        rows.append({
            "variant":        f"gk_within_{window}bars",
            "gk_window":      window,
            "n_trades":       len(gk_only),
            "pct_with_gk":    round(pct_gk, 4),
            "missed_winners": missed_w,
            "avoided_losers": avoided_l,
            "mar":            round(m.get("mar",    np.nan), 4),
            "cagr":           round(m.get("cagr",   np.nan), 4),
            "max_dd":         round(m.get("max_dd", np.nan), 4),
            "hit_rate":       round((gk_only["net_return"] > 0).mean(), 4) if not gk_only.empty else np.nan,
            "tp1_rate":       round(_tp_rate(gk_only), 4),
        })
        print(f"  gk_window={window}: n={len(gk_only)}, pct_with_gk={pct_gk:.1%}", flush=True)

    # GK as multiplier (1.25×) — keep all trades, boost size for GK ones
    df["has_gk"] = tag_gk(df, 5)
    m_mult = _metrics(df, adv50_map)  # _build_equity_adv_capped_v2 already handles gk_mult via has_gk
    rows.append({
        "variant": "gk_mult_125x",
        "gk_window": 5,
        "n_trades": len(df),
        "pct_with_gk": round(df["has_gk"].mean(), 4),
        "missed_winners": 0,
        "avoided_losers": 0,
        "mar": round(m_mult.get("mar", np.nan), 4),
        "cagr": round(m_mult.get("cagr", np.nan), 4),
        "max_dd": round(m_mult.get("max_dd", np.nan), 4),
        "hit_rate": round((df["net_return"] > 0).mean(), 4),
        "tp1_rate": round(_tp_rate(df), 4),
    })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "s3_gk_overlay_tests.csv", index=False)
    print(f"  Saved s3_gk_overlay_tests.csv ({len(out)} rows)", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — S3 breadth regime filter
# ─────────────────────────────────────────────────────────────────────────────

def run_test4(s3_base: pd.DataFrame, a3_breadth: pd.Series, s3_breadth: pd.Series, adv50_map: dict):
    print("\n=== TEST 4: S3 breadth regime filter ===", flush=True)

    df = s3_base.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])

    def tag_breadth(series_name, series, floor):
        vals = df["signal_date"].map(lambda d: series.get(d.normalize(), np.nan))
        return vals >= floor, vals

    rows = []

    # Baseline
    m0 = _metrics(df, adv50_map)
    rows.append({
        "filter": "no_breadth_filter",
        "breadth_type": "none",
        "floor": np.nan,
        "n_trades": len(df),
        "pct_kept": 1.0,
        "missed_winners": 0,
        "avoided_losers": 0,
        "mar":     round(m0.get("mar",    np.nan), 4),
        "cagr":    round(m0.get("cagr",   np.nan), 4),
        "max_dd":  round(m0.get("max_dd", np.nan), 4),
        "hit_rate": round((df["net_return"] > 0).mean(), 4),
    })

    for btype, series in [("a3_breadth", a3_breadth), ("s3_breadth", s3_breadth)]:
        for floor in [0.40, 0.50, 0.60]:
            mask, bvals = tag_breadth(btype, series, floor)
            kept    = df[mask]
            dropped = df[~mask]
            if kept.empty:
                continue
            missed_w  = int((dropped["net_return"] > 0).sum())
            avoided_l = int((dropped["net_return"] < 0).sum())
            m = _metrics(kept, adv50_map)
            rows.append({
                "filter":         f"{btype}>={floor:.0%}",
                "breadth_type":   btype,
                "floor":          floor,
                "n_trades":       len(kept),
                "pct_kept":       round(mask.mean(), 4),
                "missed_winners": missed_w,
                "avoided_losers": avoided_l,
                "mar":     round(m.get("mar",    np.nan), 4),
                "cagr":    round(m.get("cagr",   np.nan), 4),
                "max_dd":  round(m.get("max_dd", np.nan), 4),
                "hit_rate": round((kept["net_return"] > 0).mean(), 4),
            })
            print(f"  {btype}>={floor:.0%}: n={len(kept)}, kept={mask.mean():.1%}", flush=True)

    # Improving breadth over 10/20 bars
    for window in [10, 20]:
        bvals = df["signal_date"].map(lambda d: a3_breadth.get(d.normalize(), np.nan))
        bvals_prior = df["signal_date"].map(
            lambda d: a3_breadth.get((d - pd.Timedelta(days=int(window * 1.4))).normalize(), np.nan)
        )
        improving = (bvals > bvals_prior) & bvals.notna() & bvals_prior.notna()
        kept = df[improving]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter":         f"a3_breadth_improving_{window}bars",
            "breadth_type":   "a3_breadth",
            "floor":          np.nan,
            "n_trades":       len(kept),
            "pct_kept":       round(improving.mean(), 4),
            "missed_winners": int((df[~improving]["net_return"] > 0).sum()),
            "avoided_losers": int((df[~improving]["net_return"] < 0).sum()),
            "mar":     round(m.get("mar",    np.nan), 4),
            "cagr":    round(m.get("cagr",   np.nan), 4),
            "max_dd":  round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((kept["net_return"] > 0).mean(), 4),
        })
        print(f"  breadth_improving_{window}bars: n={len(kept)}, kept={improving.mean():.1%}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "s3_breadth_regime_tests.csv", index=False)
    print(f"  Saved s3_breadth_regime_tests.csv ({len(out)} rows)", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — S3 exit optimization
# ─────────────────────────────────────────────────────────────────────────────

def run_test5(s3_cache: dict, adv50_map: dict, regime: pd.Series):
    print("\n=== TEST 5: S3 exit optimization ===", flush=True)
    rows = []

    tp_variants    = [0.10, 0.12, 0.15, 0.18]
    trail_variants = [2.0, 2.5, 3.0, 3.5]
    max_hold_vars  = [60, 90, 120, 180, 250]
    no_progress    = [(0.05, 20), (0.05, 30), (0.08, 30)]
    cloud_loss_bs  = [2, 3]

    combos = []
    for tp in tp_variants:
        for trail in trail_variants:
            combos.append(("tp_trail", tp, trail, 250, None, None, None))
    for mh in max_hold_vars:
        combos.append(("max_hold", 0.18, 3.5, mh, None, None, None))
    for np_pct, np_bars in no_progress:
        combos.append(("no_progress", 0.18, 3.5, 250, np_pct, np_bars, None))
    for cl_b in cloud_loss_bs:
        combos.append(("cloud_loss", 0.18, 3.5, 250, None, None, cl_b))

    for label, tp, trail, mh, np_pct, np_bars, cl_b in combos:
        cfg = {"tp_pct": tp, "tp_frac": 0.50, "trail_mult": trail, "max_hold": mh}
        df = _build_trades(
            s3_cache, cfg, gate_by_date=regime,
            adv50_map=adv50_map,
            cloud_loss_bars=cl_b,
            no_progress_pct=np_pct,
            no_progress_bars=np_bars,
        )
        if df.empty:
            continue
        m = _metrics(df, adv50_map)
        rows.append({
            "variant":          label,
            "tp_pct":           tp,
            "trail_mult":       trail,
            "max_hold":         mh,
            "no_progress_pct":  np_pct,
            "no_progress_bars": np_bars,
            "cloud_loss_bars":  cl_b,
            "n_trades":         len(df),
            "mar":              round(m.get("mar",    np.nan), 4),
            "cagr":             round(m.get("cagr",   np.nan), 4),
            "max_dd":           round(m.get("max_dd", np.nan), 4),
            "hit_rate":         round((df["net_return"] > 0).mean(), 4),
            "tp1_rate":         round(_tp_rate(df), 4),
            "avg_hold_bars":    round(df["hold_bars"].mean(), 1),
        })

    out = pd.DataFrame(rows)
    out = out.sort_values("mar", ascending=False)
    out.to_csv(OUT_DIR / "s3_exit_optimization_tests.csv", index=False)
    print(f"  Saved s3_exit_optimization_tests.csv ({len(out)} rows)", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — S3 high-liquidity subset
# ─────────────────────────────────────────────────────────────────────────────

def run_test6(s3_base: pd.DataFrame, adv50_map: dict):
    print("\n=== TEST 6: S3 high-liquidity subset ===", flush=True)

    df = s3_base.copy()
    if (df["adv50_value"] == 0).all():
        df = _tag_adv50(df, adv50_map)

    rows = []

    # Baseline
    m0 = _metrics(df, adv50_map)
    rows.append({
        "filter": "no_adv_floor",
        "adv_floor_B": 0,
        "n_trades": len(df),
        "pct_kept": 1.0,
        "mar":     round(m0.get("mar",    np.nan), 4),
        "cagr":    round(m0.get("cagr",   np.nan), 4),
        "max_dd":  round(m0.get("max_dd", np.nan), 4),
        "hit_rate": round((df["net_return"] > 0).mean(), 4),
        "avg_adv_B": round(df["adv50_value"].mean() / 1e9, 2),
    })

    for floor_b in [10, 20, 50, 100]:
        floor_vnd = floor_b * 1e9
        kept = df[df["adv50_value"] >= floor_vnd]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter":    f"adv>={floor_b}B",
            "adv_floor_B": floor_b,
            "n_trades":  len(kept),
            "pct_kept":  round(len(kept) / len(df), 4),
            "mar":       round(m.get("mar",    np.nan), 4),
            "cagr":      round(m.get("cagr",   np.nan), 4),
            "max_dd":    round(m.get("max_dd", np.nan), 4),
            "hit_rate":  round((kept["net_return"] > 0).mean(), 4),
            "avg_adv_B": round(kept["adv50_value"].mean() / 1e9, 2),
        })
        print(f"  adv>={floor_b}B: n={len(kept)}, kept={len(kept)/len(df):.1%}", flush=True)

    # Top N ADV symbols
    sym_adv = df.groupby("symbol")["adv50_value"].median().sort_values(ascending=False)
    for top_n in [50, 100]:
        top_syms = set(sym_adv.head(top_n).index)
        kept = df[df["symbol"].isin(top_syms)]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter":    f"top_{top_n}_adv_symbols",
            "adv_floor_B": np.nan,
            "n_trades":  len(kept),
            "pct_kept":  round(len(kept) / len(df), 4),
            "mar":       round(m.get("mar",    np.nan), 4),
            "cagr":      round(m.get("cagr",   np.nan), 4),
            "max_dd":    round(m.get("max_dd", np.nan), 4),
            "hit_rate":  round((kept["net_return"] > 0).mean(), 4),
            "avg_adv_B": round(kept["adv50_value"].mean() / 1e9, 2),
        })
        print(f"  top_{top_n}_adv: n={len(kept)}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "s3_liquidity_subset_tests.csv", index=False)
    print(f"  Saved s3_liquidity_subset_tests.csv ({len(out)} rows)", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Findings writers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(v, pct=False, dec=3):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    if pct:
        return f"{v:.1%}"
    return f"{v:.{dec}f}"


def write_test1_findings(df: pd.DataFrame):
    lines = ["# S3 Lead A3 — Findings\n\n",
             "Does prior S3 signal (within N bars) improve A3 trade quality?\n\n",
             "## Summary Table\n\n",
             "| S3 Lead Window | Group | N | MAR | CAGR | MaxDD | Avg Net Ret | Hit Rate | TP1 Rate |\n",
             "|----------------|-------|---|-----|------|-------|-------------|----------|----------|\n"]
    for _, r in df.iterrows():
        lines.append(f"| {r['s3_lead_window_bars']} bars | {r['group']} | {r['n_trades']} | "
                     f"{_fmt(r['mar'])} | {_fmt(r['cagr'], pct=True)} | {_fmt(r['max_dd'], pct=True)} | "
                     f"{_fmt(r['avg_net_ret'], pct=True)} | {_fmt(r['hit_rate'], pct=True)} | "
                     f"{_fmt(r['tp1_rate'], pct=True)} |\n")

    # Verdict
    w30 = df[(df["s3_lead_window_bars"] == 30)]
    with_s3 = w30[w30["group"] == "with_s3"]
    without  = w30[w30["group"] == "without_s3"]
    if not with_s3.empty and not without.empty:
        mar_diff = float(with_s3["mar"].iloc[0]) - float(without["mar"].iloc[0])
        verdict = "OVERLAY_SUPPORTED" if mar_diff > 0.02 else "OVERLAY_NOT_SUPPORTED"
        lines += [f"\n## Verdict: {verdict}\n\n",
                  f"MAR difference at 30-bar window (with_s3 − without_s3): {mar_diff:+.3f}\n\n",
                  f"Gate: +0.02 MAR required to justify using S3 as A3 priority overlay.\n"]

    (OUT_DIR / "S3_LEAD_A3_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  Saved S3_LEAD_A3_FINDINGS.md", flush=True)


def write_test2_findings(df: pd.DataFrame):
    lines = ["# S3 Scout to A3 — Findings\n\n",
             "## Top 10 configurations by MAR\n\n",
             "| Scout% | Confirm Window | NC Exit | N | Conv Rate | MAR | CAGR | MaxDD | Ret(Conv) | Ret(NC) |\n",
             "|--------|---------------|---------|---|-----------|-----|------|-------|-----------|--------|\n"]
    top10 = df.sort_values("mar_all", ascending=False).head(10)
    for _, r in top10.iterrows():
        lines.append(f"| {r['scout_pct']:.0%} | {int(r['confirm_window'])} bars | "
                     f"{int(r['no_confirm_exit'])} bars | {r['n_scouts']} | "
                     f"{_fmt(r['conversion_rate'], pct=True)} | {_fmt(r['mar_all'])} | "
                     f"{_fmt(r['cagr_all'], pct=True)} | {_fmt(r['max_dd_all'], pct=True)} | "
                     f"{_fmt(r['avg_ret_converted'], pct=True)} | {_fmt(r['avg_ret_noconvert'], pct=True)} |\n")

    best = top10.iloc[0] if not top10.empty else None
    if best is not None:
        verdict = "SCOUT_SUPPORTED" if float(best["mar_all"]) >= 0.30 else "SCOUT_NOT_SUPPORTED"
        lines += [f"\n## Verdict: {verdict}\n\n",
                  f"Best MAR: {_fmt(best['mar_all'])} at scout={best['scout_pct']:.0%}, "
                  f"confirm={int(best['confirm_window'])} bars.\n\n",
                  f"Gate: MAR >= 0.30 required for PAPER_TRADE_SHADOW consideration.\n"]

    (OUT_DIR / "S3_SCOUT_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  Saved S3_SCOUT_FINDINGS.md", flush=True)


def write_test3_findings(df: pd.DataFrame):
    lines = ["# S3 + GK Confirmation — Findings\n\n",
             "## Results\n\n",
             "| Variant | N | % Kept | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate | Missed W | Avoided L |\n",
             "|---------|---|--------|-----|------|-------|----------|----------|----------|-----------|\n"]
    for _, r in df.iterrows():
        lines.append(f"| {r['variant']} | {r['n_trades']} | {_fmt(r['pct_with_gk'], pct=True)} | "
                     f"{_fmt(r['mar'])} | {_fmt(r['cagr'], pct=True)} | {_fmt(r['max_dd'], pct=True)} | "
                     f"{_fmt(r['hit_rate'], pct=True)} | {_fmt(r['tp1_rate'], pct=True)} | "
                     f"{int(r['missed_winners']) if not np.isnan(r['missed_winners']) else 'N/A'} | "
                     f"{int(r['avoided_losers']) if not np.isnan(r['avoided_losers']) else 'N/A'} |\n")

    base_mar = df[df["variant"] == "no_gk_filter"]["mar"].iloc[0] if "no_gk_filter" in df["variant"].values else np.nan
    best = df[df["variant"] != "no_gk_filter"].sort_values("mar", ascending=False)
    if not best.empty:
        best_mar = float(best.iloc[0]["mar"])
        verdict = "GK_IMPROVES_S3" if (not np.isnan(base_mar) and best_mar > base_mar + 0.02) else "GK_NEUTRAL_OR_HARMFUL"
        lines += [f"\n## Verdict: {verdict}\n\n",
                  f"Baseline MAR: {_fmt(base_mar)}. Best GK variant MAR: {_fmt(best_mar)}.\n"]

    (OUT_DIR / "S3_GK_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  Saved S3_GK_FINDINGS.md", flush=True)


def write_test4_findings(df: pd.DataFrame):
    lines = ["# S3 Breadth Regime Filter — Findings\n\n",
             "## Results\n\n",
             "| Filter | N | % Kept | MAR | CAGR | MaxDD | Hit Rate | Missed W | Avoided L |\n",
             "|--------|---|--------|-----|------|-------|----------|----------|-----------|\n"]
    for _, r in df.iterrows():
        lines.append(f"| {r['filter']} | {r['n_trades']} | {_fmt(r['pct_kept'], pct=True)} | "
                     f"{_fmt(r['mar'])} | {_fmt(r['cagr'], pct=True)} | {_fmt(r['max_dd'], pct=True)} | "
                     f"{_fmt(r['hit_rate'], pct=True)} | {r['missed_winners']} | {r['avoided_losers']} |\n")

    base = df[df["filter"] == "no_breadth_filter"]
    base_mar = float(base["mar"].iloc[0]) if not base.empty else np.nan
    best = df[df["filter"] != "no_breadth_filter"].sort_values("mar", ascending=False)
    if not best.empty:
        best_mar = float(best.iloc[0]["mar"])
        verdict = "BREADTH_FILTER_HELPS" if best_mar > base_mar + 0.02 else "BREADTH_FILTER_NEUTRAL_OR_HARMFUL"
        lines += [f"\n## Verdict: {verdict}\n\n",
                  f"Baseline MAR: {_fmt(base_mar)}. Best breadth-filtered MAR: {_fmt(best_mar)}.\n\n",
                  f"Note: Unlike A3, breadth may be a valid hard filter for S3 since S3 is currently RESEARCH_ONLY.\n"]

    (OUT_DIR / "S3_BREADTH_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  Saved S3_BREADTH_FINDINGS.md", flush=True)


def write_test5_findings(df: pd.DataFrame):
    lines = ["# S3 Exit Optimization — Findings\n\n",
             "## Top 15 configurations by MAR\n\n",
             "| Variant | TP% | Trail | MaxHold | Cloud Loss | No-Progress | N | MAR | CAGR | MaxDD | TP1 Rate | Avg Hold |\n",
             "|---------|-----|-------|---------|------------|-------------|---|-----|------|-------|----------|----------|\n"]
    top15 = df.sort_values("mar", ascending=False).head(15)
    for _, r in top15.iterrows():
        cl = f"{int(r['cloud_loss_bars'])}b" if not pd.isna(r["cloud_loss_bars"]) else "—"
        np_ = f"{r['no_progress_pct']:.0%}/{int(r['no_progress_bars'])}b" if not pd.isna(r["no_progress_pct"]) else "—"
        lines.append(f"| {r['variant']} | {r['tp_pct']:.0%} | {r['trail_mult']}× | {int(r['max_hold'])} | "
                     f"{cl} | {np_} | {r['n_trades']} | {_fmt(r['mar'])} | {_fmt(r['cagr'], pct=True)} | "
                     f"{_fmt(r['max_dd'], pct=True)} | {_fmt(r['tp1_rate'], pct=True)} | "
                     f"{r['avg_hold_bars']:.0f}b |\n")

    best = df.sort_values("mar", ascending=False).iloc[0] if not df.empty else None
    if best is not None:
        lines += [f"\n## Best exit config\n\n",
                  f"- TP: {best['tp_pct']:.0%}, Trail: {best['trail_mult']}×ATR14, MaxHold: {int(best['max_hold'])} bars\n",
                  f"- MAR: {_fmt(best['mar'])}, CAGR: {_fmt(best['cagr'], pct=True)}, MaxDD: {_fmt(best['max_dd'], pct=True)}\n\n",
                  f"Gate: Best exit cannot change RESEARCH_ONLY verdict if baseline MAR < 0.30.\n"]

    (OUT_DIR / "S3_EXIT_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  Saved S3_EXIT_FINDINGS.md", flush=True)


def write_test6_findings(df: pd.DataFrame):
    lines = ["# S3 High-Liquidity Subset — Findings\n\n",
             "## Results\n\n",
             "| Filter | N | % Kept | MAR | CAGR | MaxDD | Hit Rate | Avg ADV (B) |\n",
             "|--------|---|--------|-----|------|-------|----------|-------------|\n"]
    for _, r in df.iterrows():
        lines.append(f"| {r['filter']} | {r['n_trades']} | {_fmt(r['pct_kept'], pct=True)} | "
                     f"{_fmt(r['mar'])} | {_fmt(r['cagr'], pct=True)} | {_fmt(r['max_dd'], pct=True)} | "
                     f"{_fmt(r['hit_rate'], pct=True)} | {_fmt(r['avg_adv_B'], dec=1)} |\n")

    base_mar = float(df[df["filter"] == "no_adv_floor"]["mar"].iloc[0]) if "no_adv_floor" in df["filter"].values else np.nan
    best = df[df["filter"] != "no_adv_floor"].sort_values("mar", ascending=False)
    if not best.empty:
        best_mar = float(best.iloc[0]["mar"])
        verdict = "LIQUIDITY_FILTER_HELPS" if best_mar > base_mar + 0.02 else "LIQUIDITY_FILTER_NEUTRAL"
        lines += [f"\n## Verdict: {verdict}\n\n",
                  f"Baseline MAR: {_fmt(base_mar)}. Best liquidity-filtered MAR: {_fmt(best_mar)}.\n"]

    (OUT_DIR / "S3_LIQUIDITY_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  Saved S3_LIQUIDITY_FINDINGS.md", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Final decision memo
# ─────────────────────────────────────────────────────────────────────────────

def write_decision_memo(t1, t2, t3, t4, t5, t6, s3_base_mar: float, a3_mar: float = 0.416):
    def best_mar(df, col="mar"):
        if df is None or df.empty:
            return np.nan
        vals = df[col].dropna()
        return float(vals.max()) if not vals.empty else np.nan

    def best_mar_alt(df, col="mar_all"):
        if df is None or df.empty:
            return np.nan
        vals = df[col].dropna() if col in df.columns else pd.Series(dtype=float)
        return float(vals.max()) if not vals.empty else np.nan

    lead_overlay_mar = np.nan
    if t1 is not None and not t1.empty:
        with_s3_30 = t1[(t1["s3_lead_window_bars"] == 30) & (t1["group"] == "with_s3")]
        without_30 = t1[(t1["s3_lead_window_bars"] == 30) & (t1["group"] == "without_s3")]
        if not with_s3_30.empty and not without_30.empty:
            lead_overlay_mar = float(with_s3_30["mar"].iloc[0]) - float(without_30["mar"].iloc[0])

    scout_best   = best_mar_alt(t2)
    gk_best      = best_mar(t3)
    breadth_best = best_mar(t4)
    exit_best    = best_mar(t5)
    liq_best     = best_mar(t6)

    # Classification logic
    classification = "KEEP_RESEARCH_ONLY"
    rationale = []

    if scout_best >= 0.30 or breadth_best >= 0.30 or gk_best >= 0.30 or liq_best >= 0.30:
        classification = "PAPER_TRADE_SHADOW"
        rationale.append(f"At least one variant reached MAR >= 0.30 (scout={_fmt(scout_best)}, "
                         f"breadth={_fmt(breadth_best)}, gk={_fmt(gk_best)}, liq={_fmt(liq_best)})")

    if lead_overlay_mar > 0.02:
        classification = max(classification, "A3_PRIORITY_OVERLAY",
                             key=lambda x: ["KEEP_RESEARCH_ONLY","WATCHLIST_ONLY",
                                            "A3_PRIORITY_OVERLAY","SCOUT_ONLY_SMALL_SIZE",
                                            "PAPER_TRADE_SHADOW","PRODUCTION_CANDIDATE"].index(x))
        rationale.append(f"S3 lead improves A3 MAR by {lead_overlay_mar:+.3f} at 30-bar window")

    best_any = max(x for x in [scout_best, gk_best, breadth_best, exit_best, liq_best] if not np.isnan(x)) \
        if any(not np.isnan(x) for x in [scout_best, gk_best, breadth_best, exit_best, liq_best]) else np.nan

    if not np.isnan(best_any) and best_any >= 0.35:
        classification = "PAPER_TRADE_SHADOW"
        rationale.append(f"Best variant MAR={_fmt(best_any)} >= 0.35")

    if not rationale:
        rationale.append(f"No variant exceeded MAR 0.30 gate. S3 baseline MAR={_fmt(s3_base_mar)}.")

    lines = [
        "# S3 Upgrade Decision Memo\n\n",
        f"Date: 2026-05-16\n\n",
        "---\n\n",
        "## Reference Benchmarks\n\n",
        f"| Strategy | MAR |\n|----------|-----|\n",
        f"| A3 DP-First (production) | 0.416 |\n",
        f"| S3 standalone baseline | {_fmt(s3_base_mar)} |\n",
        f"| Gate: PAPER_TRADE_SHADOW | 0.30 |\n",
        f"| Gate: PRODUCTION_CANDIDATE | ~A3 DP |\n\n",
        "---\n\n",
        "## Test Summary\n\n",
        "| Test | Best MAR | Gate | Pass? |\n",
        "|------|----------|------|-------|\n",
        f"| T1: A3 lead overlay | MAR delta {_fmt(lead_overlay_mar)} | +0.02 delta | {'YES' if lead_overlay_mar > 0.02 else 'NO'} |\n",
        f"| T2: Scout before A3 | {_fmt(scout_best)} | 0.30 | {'YES' if scout_best >= 0.30 else 'NO'} |\n",
        f"| T3: GK confirmation | {_fmt(gk_best)} | 0.30 | {'YES' if gk_best >= 0.30 else 'NO'} |\n",
        f"| T4: Breadth regime | {_fmt(breadth_best)} | 0.30 | {'YES' if breadth_best >= 0.30 else 'NO'} |\n",
        f"| T5: Exit optimization | {_fmt(exit_best)} | 0.30 | {'YES' if exit_best >= 0.30 else 'NO'} |\n",
        f"| T6: Liquidity subset | {_fmt(liq_best)} | 0.30 | {'YES' if liq_best >= 0.30 else 'NO'} |\n\n",
        "---\n\n",
        f"## Classification: {classification}\n\n",
        "### Rationale\n\n",
    ]
    for r in rationale:
        lines.append(f"- {r}\n")

    lines += [
        "\n### Upgrade gates\n\n",
        "- **PAPER_TRADE_SHADOW**: MAR >= 0.30, stable by year, corrected liquidity passes.\n",
        "- **PRODUCTION_CANDIDATE**: MAR near A3 DP (0.416), MaxDD acceptable, OOS stable, adds combined value.\n",
        "- **A3_PRIORITY_OVERLAY**: A3 trades with prior S3 must outperform without S3 by +0.02 MAR.\n",
        "- **SCOUT_ONLY_SMALL_SIZE**: Scout-to-A3 conversion improves blended entry without increasing MaxDD.\n\n",
        "### A3 is unchanged\n\n",
        "Regardless of S3 classification, A3 DP-First production logic is not modified.\n",
    ]

    (OUT_DIR / "S3_UPGRADE_DECISION_MEMO.md").write_text("".join(lines), encoding="utf-8")
    print(f"  Saved S3_UPGRADE_DECISION_MEMO.md — Classification: {classification}", flush=True)
    return classification


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", default="all",
                        help="1|2|3|4|5|6|all")
    args = parser.parse_args()
    run = set(args.test.split(",")) if args.test != "all" else {"1","2","3","4","5","6"}

    print("Loading panel...", flush=True)
    panel = load_panel()
    print(f"  Panel: {len(panel)} rows, {panel['symbol'].nunique()} symbols", flush=True)

    print("Loading VNINDEX...", flush=True)
    vnx = load_vnindex()
    regime = _regime_gate_100(vnx)

    print("Building ADV50 map...", flush=True)
    adv50_map = _build_adv50_map(panel)

    print("Building A3 signal cache...", flush=True)
    a3_cache = _build_signal_cache(panel, "A3")
    print(f"  A3 cache: {len(a3_cache)} symbols", flush=True)

    print("Building S3 signal cache...", flush=True)
    s3_cache = _build_signal_cache(panel, "S3")
    print(f"  S3 cache: {len(s3_cache)} symbols", flush=True)

    print("Building GK caches...", flush=True)
    a3_univ = get_universe(panel, "ex_vin3")
    s3_univ = get_universe(panel, "full")

    def build_gk_cache(universe):
        gk_c = {}
        for sym, sdf in panel[panel["symbol"].isin(universe)].groupby("symbol", sort=False):
            sdf = sdf.sort_values("date").reset_index(drop=True)
            if len(sdf) < 150:
                continue
            c = sdf["close"].astype(float)
            h = sdf["high"].astype(float)
            lo = sdf.get("low", c).astype(float)
            gk = compute_gk(c, h, lo)
            buy_dates = set(pd.to_datetime(sdf.loc[gk["gk_buy"], "date"]).dt.normalize())
            if buy_dates:
                gk_c[sym] = buy_dates
        return gk_c

    gk_cache_a3 = build_gk_cache(a3_univ)
    gk_cache_s3 = build_gk_cache(s3_univ)
    print(f"  GK A3: {len(gk_cache_a3)} syms, GK S3: {len(gk_cache_s3)} syms", flush=True)

    # Build baseline trade sets
    print("Building A3 baseline trades...", flush=True)
    a3_trades = _build_trades(a3_cache, EXIT_A3, gate_by_date=regime, adv50_map=adv50_map)
    a3_trades  = _tag_adv50(a3_trades, adv50_map)
    print(f"  A3 trades: {len(a3_trades)}", flush=True)

    print("Building S3 baseline trades...", flush=True)
    s3_trades = _build_trades(s3_cache, EXIT_S3, gate_by_date=regime, adv50_map=adv50_map)
    s3_trades  = _tag_adv50(s3_trades, adv50_map)
    print(f"  S3 trades: {len(s3_trades)}", flush=True)

    # S3 baseline MAR
    s3_base_m = _metrics(s3_trades, adv50_map)
    s3_base_mar = round(s3_base_m.get("mar", np.nan), 4)
    print(f"  S3 baseline MAR={s3_base_mar}", flush=True)

    # Breadth series (for tests 4)
    print("Building breadth series...", flush=True)
    a3_breadth = _build_breadth_series(panel, a3_univ, 20, 100)
    s3_breadth = _build_breadth_series(panel, s3_univ, 21, 55)

    t1 = t2 = t3 = t4 = t5 = t6 = None

    if "1" in run:
        t1 = run_test1(a3_trades, s3_cache, adv50_map)
        write_test1_findings(t1)

    if "2" in run:
        t2 = run_test2(s3_cache, a3_cache, adv50_map, regime)
        write_test2_findings(t2)

    if "3" in run:
        t3 = run_test3(s3_trades, gk_cache_s3, adv50_map)
        write_test3_findings(t3)

    if "4" in run:
        t4 = run_test4(s3_trades, a3_breadth, s3_breadth, adv50_map)
        write_test4_findings(t4)

    if "5" in run:
        t5 = run_test5(s3_cache, adv50_map, regime)
        write_test5_findings(t5)

    if "6" in run:
        t6 = run_test6(s3_trades, adv50_map)
        write_test6_findings(t6)

    write_decision_memo(t1, t2, t3, t4, t5, t6, s3_base_mar)
    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
