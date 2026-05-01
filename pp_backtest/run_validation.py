"""
Validation experiments: OOS eras, ranking ablation, capacity test.
Same strategy/config; no optimization. Reports portfolio stats and skip counts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

try:
    from pp_backtest.config import BacktestConfig
    from pp_backtest.data import fetch_ohlcv_fireant
    from pp_backtest.weekly_bars import daily_to_weekly
    from pp_backtest.signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        sma,
        ema,
    )
    from pp_backtest.market_regime import add_book_regime_columns, weekly_regime_from_daily
    from pp_backtest.eligibility import get_global_eligibility, EligibilityMap
    from pp_backtest.portfolio_sim import (
        PortfolioConfig,
        run_portfolio_backtest,
        DEFAULT_INITIAL_EQUITY_VND,
    )
except ImportError:
    from config import BacktestConfig
    from data import fetch_ohlcv_fireant
    from weekly_bars import daily_to_weekly
    from signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        sma,
        ema,
    )
    from market_regime import add_book_regime_columns, weekly_regime_from_daily
    from eligibility import get_global_eligibility, EligibilityMap
    from portfolio_sim import (
        PortfolioConfig,
        run_portfolio_backtest,
        DEFAULT_INITIAL_EQUITY_VND,
    )


def load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs(cfg: BacktestConfig, symbols: list[str]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    fetch = fetch_ohlcv_fireant
    try:
        market_daily = fetch("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            daily_df = fetch(sym, cfg.start, cfg.end)
        except Exception:
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < 11:
            continue
        c = wdf["close"].astype(float)
        wdf["ma10"] = sma(c, 10)
        wdf["ema21"] = ema(c, 21)
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf
    return weekly_dfs, market_weekly_regime


def get_eligibility_for_period(weekly_dfs: dict[str, pd.DataFrame]) -> EligibilityMap:
    try:
        return get_global_eligibility()
    except FileNotFoundError:
        rows = []
        for sym, wdf in weekly_dfs.items():
            wdf = wdf.copy()
            wdf["value"] = wdf["close"].astype(float) * wdf["volume"].astype(float)
            wdf["date"] = pd.to_datetime(wdf["date"])
            for i in range(len(wdf)):
                if i < 50:
                    continue
                row = wdf.iloc[i]
                dt = row["date"]
                tail50 = wdf.iloc[i - 50:i]
                tail20 = wdf.iloc[i - 20:i]
                adtv50 = float(tail50["value"].mean())
                adtv20 = float(tail20["value"].mean())
                eligible = adtv20 >= 2e9 and adtv50 >= 4e9
                rows.append({
                    "symbol": sym,
                    "month_start": dt,
                    "adtv20": adtv20,
                    "adtv50": adtv50,
                    "listed_flag": True,
                    "min_history_flag": True,
                    "active_flag": True,
                    "eligible_flag": eligible,
                })
        if not rows:
            raise FileNotFoundError("No eligibility rows from weekly_dfs")
        return EligibilityMap(df=pd.DataFrame(rows))


def default_config(initial_equity_vnd: float = DEFAULT_INITIAL_EQUITY_VND) -> PortfolioConfig:
    return PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=8,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=initial_equity_vnd,
        fee_bps_per_side=15.0,
    )


def stats_row(stats: dict, label: str = "") -> dict:
    return {
        "label": label,
        "CAGR": stats.get("cagr", np.nan),
        "MDD": stats.get("mdd", np.nan),
        "MAR": stats.get("mar", np.nan),
        "n_trades": stats.get("n_trades", 0),
        "final_equity": stats.get("final_equity", 0),
        "avg_heat": stats.get("avg_heat", np.nan),
        "avg_gross_exposure": stats.get("avg_gross_exposure", np.nan),
        "skipped_ineligible": stats.get("skipped_ineligible", 0),
        "skipped_regime_off": stats.get("skipped_regime_off", 0),
        "skipped_no_new_positions": stats.get("skipped_no_new_positions", 0),
        "skipped_max_positions": stats.get("skipped_max_positions", 0),
        "skipped_liquidity": stats.get("skipped_liquidity", 0),
    }


def print_table(rows: list[dict]) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    # Format for display
    for col in ["CAGR", "MDD", "avg_heat", "avg_gross_exposure"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.4f}" if isinstance(x, (int, float)) and not np.isnan(x) else str(x))
    if "MAR" in df.columns:
        df["MAR"] = df["MAR"].apply(lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and not np.isnan(x) else str(x))
    if "final_equity" in df.columns:
        df["final_equity"] = df["final_equity"].apply(lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) else str(x))
    print(df.to_string(index=False))


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", nargs="+", type=int, default=[1, 2, 3], help="Which sections to run: 1=OOS, 2=ranking, 3=capacity")
    ap.add_argument("--out", default=None, help="Write summary to this file (e.g. artifacts/validation_results.md)")
    args = ap.parse_args()
    run_s1 = 1 in args.sections
    run_s2 = 2 in args.sections
    run_s3 = 3 in args.sections
    out_path = Path(args.out) if args.out else (_REPO / "artifacts" / "validation_results.md")

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    symbols = load_universe(universe_path)
    print(f"[validation] universe size = {len(symbols)}\n")

    lines_out: list[str] = []

    # -------------------------------------------------------------------------
    # 1) Out-of-sample era validation
    # -------------------------------------------------------------------------
    oos_rows: list[dict] = []
    if run_s1:
        oos_periods = [
            ("2012-01-01", "2017-12-31", "2012-2017"),
            ("2022-01-01", "2024-12-31", "2022-2024"),
            ("2025-01-01", "2026-02-21", "2025-2026Q1"),
            ("2012-01-01", "2026-02-21", "full_sample"),
        ]
        print("=" * 80)
        print("1) OUT-OF-SAMPLE ERA VALIDATION (same config, default ranking)")
        print("=" * 80)
        for start, end, label in oos_periods:
            cfg = BacktestConfig()
            cfg.start = start
            cfg.end = end
            print(f"\n  [{label}] Building data ({start} to {end})...", flush=True)
            weekly_dfs, _ = build_weekly_dfs(cfg, symbols)
            if not weekly_dfs:
                print(f"  No data for {label}; skip.", flush=True)
                continue
            print(f"  [{label}] Building eligibility, running backtest...", flush=True)
            eligibility = get_eligibility_for_period(weekly_dfs)
            _, stats = run_portfolio_backtest(
                weekly_dfs,
                default_config(),
                eligibility=eligibility,
                ranking_mode="default",
            )
            oos_rows.append(stats_row(stats, label))
            print(f"  [{label}] CAGR={stats.get('cagr', np.nan):.2%} MDD={stats.get('mdd', np.nan):.2%} n_trades={stats.get('n_trades', 0)}", flush=True)
        if oos_rows:
            print_table(oos_rows)

    # -------------------------------------------------------------------------
    # 2) Ranking ablation (2018-2021 only)
    # -------------------------------------------------------------------------
    rank_rows: list[dict] = []
    weekly_dfs_s2s3 = None
    eligibility_s2s3 = None
    if run_s2 or run_s3:
        cfg = BacktestConfig()
        cfg.start = "2018-01-01"
        cfg.end = "2021-12-31"
        print("\n" + "=" * 80, flush=True)
        if run_s2:
            print("2) RANKING ABLATION (2018-01-01 to 2021-12-31)")
            print("=" * 80)
        print("\n  Building data for 2018-2021...", flush=True)
        weekly_dfs_s2s3, _ = build_weekly_dfs(cfg, symbols)
        if weekly_dfs_s2s3:
            eligibility_s2s3 = get_eligibility_for_period(weekly_dfs_s2s3)

    if run_s2 and weekly_dfs_s2s3 and eligibility_s2s3 is not None:
        ranking_modes = [
            ("default", "current ranking"),
            ("adtv20_only", "ADTV20 descending only"),
            ("tightness_only", "tightness_3w ascending only"),
            ("ext_only", "ext_vs_ma10 ascending only"),
            ("random", "random (seed=42)"),
        ]
        for mode, desc in ranking_modes:
            print(f"  Ranking: {desc}...", flush=True)
            _, stats = run_portfolio_backtest(
                weekly_dfs_s2s3,
                default_config(),
                eligibility=eligibility_s2s3,
                ranking_mode=mode,
            )
            rank_rows.append(stats_row(stats, desc))
        print_table(rank_rows)

    # -------------------------------------------------------------------------
    # 3) Capacity test (2018-2021, current ranking)
    # -------------------------------------------------------------------------
    cap_rows: list[dict] = []
    if run_s3:
        print("\n" + "=" * 80)
        print("3) CAPACITY TEST (2018-01-01 to 2021-12-31, current ranking)")
        print("=" * 80)
        if not weekly_dfs_s2s3 or eligibility_s2s3 is None:
            print("\n  Building data for 2018-2021...", flush=True)
            cfg_cap = BacktestConfig()
            cfg_cap.start = "2018-01-01"
            cfg_cap.end = "2021-12-31"
            weekly_dfs_cap, _ = build_weekly_dfs(cfg_cap, symbols)
            eligibility_cap = get_eligibility_for_period(weekly_dfs_cap) if weekly_dfs_cap else None
        else:
            weekly_dfs_cap = weekly_dfs_s2s3
            eligibility_cap = eligibility_s2s3
        if weekly_dfs_cap and eligibility_cap is not None:
            capacity_levels = [
                (1e9, "1bn VND"),
                (5e9, "5bn VND"),
                (10e9, "10bn VND"),
            ]
            for nav_vnd, label in capacity_levels:
                print(f"  Capacity {label}...", flush=True)
                config = default_config(initial_equity_vnd=nav_vnd)
                _, stats = run_portfolio_backtest(
                    weekly_dfs_cap,
                    config,
                    eligibility=eligibility_cap,
                    ranking_mode="default",
                )
                cap_rows.append(stats_row(stats, label))
            print_table(cap_rows)
        else:
            print("  No data; skip capacity test.", flush=True)

    # Write summary to file
    if out_path and (oos_rows or rank_rows or cap_rows):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("# Validation Results\n\n")
            if oos_rows:
                f.write("## 1) Out-of-sample era validation\n\n```\n")
                f.write(pd.DataFrame(oos_rows).to_string(index=False) + "\n```\n\n")
            if rank_rows:
                f.write("## 2) Ranking ablation (2018-2021)\n\n```\n")
                f.write(pd.DataFrame(rank_rows).to_string(index=False) + "\n```\n\n")
            if cap_rows:
                f.write("## 3) Capacity test (2018-2021)\n\n```\n")
                f.write(pd.DataFrame(cap_rows).to_string(index=False) + "\n```\n\n")
        print(f"\n[validation] summary written to {out_path}")

    print("\n[validation] done.")


if __name__ == "__main__":
    main()
