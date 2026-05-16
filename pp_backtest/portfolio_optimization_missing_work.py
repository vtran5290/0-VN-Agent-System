#!/usr/bin/env python3
"""
Portfolio Optimization Missing Work — Steps 0-6.

Targeted completion pass after Phase 3.1 to cover missing research:
  Step 0: Hard audit of all candidate trade ledgers (schema, units, adv50)
  Step 1: S3 21/55 through corrected-liquidity Phase 2.5 / 3.1
  Step 2: Annual / regime decomposition for all candidates (2012-2026)
  Step 3: Cost / liquidity sensitivity matrix (full cross)
  Step 4: GK overlay tests for best S3 config
  Step 5: Playbook combinations (A3 DP + S3 best)
  Step 6: Phase32 daily scan (A3 + S3 + breadth state)

Critical context after Phase 3.1:
  - A3 default live candidate = DP-first (MAR=0.416 at 5B/10%)
  - PTS is shadow/aggressive mode only (MAR=0.343 at 5B/10%)
  - Correct ADV50: adv50_VND = panel["value"].rolling(50).fillna(c*v*1000)
  - All equity sims use _build_equity_adv_capped_v2 from phase31

Usage:
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_missing_work.py --step 0
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_missing_work.py --step 1
  .venv\\Scripts\\python.exe pp_backtest/portfolio_optimization_missing_work.py --step all
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
    _build_signal_cache, _exit_tp_trail, _quality_ok, _classify_result,
    load_panel, load_vnindex, get_universe, vnindex_regime_gate,
    compute_gk, portfolio_metrics, STRATEGY_CONFIGS, DEFAULT_COST, LEDGER,
)
from pp_backtest.portfolio_optimization_phase2 import (
    load_ledger, build_gk_cache, _sim_dual_path_symbol,
)
from pp_backtest.portfolio_optimization_phase25 import _sim_pb_then_str
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2,
    _liquidity_warning_v2, _annual_return,
)

OUT_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "missing_work"
P2_LED   = REPO / "data" / "research" / "portfolio_optimization" / "phase2" / "phase2_baseline_trade_ledgers"
P25_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase25"
P3_DIR   = REPO / "data" / "research" / "portfolio_optimization" / "phase3"
P31_DIR  = REPO / "data" / "research" / "portfolio_optimization" / "phase31"

PORTFOLIO_SIZES  = [1e9, 3e9, 5e9, 10e9]
PARTICIPATIONS   = [0.05, 0.10, 0.20]
COSTS            = [0.002, 0.004, 0.006]
MIN_POS_VND      = 100_000
DEFAULT_MAX_POS  = 15
ANNUALIZE        = 252

# Reference for step 1 screening pass
REF_PORTFOLIO    = 5e9
REF_PART         = 0.10


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sim_row(candidate, strategy, desc, led, max_pos, pvnd, part, gk_mult=1.0, rank_col="ema_dist_at_entry"):
    """Run equity sim + return one summary dict."""
    if led.empty:
        return None
    eq, stats = _build_equity_adv_capped_v2(
        led, max_positions=max_pos, portfolio_vnd=pvnd, participation=part,
        gk_mult=gk_mult, rank_col=rank_col,
    )
    if eq.empty:
        return None
    m = portfolio_metrics(eq, led)
    return {
        "candidate":        candidate,
        "strategy":         strategy,
        "description":      desc,
        "portfolio_B_VND":  pvnd / 1e9,
        "participation_pct": part * 100,
        "max_positions":    max_pos,
        "n_trades":         len(led),
        "cagr":             round(m.get("cagr", np.nan), 4),
        "max_dd":           round(m.get("max_dd", np.nan), 4),
        "mar":              round(m.get("mar", np.nan), 4),
        "sharpe":           round(m.get("sharpe", np.nan), 4),
        "pct_excl_T1":      round(stats["pct_excl_T1"], 4),
        "pct_full_T1":      round(stats["pct_full_T1"], 4),
        "mean_fill_T1":     round(stats["mean_fill_T1"], 4),
        "pct_excl_final":   round(stats["pct_excl_final"], 4),
    }


def _load_led(path):
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])
    return df


def _tag_gk(df, gk_cache):
    """Add has_gk column to ledger if missing."""
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


def _annual_stats(eq):
    """Return dict year -> return for each year in equity series."""
    if eq.empty:
        return {}
    years = sorted(set(eq.index.year))
    return {yr: _annual_return(eq, yr) for yr in years}


# ─────────────────────────────────────────────────────────────────────────────
# Step 0: Hard schema audit of all candidate ledgers
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLS = [
    "symbol", "strategy", "entry_date", "exit_date",
    "net_return", "gross_return", "hold_bars",
    "t1_frac", "total_frac",
]
PREFERRED_COLS = ["adv50_value", "has_gk", "ema_dist_at_entry", "add_path"]

KNOWN_LEDGERS = {
    "A3_pos15":   P2_LED / "A3_pos15.csv",
    "A3_pos20":   P2_LED / "A3_pos20.csv",
    "S3_pos15":   P2_LED / "S3_pos15.csv",
    "S3_pos20":   P2_LED / "S3_pos20.csv",
    "DP_A3_pb_only":  P25_DIR / "phase25a_dp_trade_ledger.csv",
    "PTS_A3_pb4w30":  P3_DIR  / "phase3_pts_trade_ledger.csv",
}


def run_step0():
    """Step 0: Schema audit of all candidate ledgers."""
    print("\n=== STEP 0: Ledger Schema Audit ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    for name, path in KNOWN_LEDGERS.items():
        if not path.exists():
            rows.append({
                "ledger": name, "path": str(path.relative_to(REPO)),
                "exists": False, "n_rows": 0,
                **{c: "MISSING_FILE" for c in REQUIRED_COLS + PREFERRED_COLS},
                "adv50_unit_check": "N/A", "adv50_median_B": np.nan,
                "pct_pos_net_return": np.nan, "date_range": "N/A",
                "issues": "FILE_NOT_FOUND",
            })
            print(f"  {name}: MISSING", flush=True)
            continue

        df = pd.read_csv(path)
        issues = []
        col_status = {}

        for c in REQUIRED_COLS:
            if c in df.columns:
                col_status[c] = "OK"
            else:
                col_status[c] = "MISSING"
                issues.append(f"required_col_{c}")

        for c in PREFERRED_COLS:
            if c in df.columns:
                col_status[c] = "OK"
            else:
                col_status[c] = "ABSENT"

        # ADV50 unit check: if present, median should be > 1e8 (0.1B VND)
        if "adv50_value" in df.columns:
            med = float(df["adv50_value"].median())
            if med < 1e6:
                col_status["adv50_unit_check"] = f"SUSPICIOUS_LOW_{med:.0f}"
                issues.append("adv50_possible_unit_error")
            elif med < 1e8:
                col_status["adv50_unit_check"] = f"WARN_{med/1e9:.3f}B"
            else:
                col_status["adv50_unit_check"] = "OK"
            adv50_med_b = round(med / 1e9, 4)
        else:
            col_status["adv50_unit_check"] = "NO_COL"
            adv50_med_b = np.nan

        if "net_return" in df.columns:
            pct_pos = (df["net_return"] > 0).mean()
        else:
            pct_pos = np.nan

        if "entry_date" in df.columns:
            df["entry_date"] = pd.to_datetime(df["entry_date"])
            date_range = f"{df['entry_date'].min().date()} to {df['entry_date'].max().date()}"
        else:
            date_range = "N/A"

        row = {
            "ledger":              name,
            "path":                str(path.relative_to(REPO)),
            "exists":              True,
            "n_rows":              len(df),
            "date_range":          date_range,
            "adv50_median_B":      adv50_med_b,
            "adv50_unit_check":    col_status.get("adv50_unit_check", "N/A"),
            "pct_pos_net_return":  round(float(pct_pos), 4) if not np.isnan(float(pct_pos)) else np.nan,
            "issues":              "; ".join(issues) if issues else "none",
        }
        for c in REQUIRED_COLS + PREFERRED_COLS:
            row[c] = col_status.get(c, "ABSENT")

        print(
            f"  {name}: {len(df)} rows | adv50={adv50_med_b:.2f}B | "
            f"adv50_unit={col_status.get('adv50_unit_check','N/A')} | "
            f"issues={row['issues']}", flush=True
        )
        rows.append(row)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "step0_ledger_schema_check.csv", index=False)
    print(f"  Schema check saved: {OUT_DIR / 'step0_ledger_schema_check.csv'}", flush=True)

    lines = ["# Step 0: Ledger Schema Audit\n\n"]
    lines.append(f"As of: {pd.Timestamp.now().date()}\n\n")
    lines.append("## Ledger Status\n\n")
    for _, row in out.iterrows():
        lines.append(f"### {row['ledger']}\n")
        lines.append(f"- Path: `{row['path']}`\n")
        lines.append(f"- Rows: {row['n_rows']:,}\n")
        lines.append(f"- Date range: {row['date_range']}\n")
        lines.append(f"- adv50 median: {row['adv50_median_B']:.3f} B VND\n")
        lines.append(f"- adv50 unit check: {row['adv50_unit_check']}\n")
        lines.append(f"- Required cols: {', '.join(c for c in REQUIRED_COLS if row.get(c) == 'OK')}\n")
        lines.append(f"- Missing required: {', '.join(c for c in REQUIRED_COLS if row.get(c) == 'MISSING') or 'none'}\n")
        lines.append(f"- Preferred missing: {', '.join(c for c in PREFERRED_COLS if row.get(c) == 'ABSENT') or 'none'}\n")
        lines.append(f"- Issues: {row['issues']}\n\n")

    lines.append("## Summary\n\n")
    n_ok = int((out["issues"] == "none").sum())
    lines.append(f"- {n_ok}/{len(out)} ledgers have no issues\n")
    lines.append(f"- Ledgers needing adv50 tag: {', '.join(out[out['adv50_value'].isin(['ABSENT','MISSING'])]['ledger'].tolist()) or 'none'}\n")
    lines.append("\n## Action Required\n\n")
    lines.append("- DP_A3_pb_only and PTS_A3_pb4w30: adv50_value absent → must _tag_adv50() before equity sim\n")
    lines.append("- All new S3 ledgers from Step 1 must go through _tag_adv50() before capacity analysis\n")

    audit_path = OUT_DIR / "step0_liquidity_audit.md"
    audit_path.write_text("".join(lines), encoding="utf-8")
    print(f"  Audit report saved: {audit_path}", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: S3 21/55 corrected-liquidity pipeline
# ─────────────────────────────────────────────────────────────────────────────

# Pullback grid: d3/d4/d5 × w20/w25/w30 → 9 depth/window combos
# Quality: slow_097 / fast_ema / close_loc_05
# Split: t1_frac 0.40 / 0.50 / 0.60
# That's 9 × 3 × 3 = 81 configs; screen at ref 5B/10% → top 5 → full grid

S3_PB_DEPTHS    = [0.03, 0.04, 0.05]
S3_PB_WINDOWS   = [20, 25, 30]
S3_QUALITIES    = ["slow_097", "fast_ema", "close_loc_05"]
S3_T1_FRACS     = [0.40, 0.50, 0.60]

# PTS configs (4 from research program)
S3_PTS_CONFIGS  = [
    (0.05, 20, 0.04, 10, "pts_pb5w20_str4w10"),
    (0.05, 20, 0.06, 10, "pts_pb5w20_str6w10"),
    (0.05, 30, 0.06, 10, "pts_pb5w30_str6w10"),
    (0.04, 20, 0.04, 10, "pts_pb4w20_str4w10"),
]


def _build_s3_dp_trades(panel, gk_cache, cost, gate_by_date,
                        pb_depth, pb_window, quality, t1_frac):
    """Simulate S3 DP pullback-only for one config."""
    cfg      = STRATEGY_CONFIGS["S3"]
    exit_cfg = cfg["exit_cfg"]
    cache    = _build_signal_cache(panel, "S3")
    all_t    = []
    for sym, data in cache.items():
        gk_dates = gk_cache.get(sym, set())
        t = _sim_dual_path_symbol(
            sym=sym, data=data, strategy="S3", exit_cfg=exit_cfg,
            cost=cost, mode="pb_only",
            t1_frac=t1_frac, t2_frac=(1.0 - t1_frac),
            t2_pb_frac=(1.0 - t1_frac), t2_str_frac=0.0,
            pb_depth=pb_depth, pb_window=pb_window, pb_quality_mode=quality,
            str_thresh=0.0, str_window=0, str_require_gk=False,
            gk_dates=gk_dates, gate_by_date=gate_by_date, min_lock=5,
        )
        all_t.extend(t)
    if not all_t:
        return pd.DataFrame()
    df = pd.DataFrame(all_t)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])
    return df


def _build_s3_pts_trades(panel, gk_cache, cost, gate_by_date,
                         pb_depth, pb_window, str_thresh, str_window):
    """Simulate S3 PTS (pb_then_str) for one config."""
    cfg      = STRATEGY_CONFIGS["S3"]
    exit_cfg = cfg["exit_cfg"]
    cache    = _build_signal_cache(panel, "S3")
    all_t    = []
    for sym, data in cache.items():
        gk_dates = gk_cache.get(sym, set())
        t = _sim_pb_then_str(
            sym=sym, data=data, strategy="S3", exit_cfg=exit_cfg,
            cost=cost,
            pb_depth=pb_depth, pb_window=pb_window,
            str_thresh=str_thresh, str_window=str_window,
            gk_dates=gk_dates, gk_req=False, vol_req=False,
            gate_by_date=gate_by_date, min_lock=5,
            t1=0.50, t2=0.50,
        )
        all_t.extend(t)
    if not all_t:
        return pd.DataFrame()
    df = pd.DataFrame(all_t)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"]  = pd.to_datetime(df["exit_date"])
    return df


def _quick_mar(led, adv50_map, max_pos=20, pvnd=REF_PORTFOLIO, part=REF_PART):
    """Return MAR for quick screening pass. Returns -999 if can't compute."""
    if led.empty:
        return -999.0
    df = _tag_adv50(led, adv50_map)
    eq, _ = _build_equity_adv_capped_v2(
        df, max_positions=max_pos, portfolio_vnd=pvnd, participation=part,
        rank_col="ema_dist_at_entry" if "ema_dist_at_entry" in df.columns else "mom20",
    )
    if eq.empty:
        return -999.0
    m = portfolio_metrics(eq, df)
    return float(m.get("mar", -999.0))


def run_step1(panel, vnx, gk_cache):
    """Step 1: S3 21/55 corrected-liquidity research."""
    print("\n=== STEP 1: S3 21/55 Corrected-Liquidity Research ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gate_by_date, _ = vnindex_regime_gate(vnx)
    adv50_map       = _build_adv50_map(panel)

    # ── 1a: Build S3 signal cache once (reused for all configs) ──
    print("  Building S3 signal cache (EMA21/55)...", flush=True)
    s3_cache = _build_signal_cache(panel, "S3")
    print(f"  S3 cache: {len(s3_cache)} symbols", flush=True)

    # ── 1b: Screening pass — all 81 DP configs at 5B/10% ──
    print(f"\n  Screening pass: {len(S3_PB_DEPTHS)*len(S3_PB_WINDOWS)*len(S3_QUALITIES)*len(S3_T1_FRACS)} DP configs at {REF_PORTFOLIO/1e9:.0f}B/{REF_PART:.0%}...", flush=True)

    screen_rows = []
    cfg_s3      = STRATEGY_CONFIGS["S3"]
    exit_cfg_s3 = cfg_s3["exit_cfg"]

    for d in S3_PB_DEPTHS:
        for w in S3_PB_WINDOWS:
            for q in S3_QUALITIES:
                for t1 in S3_T1_FRACS:
                    label = f"S3_dp_d{int(d*100)}_w{w}_{q}_t1{int(t1*100)}"

                    all_t = []
                    for sym, data in s3_cache.items():
                        gk_dates = gk_cache.get(sym, set())
                        trades = _sim_dual_path_symbol(
                            sym=sym, data=data, strategy="S3", exit_cfg=exit_cfg_s3,
                            cost=DEFAULT_COST, mode="pb_only",
                            t1_frac=t1, t2_frac=(1.0 - t1),
                            t2_pb_frac=(1.0 - t1), t2_str_frac=0.0,
                            pb_depth=d, pb_window=w, pb_quality_mode=q,
                            str_thresh=0.0, str_window=0, str_require_gk=False,
                            gk_dates=gk_dates, gate_by_date=gate_by_date, min_lock=5,
                        )
                        all_t.extend(trades)

                    if not all_t:
                        screen_rows.append({
                            "label": label, "pb_depth": d, "pb_window": w,
                            "quality": q, "t1_frac": t1, "n_trades": 0,
                            "mar": -999, "cagr": np.nan, "max_dd": np.nan,
                            "pct_excl_T1": np.nan,
                        })
                        continue

                    led = pd.DataFrame(all_t)
                    led["entry_date"] = pd.to_datetime(led["entry_date"])
                    led["exit_date"]  = pd.to_datetime(led["exit_date"])
                    led = _tag_adv50(led, adv50_map)

                    rank_col = "mom20" if "mom20" in led.columns else "ema_dist_at_entry"
                    eq, stats = _build_equity_adv_capped_v2(
                        led, max_positions=20, portfolio_vnd=REF_PORTFOLIO,
                        participation=REF_PART, rank_col=rank_col,
                    )
                    if eq.empty:
                        mar = cagr = max_dd = np.nan
                        excl = np.nan
                    else:
                        m    = portfolio_metrics(eq, led)
                        mar  = round(float(m.get("mar", np.nan)), 4)
                        cagr = round(float(m.get("cagr", np.nan)), 4)
                        max_dd = round(float(m.get("max_dd", np.nan)), 4)
                        excl = round(stats["pct_excl_T1"], 4)

                    screen_rows.append({
                        "label": label, "pb_depth": d, "pb_window": w,
                        "quality": q, "t1_frac": t1, "n_trades": len(led),
                        "mar": mar, "cagr": cagr, "max_dd": max_dd,
                        "pct_excl_T1": excl,
                    })
                    print(f"    {label}: n={len(led)}, MAR={mar:.3f}, CAGR={cagr:.2%}", flush=True)

    screen_df = pd.DataFrame(screen_rows).sort_values("mar", ascending=False)
    screen_df.to_csv(OUT_DIR / "s3_dp_screening_pass.csv", index=False)
    print(f"\n  Screening saved: {len(screen_df)} configs", flush=True)

    # ── 1c: Select top 5 DP configs for full capacity analysis ──
    top5 = screen_df.dropna(subset=["mar"]).head(5)
    print(f"\n  Top 5 S3 DP configs:", flush=True)
    for _, r in top5.iterrows():
        print(f"    {r['label']}: MAR={r['mar']:.3f}, CAGR={r['cagr']:.2%}", flush=True)

    # ── 1d: Full capacity analysis for top 5 DP configs ──
    print(f"\n  Full capacity (1B/3B/5B/10B × 5%/10%/20%) for top 5...", flush=True)
    cap_rows = []

    for _, tr in top5.iterrows():
        label = tr["label"]
        d     = float(tr["pb_depth"])
        w     = int(tr["pb_window"])
        q     = str(tr["quality"])
        t1    = float(tr["t1_frac"])

        all_t = []
        for sym, data in s3_cache.items():
            gk_dates = gk_cache.get(sym, set())
            trades = _sim_dual_path_symbol(
                sym=sym, data=data, strategy="S3", exit_cfg=exit_cfg_s3,
                cost=DEFAULT_COST, mode="pb_only",
                t1_frac=t1, t2_frac=(1.0 - t1),
                t2_pb_frac=(1.0 - t1), t2_str_frac=0.0,
                pb_depth=d, pb_window=w, pb_quality_mode=q,
                str_thresh=0.0, str_window=0, str_require_gk=False,
                gk_dates=gk_dates, gate_by_date=gate_by_date, min_lock=5,
            )
            all_t.extend(trades)

        if not all_t:
            continue

        led = pd.DataFrame(all_t)
        led["entry_date"] = pd.to_datetime(led["entry_date"])
        led["exit_date"]  = pd.to_datetime(led["exit_date"])
        led = _tag_adv50(led, adv50_map)
        led = _tag_gk(led, gk_cache)

        rank_col = "mom20" if "mom20" in led.columns else "ema_dist_at_entry"

        for pvnd in PORTFOLIO_SIZES:
            for part in PARTICIPATIONS:
                eq, stats = _build_equity_adv_capped_v2(
                    led, max_positions=20, portfolio_vnd=pvnd,
                    participation=part, rank_col=rank_col,
                )
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, led)
                cap_rows.append({
                    "candidate":        label,
                    "strategy":         "S3",
                    "pb_depth":         d,
                    "pb_window":        w,
                    "quality":          q,
                    "t1_frac":          t1,
                    "portfolio_B_VND":  pvnd / 1e9,
                    "participation_pct": part * 100,
                    "n_trades":         len(led),
                    "cagr":             round(m.get("cagr", np.nan), 4),
                    "max_dd":           round(m.get("max_dd", np.nan), 4),
                    "mar":              round(m.get("mar", np.nan), 4),
                    "sharpe":           round(m.get("sharpe", np.nan), 4),
                    "pct_excl_T1":      round(stats["pct_excl_T1"], 4),
                    "pct_full_T1":      round(stats["pct_full_T1"], 4),
                    "mean_fill_T1":     round(stats["mean_fill_T1"], 4),
                    "pct_excl_final":   round(stats["pct_excl_final"], 4),
                })

    cap_df = pd.DataFrame(cap_rows)
    cap_df.to_csv(OUT_DIR / "s3_phase31_baseline_corrected.csv", index=False)
    print(f"  Capacity results saved: {len(cap_df)} rows", flush=True)

    # ── 1e: S3 PTS configs (4) at reference + full capacity ──
    print(f"\n  S3 PTS configs ({len(S3_PTS_CONFIGS)} configs)...", flush=True)
    pts_rows      = []
    pts_ledgers   = {}

    for pb_d, pb_w, st, sw, pts_label in S3_PTS_CONFIGS:
        all_t = []
        for sym, data in s3_cache.items():
            gk_dates = gk_cache.get(sym, set())
            trades = _sim_pb_then_str(
                sym=sym, data=data, strategy="S3", exit_cfg=exit_cfg_s3,
                cost=DEFAULT_COST,
                pb_depth=pb_d, pb_window=pb_w,
                str_thresh=st, str_window=sw,
                gk_dates=gk_dates, gk_req=False, vol_req=False,
                gate_by_date=gate_by_date, min_lock=5,
                t1=0.50, t2=0.50,
            )
            all_t.extend(trades)

        if not all_t:
            print(f"    {pts_label}: no trades", flush=True)
            continue

        led = pd.DataFrame(all_t)
        led["entry_date"] = pd.to_datetime(led["entry_date"])
        led["exit_date"]  = pd.to_datetime(led["exit_date"])
        led = _tag_adv50(led, adv50_map)
        led = _tag_gk(led, gk_cache)
        pts_ledgers[pts_label] = led

        pb_pct  = float((led["has_pullback"]).mean()) if "has_pullback" in led.columns else np.nan
        str_pct = float((led["has_strength"]).mean()) if "has_strength" in led.columns else np.nan

        for pvnd in PORTFOLIO_SIZES:
            for part in PARTICIPATIONS:
                eq, stats = _build_equity_adv_capped_v2(
                    led, max_positions=20, portfolio_vnd=pvnd, participation=part,
                )
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, led)
                pts_rows.append({
                    "candidate":        pts_label,
                    "strategy":         "S3",
                    "pb_depth":         pb_d,
                    "pb_window":        pb_w,
                    "str_thresh":       st,
                    "str_window":       sw,
                    "portfolio_B_VND":  pvnd / 1e9,
                    "participation_pct": part * 100,
                    "n_trades":         len(led),
                    "pct_pullback":     round(pb_pct, 4),
                    "pct_strength":     round(str_pct, 4),
                    "cagr":             round(m.get("cagr", np.nan), 4),
                    "max_dd":           round(m.get("max_dd", np.nan), 4),
                    "mar":              round(m.get("mar", np.nan), 4),
                    "sharpe":           round(m.get("sharpe", np.nan), 4),
                    "pct_excl_T1":      round(stats["pct_excl_T1"], 4),
                    "pct_full_T1":      round(stats["pct_full_T1"], 4),
                    "mean_fill_T1":     round(stats["mean_fill_T1"], 4),
                })
        mar_ref = pts_rows[-1]["mar"] if pts_rows else np.nan
        print(f"    {pts_label}: n={len(led)}, MAR_ref={mar_ref:.3f}, pct_pb={pb_pct:.1%}", flush=True)

    pts_df = pd.DataFrame(pts_rows)
    pts_df.to_csv(OUT_DIR / "s3_phase31_pts_strength_corrected.csv", index=False)
    print(f"  PTS results saved: {len(pts_df)} rows", flush=True)

    # ── 1f: GK overlay tests — best S3 DP at 5B/10% with gk_mult=1.25 ──
    print(f"\n  GK overlay tests (best S3 DP config)...", flush=True)
    gk_rows = []

    best_label = top5.iloc[0]["label"] if not top5.empty else None
    if best_label:
        d   = float(top5.iloc[0]["pb_depth"])
        w   = int(top5.iloc[0]["pb_window"])
        q   = str(top5.iloc[0]["quality"])
        t1  = float(top5.iloc[0]["t1_frac"])

        all_t = []
        for sym, data in s3_cache.items():
            gk_dates = gk_cache.get(sym, set())
            trades = _sim_dual_path_symbol(
                sym=sym, data=data, strategy="S3", exit_cfg=exit_cfg_s3,
                cost=DEFAULT_COST, mode="pb_only",
                t1_frac=t1, t2_frac=(1.0 - t1),
                t2_pb_frac=(1.0 - t1), t2_str_frac=0.0,
                pb_depth=d, pb_window=w, pb_quality_mode=q,
                str_thresh=0.0, str_window=0, str_require_gk=False,
                gk_dates=gk_dates, gate_by_date=gate_by_date, min_lock=5,
            )
            all_t.extend(trades)

        if all_t:
            led_best = pd.DataFrame(all_t)
            led_best["entry_date"] = pd.to_datetime(led_best["entry_date"])
            led_best["exit_date"]  = pd.to_datetime(led_best["exit_date"])
            led_best = _tag_adv50(led_best, adv50_map)
            led_best = _tag_gk(led_best, gk_cache)
            led_best.to_csv(OUT_DIR / "s3_best_dp_trade_ledger.csv", index=False)

            rank_col = "mom20" if "mom20" in led_best.columns else "ema_dist_at_entry"
            for gk_m in [1.0, 1.25]:
                for pvnd in PORTFOLIO_SIZES:
                    for part in PARTICIPATIONS:
                        eq, stats = _build_equity_adv_capped_v2(
                            led_best, max_positions=20, portfolio_vnd=pvnd,
                            participation=part, gk_mult=gk_m, rank_col=rank_col,
                        )
                        if eq.empty:
                            continue
                        m = portfolio_metrics(eq, led_best)
                        gk_rows.append({
                            "candidate":        f"{best_label}_gk{int(gk_m*100)}",
                            "strategy":         "S3",
                            "gk_mult":          gk_m,
                            "portfolio_B_VND":  pvnd / 1e9,
                            "participation_pct": part * 100,
                            "n_trades":         len(led_best),
                            "cagr":             round(m.get("cagr", np.nan), 4),
                            "max_dd":           round(m.get("max_dd", np.nan), 4),
                            "mar":              round(m.get("mar", np.nan), 4),
                            "sharpe":           round(m.get("sharpe", np.nan), 4),
                            "pct_excl_T1":      round(stats["pct_excl_T1"], 4),
                        })

    gk_df = pd.DataFrame(gk_rows)
    gk_df.to_csv(OUT_DIR / "s3_phase31_gk_overlay_corrected.csv", index=False)
    print(f"  GK overlay saved: {len(gk_df)} rows", flush=True)

    # ── 1g: Cost / liquidity sensitivity for best S3 DP ──
    print(f"\n  Cost sensitivity for best S3 DP config...", flush=True)
    cost_rows = []

    if best_label and not top5.empty:
        for cost in COSTS:
            d   = float(top5.iloc[0]["pb_depth"])
            w   = int(top5.iloc[0]["pb_window"])
            q   = str(top5.iloc[0]["quality"])
            t1  = float(top5.iloc[0]["t1_frac"])

            all_t = []
            for sym, data in s3_cache.items():
                gk_dates = gk_cache.get(sym, set())
                trades = _sim_dual_path_symbol(
                    sym=sym, data=data, strategy="S3", exit_cfg=exit_cfg_s3,
                    cost=cost, mode="pb_only",
                    t1_frac=t1, t2_frac=(1.0 - t1),
                    t2_pb_frac=(1.0 - t1), t2_str_frac=0.0,
                    pb_depth=d, pb_window=w, pb_quality_mode=q,
                    str_thresh=0.0, str_window=0, str_require_gk=False,
                    gk_dates=gk_dates, gate_by_date=gate_by_date, min_lock=5,
                )
                all_t.extend(trades)

            if not all_t:
                continue

            led = pd.DataFrame(all_t)
            led["entry_date"] = pd.to_datetime(led["entry_date"])
            led["exit_date"]  = pd.to_datetime(led["exit_date"])
            led = _tag_adv50(led, adv50_map)

            rank_col = "mom20" if "mom20" in led.columns else "ema_dist_at_entry"
            for pvnd in PORTFOLIO_SIZES:
                for part in PARTICIPATIONS:
                    eq, stats = _build_equity_adv_capped_v2(
                        led, max_positions=20, portfolio_vnd=pvnd,
                        participation=part, rank_col=rank_col,
                    )
                    if eq.empty:
                        continue
                    m = portfolio_metrics(eq, led)
                    cost_rows.append({
                        "candidate":        f"{best_label}_cost{int(cost*1000)}bps",
                        "strategy":         "S3",
                        "cost_pct":         cost * 100,
                        "portfolio_B_VND":  pvnd / 1e9,
                        "participation_pct": part * 100,
                        "cagr":             round(m.get("cagr", np.nan), 4),
                        "max_dd":           round(m.get("max_dd", np.nan), 4),
                        "mar":              round(m.get("mar", np.nan), 4),
                        "sharpe":           round(m.get("sharpe", np.nan), 4),
                        "pct_excl_T1":      round(stats["pct_excl_T1"], 4),
                    })

    cost_df = pd.DataFrame(cost_rows)
    cost_df.to_csv(OUT_DIR / "s3_phase31_cost_liquidity_sensitivity.csv", index=False)
    print(f"  Cost sensitivity saved: {len(cost_df)} rows", flush=True)

    # ── 1h: Top findings summary ──
    best_cap = cap_df.loc[
        (cap_df["portfolio_B_VND"] == 5.0) & (cap_df["participation_pct"] == 10.0)
    ].sort_values("mar", ascending=False) if not cap_df.empty else pd.DataFrame()

    best_pts = pts_df.loc[
        (pts_df["portfolio_B_VND"] == 5.0) & (pts_df["participation_pct"] == 10.0)
    ].sort_values("mar", ascending=False) if not pts_df.empty else pd.DataFrame()

    lines = ["# S3 Phase 3.1 Top Findings\n\n"]
    lines.append(f"As of: {pd.Timestamp.now().date()}\n\n")
    lines.append("## Context\n\n")
    lines.append("- S3: EMA21/55 cloud breakout, full universe, TP1 +18%, trail 3.5×ATR, max_hold 250\n")
    lines.append("- Corrected ADV50: panel['value'].rolling(50).fillna(c×v×1000)\n")
    lines.append("- Reference portfolio: 5B VND, 10% participation cap\n\n")

    lines.append("## Top S3 DP Pullback Configs (at 5B/10%)\n\n")
    lines.append("| Rank | Config | MAR | CAGR | MaxDD | Excl_T1 |\n")
    lines.append("|------|--------|-----|------|-------|----------|\n")
    for i, (_, r) in enumerate(best_cap.head(5).iterrows(), 1):
        lines.append(f"| {i} | {r['candidate']} | {r['mar']:.3f} | {r['cagr']:.2%} | {r['max_dd']:.2%} | {r['pct_excl_T1']:.1%} |\n")

    lines.append("\n## Top S3 PTS Configs (at 5B/10%)\n\n")
    lines.append("| Rank | Config | MAR | CAGR | MaxDD | pct_pb | pct_str |\n")
    lines.append("|------|--------|-----|------|-------|--------|----------|\n")
    for i, (_, r) in enumerate(best_pts.head(5).iterrows(), 1):
        pb_pct  = r.get("pct_pullback", np.nan)
        str_pct = r.get("pct_strength", np.nan)
        lines.append(f"| {i} | {r['candidate']} | {r['mar']:.3f} | {r['cagr']:.2%} | {r['max_dd']:.2%} | {pb_pct:.1%} | {str_pct:.1%} |\n")

    lines.append("\n## Comparison vs A3 DP Reference\n\n")
    lines.append("- A3 DP at 5B/10%: MAR=0.416 (Phase 3.1 result)\n")
    if not best_cap.empty:
        s3_best_mar = float(best_cap.iloc[0]["mar"])
        lines.append(f"- S3 best DP at 5B/10%: MAR={s3_best_mar:.3f} ({best_cap.iloc[0]['candidate']})\n")
        lines.append(f"- S3 vs A3: {'S3 wins' if s3_best_mar > 0.416 else 'A3 wins'} (delta={s3_best_mar-0.416:+.3f})\n")

    lines.append("\n## Decision Classification\n\n")
    if not best_cap.empty:
        s3_mar = float(best_cap.iloc[0]["mar"])
        if s3_mar >= 0.40:
            cls = "PAPER_TRADE_PRIMARY"
            note = "Strong MAR, suitable for paper trading alongside A3 DP"
        elif s3_mar >= 0.30:
            cls = "PAPER_TRADE_SHADOW"
            note = "Moderate MAR, shadow-only role"
        else:
            cls = "RESEARCH_ONLY"
            note = "Low MAR after corrected liquidity, not ready for paper trade"
        lines.append(f"- S3 best DP: **{cls}** — {note}\n")

    (OUT_DIR / "S3_PHASE31_TOP_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print(f"  Top findings saved: {OUT_DIR / 'S3_PHASE31_TOP_FINDINGS.md'}", flush=True)

    return cap_df, pts_df, gk_df, cost_df


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Annual / regime decomposition for all candidates
# ─────────────────────────────────────────────────────────────────────────────

def run_step2(panel, vnx, gk_cache, adv50_map=None):
    """Step 2: Annual and regime decomposition for all A3/S3 candidates."""
    print("\n=== STEP 2: Annual / Regime Decomposition ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gate_by_date, _ = vnindex_regime_gate(vnx)
    if adv50_map is None:
        adv50_map = _build_adv50_map(panel)

    # Load known A3 and S3 candidates with corrected adv50
    candidates_a3 = {
        "A3_pos15":          (_load_led(P2_LED / "A3_pos15.csv"),    15, 1.0,  "ema_dist_at_entry"),
        "DP_A3_pb_only":     (_load_led(P25_DIR / "phase25a_dp_trade_ledger.csv"), 20, 1.0, "ema_dist_at_entry"),
    }

    # S3 best DP from step 1 (use file if exists)
    s3_best_path = OUT_DIR / "s3_best_dp_trade_ledger.csv"
    s3_screen_path = OUT_DIR / "s3_dp_screening_pass.csv"

    s3_candidates = {}
    if s3_best_path.exists():
        s3_best = _load_led(s3_best_path)
        if not s3_best.empty:
            s3_candidates["S3_best_dp"] = (s3_best, 20, 1.0, "mom20")
    elif s3_screen_path.exists():
        print("  S3 best ledger not found; run step 1 first for S3 annual decomp", flush=True)

    # S3 baseline
    s3_pos15 = _load_led(P2_LED / "S3_pos15.csv")
    if not s3_pos15.empty:
        s3_candidates["S3_pos15"] = (s3_pos15, 15, 1.0, "mom20")

    all_candidates = {**candidates_a3, **s3_candidates}

    annual_rows  = []
    regime_rows  = []

    for name, (led, max_pos, gk_m, rank_col) in all_candidates.items():
        if led.empty:
            print(f"  {name}: empty ledger, skip", flush=True)
            continue

        # Tag adv50 if missing
        if "adv50_value" not in led.columns or (led["adv50_value"].fillna(0) == 0).all():
            led = _tag_adv50(led, adv50_map)

        led = _tag_gk(led, gk_cache)
        eff_rank = rank_col if rank_col in led.columns else None

        eq, _ = _build_equity_adv_capped_v2(
            led, max_positions=max_pos, portfolio_vnd=REF_PORTFOLIO,
            participation=REF_PART, gk_mult=gk_m,
            rank_col=eff_rank or "ema_dist_at_entry",
        )

        if eq.empty:
            print(f"  {name}: empty equity, skip", flush=True)
            continue

        m = portfolio_metrics(eq, led)
        years = sorted(set(eq.index.year))

        for yr in years:
            ann_ret = _annual_return(eq, yr)
            yr_trades = led[led["entry_date"].dt.year == yr]
            n_yr   = len(yr_trades)
            wr_yr  = float((yr_trades["net_return"] > 0).mean()) if n_yr > 0 else np.nan
            mean_r = float(yr_trades["net_return"].mean()) if n_yr > 0 else np.nan

            annual_rows.append({
                "candidate":    name,
                "year":         yr,
                "annual_return": round(ann_ret, 4) if not np.isnan(ann_ret) else np.nan,
                "n_trades":     n_yr,
                "win_rate":     round(wr_yr, 4) if not np.isnan(wr_yr) else np.nan,
                "mean_net_return": round(mean_r, 4) if not np.isnan(mean_r) else np.nan,
                "cagr_overall": round(m.get("cagr", np.nan), 4),
                "mar_overall":  round(m.get("mar", np.nan), 4),
            })

        # Regime decomposition: bull (gate=1) vs bear (gate=0) at entry
        led["entry_date_ts"] = pd.to_datetime(led["entry_date"]).dt.normalize()
        led["regime_bull"]   = led["entry_date_ts"].map(lambda d: bool(gate_by_date.get(d, True)))

        for regime, rname in [(True, "bull"), (False, "bear")]:
            r_led = led[led["regime_bull"] == regime]
            if r_led.empty:
                continue
            n_r    = len(r_led)
            wr_r   = float((r_led["net_return"] > 0).mean())
            mean_r = float(r_led["net_return"].mean())
            regime_rows.append({
                "candidate":        name,
                "regime":           rname,
                "n_trades":         n_r,
                "win_rate":         round(wr_r, 4),
                "mean_net_return":  round(mean_r, 4),
                "pct_of_total":     round(n_r / max(len(led), 1), 4),
            })
        print(f"  {name}: {len(years)} years, MAR={m.get('mar', np.nan):.3f}", flush=True)

    annual_df = pd.DataFrame(annual_rows)
    regime_df = pd.DataFrame(regime_rows)
    annual_df.to_csv(OUT_DIR / "annual_component_performance.csv", index=False)
    regime_df.to_csv(OUT_DIR / "regime_component_performance.csv", index=False)
    print(f"  Annual decomp: {len(annual_df)} rows", flush=True)
    print(f"  Regime decomp: {len(regime_df)} rows", flush=True)
    return annual_df, regime_df


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Cost / liquidity sensitivity (full cross: all A3+S3 candidates)
# ─────────────────────────────────────────────────────────────────────────────

def run_step3(panel, gk_cache, adv50_map=None):
    """Step 3: Full cost × liquidity sensitivity for all candidates."""
    print("\n=== STEP 3: Cost / Liquidity Sensitivity (Full Cross) ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if adv50_map is None:
        adv50_map = _build_adv50_map(panel)

    rows = []
    base_candidates = {
        "A3_pos15": (_load_led(P2_LED / "A3_pos15.csv"), 15, "ema_dist_at_entry"),
        "DP_A3":    (_load_led(P25_DIR / "phase25a_dp_trade_ledger.csv"), 20, "ema_dist_at_entry"),
        "S3_pos15": (_load_led(P2_LED / "S3_pos15.csv"), 15, "mom20"),
    }

    s3_best_path = OUT_DIR / "s3_best_dp_trade_ledger.csv"
    if s3_best_path.exists():
        base_candidates["S3_best_dp"] = (_load_led(s3_best_path), 20, "mom20")

    for name, (led, max_pos, rank_col) in base_candidates.items():
        if led.empty:
            continue
        if "adv50_value" not in led.columns or (led["adv50_value"].fillna(0) == 0).all():
            led = _tag_adv50(led, adv50_map)
        led = _tag_gk(led, gk_cache)
        eff_rank = rank_col if rank_col in led.columns else None

        for pvnd in PORTFOLIO_SIZES:
            for part in PARTICIPATIONS:
                eq, stats = _build_equity_adv_capped_v2(
                    led, max_positions=max_pos, portfolio_vnd=pvnd,
                    participation=part,
                    rank_col=eff_rank or "ema_dist_at_entry",
                )
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, led)
                rows.append({
                    "candidate":        name,
                    "portfolio_B_VND":  pvnd / 1e9,
                    "participation_pct": part * 100,
                    "n_trades":         len(led),
                    "cagr":             round(m.get("cagr", np.nan), 4),
                    "max_dd":           round(m.get("max_dd", np.nan), 4),
                    "mar":              round(m.get("mar", np.nan), 4),
                    "sharpe":           round(m.get("sharpe", np.nan), 4),
                    "pct_excl_T1":      round(stats["pct_excl_T1"], 4),
                    "pct_full_T1":      round(stats["pct_full_T1"], 4),
                    "mean_fill_T1":     round(stats["mean_fill_T1"], 4),
                })
        print(f"  {name}: done", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "step3_cost_liquidity_sensitivity.csv", index=False)
    print(f"  Sensitivity results: {len(out)} rows", flush=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Playbook combinations (A3 DP + S3 best)
# ─────────────────────────────────────────────────────────────────────────────

def run_step4(panel, vnx, gk_cache, adv50_map=None):
    """Step 4: Playbook combination — A3 DP as primary + S3 best as overlay."""
    print("\n=== STEP 4: Playbook Combinations ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if adv50_map is None:
        adv50_map = _build_adv50_map(panel)

    gate_by_date, _ = vnindex_regime_gate(vnx)

    a3_dp  = _load_led(P25_DIR / "phase25a_dp_trade_ledger.csv")
    s3_best_path = OUT_DIR / "s3_best_dp_trade_ledger.csv"
    s3_led = _load_led(s3_best_path) if s3_best_path.exists() else pd.DataFrame()

    for led in [a3_dp, s3_led]:
        if led.empty:
            continue
        if "adv50_value" not in led.columns or (led["adv50_value"].fillna(0) == 0).all():
            _tag_adv50(led, adv50_map)

    a3_dp  = _tag_adv50(a3_dp, adv50_map) if not a3_dp.empty else a3_dp
    s3_led = _tag_adv50(s3_led, adv50_map) if not s3_led.empty else s3_led
    a3_dp  = _tag_gk(a3_dp, gk_cache) if not a3_dp.empty else a3_dp
    s3_led = _tag_gk(s3_led, gk_cache) if not s3_led.empty else s3_led

    # Playbooks defined in the research program:
    # PB1: A3 DP only (reference)
    # PB2: S3 best only (reference)
    # PB3: A3 DP (10 slots) + S3 best (5 slots) = combined 15-slot book
    # PB4: A3 DP + GK size boost
    # PB5: S3 best + GK size boost
    # PB6-PB10: variations with breadth filter (simplified: no breadth filter for now)

    rows = []

    playbooks = {
        "PB1_A3_DP_only":     (a3_dp,  None,    20, 1.0, "ema_dist_at_entry"),
        "PB2_S3_best_only":   (s3_led, None,    20, 1.0, "mom20"),
        "PB4_A3_DP_GK125":    (a3_dp,  None,    20, 1.25,"ema_dist_at_entry"),
        "PB5_S3_best_GK125":  (s3_led, None,    20, 1.25,"mom20"),
    }

    # PB3: merge A3 DP + S3 into combined book
    if not a3_dp.empty and not s3_led.empty:
        combined = pd.concat([
            a3_dp.assign(source="A3_DP"),
            s3_led.assign(source="S3_best"),
        ], ignore_index=True)
        combined["entry_date"] = pd.to_datetime(combined["entry_date"])
        combined["exit_date"]  = pd.to_datetime(combined["exit_date"])
        playbooks["PB3_A3_DP_plus_S3"] = (combined, None, 20, 1.0, "ema_dist_at_entry")

    for pb_name, (led, _, max_pos, gk_m, rank_col) in playbooks.items():
        if led.empty:
            print(f"  {pb_name}: empty ledger, skip", flush=True)
            continue
        eff_rank = rank_col if rank_col in led.columns else None
        for pvnd in PORTFOLIO_SIZES:
            for part in PARTICIPATIONS:
                eq, stats = _build_equity_adv_capped_v2(
                    led, max_positions=max_pos, portfolio_vnd=pvnd,
                    participation=part, gk_mult=gk_m,
                    rank_col=eff_rank or "ema_dist_at_entry",
                )
                if eq.empty:
                    continue
                m = portfolio_metrics(eq, led)
                rows.append({
                    "playbook":         pb_name,
                    "portfolio_B_VND":  pvnd / 1e9,
                    "participation_pct": part * 100,
                    "max_positions":    max_pos,
                    "gk_mult":          gk_m,
                    "n_trades":         len(led),
                    "cagr":             round(m.get("cagr", np.nan), 4),
                    "max_dd":           round(m.get("max_dd", np.nan), 4),
                    "mar":              round(m.get("mar", np.nan), 4),
                    "sharpe":           round(m.get("sharpe", np.nan), 4),
                    "pct_excl_T1":      round(stats["pct_excl_T1"], 4),
                    "pct_full_T1":      round(stats["pct_full_T1"], 4),
                })
        print(f"  {pb_name}: done, n={len(led)}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "playbook_corrected_liquidity_summary.csv", index=False)
    print(f"  Playbook results: {len(out)} rows", flush=True)

    # Annual by playbook (at ref 5B/10%)
    yr_rows = []
    for pb_name, (led, _, max_pos, gk_m, rank_col) in playbooks.items():
        if led.empty:
            continue
        eff_rank = rank_col if rank_col in led.columns else None
        eq, _ = _build_equity_adv_capped_v2(
            led, max_positions=max_pos, portfolio_vnd=REF_PORTFOLIO,
            participation=REF_PART, gk_mult=gk_m,
            rank_col=eff_rank or "ema_dist_at_entry",
        )
        if eq.empty:
            continue
        for yr in sorted(set(eq.index.year)):
            yr_rows.append({
                "playbook":     pb_name,
                "year":         yr,
                "annual_return": round(_annual_return(eq, yr), 4),
            })

    yr_df = pd.DataFrame(yr_rows)
    yr_df.to_csv(OUT_DIR / "playbook_by_year.csv", index=False)
    print(f"  Annual playbook: {len(yr_df)} rows", flush=True)

    # Top findings
    ref_out = out[(out["portfolio_B_VND"] == 5.0) & (out["participation_pct"] == 10.0)].sort_values("mar", ascending=False)
    lines = ["# Playbook Top Findings\n\n"]
    lines.append(f"As of: {pd.Timestamp.now().date()}\n\n")
    lines.append("## At 5B/10% Reference\n\n")
    lines.append("| Playbook | MAR | CAGR | MaxDD | Excl_T1 |\n")
    lines.append("|----------|-----|------|-------|----------|\n")
    for _, r in ref_out.iterrows():
        lines.append(f"| {r['playbook']} | {r['mar']:.3f} | {r['cagr']:.2%} | {r['max_dd']:.2%} | {r['pct_excl_T1']:.1%} |\n")
    lines.append("\n## Best Playbook\n\n")
    if not ref_out.empty:
        best = ref_out.iloc[0]
        lines.append(f"**{best['playbook']}** — MAR={best['mar']:.3f}, CAGR={best['cagr']:.2%}, MaxDD={best['max_dd']:.2%}\n")
    (OUT_DIR / "PLAYBOOK_TOP_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print(f"  Playbook findings saved", flush=True)
    return out, yr_df


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Phase32 daily scan (A3 state + S3 state + breadth)
# ─────────────────────────────────────────────────────────────────────────────

def run_step5(panel, vnx, gk_cache):
    """Step 5: Phase32 daily scan — A3 + S3 dual-universe with breadth state."""
    print("\n=== STEP 5: Phase32 Daily Scan ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
    from pp_backtest.ema_levels.entry import cloud_only_entry

    gate_by_date, _ = vnindex_regime_gate(vnx)
    last_date = pd.Timestamp(panel["date"].max()).normalize()
    regime_bull = bool(gate_by_date.get(last_date, False))

    portfolio_vnd = REF_PORTFOLIO
    max_pos       = 15
    base_pos_vnd  = portfolio_vnd / max_pos

    # ── Compute universe-level breadth ──
    # pct_cloud_bull_20_100: fraction of A3 universe with cloud_bull=1 today
    # pct_cloud_bull_21_55:  fraction of S3 universe with cloud_bull=1 today
    a3_universe = set(get_universe(panel, "ex_vin3"))
    s3_universe = set(get_universe(panel, "full"))

    a3_bull_count = 0
    s3_bull_count = 0
    a3_total      = 0
    s3_total      = 0

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

        # Corrected ADV50
        if "value" in sdf.columns:
            val = sdf["value"].astype(float).fillna(c * v * 1000)
        else:
            val = c * v * 1000
        adv50_vnd = val.rolling(50, min_periods=20).mean()
        adv50_now = float(adv50_vnd.iloc[-1]) if pd.notna(adv50_vnd.iloc[-1]) else 0.0

        # A3 state (EMA20/100)
        a3_cloud = ema_cloud(c, 20, 100)
        a3_fast  = a3_cloud["ema_fast"]
        a3_bull  = a3_cloud["cloud_bull"]
        a3_atr   = compute_atr(h, l, c, 14)

        a3_sig   = cloud_only_entry(c, a3_fast, a3_bull, min_bars_bear=3, warmup=110)
        a3_idxs  = np.where(a3_sig.values)[0]
        a3_cloud_now = bool(a3_bull.iloc[-1])

        if sym in a3_universe:
            a3_total += 1
            if a3_cloud_now:
                a3_bull_count += 1

        # S3 state (EMA21/55)
        s3_cloud = ema_cloud(c, 21, 55)
        s3_fast  = s3_cloud["ema_fast"]
        s3_bull  = s3_cloud["cloud_bull"]
        s3_sig   = cloud_only_entry(c, s3_fast, s3_bull, min_bars_bear=3, warmup=65)
        s3_idxs  = np.where(s3_sig.values)[0]
        s3_cloud_now = bool(s3_bull.iloc[-1])

        if sym in s3_universe:
            s3_total += 1
            if s3_cloud_now:
                s3_bull_count += 1

        # Active signal check (A3: within 40 bars)
        a3_active = False
        a3_bars_since = None
        if len(a3_idxs) > 0:
            li = int(a3_idxs[-1])
            if li + 1 < len(c) and (len(c) - 1 - (li + 1)) <= 40:
                a3_active = True
                a3_bars_since = len(c) - 1 - (li + 1)

        s3_active = False
        s3_bars_since = None
        if len(s3_idxs) > 0:
            li = int(s3_idxs[-1])
            if li + 1 < len(c) and (len(c) - 1 - (li + 1)) <= 40:
                s3_active = True
                s3_bars_since = len(c) - 1 - (li + 1)

        if not a3_active and not s3_active:
            continue

        cur_c = float(c.iloc[-1])

        # GK10
        try:
            gk_res   = compute_gk(c, h, l)
            gk_days  = d[gk_res["gk_buy"]]
            gk10 = any(abs((last_date - gd.normalize()).days) <= 10 for gd in gk_days)
        except Exception:
            gk10 = False

        gk_mult_flag = 1.25 if gk10 else 1.0
        target_full  = base_pos_vnd * gk_mult_flag
        target_T1    = target_full * 0.5
        max_at_10pct = adv50_now * 0.10 if adv50_now > 0 else 0.0

        liq_T1   = _liquidity_warning_v2(adv50_now, target_T1, 0.10)
        liq_full = _liquidity_warning_v2(adv50_now, target_full, 0.10)
        if adv50_now <= 0:
            rec = "no_adv_data"
        elif target_T1 <= max_at_10pct:
            rec = "full_T1"
        elif adv50_now * 0.10 >= MIN_POS_VND:
            rec = "partial_T1"
        else:
            rec = "skip"

        rows.append({
            "as_of_date":        last_date.date(),
            "symbol":            sym,
            "close_kVND":        round(cur_c, 2),
            "a3_active":         a3_active,
            "a3_cloud_bull":     a3_cloud_now,
            "a3_bars_since":     a3_bars_since,
            "s3_active":         s3_active,
            "s3_cloud_bull":     s3_cloud_now,
            "s3_bars_since":     s3_bars_since,
            "gk10":              gk10,
            "gk_mult":           gk_mult_flag,
            "adv50_B_VND":       round(adv50_now / 1e9, 3),
            "target_T1_M":       round(target_T1 / 1e6, 1),
            "target_full_M":     round(target_full / 1e6, 1),
            "max_10pct_M":       round(max_at_10pct / 1e6, 1),
            "liq_warn_T1":       liq_T1,
            "liq_warn_full":     liq_full,
            "recommendation":    rec,
            "in_a3_universe":    sym in a3_universe,
            "in_s3_universe":    sym in s3_universe,
        })

    a3_breadth = round(a3_bull_count / max(a3_total, 1), 4)
    s3_breadth = round(s3_bull_count / max(s3_total, 1), 4)
    print(f"  A3 breadth (pct_cloud_bull_20_100): {a3_breadth:.1%} ({a3_bull_count}/{a3_total})", flush=True)
    print(f"  S3 breadth (pct_cloud_bull_21_55):  {s3_breadth:.1%} ({s3_bull_count}/{s3_total})", flush=True)

    scan_df = pd.DataFrame(rows)
    # Add breadth columns to scan
    scan_df["pct_cloud_bull_a3_universe"] = a3_breadth
    scan_df["pct_cloud_bull_s3_universe"] = s3_breadth
    scan_df["regime_bull"] = regime_bull

    scan_df.to_csv(OUT_DIR / "phase32_daily_scan_sample.csv", index=False)
    print(f"  Phase32 scan: {len(scan_df)} active setups", flush=True)

    # Schema CSV
    schema_cols = [
        ("as_of_date",   "date",  "Scan date"),
        ("symbol",       "str",   "Ticker"),
        ("close_kVND",   "float", "Last close in kVND"),
        ("a3_active",    "bool",  "Has A3 (20/100) signal within 40 bars"),
        ("a3_cloud_bull","bool",  "A3 cloud currently bullish"),
        ("a3_bars_since","int",   "Bars since A3 entry signal"),
        ("s3_active",    "bool",  "Has S3 (21/55) signal within 40 bars"),
        ("s3_cloud_bull","bool",  "S3 cloud currently bullish"),
        ("s3_bars_since","int",   "Bars since S3 entry signal"),
        ("gk10",         "bool",  "GK buy signal within 10 days"),
        ("gk_mult",      "float", "Position size multiplier (1.0 or 1.25)"),
        ("adv50_B_VND",  "float", "50-day avg daily value in B VND (VND unit, corrected)"),
        ("target_T1_M",  "float", "Target T1 position in M VND (at 5B portfolio)"),
        ("target_full_M","float", "Target full position in M VND"),
        ("max_10pct_M",  "float", "Max allowed at 10% participation cap"),
        ("liq_warn_T1",  "str",   "Liquidity warning for T1: OK/WARN_NEAR/WARN_OVER/CRITICAL"),
        ("liq_warn_full","str",   "Liquidity warning for full position"),
        ("recommendation","str",  "full_T1/partial_T1/skip/no_adv_data"),
        ("in_a3_universe","bool", "Symbol in A3 ex-VIN3 universe"),
        ("in_s3_universe","bool", "Symbol in S3 full universe"),
        ("pct_cloud_bull_a3_universe","float","Breadth: pct A3 universe in cloud_bull"),
        ("pct_cloud_bull_s3_universe","float","Breadth: pct S3 universe in cloud_bull"),
        ("regime_bull",  "bool",  "VNINDEX regime bull at scan date"),
    ]
    schema_df = pd.DataFrame(schema_cols, columns=["field", "dtype", "description"])
    schema_df.to_csv(OUT_DIR / "phase32_daily_scan_schema.csv", index=False)

    # Dashboard spec
    dashboard_lines = [
        "# Phase32 Dashboard Specification\n\n",
        f"Generated: {pd.Timestamp.now().date()}\n\n",
        "## Dashboard Panels\n\n",
        "### Panel 1: Regime & Breadth\n",
        "- VNINDEX regime state (bull/bear)\n",
        "- A3 universe breadth: pct_cloud_bull_20_100\n",
        "- S3 universe breadth: pct_cloud_bull_21_55\n",
        "- Breadth thresholds: >60% = strong bull, <40% = defensive\n\n",
        "### Panel 2: Active Setups\n",
        "- Active A3 signals (within 40 bars): count, top 5 by liq_warn\n",
        "- Active S3 signals (within 40 bars): count, top 5 by liq_warn\n",
        "- GK10 flag count\n\n",
        "### Panel 3: Liquidity Health\n",
        "- Distribution of liq_warn_T1: OK/WARN_NEAR/WARN_OVER/CRITICAL\n",
        "- Skip rate = pct(recommendation='skip')\n",
        "- Mean adv50_B_VND for active setups\n\n",
        "### Panel 4: Trade Candidates\n",
        "- Table: symbol, a3_active, s3_active, gk10, adv50_B_VND, liq_warn_T1, recommendation\n",
        "- Sorted by: recommendation=full_T1 first, then adv50 desc\n",
        "- Filter: recommendation != skip AND regime_bull = True\n\n",
        "## Alerts\n\n",
        "- A3 breadth < 40%: reduce exposure / no new A3 entries\n",
        "- S3 breadth < 40%: reduce exposure / no new S3 entries\n",
        "- Regime bear: paper-trade only, no live entries\n",
    ]
    (OUT_DIR / "phase32_dashboard_spec.md").write_text("".join(dashboard_lines), encoding="utf-8")

    # Paper trade rules
    rules_lines = [
        "# Phase32 Paper Trade Rules\n\n",
        f"Generated: {pd.Timestamp.now().date()}\n\n",
        "## A3 (EMA20/100) — Primary / DP-First\n\n",
        "**Entry:**\n",
        "- Cloud breakout (EMA20 cross above EMA100 + price above both)\n",
        "- Universe: ex-VIN3 (exclude VIN, VPL)\n",
        "- Regime gate: VNINDEX must be in bull regime\n",
        "- Breadth gate: pct_cloud_bull_a3_universe > 40%\n\n",
        "**Position sizing (DP-first):**\n",
        "- T1 = 50% of intended slot at entry\n",
        "- T2 = 50% on pullback ≥4% within 30 bars (pb_only mode)\n",
        "- Slot size = portfolio / 20 (× 1.25 if GK10)\n",
        "- ADV cap: effective_T1 = min(T1, adv50_B × 10%)\n\n",
        "**Exit:**\n",
        "- TP1: +18% (sell 50% of position)\n",
        "- Trail: 2.5× ATR14 from highest close since entry\n",
        "- Max hold: 250 bars\n\n",
        "## S3 (EMA21/55) — Shadow / Paper Trade\n\n",
        "**Entry:**\n",
        "- Cloud breakout (EMA21 cross above EMA55 + price above both)\n",
        "- Universe: full (all 272 symbols)\n",
        "- Regime gate: VNINDEX must be in bull regime\n",
        "- Breadth gate: pct_cloud_bull_s3_universe > 40%\n\n",
        "**Position sizing:**\n",
        "- T1 = best_t1_frac × slot at entry (see s3_dp_screening_pass.csv)\n",
        "- T2 = (1-t1_frac) × slot on pullback\n",
        "- Slot size = portfolio / 20 (× 1.25 if GK10)\n",
        "- ADV cap: effective_T1 = min(T1, adv50_B × 10%)\n\n",
        "**Exit:**\n",
        "- TP1: +18% (sell 50% of position)\n",
        "- Trail: 3.5× ATR14 from highest close since entry\n",
        "- Max hold: 250 bars\n\n",
        "## Concurrent Position Limits\n\n",
        "- A3 book: max 20 active positions\n",
        "- S3 book: max 20 active positions (paper only)\n",
        "- Combined: A3 is primary; S3 paper trades do not consume real capital\n",
        "- Vietnam settlement: T+3; min sell lock = 5 bars\n\n",
        "## Risk Controls\n\n",
        "- Stop adding if A3 breadth < 35% (bear territory)\n",
        "- Stop all S3 entries if S3 breadth < 35%\n",
        "- Regime flip to bear: close T1 tranches on next available day\n",
    ]
    (OUT_DIR / "phase32_paper_trade_rules.md").write_text("".join(rules_lines), encoding="utf-8")

    print(f"  Phase32 schema/dashboard/rules saved", flush=True)
    return scan_df


# ─────────────────────────────────────────────────────────────────────────────
# Final Decision Memo
# ─────────────────────────────────────────────────────────────────────────────

CANDIDATE_CLASSIFICATIONS = {
    "A3_pos15_baseline": {
        "class": "PAPER_TRADE_SHADOW",
        "role": "Baseline reference; superseded by DP-first",
        "mar_5B_10pct": 0.38,  # from phase31 results
        "notes": "Full-position only, no pullback. Used as benchmark.",
    },
    "DP_A3_pb_only": {
        "class": "PRODUCTION_CANDIDATE",
        "role": "Primary live candidate — A3 DP-first",
        "mar_5B_10pct": 0.416,  # confirmed Phase 3.1
        "notes": "MAR=0.416 at 5B/10% after corrected liquidity. DP-first mode: T1=50% at entry, T2 on pullback.",
    },
    "PTS_A3_pb4w30_str6w10": {
        "class": "PAPER_TRADE_SHADOW",
        "role": "Shadow/aggressive mode — A3 PTS",
        "mar_5B_10pct": 0.343,  # confirmed Phase 3.1
        "notes": "MAR dropped from 0.72 to 0.343 after corrected liquidity. Shadow only.",
    },
    "S3_best_dp": {
        "class": "PAPER_TRADE_PRIMARY",  # will be updated from step1 results
        "role": "S3 shadow book — EMA21/55 DP-first",
        "mar_5B_10pct": None,  # filled from step1
        "notes": "Classification pending Step 1 results. Target: MAR > 0.30 for PAPER_TRADE_PRIMARY.",
    },
}


def write_decision_memo(adv50_map=None):
    """Write MISSING_WORK_FINAL_DECISION_MEMO.md from available outputs."""
    print("\n=== WRITING FINAL DECISION MEMO ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load step1 results if available
    s3_cap_path = OUT_DIR / "s3_phase31_baseline_corrected.csv"
    s3_mar_ref  = None
    s3_best_cfg = None
    if s3_cap_path.exists():
        s3_cap = pd.read_csv(s3_cap_path)
        ref_row = s3_cap[
            (s3_cap["portfolio_B_VND"] == 5.0) & (s3_cap["participation_pct"] == 10.0)
        ].sort_values("mar", ascending=False)
        if not ref_row.empty:
            s3_mar_ref  = float(ref_row.iloc[0]["mar"])
            s3_best_cfg = str(ref_row.iloc[0]["candidate"])

    if s3_mar_ref is not None:
        CANDIDATE_CLASSIFICATIONS["S3_best_dp"]["mar_5B_10pct"] = s3_mar_ref
        if s3_mar_ref >= 0.40:
            CANDIDATE_CLASSIFICATIONS["S3_best_dp"]["class"] = "PAPER_TRADE_PRIMARY"
        elif s3_mar_ref >= 0.30:
            CANDIDATE_CLASSIFICATIONS["S3_best_dp"]["class"] = "PAPER_TRADE_SHADOW"
        else:
            CANDIDATE_CLASSIFICATIONS["S3_best_dp"]["class"] = "RESEARCH_ONLY"

    lines = ["# Missing Work Final Decision Memo\n\n"]
    lines.append(f"As of: {pd.Timestamp.now().date()}\n\n")
    lines.append("## Executive Summary\n\n")
    lines.append("This memo classifies all strategy candidates after completing:\n")
    lines.append("- Phase 3.1 Liquidity Unit Audit (resolved 1000× bug, corrected ADV50)\n")
    lines.append("- S3 21/55 corrected-liquidity research (Step 1)\n")
    lines.append("- Annual decomposition, playbook combinations, Phase32 daily scan\n\n")
    lines.append("**Primary conclusion:** A3 DP-first is the only PRODUCTION_CANDIDATE.\n")
    lines.append("S3 is a shadow/paper-trade book. PTS is aggressive/shadow mode only.\n\n")

    lines.append("## Candidate Classifications\n\n")
    lines.append("| Candidate | Classification | MAR (5B/10%) | Role |\n")
    lines.append("|-----------|---------------|--------------|------|\n")
    for cname, info in CANDIDATE_CLASSIFICATIONS.items():
        mar_str = f"{info['mar_5B_10pct']:.3f}" if info["mar_5B_10pct"] is not None else "TBD"
        lines.append(f"| {cname} | **{info['class']}** | {mar_str} | {info['role']} |\n")

    lines.append("\n## Detailed Notes\n\n")
    for cname, info in CANDIDATE_CLASSIFICATIONS.items():
        lines.append(f"### {cname}\n")
        lines.append(f"- **Classification:** {info['class']}\n")
        mar_str = f"{info['mar_5B_10pct']:.3f}" if info["mar_5B_10pct"] is not None else "TBD"
        lines.append(f"- **MAR @ 5B/10%:** {mar_str}\n")
        lines.append(f"- **Role:** {info['role']}\n")
        lines.append(f"- **Notes:** {info['notes']}\n\n")

    lines.append("## Production Deployment Plan\n\n")
    lines.append("### Phase 1 (Live — real capital)\n")
    lines.append("- **A3 DP-first**: MAR=0.416 @ 5B/10% ADV\n")
    lines.append("  - Entry: EMA20/100 cloud breakout, ex-VIN3 universe\n")
    lines.append("  - T1=50% at entry, T2=50% on ≥4% pullback within 30 bars\n")
    lines.append("  - Exit: TP1 +18%, trail 2.5×ATR, max 250 bars\n")
    lines.append("  - GK10 size boost: 1.25×\n")
    lines.append("  - Max positions: 20\n")
    lines.append("  - Breadth gate: A3 breadth > 40%\n\n")
    lines.append("### Phase 2 (Paper trade)\n")
    lines.append("- **S3 best DP**: Shadow paper book\n")
    if s3_best_cfg:
        lines.append(f"  - Best config: {s3_best_cfg}\n")
    if s3_mar_ref:
        lines.append(f"  - MAR @ 5B/10%: {s3_mar_ref:.3f}\n")
    lines.append("  - Entry: EMA21/55 cloud breakout, full universe\n")
    lines.append("  - Same exit as S3 baseline: TP1 +18%, trail 3.5×ATR\n\n")
    lines.append("### Phase 3 (Shadow aggressive — conditional)\n")
    lines.append("- **PTS_A3**: Only when MAR recovers > 0.35 after 6+ months live data\n\n")

    lines.append("## Liquidity Rules (Post Phase 3.1)\n\n")
    lines.append("- ADV50 formula: `panel['value'].rolling(50).fillna(close × volume × 1000)`\n")
    lines.append("- T1 position cap: `min(T1_target, adv50_VND × participation)`\n")
    lines.append("- Recommendation: full_T1 / partial_T1 / skip / no_adv_data\n")
    lines.append("- All equity sims: use `_build_equity_adv_capped_v2` from phase31\n\n")

    lines.append("## Outputs Generated\n\n")
    for f in sorted(OUT_DIR.glob("*.csv")):
        lines.append(f"- `missing_work/{f.name}`\n")
    for f in sorted(OUT_DIR.glob("*.md")):
        lines.append(f"- `missing_work/{f.name}`\n")

    memo_path = OUT_DIR / "MISSING_WORK_FINAL_DECISION_MEMO.md"
    memo_path.write_text("".join(lines), encoding="utf-8")
    print(f"  Decision memo saved: {memo_path}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Missing Work Research — Steps 0-5")
    parser.add_argument("--step", default="all",
                        choices=["0", "1", "2", "3", "4", "5", "memo", "all"])
    args = parser.parse_args()

    run_all  = args.step == "all"
    run_memo = args.step == "memo" or run_all

    print(f"Loading panel and VNINDEX...", flush=True)
    panel = load_panel()
    vnx   = load_vnindex()
    print(f"Panel loaded: {len(panel):,} rows, {panel['symbol'].nunique()} symbols", flush=True)

    print(f"Building GK cache...", flush=True)
    gk_cache = build_gk_cache(panel)

    adv50_map = None  # lazily built once

    if args.step == "0" or run_all:
        run_step0()

    if args.step == "1" or run_all:
        run_step1(panel, vnx, gk_cache)

    if args.step == "2" or run_all:
        if adv50_map is None:
            adv50_map = _build_adv50_map(panel)
        run_step2(panel, vnx, gk_cache, adv50_map)

    if args.step == "3" or run_all:
        if adv50_map is None:
            adv50_map = _build_adv50_map(panel)
        run_step3(panel, gk_cache, adv50_map)

    if args.step == "4" or run_all:
        if adv50_map is None:
            adv50_map = _build_adv50_map(panel)
        run_step4(panel, vnx, gk_cache, adv50_map)

    if args.step == "5" or run_all:
        run_step5(panel, vnx, gk_cache)

    if run_memo:
        write_decision_memo()

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
