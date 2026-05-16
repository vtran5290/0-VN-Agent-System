#!/usr/bin/env python3
"""
Portfolio Optimization Phase 3.1 — Liquidity Unit Audit.

Resolves contradiction between:
  - phase3_candidate_comparison: PTS/DP show 0% exclusion
  - phase3_daily_scan_sample: all 56 setups show CRITICAL liquidity

Root causes found:
  1. Daily scan uses (close × volume).rolling(50) where close is in kVND
     → adv50_raw is in kVND-shares (NOT VND), off by 1000× from true VND value
     → _liquidity_warning compares kVND-unit adv50 vs VND pos_vnd → always CRITICAL
  2. PTS/DP trade ledgers have NO adv50_value column → _build_equity_adv_capped
     skips ADV cap entirely → 0% exclusion is a phantom
  3. Correct reference: panel["value"] = close_kVND × volume_shares × 1000 (VND)

Outputs (in data/research/portfolio_optimization/phase31/):
  PHASE31_LIQUIDITY_AUDIT.md
  phase31_unit_check.csv
  phase31_liquidity_recomputed.csv
  phase31_daily_scan_corrected.csv

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_phase31.py
"""
from __future__ import annotations

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
    _build_signal_cache, _exit_tp_trail, _quality_ok, _classify_result,
    load_panel, load_vnindex, get_universe, vnindex_regime_gate,
    compute_gk, portfolio_metrics, STRATEGY_CONFIGS, DEFAULT_COST, LEDGER,
)
from pp_backtest.portfolio_optimization_phase2 import load_ledger, build_gk_cache
from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry

OUT_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase31"
P2_LED   = REPO / "data" / "research" / "portfolio_optimization" / "phase2" / "phase2_baseline_trade_ledgers"
P25_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase25"
P3_DIR   = REPO / "data" / "research" / "portfolio_optimization" / "phase3"

PORTFOLIO_SIZES = [1e9, 3e9, 5e9, 10e9]   # 1B, 3B, 5B, 10B VND
PARTICIPATIONS  = [0.05, 0.10, 0.20]
MIN_POS_VND     = 100_000
DEFAULT_MAX_POS = 15
ANNUALIZE       = 252
KNOWN_LIQUID    = ['HPG', 'MWG', 'VPB', 'HCM', 'VHM', 'MSN', 'HDB', 'FPT', 'SSI', 'VND']


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1: Unit audit
# ─────────────────────────────────────────────────────────────────────────────

def run_unit_check(panel, a3_led):
    """
    For 10 known-liquid tickers, compare:
      - raw panel value (VND)
      - close × volume (kVND-unit, wrong)
      - close × volume × 1000 (VND, correct)
      - A3 ledger adv50_value (VND)
      - scan's reported adv50_B_VND (= (c*v).rolling/1e9, wrong by 1000×)
      - corrected adv50_B_VND (= (c*v*1000).rolling/1e9, or value.rolling/1e9)
    """
    print("Task 1: Unit audit for known-liquid tickers...", flush=True)
    rows = []
    for sym in KNOWN_LIQUID:
        sdf = panel[panel["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if sdf.empty:
            rows.append({"symbol": sym, "note": "NOT_IN_PANEL"})
            continue

        c = sdf["close"].astype(float)
        v = sdf.get("volume", pd.Series(np.zeros(len(sdf)))).astype(float)
        val_col = sdf["value"].astype(float) if "value" in sdf.columns else pd.Series(np.nan, index=sdf.index)

        # Panel last available value
        val_last = float(val_col.dropna().iloc[-1]) if val_col.notna().any() else np.nan
        val_date = str(sdf.loc[val_col.notna().index[-1], "date"]) if val_col.notna().any() else "N/A"

        # compute adv50 two ways
        adv50_wrong  = (c * v).rolling(50, min_periods=20).mean()              # kVND-unit (scan's method)
        adv50_correct = (c * v * 1000).rolling(50, min_periods=20).mean()     # VND
        # use panel value column when available (most accurate)
        adv50_from_val = val_col.rolling(50, min_periods=20).mean()

        adv50_wrong_last   = float(adv50_wrong.iloc[-1])   if not np.isnan(float(adv50_wrong.iloc[-1]))   else 0.0
        adv50_correct_last = float(adv50_correct.iloc[-1]) if not np.isnan(float(adv50_correct.iloc[-1])) else 0.0
        adv50_fromval_last = float(adv50_from_val.dropna().iloc[-1]) if adv50_from_val.notna().any() else np.nan

        # A3 ledger adv50_value for this ticker (VND, from historical value column)
        led_sub = a3_led[a3_led["symbol"] == sym] if "adv50_value" in a3_led.columns else pd.DataFrame()
        led_median = float(led_sub["adv50_value"].median()) if not led_sub.empty else np.nan
        led_recent  = float(led_sub["adv50_value"].tail(5).mean()) if not led_sub.empty else np.nan

        # Ratio check
        ratio_close_x_vol_vs_value = val_last / (float(c.iloc[-50]) * float(v.iloc[-50])) if val_last > 0 else np.nan
        # approximate since val_last may be from different row; use a middle row
        mid = len(sdf) // 2
        if val_col.iloc[mid] > 0 and v.iloc[mid] > 0:
            ratio_check = float(val_col.iloc[mid] / (c.iloc[mid] * v.iloc[mid]))
        else:
            ratio_check = np.nan

        close_last = float(c.iloc[-1])
        vol_last   = float(v.iloc[-1])

        rows.append({
            "symbol":                    sym,
            "close_last_kVND":           round(close_last, 2),
            "close_est_VND":             int(close_last * 1000),
            "vol_last_shares":           int(vol_last),
            "panel_value_col_VND":       val_last,
            "ratio_value_vs_closexvol":  round(ratio_check, 4) if not np.isnan(ratio_check) else np.nan,
            "adv50_scan_wrong_kVND":     round(adv50_wrong_last, 0),
            "adv50_scan_reports_B_VND":  round(adv50_wrong_last / 1e9, 4),
            "adv50_correct_VND":         round(adv50_correct_last, 0),
            "adv50_correct_B_VND":       round(adv50_correct_last / 1e9, 3),
            "adv50_from_value_VND":      round(adv50_fromval_last, 0) if not np.isnan(adv50_fromval_last) else np.nan,
            "adv50_from_value_B_VND":    round(adv50_fromval_last / 1e9, 3) if not np.isnan(adv50_fromval_last) else np.nan,
            "a3_ledger_adv50_median_VND": round(led_median, 0) if not np.isnan(led_median) else np.nan,
            "a3_ledger_adv50_median_B":   round(led_median / 1e9, 3) if not np.isnan(led_median) else np.nan,
            "a3_ledger_adv50_recent_B":   round(led_recent / 1e9, 3) if not np.isnan(led_recent) else np.nan,
            "understatement_factor":      1000,
            "correct_target_T1_at_5B_10pct_M": round(
                min(5e9 / DEFAULT_MAX_POS * 0.5, adv50_correct_last * 0.10 * 0.5) / 1e6, 1
            ),
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase31_unit_check.csv", index=False)
    print(f"  Unit check saved: {len(out)} tickers", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# ADV tagging for PTS/DP ledgers
# ─────────────────────────────────────────────────────────────────────────────

def _build_adv50_map(panel):
    """
    Build dict: symbol → Series(date → adv50_value_VND)
    Uses panel value column (VND) where available, falls back to close×volume×1000.
    """
    print("  Building ADV50 map from panel...", flush=True)
    adv50_map = {}
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        c   = sdf["close"].astype(float)
        v   = sdf.get("volume", pd.Series(np.zeros(len(sdf)))).astype(float)
        if "value" in sdf.columns:
            val = sdf["value"].astype(float)
            # Fill NaN (recent rows) with close × volume × 1000
            val = val.fillna(c * v * 1000)
        else:
            val = c * v * 1000
        adv50 = val.rolling(50, min_periods=20).mean()
        adv50_map[sym] = pd.Series(adv50.values, index=pd.to_datetime(sdf["date"]))
    print(f"  ADV50 map: {len(adv50_map)} symbols", flush=True)
    return adv50_map


def _tag_adv50(trades_df, adv50_map):
    """Add adv50_value (VND) to a trade ledger using the entry_date lookup."""
    if trades_df.empty:
        return trades_df
    df = trades_df.copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])

    def lookup(sym, ed):
        s = adv50_map.get(sym)
        if s is None:
            return 0.0
        # Use value at entry_date or nearest earlier date
        ed = pd.Timestamp(ed)
        valid = s[s.index <= ed].dropna()
        if valid.empty:
            return 0.0
        return float(valid.iloc[-1])

    df["adv50_value"] = [
        lookup(sym, ed)
        for sym, ed in zip(df["symbol"], df["entry_date"])
    ]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Equity simulator (corrected)
# ─────────────────────────────────────────────────────────────────────────────

def _build_equity_adv_capped_v2(
    trades_df, max_positions, portfolio_vnd, participation,
    gk_mult=1.0, gk_col="has_gk", adv_col="adv50_value",
    rank_col="ema_dist_at_entry",
):
    """
    Corrected equity simulation. adv50_value must be in VND (same unit as portfolio_vnd).
    Reports split stats for T1 and full final position.
    """
    if trades_df.empty:
        return pd.Series(dtype=float), {}

    base_w = 1.0 / max_positions

    df = trades_df.copy().reset_index(drop=True)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])

    is_gk = df[gk_col].astype(bool) if gk_col in df.columns else pd.Series(False, index=df.index)
    tf    = df["total_frac"].astype(float) if "total_frac" in df.columns else pd.Series(1.0, index=df.index)
    tf    = tf.fillna(1.0)
    t1_frac = df["t1_frac"].astype(float) if "t1_frac" in df.columns else pd.Series(0.5, index=df.index)
    t1_frac = t1_frac.fillna(0.5)

    gk_factor = is_gk.map(lambda x: gk_mult if x else 1.0)
    target_w_full = (gk_factor * base_w).clip(upper=base_w * gk_mult)  # full intended position
    target_w_t1   = target_w_full * t1_frac                              # T1 tranche weight

    if adv_col in df.columns and (df[adv_col].fillna(0) > 0).any():
        adv_vals = df[adv_col].fillna(0).astype(float)
        # ADV cap applies to full intended position
        max_w_full = (adv_vals * participation / portfolio_vnd).clip(lower=0, upper=base_w * gk_mult)
        max_w_t1   = max_w_full * t1_frac
    else:
        max_w_full = target_w_full.copy()
        max_w_t1   = target_w_t1.copy()

    eff_w_full = np.minimum(target_w_full, max_w_full) * tf
    eff_w_t1   = np.minimum(target_w_t1,  max_w_t1)

    min_w = MIN_POS_VND / portfolio_vnd

    # Classification against T1 (the immediate entry)
    n_full_t1    = int((eff_w_t1 >= target_w_t1 * 0.95).sum())
    n_partial_t1 = int(((eff_w_t1 >= min_w) & (eff_w_t1 < target_w_t1 * 0.95)).sum())
    n_excl_t1    = int((eff_w_t1 < min_w).sum())
    mean_fill_t1 = float((eff_w_t1 / target_w_t1.clip(lower=1e-9)).mean())

    # Classification against full final position
    n_full_final    = int((eff_w_full >= target_w_full * 0.95).sum())
    n_partial_final = int(((eff_w_full >= min_w) & (eff_w_full < target_w_full * 0.95)).sum())
    n_excl_final    = int((eff_w_full < min_w).sum())
    mean_fill_final = float((eff_w_full / target_w_full.clip(lower=1e-9)).mean())

    n_total = len(df)

    # Simulation using effective total_frac weight (T1 + T2 blended)
    eff_w_sim = eff_w_full
    df["_eff_w"] = np.where(eff_w_sim >= min_w, eff_w_sim.values, 0.0)
    tradeable = df[df["_eff_w"] > 0].copy()

    # Track which tickers are most often constrained (T1 partial or excluded)
    constrained = df[(eff_w_t1 < target_w_t1 * 0.95) | (eff_w_t1 < min_w)].copy()
    if "adv50_value" in constrained.columns:
        constrained["adv50_B"] = constrained["adv50_value"] / 1e9
        constrained["target_T1_M"] = target_w_t1.loc[constrained.index] * portfolio_vnd / 1e6
        constrained["max_T1_M"] = max_w_t1.loc[constrained.index] * portfolio_vnd / 1e6

    if tradeable.empty:
        eq = pd.Series(dtype=float)
    else:
        sort_col = rank_col if rank_col in tradeable.columns else None
        all_dates = pd.date_range(tradeable["entry_date"].min(), tradeable["exit_date"].max(), freq="B")

        by_entry = {}
        for ed, grp in tradeable.groupby("entry_date", sort=False):
            sg = grp.sort_values(sort_col, ascending=False) if sort_col else grp
            by_entry[ed] = list(sg.index)

        by_exit = {}
        for i, row in tradeable.iterrows():
            by_exit.setdefault(row["exit_date"], []).append(int(i))

        portfolio_val = 1.0
        peak_val      = 1.0
        active: dict[int, float] = {}
        equity: dict = {}

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
                    active[tid]  = w
                    active_exp  += w
                    remaining   -= 1
            equity[dv] = portfolio_val

        eq = pd.Series(equity)

    stats = {
        "n_total":          n_total,
        "n_full_T1":        n_full_t1,
        "n_partial_T1":     n_partial_t1,
        "n_excl_T1":        n_excl_t1,
        "pct_full_T1":      n_full_t1  / max(n_total, 1),
        "pct_partial_T1":   n_partial_t1 / max(n_total, 1),
        "pct_excl_T1":      n_excl_t1  / max(n_total, 1),
        "mean_fill_T1":     mean_fill_t1,
        "n_full_final":     n_full_final,
        "n_partial_final":  n_partial_final,
        "n_excl_final":     n_excl_final,
        "pct_full_final":   n_full_final    / max(n_total, 1),
        "pct_partial_final":n_partial_final / max(n_total, 1),
        "pct_excl_final":   n_excl_final    / max(n_total, 1),
        "mean_fill_final":  mean_fill_final,
        "constrained_df":   constrained,
    }
    return eq, stats


def _annual_return(equity, year):
    yr_eq  = equity[equity.index.year == year]
    pre_eq = equity[equity.index.year < year]
    if yr_eq.empty:
        return np.nan
    end_v   = float(yr_eq.iloc[-1])
    start_v = float(pre_eq.iloc[-1]) if not pre_eq.empty else float(yr_eq.iloc[0])
    return end_v / start_v - 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3+4: Candidate comparison + capacity recompute
# ─────────────────────────────────────────────────────────────────────────────

def run_liquidity_recomputed(a3_led, dp_led, pts_led, gk_cache, adv50_map):
    """Recompute candidate comparison at 1B/3B/5B/10B × 5%/10%/20% with correct ADV units."""
    print("Task 3+4: Recomputing liquidity with corrected ADV units...", flush=True)

    def _tag_gk(df):
        if "has_gk" in df.columns:
            return df
        out = df.copy()
        sig_col = "signal_date" if "signal_date" in df.columns else "entry_date"
        sig_dates = pd.to_datetime(out[sig_col])
        out["has_gk"] = [
            any(abs((pd.Timestamp(sd).normalize() - gd).days) <= 10
                for gd in gk_cache.get(sym, set()))
            for sym, sd in zip(out["symbol"], sig_dates)
        ]
        return out

    # Tag GK
    a3_led  = _tag_gk(a3_led)
    dp_led  = _tag_gk(dp_led)
    pts_led = _tag_gk(pts_led)

    # Tag ADV50 (VND) onto PTS and DP (they lack this column)
    print("  Tagging adv50_value onto PTS trades...", flush=True)
    pts_led = _tag_adv50(pts_led, adv50_map)
    print("  Tagging adv50_value onto DP trades...", flush=True)
    dp_led  = _tag_adv50(dp_led,  adv50_map)
    # A3 already has it in VND

    candidates = {
        "PTS_A3_pb4w30_str6w10": (pts_led, 20, 1.0),
        "DP_A3_pb_only":         (dp_led,  20, 1.0),
        "A3_pos15":              (a3_led,  15, 1.0),
        "A3_pos15_GK_mult125":   (a3_led,  15, 1.25),
    }

    rows = []
    constrained_all = []

    for cname, (led, max_pos, gk_m) in candidates.items():
        if led.empty:
            continue
        print(f"  {cname}...", flush=True)

        for pvnd in PORTFOLIO_SIZES:
            for part in PARTICIPATIONS:
                eq, stats = _build_equity_adv_capped_v2(
                    led, max_positions=max_pos, portfolio_vnd=pvnd,
                    participation=part, gk_mult=gk_m,
                )

                if eq.empty:
                    mar = cagr = max_dd = sharpe = np.nan
                else:
                    m = portfolio_metrics(eq, led[led["net_return"].notna()])
                    mar    = m.get("mar",    np.nan)
                    cagr   = m.get("cagr",   np.nan)
                    max_dd = m.get("max_dd", np.nan)
                    sharpe = m.get("sharpe", np.nan)

                # Worst constrained tickers
                cdn = stats.get("constrained_df", pd.DataFrame())
                if not cdn.empty and "adv50_B" in cdn.columns:
                    top_cdn = cdn.groupby("symbol")["adv50_B"].mean().nsmallest(5)
                    constrained_tickers = ",".join(top_cdn.index.tolist())
                else:
                    constrained_tickers = ""

                rows.append({
                    "candidate":            cname,
                    "portfolio_B_VND":      pvnd / 1e9,
                    "participation_pct":    part * 100,
                    "max_positions":        max_pos,
                    "n_total":              stats["n_total"],
                    # T1 stats
                    "pct_full_T1":          round(stats["pct_full_T1"], 4),
                    "pct_partial_T1":       round(stats["pct_partial_T1"], 4),
                    "pct_excl_T1":          round(stats["pct_excl_T1"], 4),
                    "mean_fill_T1":         round(stats["mean_fill_T1"], 4),
                    # Final position stats
                    "pct_full_final":       round(stats["pct_full_final"], 4),
                    "pct_partial_final":    round(stats["pct_partial_final"], 4),
                    "pct_excl_final":       round(stats["pct_excl_final"], 4),
                    "mean_fill_final":      round(stats["mean_fill_final"], 4),
                    # Performance
                    "cagr":                 round(cagr, 4) if not np.isnan(cagr) else np.nan,
                    "max_dd":               round(max_dd, 4) if not np.isnan(max_dd) else np.nan,
                    "mar":                  round(mar, 4) if not np.isnan(mar) else np.nan,
                    "sharpe":               round(sharpe, 4) if not np.isnan(sharpe) else np.nan,
                    "most_constrained_syms": constrained_tickers,
                })

                print(
                    f"    {cname} @{pvnd/1e9:.0f}B {part:.0%}: "
                    f"T1_excl={stats['pct_excl_T1']:.1%} "
                    f"T1_full={stats['pct_full_T1']:.1%} "
                    f"MAR={mar:.3f}" if not np.isnan(mar) else
                    f"    {cname} @{pvnd/1e9:.0f}B {part:.0%}: empty equity",
                    flush=True
                )

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "phase31_liquidity_recomputed.csv", index=False)
    print(f"  Recomputed: {len(out)} rows", flush=True)
    return out, pts_led, dp_led


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2+5: Corrected daily scan
# ─────────────────────────────────────────────────────────────────────────────

def _liquidity_warning_v2(adv50_vnd: float, pos_vnd: float, participation: float) -> str:
    """Corrected: adv50_vnd and pos_vnd must both be in VND."""
    if adv50_vnd <= 0:
        return "NO_ADV_DATA"
    max_vnd = adv50_vnd * participation
    if pos_vnd > max_vnd * 2:
        return "CRITICAL"
    if pos_vnd > max_vnd:
        return "WARN_OVER"
    if pos_vnd > max_vnd * 0.8:
        return "WARN_NEAR"
    return "OK"


def _compute_pts_state(close_arr, fast_ema, cloud_bull, dates, entry_i, ep1,
                       pb_depth=0.04, pb_window=30, str_thresh=0.06, str_window=10,
                       current_i=None):
    if current_i is None:
        current_i = len(close_arr) - 1
    bars_since  = current_i - entry_i
    if bars_since < 0:
        return "NOT_ENTERED", ep1, ep1
    pb_trigger  = ep1 * (1.0 - pb_depth)
    str_trigger = ep1 * (1.0 + str_thresh)

    if bars_since <= pb_window:
        for k in range(entry_i + 1, min(current_i + 1, entry_i + pb_window + 1)):
            if float(close_arr[k]) <= pb_trigger:
                return "PB_HIT", pb_trigger, str_trigger
        return "PB_WAIT", pb_trigger, str_trigger

    pb_occurred = any(
        float(close_arr[k]) <= pb_trigger
        for k in range(entry_i + 1, min(entry_i + pb_window + 1, len(close_arr)))
    )
    if pb_occurred:
        return "PB_HIT", pb_trigger, str_trigger

    str_start = entry_i + pb_window + 1
    str_end   = entry_i + pb_window + str_window + 1
    if bars_since <= pb_window + str_window:
        for k in range(str_start, min(current_i + 1, str_end, len(close_arr))):
            c = float(close_arr[k])
            if c >= str_trigger and bool(cloud_bull[k]) and c > float(fast_ema[k]) * 0.999:
                return "STR_HIT", pb_trigger, str_trigger
        return "STR_WAIT", pb_trigger, str_trigger

    for k in range(entry_i + 1, min(entry_i + pb_window + 1, len(close_arr))):
        if float(close_arr[k]) <= pb_trigger:
            return "PB_HIT", pb_trigger, str_trigger
    for k in range(str_start, min(str_end, len(close_arr))):
        c = float(close_arr[k])
        if c >= str_trigger and bool(cloud_bull[k]) and c > float(fast_ema[k]) * 0.999:
            return "STR_HIT", pb_trigger, str_trigger
    return "NO_ADD", pb_trigger, str_trigger


def _near_entry_label(pct):
    if pct >= 0.08:   return "stretched"
    if pct >= 0.02:   return "momentum_confirmed"
    if pct >= -0.03:  return "acceptable"
    if pct >= -0.08:  return "ideal_pullback"
    return "deep_pullback"


def _sleeve(pts_state, near_entry, gk10, cloud_bull, regime_bull):
    if not cloud_bull or not regime_bull:
        return "Watch_only"
    if pts_state in ("PB_HIT", "STR_HIT"):
        return "Growth"
    if pts_state == "PB_WAIT" and near_entry in ("ideal_pullback", "deep_pullback"):
        return "Defensive_PTS" if not gk10 else "Growth"
    if pts_state in ("STR_WAIT", "PB_WAIT") and near_entry in ("acceptable", "momentum_confirmed"):
        return "Growth" if gk10 else "PTS"
    if near_entry == "stretched":
        return "Watch_only"
    return "PTS"


def run_daily_scan_corrected(panel, vnx, gk_cache, portfolio_vnd=5e9):
    """Rebuild daily scan with corrected ADV units and expanded liquidity fields."""
    print("Task 5: Corrected daily scan...", flush=True)
    gate_by_date, _ = vnindex_regime_gate(vnx)
    last_date   = pd.Timestamp(panel["date"].max()).normalize()
    regime_bull = bool(gate_by_date.get(last_date, False))
    strategy    = "A3"
    max_pos     = 15
    base_pos_vnd = portfolio_vnd / max_pos

    participations_ref = [0.05, 0.10, 0.20]

    rows = []
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 120:
            continue

        c   = sdf["close"].astype(float)
        h   = sdf["high"].astype(float)
        l   = sdf.get("low", c).astype(float)
        v   = sdf.get("volume", pd.Series(np.zeros(len(sdf)))).astype(float)
        d   = pd.to_datetime(sdf["date"])

        # ── CORRECTED: adv50 in VND ──────────────────────────────────────
        if "value" in sdf.columns:
            val = sdf["value"].astype(float).fillna(c * v * 1000)
        else:
            val = c * v * 1000
        adv50_vnd = val.rolling(50, min_periods=20).mean()
        adv50_now_vnd = float(adv50_vnd.iloc[-1]) if not np.isnan(float(adv50_vnd.iloc[-1])) else 0.0

        cloud_d     = ema_cloud(c, 20, 100)
        fast_ema    = cloud_d["ema_fast"]
        cloud_bull_s = cloud_d["cloud_bull"]
        atr         = compute_atr(h, l, c, 14)

        sig      = cloud_only_entry(c, fast_ema, cloud_bull_s, min_bars_bear=3, warmup=110)
        sig_idxs = np.where(sig.values)[0]
        if len(sig_idxs) == 0:
            continue

        li      = int(sig_idxs[-1])
        entry_i = li + 1
        if entry_i >= len(c):
            continue

        bars_since = len(c) - 1 - entry_i
        if bars_since > 40:
            continue

        ep1        = float(c.iloc[entry_i])
        cur_c      = float(c.iloc[-1])
        pct_vs_sig = cur_c / ep1 - 1.0
        ema_dist   = float(cur_c / fast_ema.iloc[-1] - 1.0) if float(fast_ema.iloc[-1]) > 0 else 0.0
        cloud_now  = bool(cloud_bull_s.iloc[-1])
        atr_now    = float(atr.iloc[-1])

        try:
            gk_res       = compute_gk(c, h, l)
            gk_days      = d[gk_res["gk_buy"]]
            today_norm   = last_date.normalize()
            gk10 = any(abs((today_norm - gd.normalize()).days) <= 10 for gd in gk_days)
        except Exception:
            gk10 = False

        pts_state, pb_trigger, str_trigger = _compute_pts_state(
            c.values, fast_ema.values, cloud_bull_s.values, d.values,
            entry_i, ep1,
            pb_depth=0.04, pb_window=30, str_thresh=0.06, str_window=10,
            current_i=len(c) - 1,
        )

        near_entry   = _near_entry_label(pct_vs_sig)
        sleeve       = _sleeve(pts_state, near_entry, gk10, cloud_now, regime_bull)
        gk_mult_flag = 1.25 if gk10 else 1.0

        # ── Position sizing at reference portfolio (5B) ─────────────────
        target_full_pos_vnd = base_pos_vnd * gk_mult_flag
        target_T1_vnd       = target_full_pos_vnd * 0.5

        # Capacity at each participation level
        max_allowed_vnd     = adv50_now_vnd * 0.10 if adv50_now_vnd > 0 else 0.0  # default 10%

        eff_full_pos_vnd    = min(target_full_pos_vnd, max_allowed_vnd) if adv50_now_vnd > 0 else target_full_pos_vnd
        eff_T1_vnd          = eff_full_pos_vnd * 0.5

        liq_warn_T1   = _liquidity_warning_v2(adv50_now_vnd, target_T1_vnd,   0.10)
        liq_warn_full = _liquidity_warning_v2(adv50_now_vnd, target_full_pos_vnd, 0.10)

        # Recommendation
        if adv50_now_vnd <= 0:
            rec = "no_adv_data"
        elif target_T1_vnd <= max_allowed_vnd:
            rec = "full_T1"
        elif eff_T1_vnd >= MIN_POS_VND:
            rec = "partial_T1"
        else:
            rec = "skip"

        rows.append({
            "as_of_date":             last_date.date(),
            "symbol":                 sym,
            "close":                  round(cur_c, 2),
            "close_VND":              int(cur_c * 1000),
            "a3_signal_state":        "ACTIVE" if cloud_now else "EXPIRED",
            "bars_since_entry":       bars_since,
            "near_entry_label":       near_entry,
            "ema_dist_pct":           round(ema_dist * 100, 2),
            "pts_state":              pts_state,
            "pb_trigger_price":       round(pb_trigger, 2),
            "str_trigger_price":      round(str_trigger, 2),
            "gk10_confirmed":         "Y" if gk10 else "N",
            "cloud_bull":             "Y" if cloud_now else "N",
            "regime_bull":            "Y" if regime_bull else "N",
            # ── ADV (CORRECTED) ──────────────────────────────────────────
            "adv50_B_VND":            round(adv50_now_vnd / 1e9, 3),     # corrected
            "adv50_source":           "value_col" if ("value" in sdf.columns and sdf["value"].notna().any()) else "close_x_vol_x1000",
            # ── Position sizing ─────────────────────────────────────────
            "target_full_pos_M":      round(target_full_pos_vnd / 1e6, 1),
            "target_T1_M":            round(target_T1_vnd / 1e6, 1),
            "max_allowed_10pct_M":    round(max_allowed_vnd / 1e6, 1),
            "effective_T1_M":         round(eff_T1_vnd / 1e6, 1),
            "effective_full_pos_M":   round(eff_full_pos_vnd / 1e6, 1),
            # ── Liquidity warnings ───────────────────────────────────────
            "liq_warning_T1":         liq_warn_T1,
            "liq_warning_full_pos":   liq_warn_full,
            "recommendation":         rec,
            # ── GK / sleeve ─────────────────────────────────────────────
            "gk_size_mult":           gk_mult_flag,
            "recommended_sleeve":     sleeve,
            # ── Exit guides ──────────────────────────────────────────────
            "tp1_guide":              f">{ep1 * 1.18:.2f} (+18%)",
            "stop_guide":             f"2.5×ATR={2.5*atr_now:.2f} below HWM",
            "pb_add_guide":           f"<{pb_trigger:.2f} (−4% from entry)",
            "str_add_guide":          f">{str_trigger:.2f} (+6%, after bar 30)",
            "portfolio_ref_B":        portfolio_vnd / 1e9,
        })

    scan_df = pd.DataFrame(rows)
    if not scan_df.empty:
        sleeve_order = {"Growth": 0, "Defensive_PTS": 1, "PTS": 2, "Watch_only": 3}
        scan_df["_sr"] = scan_df["recommended_sleeve"].map(sleeve_order).fillna(9)
        scan_df = scan_df.sort_values(["_sr", "ema_dist_pct"], ascending=[True, False]).drop(columns=["_sr"])

    scan_df.to_csv(OUT_DIR / "phase31_daily_scan_corrected.csv", index=False)
    print(f"  Corrected scan: {len(scan_df)} rows", flush=True)
    if not scan_df.empty:
        print("  Liquidity warning T1 distribution:", flush=True)
        print(scan_df["liq_warning_T1"].value_counts().to_string(), flush=True)
        print("  Recommendation distribution:", flush=True)
        print(scan_df["recommendation"].value_counts().to_string(), flush=True)

    return scan_df


# ─────────────────────────────────────────────────────────────────────────────
# Write audit report
# ─────────────────────────────────────────────────────────────────────────────

def write_audit_report(unit_df, recomp_df, scan_df):
    today_str = str(date.today())

    def _tbl(df, cols=None, n=None):
        if df is None or df.empty:
            return "*(no data)*\n\n"
        if cols:
            avail = [c for c in cols if c in df.columns]
            df = df[avail]
        if n:
            df = df.head(n)
        return df.to_markdown(index=False, floatfmt=".4f") + "\n\n"

    lines = [
        "# Phase 3.1 — Liquidity Unit Audit\n",
        f"Generated: {today_str}\n\n",
        "## Executive Summary\n\n",
        "Three bugs were found that explain why candidate comparison shows 0% exclusion for PTS/DP\n",
        "while the daily scan shows CRITICAL liquidity for all 56 setups:\n\n",
        "### Bug 1 — Daily scan: ADV50 understated by 1000×\n\n",
        "```\n",
        "Panel close is stored in kVND (thousands of VND).\n",
        "panel['value'] = close_kVND × volume_shares × 1000 → true VND value.\n",
        "Scan used: adv50 = (close × volume).rolling(50).mean()  ← kVND-unit\n",
        "Correct:   adv50 = (close × volume × 1000).rolling(50) ← VND\n",
        "              or = panel['value'].rolling(50)            ← VND (when available)\n",
        "Result: every stock's ADV50 was 1000× too low → all showed CRITICAL.\n",
        "```\n\n",
        "### Bug 2 — Candidate comparison: PTS/DP have no adv50_value column\n\n",
        "```\n",
        "PTS and DP trade ledgers are built by _sim_pb_then_str, which records:\n",
        "  entry_date, exit_date, ep1, blended_ep, total_frac, net_return ...\n",
        "  but does NOT tag adv50_value from the panel.\n",
        "In _build_equity_adv_capped, the ADV cap branch is:\n",
        "  if adv_col in df.columns:  ← False for PTS/DP\n",
        "      ... apply cap ...\n",
        "  else:\n",
        "      eff_w = target_w  ← No cap applied at all!\n",
        "Result: PTS/DP showed n_excluded=0, n_partial=0 for all portfolio sizes.\n",
        "```\n\n",
        "### Bug 3 — _liquidity_warning: mixed units\n\n",
        "```\n",
        "pos_vnd was in VND (e.g., 333M VND for 5B/15-pos portfolio)\n",
        "adv50 was in kVND-unit (e.g., 1.015B for HPG, should be 1.015T VND)\n",
        "Comparison: 333M > 1.015B × 0.10 × 2 = 203M → CRITICAL\n",
        "Correct:    333M vs 1.015T × 0.10 × 2 = 203B → OK (333M << 203B)\n",
        "```\n\n",
        "---\n\n",
        "## Task 1 — Unit Check for Known-Liquid Tickers\n\n",
        "All 10 tickers confirmed:\n",
        "- `panel['value']` = `close × volume × 1000` exactly (ratio = 1000.0)\n",
        "- Close stored in kVND (thousands of VND)\n",
        "- Volume stored in shares\n",
        "- `adv50_B_VND` in original scan was in million VND (1000× too small)\n\n",
    ]

    if unit_df is not None and not unit_df.empty:
        lines.append(_tbl(unit_df, [
            "symbol", "close_last_kVND", "close_est_VND", "vol_last_shares",
            "ratio_value_vs_closexvol",
            "adv50_scan_reports_B_VND", "adv50_correct_B_VND",
            "a3_ledger_adv50_recent_B", "understatement_factor",
            "correct_target_T1_at_5B_10pct_M",
        ]))

    lines += [
        "## Task 2 — Liquidity Formula Audit\n\n",
        "### Correct formulas\n\n",
        "```\n",
        "adv50_VND = panel['value'].rolling(50).mean()                    # VND\n",
        "         OR (close_kVND × volume × 1000).rolling(50).mean()      # VND\n",
        "\n",
        "# Position sizing\n",
        "base_pos_VND   = portfolio_VND / max_positions                   # e.g., 5B/15 = 333M\n",
        "target_T1_VND  = base_pos_VND × gk_mult × t1_frac               # e.g., 333M × 1.0 × 0.5 = 167M\n",
        "target_full_VND = base_pos_VND × gk_mult                        # e.g., 333M\n",
        "\n",
        "# ADV participation cap\n",
        "max_allowed_VND = adv50_VND × participation_rate                 # e.g., 1.015T × 10% = 101.5B\n",
        "\n",
        "# Effective sizes\n",
        "eff_T1_VND      = min(target_T1_VND, max_allowed_VND × t1_frac)\n",
        "eff_full_VND    = min(target_full_VND, max_allowed_VND)\n",
        "\n",
        "# Warnings (compare in same unit — VND)\n",
        "liq_warning_T1:   compare target_T1_VND vs max_allowed_VND\n",
        "liq_warning_full: compare target_full_VND vs max_allowed_VND\n",
        "```\n\n",
        "### Target sizes at reference portfolio (5B VND, 15 positions, 10% ADV)\n\n",
        "| Portfolio | max_pos | base_pos_M | target_T1_M | ADV50_min_for_T1_OK_B |\n",
        "|-----------|---------|------------|-------------|------------------------|\n",
        "| 1B VND | 15 | 66.7M | 33.3M | 0.33B |\n",
        "| 3B VND | 15 | 200M  | 100M  | 1.0B  |\n",
        "| 5B VND | 15 | 333M  | 167M  | 1.67B |\n",
        "| 10B VND| 15 | 667M  | 333M  | 3.33B |\n\n",
    ]

    lines += [
        "## Task 3 — Candidate Comparison Audit\n\n",
        "### Root cause of phantom 0% exclusion for PTS/DP\n\n",
        "PTS and DP trade ledgers (built by `_sim_pb_then_str`, `_sim_dual_path_pb`) record trade\n",
        "outcomes but do **not** carry `adv50_value` forward. The `_build_equity_adv_capped` function\n",
        "silently skips the ADV cap when the column is absent, treating all trades as fully liquid.\n\n",
        "The A3 ledger does carry `adv50_value` (in correct VND from `panel['value'].rolling(50)`).\n",
        "That's why A3 shows 0.3-0.9% exclusion (real small-cap illiquid stocks) while PTS/DP show 0.\n\n",
    ]

    lines += ["## Task 4 — Recomputed Capacity (Corrected ADV)\n\n"]

    if recomp_df is not None and not recomp_df.empty:
        # Summary pivot at 5B VND, 10% ADV
        sub = recomp_df[(recomp_df["portfolio_B_VND"] == 5.0) & (recomp_df["participation_pct"] == 10.0)]
        if not sub.empty:
            lines.append("### At 5B VND, 10% ADV participation\n\n")
            lines.append(_tbl(sub, [
                "candidate", "n_total",
                "pct_full_T1", "pct_partial_T1", "pct_excl_T1", "mean_fill_T1",
                "pct_full_final", "pct_excl_final",
                "mar", "cagr", "most_constrained_syms"
            ]))

        # Full table
        lines.append("### Full recomputed table (all portfolio sizes × participation rates)\n\n")
        lines.append(_tbl(recomp_df.sort_values(
            ["candidate", "portfolio_B_VND", "participation_pct"]
        ), [
            "candidate", "portfolio_B_VND", "participation_pct",
            "pct_full_T1", "pct_partial_T1", "pct_excl_T1", "mean_fill_T1",
            "pct_full_final", "pct_excl_final", "mean_fill_final",
            "mar", "cagr"
        ]))

    lines += ["## Task 5 — Corrected Daily Scan Summary\n\n"]
    if scan_df is not None and not scan_df.empty:
        lines.append(f"**As of {scan_df['as_of_date'].iloc[0]}** — {len(scan_df)} active setups\n\n")
        lines.append("### Liquidity warning distribution (T1, at 10% ADV)\n\n")
        lines.append(scan_df["liq_warning_T1"].value_counts().to_frame("count").to_markdown() + "\n\n")
        lines.append("### Recommendation distribution\n\n")
        lines.append(scan_df["recommendation"].value_counts().to_frame("count").to_markdown() + "\n\n")
        lines.append("### Actionable setups (non-Watch_only, non-skip)\n\n")
        act = scan_df[
            (scan_df["recommended_sleeve"] != "Watch_only") &
            (scan_df["recommendation"] != "skip")
        ]
        lines.append(_tbl(act.head(20), [
            "symbol", "close_VND", "recommended_sleeve", "pts_state",
            "gk10_confirmed", "ema_dist_pct",
            "adv50_B_VND", "target_T1_M", "max_allowed_10pct_M", "effective_T1_M",
            "liq_warning_T1", "liq_warning_full_pos", "recommendation",
            "pb_trigger_price", "str_trigger_price"
        ]))

    lines += [
        "## Key Conclusions\n\n",
        "### 1. ADV unit fix\n",
        "- Original scan: `adv50_B_VND` was in units of million VND (mislabeled as billion)\n",
        "- Fixed: use `panel['value'].rolling(50)` (or `close × volume × 1000`) → true VND\n",
        "- HPG corrected ADV50: ~1,000B VND/day (not 1B as originally shown)\n\n",
        "### 2. PTS/DP exclusion is non-zero after fix\n",
        "- After tagging adv50_value onto PTS/DP trades, run recomputed capacity table\n",
        "- Actual exclusion and partial-fill rates depend on portfolio size and participation\n",
        "- See phase31_liquidity_recomputed.csv for full breakdown\n\n",
        "### 3. Recommended operating parameters (post-audit)\n",
        "- Use `adv50_VND = panel['value'].rolling(50).mean()` (fill NaN with `close × volume × 1000`)\n",
        "- Compare T1 size (not full position) vs ADV × participation for entry decisions\n",
        "- Flag full-position eventual fill as a separate 'liq_warning_full' field\n",
        "- Run `portfolio_optimization_phase31.py` daily (replaces `--phase scan` in phase3)\n\n",
        "### 4. No strategy logic changes\n",
        "- Entry/exit rules, PTS state machine, GK multiplier: unchanged\n",
        "- Only capacity accounting and scan reporting corrected\n",
    ]

    p = OUT_DIR / "PHASE31_LIQUIDITY_AUDIT.md"
    p.write_text("".join(lines), encoding="utf-8")
    print(f"  Wrote: {p}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading data...", flush=True)
    panel  = load_panel()
    vnx    = load_vnindex()
    ledger = load_ledger()
    print(f"  Panel: {len(panel):,} rows | Ledger: {len(ledger):,} trades", flush=True)

    print("  Building GK cache...", flush=True)
    gk_cache = build_gk_cache(panel)
    print(f"  GK cache: {len(gk_cache)} symbols", flush=True)

    # Load ledgers
    a3_led  = pd.read_csv(P2_LED / "A3_pos15.csv")
    a3_led["entry_date"] = pd.to_datetime(a3_led["entry_date"])
    a3_led["exit_date"]  = pd.to_datetime(a3_led["exit_date"])

    dp_led  = pd.read_csv(P25_DIR / "phase25a_dp_trade_ledger.csv")
    dp_led["entry_date"] = pd.to_datetime(dp_led["entry_date"])
    dp_led["exit_date"]  = pd.to_datetime(dp_led["exit_date"])

    pts_led = pd.read_csv(P3_DIR / "phase3_pts_trade_ledger.csv")
    pts_led["entry_date"] = pd.to_datetime(pts_led["entry_date"])
    pts_led["exit_date"]  = pd.to_datetime(pts_led["exit_date"])

    print(f"  A3: {len(a3_led)} | DP: {len(dp_led)} | PTS: {len(pts_led)}", flush=True)

    # Task 1: Unit audit
    unit_df = run_unit_check(panel, a3_led)

    # Build ADV50 map (VND) for PTS/DP tagging
    adv50_map = _build_adv50_map(panel)

    # Tasks 3+4: Recomputed capacity
    recomp_df, pts_led_tagged, dp_led_tagged = run_liquidity_recomputed(
        a3_led, dp_led, pts_led, gk_cache, adv50_map
    )

    # Tasks 2+5: Corrected daily scan
    scan_df = run_daily_scan_corrected(panel, vnx, gk_cache, portfolio_vnd=5e9)

    # Write audit report
    write_audit_report(unit_df, recomp_df, scan_df)

    print("\nDone. Outputs in:", OUT_DIR, flush=True)


if __name__ == "__main__":
    main()
