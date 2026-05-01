"""
Next research phase: walk-forward ranking validation, filter ablation, capacity stress.
One command runs all three parts and writes artifacts + next_phase_summary.md.
No FA, no signal changes, no large grid.
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
    from pp_backtest.signals_weekly import weekly_pocket_pivot_signal, weekly_exit_ema21_ma50, sma, ema
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
    from signals_weekly import weekly_pocket_pivot_signal, weekly_exit_ema21_ma50, sma, ema
    from market_regime import add_book_regime_columns, weekly_regime_from_daily
    from eligibility import get_global_eligibility, EligibilityMap
    from portfolio_sim import PortfolioConfig, run_portfolio_backtest, DEFAULT_INITIAL_EQUITY_VND


# Rolling: train=3y, test=1y, step=1y → test windows 2015, 2016, ..., 2023
TEST_WINDOW_YEARS = list(range(2015, 2024))  # 2015-01-01 to 2015-12-31, ...

RANKING_MODES = ["current", "extension_only", "tightness_only", "random_seed_42"]

FILTER_CONFIGS = [
    ("baseline", None, None, None),
    ("base_depth_30", 0.30, None, None),
    ("tightness_08", None, 0.08, None),
    ("ext_12", None, None, 0.12),
    ("all_three", 0.30, 0.08, 0.12),
]

CAPACITY_NAV_BN = [1, 5, 10, 20, 50, 100]


def load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs(start: str, end: str, symbols: list[str]) -> dict[str, pd.DataFrame]:
    try:
        market_daily = fetch_ohlcv_fireant("VN30", start, end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])
    weekly_dfs = {}
    for sym in symbols:
        try:
            daily_df = fetch_ohlcv_fireant(sym, start, end)
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
    return weekly_dfs


def get_eligibility(weekly_dfs: dict[str, pd.DataFrame]) -> EligibilityMap:
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
                tail50 = wdf.iloc[i - 50 : i]
                tail20 = wdf.iloc[i - 20 : i]
                adtv50 = float(tail50["value"].mean())
                adtv20 = float(tail20["value"].mean())
                eligible = adtv20 >= 2e9 and adtv50 >= 4e9
                rows.append({
                    "symbol": sym, "month_start": dt, "adtv20": adtv20, "adtv50": adtv50,
                    "listed_flag": True, "min_history_flag": True, "active_flag": True, "eligible_flag": eligible,
                })
        if not rows:
            raise FileNotFoundError("No eligibility from weekly_dfs")
        return EligibilityMap(df=pd.DataFrame(rows))


def default_config(
    initial_equity_vnd: float = DEFAULT_INITIAL_EQUITY_VND,
    base_depth_max: float | None = None,
    tightness_max: float | None = None,
    ext_max: float | None = None,
) -> PortfolioConfig:
    return PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=8,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=initial_equity_vnd,
        fee_bps_per_side=15.0,
        base_depth_pct_max=base_depth_max,
        tightness_3w_pct_max=tightness_max,
        ext_vs_ma10_max=ext_max,
    )


def _stats_row(stats: dict, **extra) -> dict:
    row = {
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
    if "avg_position_size_vnd" in stats:
        row["avg_position_size_vnd"] = stats["avg_position_size_vnd"]
    if "max_position_size_vnd" in stats:
        row["max_position_size_vnd"] = stats["max_position_size_vnd"]
    row.update(extra)
    return row


def run_part_a(artifacts_dir: Path, symbols: list[str]) -> pd.DataFrame:
    """Walk-forward: rolling test windows × ranking modes."""
    print("\n--- PART A: Walk-forward ranking validation ---", flush=True)
    rows = []
    for year in TEST_WINDOW_YEARS:
        test_start = f"{year}-01-01"
        test_end = f"{year}-12-31"
        print(f"  Window {test_start} to {test_end}...", flush=True)
        weekly_dfs = build_weekly_dfs(test_start, test_end, symbols)
        if not weekly_dfs:
            continue
        eligibility = get_eligibility(weekly_dfs)
        config = default_config(initial_equity_vnd=1_000_000_000)
        for mode in RANKING_MODES:
            _, stats = run_portfolio_backtest(weekly_dfs, config, eligibility=eligibility, ranking_mode=mode)
            rows.append(_stats_row(stats, test_start=test_start, test_end=test_end, ranking_mode=mode))
    df = pd.DataFrame(rows)
    df.to_csv(artifacts_dir / "walkforward_results.csv", index=False)

    # Summary for md
    with open(artifacts_dir / "walkforward_results.md", "w", encoding="utf-8") as f:
        f.write("# Walk-Forward Ranking Validation\n\n")
        f.write("Test window = 1 year; train = 3 years (not used for training, rolling test only).\n\n")
        f.write("## Raw results\n\n")
        f.write(df.to_string(index=False) + "\n\n## Summary by ranking_mode\n\n")
        for mode in RANKING_MODES:
            sub = df[df["ranking_mode"] == mode]
            if sub.empty:
                continue
            mar = pd.to_numeric(sub["MAR"], errors="coerce")
            mar_valid = mar.dropna()
            avg_mar = mar_valid.mean() if len(mar_valid) else np.nan
            med_mar = mar_valid.median() if len(mar_valid) else np.nan
            winning = (mar_valid > 0).sum() if len(mar_valid) else 0
            losing = (mar_valid <= 0).sum() if len(mar_valid) else 0
            f.write(f"- **{mode}**: avg MAR = {avg_mar:.3f}, median MAR = {med_mar:.3f}, winning windows = {winning}, losing = {losing}\n")
        f.write("\nBest by median MAR: ")
        medians = df.groupby("ranking_mode")["MAR"].apply(lambda s: pd.to_numeric(s, errors="coerce").median())
        if medians.notna().any():
            best = medians.idxmax()
            worst = medians.idxmin()
            f.write(f"{best}. Worst: {worst}.\n")
    return df


def run_part_b(artifacts_dir: Path, symbols: list[str], best_ranking: str) -> pd.DataFrame:
    """Filter ablation: periods × filter configs, ranking = best_ranking."""
    print("\n--- PART B: Filter ablation ---", flush=True)
    periods = [
        ("2018-01-01", "2021-12-31", "2018-2021"),
        ("2022-01-01", "2024-12-31", "2022-2024"),
        ("2012-01-01", "2024-12-31", "full_sample"),
    ]
    rows = []
    for start, end, period_label in periods:
        print(f"  Period {period_label}...", flush=True)
        weekly_dfs = build_weekly_dfs(start, end, symbols)
        if not weekly_dfs:
            continue
        eligibility = get_eligibility(weekly_dfs)
        for filter_name, bd, tight, ext in FILTER_CONFIGS:
            config = default_config(
                initial_equity_vnd=1_000_000_000,
                base_depth_max=bd,
                tightness_max=tight,
                ext_max=ext,
            )
            _, stats = run_portfolio_backtest(weekly_dfs, config, eligibility=eligibility, ranking_mode=best_ranking)
            rows.append(_stats_row(stats, filter_name=filter_name, period=period_label))
    df = pd.DataFrame(rows)
    df.to_csv(artifacts_dir / "filter_ablation_results.csv", index=False)

    with open(artifacts_dir / "filter_ablation_results.md", "w", encoding="utf-8") as f:
        f.write("# Filter Ablation\n\n")
        f.write(f"Ranking mode: {best_ranking}. Periods: 2018-2021, 2022-2024, full sample.\n\n")
        f.write("## Raw results\n\n")
        f.write(df.to_string(index=False) + "\n\n## Notes\n\n")
        ext_mar = df[(df["filter_name"] == "ext_12")]["MAR"]
        base_mar = df[(df["filter_name"] == "baseline")]["MAR"]
        if len(ext_mar) and len(base_mar):
            f.write(f"- Extension filter (ext_12) vs baseline MAR: improvement consistent = {ext_mar.mean() > base_mar.mean()}.\n")
        all_three = df[df["filter_name"] == "all_three"]
        if not all_three.empty:
            nt = all_three["n_trades"].sum()
            f.write(f"- All-three filter: total n_trades = {nt}; over-filtering = {nt < 20}.\n")
        by_filter = df.groupby("filter_name").agg({"MAR": "mean", "n_trades": "sum"}).reset_index()
        by_filter["MAR"] = pd.to_numeric(by_filter["MAR"], errors="coerce")
        best_row = by_filter.loc[by_filter["MAR"].idxmax()] if by_filter["MAR"].notna().any() else None
        if best_row is not None:
            f.write(f"- Best trade-off (by avg MAR): {best_row['filter_name']} (avg MAR {best_row['MAR']:.3f}, n_trades {best_row['n_trades']}).\n")
    return df


def run_part_c(artifacts_dir: Path, symbols: list[str], best_ranking: str) -> pd.DataFrame:
    """Capacity stress: 1,5,10,20,50,100 bn on 2018-2021."""
    print("\n--- PART C: Extended capacity stress ---", flush=True)
    start, end = "2018-01-01", "2021-12-31"
    weekly_dfs = build_weekly_dfs(start, end, symbols)
    if not weekly_dfs:
        return pd.DataFrame()
    eligibility = get_eligibility(weekly_dfs)
    rows = []
    for bn in CAPACITY_NAV_BN:
        nav_vnd = int(bn * 1e9)
        print(f"  NAV {bn}bn VND...", flush=True)
        config = default_config(initial_equity_vnd=nav_vnd)
        _, stats = run_portfolio_backtest(weekly_dfs, config, eligibility=eligibility, ranking_mode=best_ranking)
        rows.append(_stats_row(stats, nav_bn=bn, initial_equity_vnd=nav_vnd))
    df = pd.DataFrame(rows)
    df.to_csv(artifacts_dir / "capacity_stress_results.csv", index=False)

    with open(artifacts_dir / "capacity_stress_results.md", "w", encoding="utf-8") as f:
        f.write("# Extended Capacity Stress\n\n")
        f.write(f"Period: 2018-01-01 to 2021-12-31. Ranking: {best_ranking}.\n\n")
        f.write("## Raw results\n\n")
        f.write(df.to_string(index=False) + "\n\n## Notes\n\n")
        sl = df["skipped_liquidity"]
        first_material = None
        for i, r in df.iterrows():
            if r["skipped_liquidity"] > 10:
                first_material = r["nav_bn"]
                break
        f.write(f"- First NAV where skipped_liquidity becomes material (>10): {first_material}bn VND.\n")
        cagr = pd.to_numeric(df["CAGR"], errors="coerce")
        mar = pd.to_numeric(df["MAR"], errors="coerce")
        if len(cagr) >= 3 and cagr.notna().all():
            smooth = not (cagr.diff().abs().max() > 0.15)
            f.write(f"- CAGR/MAR degrades smoothly (no single drop >15pp): {smooth}.\n")
        f.write("- Safe practical NAV range (under current execution): suggest up to 10–20bn if skipped_liquidity still 0; cap at level where skipped_liquidity first rises.\n")
    return df


def write_next_phase_summary(
    artifacts_dir: Path,
    wf_df: pd.DataFrame,
    filter_df: pd.DataFrame,
    cap_df: pd.DataFrame,
    best_ranking: str,
) -> None:
    with open(artifacts_dir / "next_phase_summary.md", "w", encoding="utf-8") as f:
        f.write("# Next Phase Summary\n\n")
        f.write("## 1. Best ranking by robustness\n\n")
        f.write(f"From walk-forward: **{best_ranking}** (chosen by median MAR across test windows).\n\n")
        f.write("## 2. Best simple filter\n\n")
        if not filter_df.empty and "filter_name" in filter_df.columns:
            by_f = filter_df.groupby("filter_name")["MAR"].apply(lambda s: pd.to_numeric(s, errors="coerce").mean())
            if by_f.notna().any():
                best_f = by_f.idxmax()
                f.write(f"From filter ablation: **{best_f}** (best avg MAR across periods).\n\n")
            else:
                f.write("Inconclusive from ablation.\n\n")
        else:
            f.write("N/A.\n\n")
        f.write("## 3. Safe NAV range\n\n")
        if not cap_df.empty and "skipped_liquidity" in cap_df.columns:
            first_bind = None
            for _, r in cap_df.iterrows():
                if r["skipped_liquidity"] > 10:
                    first_bind = r.get("nav_bn", None)
                    break
            if first_bind is not None:
                f.write(f"Liquidity starts binding above **{first_bind}bn VND**. Safe range: up to that level.\n\n")
            else:
                f.write("skipped_liquidity did not exceed 10 up to 100bn; safe range under current assumptions: up to 20–50bn (conservative).\n\n")
        else:
            f.write("N/A.\n\n")
        f.write("## 4. Recommendation for next research step\n\n")
        f.write("- Lock in best ranking and best filter (if not over-filtering).\n")
        f.write("- Consider paper trading or small live pilot at NAV within safe range.\n")
        f.write("- Optionally: add sector caps or regime-based exposure in a later phase; no FA yet.\n")


def main() -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    symbols = load_universe(universe_path)
    print(f"[walkforward_validation] universe = {len(symbols)} symbols", flush=True)

    wf_df = run_part_a(artifacts_dir, symbols)
    if wf_df.empty:
        best_ranking = "extension_only"
        print("  No walk-forward data; using extension_only as best ranking.", flush=True)
    else:
        medians = wf_df.groupby("ranking_mode")["MAR"].apply(lambda s: pd.to_numeric(s, errors="coerce").median())
        best_ranking = medians.idxmax() if medians.notna().any() else "extension_only"
        print(f"  Best ranking by median MAR: {best_ranking}", flush=True)

    filter_df = run_part_b(artifacts_dir, symbols, best_ranking)
    cap_df = run_part_c(artifacts_dir, symbols, best_ranking)
    write_next_phase_summary(artifacts_dir, wf_df, filter_df, cap_df, best_ranking)

    print(f"\nWrote {artifacts_dir / 'walkforward_results.csv'}, walkforward_results.md", flush=True)
    print(f"Wrote {artifacts_dir / 'filter_ablation_results.csv'}, filter_ablation_results.md", flush=True)
    print(f"Wrote {artifacts_dir / 'capacity_stress_results.csv'}, capacity_stress_results.md", flush=True)
    print(f"Wrote {artifacts_dir / 'next_phase_summary.md'}", flush=True)


if __name__ == "__main__":
    main()
