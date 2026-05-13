#!/usr/bin/env python3
"""
Compute yearly and subperiod returns for B_cloud20_100 and B_cloud21_55
then compare against GK audit strategies side-by-side.

Usage:
    .venv\\Scripts\\python.exe pp_backtest/cloud_subperiod_returns.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_portfolio_sim import compute_all_trades, build_portfolio

PANEL_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
OUT_DIR    = REPO / "data" / "research" / "hardening"

EXCLUDE = {"VPL"}
EX_VIN3 = {"VIC", "VHM", "VRE"}

CONFIGS = {
    "B_cloud20_100": dict(ema_fast=20, ema_slow=100, rank_mode="ema_dist"),
    "B_cloud21_55":  dict(ema_fast=21, ema_slow=55,  rank_mode="momentum"),
}

# GK audit yearly returns from phase7/phase8 CSVs (2018-2026)
GK_YEARLY = {
    "A_GK_only":      dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.1651,-0.0908, 0.2123, 0.9492,-0.3070,-0.0040, 0.0670, 0.3275,-0.0313])),
    "B_GK_VE":        dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.2386,-0.0437, 0.3422, 0.8382,-0.2919,-0.0209, 0.0944, 0.2187,-0.0720])),
    "C_GK_regime":    dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.0413, 0.0104, 0.3996, 0.1589, 0.0389, 0.0147,-0.0385, 0.3723, 0.0078])),
    "H_B05ff":        dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.0408, 0.0289, 0.3969, 0.6661, 0.0522,-0.0163,-0.1499, 0.2923, 0.0174])),
    "F07_H2":         dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.0304,-0.0129, 0.7705, 0.1869,-0.0188,-0.1140, 0.0373, 0.3717,-0.0464])),
    "C06_Donchian":   dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.2235,-0.1281, 0.4069, 0.2122,-0.2988,-0.1649, 0.0391, 0.5178,-0.0699])),
    "E_GK_TS20":      dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.1636,-0.1020, 0.2288, 0.2647,-0.3286,-0.0966,-0.1072, 0.7730, 0.1248])),
    "D_GK_VE+regime": dict(zip([2018,2019,2020,2021,2022,2023,2024,2025,2026],
                               [-0.0427, 0.0271, 0.3385, 0.1848, 0.0038,-0.0523,-0.1091, 0.3020,-0.0509])),
}


def yearly_returns(equity: pd.Series) -> dict[int, float]:
    """Extract calendar-year returns from equity curve."""
    out = {}
    equity = equity.sort_index()
    for yr, grp in equity.groupby(equity.index.year):
        if len(grp) < 2:
            continue
        ret = grp.iloc[-1] / grp.iloc[0] - 1.0
        out[yr] = float(ret)
    return out


def subperiod_cagr(yr_rets: dict[int, float], from_yr: int, to_yr: int) -> tuple[float, float]:
    """Compound yearly returns for a subperiod; return (total_ret, cagr)."""
    years = sorted(y for y in yr_rets if from_yr <= y <= to_yr)
    if not years:
        return float("nan"), float("nan")
    nav = 1.0
    for y in years:
        nav *= (1 + yr_rets[y])
    # approximate n_years from count (partial years accounted for by 2026 being partial)
    n_years = len(years) - (1 - 4/12) if to_yr == 2026 else len(years)
    c = nav ** (1 / max(n_years, 0.1)) - 1.0
    return nav - 1.0, c


def run_cloud_strategy(panel: pd.DataFrame, name: str, cfg: dict) -> dict[int, float]:
    all_syms = sorted(panel["symbol"].unique())
    universe = [s for s in all_syms if s not in EXCLUDE and s not in EX_VIN3]
    print(f"  Running {name} (universe={len(universe)} symbols)...", flush=True)

    trades_df = compute_all_trades(
        panel, universe,
        entry_type="cloud_only",
        ema_fast=cfg["ema_fast"],
        ema_slow=cfg["ema_slow"],
        exit_mode="partial_tp",
        max_hold=250,
        cost=0.004,
    )
    if trades_df.empty:
        print(f"    No trades found for {name}")
        return {}

    equity = build_portfolio(trades_df, max_positions=20, rank_mode=cfg["rank_mode"])
    yr = yearly_returns(equity)
    print(f"    Done: {len(trades_df)} trades, years {min(yr)}-{max(yr)}")
    return yr


def print_comparison(cloud_yearly: dict[str, dict], all_years: list[int]) -> None:
    all_strats = list(cloud_yearly.keys()) + list(GK_YEARLY.keys())
    yr_cols = [y for y in all_years if y >= 2016]

    # Header
    print(f"\n{'Strategy':<22}", end="")
    for y in yr_cols:
        lbl = f"{y}p" if y == 2026 else str(y)
        print(f"  {lbl:>6}", end="")
    print(f"  {'2016-26':>8}  {'2018-26':>8}  {'2023-26':>8}")
    print("-" * (22 + 8 * len(yr_cols) + 30))

    for name in all_strats:
        yr_rets = cloud_yearly.get(name) or GK_YEARLY.get(name, {})
        print(f"  {name:<20}", end="")
        for y in yr_cols:
            val = yr_rets.get(y)
            if val is None:
                print(f"  {'n/a':>6}", end="")
            else:
                print(f"  {val:>+6.1%}", end="")

        # Subperiod CAGRs
        _, c2016 = subperiod_cagr(yr_rets, 2016, 2026)
        _, c2018 = subperiod_cagr(yr_rets, 2018, 2026)
        _, c2023 = subperiod_cagr(yr_rets, 2023, 2026)

        def fmt(v):
            return f"{v:>+7.1%}" if not (isinstance(v, float) and np.isnan(v)) else f"  {'n/a':>6}"

        print(f"  {fmt(c2016)}  {fmt(c2018)}  {fmt(c2023)}")


def main():
    print("Loading panel...")
    panel = pd.read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])
    panel.sort_values(["symbol", "date"], inplace=True)

    cloud_yearly = {}
    for name, cfg in CONFIGS.items():
        cloud_yearly[name] = run_cloud_strategy(panel, name, cfg)

    # Save cloud yearly returns
    rows = []
    for name, yr_rets in cloud_yearly.items():
        row = {"strategy": name}
        row.update({str(y): v for y, v in yr_rets.items()})
        rows.append(row)
    out_csv = OUT_DIR / "cloud_yearly_returns.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"\nSaved: {out_csv}")

    all_years = sorted(set(
        list(cloud_yearly.get("B_cloud20_100", {}).keys()) +
        list(cloud_yearly.get("B_cloud21_55", {}).keys())
    ))

    print("\n" + "=" * 80)
    print("SUBPERIOD COMPARISON — Cloud strategies vs GK audit strategies")
    print("(2026 is partial through ~April; GK data starts 2018)")
    print("=" * 80)
    print_comparison(cloud_yearly, all_years)

    # Summary table: just the CAGR columns
    print("\n" + "=" * 60)
    print("CAGR SUMMARY BY PERIOD")
    print(f"{'Strategy':<22} {'2016-26':>8} {'2018-26':>8} {'2023-26':>8}")
    print("-" * 50)
    all_strats = list(cloud_yearly.keys()) + list(GK_YEARLY.keys())
    for name in all_strats:
        yr_rets = cloud_yearly.get(name) or GK_YEARLY.get(name, {})
        _, c2016 = subperiod_cagr(yr_rets, 2016, 2026)
        _, c2018 = subperiod_cagr(yr_rets, 2018, 2026)
        _, c2023 = subperiod_cagr(yr_rets, 2023, 2026)

        def fmt(v):
            return f"{v:>+7.1%}" if not (isinstance(v, float) and np.isnan(v)) else f"{'n/a':>8}"

        print(f"  {name:<20} {fmt(c2016)} {fmt(c2018)} {fmt(c2023)}")


if __name__ == "__main__":
    main()
