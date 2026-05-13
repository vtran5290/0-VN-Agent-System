#!/usr/bin/env python3
"""
Portfolio hardening validation — Steps 2-6.

Steps:
  2. Ranked fill: fifo vs ema_dist vs momentum
  3. Cost sensitivity: 40 / 60 / 100 bps
  4. Position sizing: max_positions = 10 / 15 / 20
  5. VIN sensitivity: full / ex_vic / ex_vin3
  6. Subperiod regime breakdown: 2012-2017 / 2018-2022 / 2023-2026

Candidates: PRIMARY (B_cloud20_100_partial) and SHADOW (B_cloud21_55_partial).

Efficiency: for a given candidate + universe, compute_all_trades() runs once.
Cost/position/rank variants reuse the same trades_df by adjusting net_return
or calling build_portfolio() with different params.

Outputs:
  data/research/hardening/portfolio_hardening_results.csv
  data/research/hardening/vin_sensitivity_results.csv
  data/research/hardening/regime_breakdown_results.csv

Usage:
    .venv\\Scripts\\python.exe pp_backtest/run_hardening.py
    .venv\\Scripts\\python.exe pp_backtest/run_hardening.py --fast
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_portfolio_sim import (
    compute_all_trades, build_portfolio, portfolio_metrics, DEFAULT_COST,
)
from pp_backtest.candidate_strategy_manifest import PRIMARY, SHADOW, PRODUCTION_CANDIDATES

PANEL_PATH  = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
OUT_DIR     = REPO / "data" / "research" / "hardening"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EX_VIN3        = {"VIC", "VHM", "VRE"}
EX_VIC_ONLY    = {"VIC"}
EXCLUDE_ALWAYS = {"VPL"}

SUBPERIODS = [
    ("2012-01-01", "2017-12-31", "2012-2017"),
    ("2018-01-01", "2022-12-31", "2018-2022"),
    ("2023-01-01", "2030-01-01", "2023-2026"),
]

RANK_MODES   = ["fifo", "ema_dist", "momentum"]
COST_LEVELS  = [0.004, 0.006, 0.010]          # 40 / 60 / 100 bps
MAX_POS_LIST = [10, 15, 20]


# ── Universe helpers ──────────────────────────────────────────────────────────

def get_universes(all_symbols: list[str]) -> dict[str, list[str]]:
    base    = [s for s in all_symbols if s not in EXCLUDE_ALWAYS]
    return {
        "full":    base,
        "ex_vic":  [s for s in base if s not in EX_VIC_ONLY],
        "ex_vin3": [s for s in base if s not in EX_VIN3],
    }


def sample(symbols: list[str], fast: bool, n: int = 40) -> list[str]:
    return symbols[:n] if fast else symbols


# ── Core: pre-compute trades for a candidate + universe ───────────────────────

def precompute(
    cfg: dict,
    panel: pd.DataFrame,
    symbols: list[str],
) -> pd.DataFrame:
    """compute_all_trades at default cost for one (cfg, universe) combo."""
    return compute_all_trades(
        panel, symbols,
        entry_type  = cfg["entry_type"],
        ema_fast    = cfg["ema_fast"],
        ema_slow    = cfg["ema_slow"],
        exit_mode   = cfg["exit_mode"],
        max_hold    = cfg["max_hold"],
        cost        = DEFAULT_COST,
    )


def apply_cost(trades_df: pd.DataFrame, cost: float) -> pd.DataFrame:
    """Return copy with net_return adjusted to a different cost level."""
    t = trades_df.copy()
    t["net_return"] = t["gross_return"] - cost
    return t


# ── Step 2: ranked fill ───────────────────────────────────────────────────────

def step2_ranked_fill(
    panel: pd.DataFrame,
    universes: dict,
    fast: bool,
) -> pd.DataFrame:
    rows = []
    for cfg in PRODUCTION_CANDIDATES:
        symbols = sample(universes["ex_vin3"], fast)
        print(f"  [{cfg['label']}] computing trades for ranked fill...")
        t0       = time.time()
        trades   = precompute(cfg, panel, symbols)
        if trades.empty:
            continue
        print(f"    trades computed: {len(trades)} rows  ({time.time()-t0:.0f}s)")

        for rank_mode in RANK_MODES:
            equity = build_portfolio(trades, cfg["max_positions"], rank_mode)
            m      = portfolio_metrics(equity, trades)
            if not m:
                continue
            rows.append({
                "step":     "ranked_fill",
                "label":    cfg["label"],
                "variant":  rank_mode,
                "universe": "ex_vin3",
                **m,
            })
            print(f"    {rank_mode:<12}  CAGR={m['cagr']:.1%}  Sharpe={m['sharpe']:.3f}  "
                  f"maxDD={m['max_dd']:.1%}  n={m.get('n_trades',0)}")

    return pd.DataFrame(rows)


# ── Step 3: cost sensitivity ──────────────────────────────────────────────────

def step3_cost_sensitivity(
    panel: pd.DataFrame,
    universes: dict,
    fast: bool,
) -> pd.DataFrame:
    rows = []
    for cfg in PRODUCTION_CANDIDATES:
        symbols = sample(universes["ex_vin3"], fast)
        trades  = precompute(cfg, panel, symbols)
        if trades.empty:
            continue
        print(f"  [{cfg['label']}] cost sensitivity:")

        for cost in COST_LEVELS:
            t_adj  = apply_cost(trades, cost)
            equity = build_portfolio(t_adj, cfg["max_positions"], "fifo")
            m      = portfolio_metrics(equity, t_adj)
            if not m:
                continue
            bps = int(round(cost * 10000))
            rows.append({
                "step":     "cost_sensitivity",
                "label":    cfg["label"],
                "variant":  f"{bps}bps",
                "universe": "ex_vin3",
                "cost_bps": bps,
                **m,
            })
            print(f"    {bps}bps  CAGR={m['cagr']:.1%}  Sharpe={m['sharpe']:.3f}  "
                  f"maxDD={m['max_dd']:.1%}  avg_trade={m.get('avg_trade_ret',0):.1%}")

    return pd.DataFrame(rows)


# ── Step 4: position sizing ───────────────────────────────────────────────────

def step4_position_sizing(
    panel: pd.DataFrame,
    universes: dict,
    fast: bool,
) -> pd.DataFrame:
    rows = []
    for cfg in PRODUCTION_CANDIDATES:
        symbols = sample(universes["ex_vin3"], fast)
        trades  = precompute(cfg, panel, symbols)
        if trades.empty:
            continue
        print(f"  [{cfg['label']}] position sizing:")

        for max_pos in MAX_POS_LIST:
            equity = build_portfolio(trades, max_pos, "fifo")
            m      = portfolio_metrics(equity, trades)
            if not m:
                continue
            rows.append({
                "step":          "position_sizing",
                "label":         cfg["label"],
                "variant":       f"maxpos_{max_pos}",
                "universe":      "ex_vin3",
                "max_positions": max_pos,
                **m,
            })
            print(f"    max_pos={max_pos:<3}  CAGR={m['cagr']:.1%}  Sharpe={m['sharpe']:.3f}  "
                  f"maxDD={m['max_dd']:.1%}  MAR={m.get('mar',0):.2f}")

    return pd.DataFrame(rows)


# ── Step 5: VIN sensitivity ───────────────────────────────────────────────────

def step5_vin_sensitivity(
    panel: pd.DataFrame,
    universes: dict,
    fast: bool,
) -> pd.DataFrame:
    rows = []
    for cfg in PRODUCTION_CANDIDATES:
        print(f"  [{cfg['label']}] VIN sensitivity:")
        for universe_name, all_syms in universes.items():
            symbols = sample(all_syms, fast)
            trades  = precompute(cfg, panel, symbols)
            if trades.empty:
                continue
            equity  = build_portfolio(trades, cfg["max_positions"], "fifo")
            m       = portfolio_metrics(equity, trades)
            if not m:
                continue
            rows.append({
                "label":    cfg["label"],
                "universe": universe_name,
                "n_symbols": len(symbols),
                **m,
            })
            print(f"    {universe_name:<9}  n={len(symbols):<4}  CAGR={m['cagr']:.1%}  "
                  f"Sharpe={m['sharpe']:.3f}  maxDD={m['max_dd']:.1%}  "
                  f"oos={m.get('oos_avg_ret',0):.1%}")

    return pd.DataFrame(rows)


# ── Step 6: regime / subperiod breakdown ─────────────────────────────────────

def _subperiod_metrics(equity: pd.Series, trades_df: pd.DataFrame,
                       start: str, end: str) -> dict:
    """Slice equity and trades by subperiod and compute metrics."""
    eq_sl = equity.loc[start:end]
    if len(eq_sl) < 5:
        return {}
    tr_sl = trades_df[
        (trades_df["entry_date"] >= start) & (trades_df["entry_date"] <= end)
    ]
    return portfolio_metrics(eq_sl, tr_sl, test_start=start)


def step6_regime_breakdown(
    panel: pd.DataFrame,
    universes: dict,
    fast: bool,
) -> pd.DataFrame:
    rows = []
    for cfg in PRODUCTION_CANDIDATES:
        symbols = sample(universes["ex_vin3"], fast)
        trades  = precompute(cfg, panel, symbols)
        if trades.empty:
            continue
        equity  = build_portfolio(trades, cfg["max_positions"], "fifo")
        print(f"  [{cfg['label']}] subperiod breakdown:")

        for sp_start, sp_end, sp_label in SUBPERIODS:
            m = _subperiod_metrics(equity, trades, sp_start, sp_end)
            if not m:
                print(f"    {sp_label}: no data")
                continue
            rows.append({
                "label":   cfg["label"],
                "period":  sp_label,
                "n_years": m.get("n_years", 0),
                **m,
            })
            print(f"    {sp_label}  CAGR={m.get('cagr',0):.1%}  "
                  f"Sharpe={m.get('sharpe',0):.3f}  maxDD={m.get('max_dd',0):.1%}  "
                  f"n_trades={m.get('n_trades',0)}")

    return pd.DataFrame(rows)


# ── Summary printers ──────────────────────────────────────────────────────────

def print_ranked_fill_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("STEP 2 — RANKED FILL COMPARISON")
    print("=" * 80)
    print(f"  {'label':<30} {'rank_mode':<12} {'CAGR':>7} {'maxDD':>7} "
          f"{'Sharpe':>7} {'MAR':>6} {'n_tr':>6} {'hit%':>6} {'oos%':>7}")
    for _, r in df.sort_values(["label", "variant"]).iterrows():
        print(f"  {r.label:<30} {r.variant:<12} "
              f"{r.get('cagr',0):>7.1%} {r.get('max_dd',0):>7.1%} "
              f"{r.get('sharpe',0):>7.3f} {r.get('mar',0):>6.2f} "
              f"{int(r.get('n_trades',0)):>6} "
              f"{r.get('hit_rate',0):>6.1%} "
              f"{r.get('oos_avg_ret',0) if pd.notna(r.get('oos_avg_ret')) else 0:>7.1%}")


def print_cost_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("STEP 3 — COST SENSITIVITY (bps)")
    print("=" * 80)
    print(f"  {'label':<30} {'bps':>5} {'CAGR':>7} {'maxDD':>7} "
          f"{'Sharpe':>7} {'avg_tr':>7}")
    for _, r in df.sort_values(["label", "cost_bps"]).iterrows():
        print(f"  {r.label:<30} {int(r.get('cost_bps',0)):>5} "
              f"{r.get('cagr',0):>7.1%} {r.get('max_dd',0):>7.1%} "
              f"{r.get('sharpe',0):>7.3f} {r.get('avg_trade_ret',0):>7.1%}")


def print_pos_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("STEP 4 — POSITION SIZING")
    print("=" * 80)
    print(f"  {'label':<30} {'max_pos':>7} {'CAGR':>7} {'maxDD':>7} "
          f"{'Sharpe':>7} {'MAR':>6}")
    for _, r in df.sort_values(["label", "max_positions"]).iterrows():
        print(f"  {r.label:<30} {int(r.get('max_positions',0)):>7} "
              f"{r.get('cagr',0):>7.1%} {r.get('max_dd',0):>7.1%} "
              f"{r.get('sharpe',0):>7.3f} {r.get('mar',0):>6.2f}")


def print_vin_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("STEP 5 — VIN SENSITIVITY")
    print("=" * 80)
    print(f"  {'label':<30} {'universe':<10} {'n':>5} {'CAGR':>7} {'maxDD':>7} "
          f"{'Sharpe':>7} {'oos%':>7}")
    for _, r in df.sort_values(["label", "universe"]).iterrows():
        print(f"  {r.label:<30} {r.universe:<10} {int(r.get('n_symbols',0)):>5} "
              f"{r.get('cagr',0):>7.1%} {r.get('max_dd',0):>7.1%} "
              f"{r.get('sharpe',0):>7.3f} "
              f"{r.get('oos_avg_ret',0) if pd.notna(r.get('oos_avg_ret')) else 0:>7.1%}")


def print_regime_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("STEP 6 — REGIME / SUBPERIOD BREAKDOWN")
    print("=" * 80)
    print(f"  {'label':<30} {'period':<13} {'CAGR':>7} {'maxDD':>7} "
          f"{'Sharpe':>7} {'n_tr':>6} {'avg_tr':>7}")
    for _, r in df.sort_values(["label", "period"]).iterrows():
        print(f"  {r.label:<30} {r.period:<13} "
              f"{r.get('cagr',0):>7.1%} {r.get('max_dd',0):>7.1%} "
              f"{r.get('sharpe',0):>7.3f} "
              f"{int(r.get('n_trades',0)):>6} "
              f"{r.get('avg_trade_ret',0):>7.1%}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default=str(PANEL_PATH))
    ap.add_argument("--fast", action="store_true",
                    help="Use 40-symbol sample for speed testing")
    ap.add_argument("--step", type=int, default=0,
                    help="Run only this step (2-6). 0 = all.")
    args = ap.parse_args()

    print("=== Portfolio Hardening ===")
    t_start = time.time()

    panel = pd.read_parquet(args.panel)
    panel["date"] = pd.to_datetime(panel["date"])
    panel.sort_values(["symbol", "date"], inplace=True)
    print(f"Panel: {panel['symbol'].nunique()} symbols, "
          f"{panel['date'].min().date()} to {panel['date'].max().date()}")

    all_symbols = sorted(panel["symbol"].unique().tolist())
    universes   = get_universes(all_symbols)
    print(f"Universes: full={len(universes['full'])}, "
          f"ex_vic={len(universes['ex_vic'])}, "
          f"ex_vin3={len(universes['ex_vin3'])}")

    if args.fast:
        print("FAST MODE: 40-symbol sample")

    run = lambda s: (args.step == 0 or args.step == s)

    # Step 2
    if run(2):
        print("\n--- Step 2: Ranked Fill ---")
        df2 = step2_ranked_fill(panel, universes, args.fast)
        if not df2.empty:
            df2.to_csv(OUT_DIR / "step2_ranked_fill.csv", index=False)
            print_ranked_fill_summary(df2)

    # Step 3
    if run(3):
        print("\n--- Step 3: Cost Sensitivity ---")
        df3 = step3_cost_sensitivity(panel, universes, args.fast)
        if not df3.empty:
            df3.to_csv(OUT_DIR / "step3_cost_sensitivity.csv", index=False)
            print_cost_summary(df3)

    # Step 4
    if run(4):
        print("\n--- Step 4: Position Sizing ---")
        df4 = step4_position_sizing(panel, universes, args.fast)
        if not df4.empty:
            df4.to_csv(OUT_DIR / "step4_position_sizing.csv", index=False)
            print_pos_summary(df4)

    # Step 5
    if run(5):
        print("\n--- Step 5: VIN Sensitivity ---")
        df5 = step5_vin_sensitivity(panel, universes, args.fast)
        if not df5.empty:
            df5.to_csv(OUT_DIR / "vin_sensitivity_results.csv", index=False)
            print_vin_summary(df5)

    # Step 6
    if run(6):
        print("\n--- Step 6: Regime Breakdown ---")
        df6 = step6_regime_breakdown(panel, universes, args.fast)
        if not df6.empty:
            df6.to_csv(OUT_DIR / "regime_breakdown_results.csv", index=False)
            print_regime_summary(df6)

    # Combined hardening CSV (Steps 2-4)
    if args.step == 0:
        parts = []
        for name in ["step2_ranked_fill.csv", "step3_cost_sensitivity.csv",
                     "step4_position_sizing.csv"]:
            p = OUT_DIR / name
            if p.exists():
                parts.append(pd.read_csv(p))
        if parts:
            combined = pd.concat(parts, ignore_index=True)
            combined.to_csv(OUT_DIR / "portfolio_hardening_results.csv", index=False)
            print(f"\nSaved: {OUT_DIR / 'portfolio_hardening_results.csv'}")

    print(f"\nTotal elapsed: {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
