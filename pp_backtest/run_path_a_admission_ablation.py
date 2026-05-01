"""
Path A admission/ranking ablation.
- Keeps current Path A baseline signal, regime, PIT, fees, sizing, execution.
- Varies: ranking rule (6 modes) and max_positions (8, 10, 12).
- Outputs: path_a_admission_ablation.csv, .md, path_a_admission_summary.md.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

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

RANKING_MODES = [
    "current",
    "extension_first",
    "tightness_first",
    "volume_thrust_first",
    "liquidity_first",
    "simple_composite",
]
MAX_POSITIONS_LIST = [8, 10, 12]
PERIODS: List[Tuple[str, str, str]] = [
    ("2018-01-01", "2021-12-31", "2018-2021"),
    ("2024-01-01", "2026-02-21", "2024-2026Q1"),
    ("2022-01-01", "2024-12-31", "2022-2024"),
    ("2012-01-01", "2026-02-21", "full_sample"),
]

RESULTS_COLUMNS = [
    "ranking_mode", "max_positions", "period", "start", "end",
    "cagr", "mdd", "mar", "n_trades", "trades_per_month", "final_equity",
    "avg_heat", "avg_gross_exposure",
    "post_regime_candidates", "actual_entries", "chosen_rate", "rejected_max_positions",
    "skipped_ineligible", "skipped_regime_off", "skipped_no_new_positions", "skipped_liquidity",
]


def load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs(start: str, end: str, symbols: list[str]) -> dict[str, pd.DataFrame]:
    cfg = BacktestConfig()
    cfg.start = start
    cfg.end = end
    try:
        market_daily = fetch_ohlcv_fireant("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            daily_df = fetch_ohlcv_fireant(sym, cfg.start, cfg.end)
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


def _get_eligibility(weekly_dfs: dict[str, pd.DataFrame]) -> EligibilityMap:
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
                rows.append({
                    "symbol": sym,
                    "month_start": dt,
                    "adtv20": adtv20,
                    "adtv50": adtv50,
                    "listed_flag": True,
                    "min_history_flag": True,
                    "active_flag": True,
                    "eligible_flag": adtv20 >= 2e9 and adtv50 >= 4e9,
                })
        return EligibilityMap(df=pd.DataFrame(rows))


def run_one(
    weekly_dfs: dict[str, pd.DataFrame],
    eligibility: EligibilityMap,
    ranking_mode: str,
    max_positions: int,
    period_label: str,
    start: str,
    end: str,
) -> dict:
    config = PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=max_positions,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
        fee_bps_per_side=15.0,
    )
    trades_df, stats = run_portfolio_backtest(
        weekly_dfs, config, eligibility=eligibility, ranking_mode=ranking_mode
    )
    period_days = (pd.to_datetime(end) - pd.to_datetime(start)).days
    period_months = max(1, period_days / 30.0)
    n_trades = len(trades_df)
    trades_per_month = n_trades / period_months if period_months else np.nan
    return {
        "ranking_mode": ranking_mode,
        "max_positions": max_positions,
        "period": period_label,
        "start": start,
        "end": end,
        "cagr": stats.get("cagr", np.nan),
        "mdd": stats.get("mdd", np.nan),
        "mar": stats.get("mar", np.nan),
        "n_trades": n_trades,
        "trades_per_month": trades_per_month,
        "final_equity": stats.get("final_equity", np.nan),
        "avg_heat": stats.get("avg_heat", np.nan),
        "avg_gross_exposure": stats.get("avg_gross_exposure", np.nan),
        "post_regime_candidates": stats.get("post_regime_candidates", 0),
        "actual_entries": stats.get("actual_entries", n_trades),
        "chosen_rate": stats.get("chosen_rate", np.nan),
        "rejected_max_positions": stats.get("rejected_max_positions", 0),
        "skipped_ineligible": stats.get("skipped_ineligible", 0),
        "skipped_regime_off": stats.get("skipped_regime_off", 0),
        "skipped_no_new_positions": stats.get("skipped_no_new_positions", 0),
        "skipped_liquidity": stats.get("skipped_liquidity", 0),
    }


def _robustness_score(row: pd.Series) -> float:
    mar = row.get("mar")
    if pd.isna(mar):
        return -1e9
    n_trades = row.get("n_trades", 0) or 0
    penalty_neg = 0.5 if mar < 0 else 0.0
    penalty_trades = (100 - n_trades) / 100.0 if n_trades < 100 else 0.0
    return float(mar) - penalty_neg - penalty_trades


def _write_artifacts(df: pd.DataFrame, baseline_mar: dict) -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "path_a_admission_ablation.csv"
    md_path = artifacts_dir / "path_a_admission_ablation.md"
    summary_path = artifacts_dir / "path_a_admission_summary.md"

    df.to_csv(csv_path, index=False)

    def table_from(tdf: pd.DataFrame, cols: List[str]) -> str:
        cols = [c for c in cols if c in tdf.columns]
        if not cols or tdf.empty:
            return ""
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for _, row in tdf[cols].iterrows():
            fmt = [f"{row[c]:.4g}" if isinstance(row[c], (int, float)) and not isinstance(row[c], bool) else str(row[c]) for c in cols]
            lines.append("| " + " | ".join(fmt) + " |")
        return "\n".join(lines)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Admission / Ranking Ablation\n\n")
        f.write("Ranking modes: current, extension_first, tightness_first, volume_thrust_first, liquidity_first, simple_composite.\n")
        f.write("max_positions: 8, 10, 12.\n\n")
        for period in ["2018-2021", "2024-2026Q1", "2022-2024", "full_sample"]:
            sub = df[df["period"] == period]
            if sub.empty:
                continue
            sub = sub.sort_values("mar", ascending=False)
            f.write(f"## Top 10 by MAR — {period}\n\n")
            f.write(table_from(sub.head(10), ["ranking_mode", "max_positions", "mar", "cagr", "mdd", "n_trades", "chosen_rate", "rejected_max_positions"]) + "\n\n")
        by_config = df.groupby(["ranking_mode", "max_positions"]).agg(
            mar=("mar", "mean"),
            n_trades=("n_trades", "sum"),
            chosen_rate=("chosen_rate", "mean"),
            rejected_max_positions=("rejected_max_positions", "sum"),
        ).reset_index()
        by_config["robustness"] = by_config.apply(lambda r: _robustness_score(r), axis=1)
        by_config = by_config.sort_values("robustness", ascending=False)
        f.write("## Top 10 by robustness (avg MAR − penalties)\n\n")
        f.write(table_from(by_config.head(10), ["ranking_mode", "max_positions", "robustness", "mar", "n_trades", "chosen_rate"]) + "\n\n")
        f.write("## Ranking vs max_positions\n\n")
        f.write("Does ranking matter more than max_positions? See summary.\n\n")
        f.write("## chosen_rate by max_positions\n\n")
        by_mp = df.groupby("max_positions").agg(
            chosen_rate=("chosen_rate", "mean"),
            mar=("mar", "mean"),
        ).reset_index()
        f.write(table_from(by_mp, ["max_positions", "chosen_rate", "mar"]) + "\n")

    # Summary
    by_config = df.groupby(["ranking_mode", "max_positions"]).agg(
        mar=("mar", "mean"),
        n_trades=("n_trades", "sum"),
    ).reset_index()
    by_config["robustness"] = by_config.apply(_robustness_score, axis=1)
    best_robust = by_config.loc[by_config["robustness"].idxmax()]
    d18 = df[df["period"] == "2018-2021"]
    best_2018_row = d18.loc[d18["mar"].idxmax()] if not d18.empty and d18["mar"].notna().any() else None
    d24 = df[df["period"] == "2024-2026Q1"]
    best_2024 = d24.loc[d24["mar"].idxmax()] if not d24.empty and d24["mar"].notna().any() else None
    baseline_full = baseline_mar.get("full_sample")
    beats_baseline = False
    if baseline_full is not None and not df[df["period"] == "full_sample"].empty:
        best_full_mar = df[df["period"] == "full_sample"]["mar"].max()
        beats_baseline = best_full_mar > baseline_full
    ranking_matters = by_config.groupby("ranking_mode")["mar"].mean().std() > 0.01 if len(by_config) else False
    mp_matters = df.groupby("max_positions")["chosen_rate"].mean()
    mp_10_12_worth = (mp_matters.get(10, 0) or 0) > (mp_matters.get(8, 0) or 0) or (mp_matters.get(12, 0) or 0) > (mp_matters.get(8, 0) or 0)

    verdict = "keep baseline as-is"
    if beats_baseline:
        if best_robust["max_positions"] != 8 and best_robust["ranking_mode"] != "current":
            verdict = "change both ranking and max_positions"
        elif best_robust["max_positions"] != 8:
            verdict = "change max_positions only"
        elif best_robust["ranking_mode"] != "current":
            verdict = "change ranking only"
    elif best_robust["ranking_mode"] != "current" and ranking_matters:
        verdict = "change ranking only (no MAR gain but different admission quality)"
    elif best_robust["max_positions"] != 8 and mp_10_12_worth:
        verdict = "change max_positions only (higher chosen_rate)"

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Path A Admission Ablation — Summary\n\n")
        f.write(f"- **Best by robustness:** ranking_mode={best_robust['ranking_mode']}, max_positions={int(best_robust['max_positions'])}\n")
        if best_2018_row is not None:
            f.write(f"- **Best for 2018-2021:** ranking_mode={best_2018_row['ranking_mode']}, max_positions={int(best_2018_row['max_positions'])}\n")
        if best_2024 is not None:
            f.write(f"- **Best for 2024-2026Q1:** ranking_mode={best_2024['ranking_mode']}, max_positions={int(best_2024['max_positions'])}\n")
        f.write("- **Ranking vs max_positions:** " + ("Ranking changes matter more." if ranking_matters else "max_positions changes matter more or similar.") + "\n")
        f.write("- **max_positions 10 or 12 worth it?** " + ("Yes (higher chosen_rate or MAR)." if mp_10_12_worth else "No material gain.") + "\n")
        f.write(f"- **Any config beats current baseline full-sample MAR?** " + ("Yes." if beats_baseline else "No.") + "\n")
        f.write(f"- **Verdict:** {verdict}\n")


def main() -> None:
    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)
    if not symbols:
        print("[path_a_admission_ablation] No symbols; aborting.")
        return

    baseline_mar = {}
    comp_path = _REPO / "artifacts" / "path_a_vs_path_b_comparison.csv"
    if comp_path.exists():
        comp = pd.read_csv(comp_path)
        for _, r in comp.iterrows():
            p = r.get("period")
            if p and pd.notna(r.get("mar_a")):
                baseline_mar[str(p)] = float(r["mar_a"])

    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "path_a_admission_ablation.csv"
    rows: list[dict] = []
    for start, end, period_label in PERIODS:
        print(f"[path_a_admission_ablation] Building data {period_label}...", flush=True)
        weekly_dfs = build_weekly_dfs(start, end, symbols)
        if not weekly_dfs:
            print(f"  No data for {period_label}; skip.")
            continue
        eligibility = _get_eligibility(weekly_dfs)
        print(f"  {len(weekly_dfs)} symbols.", flush=True)
        period_rows: list[dict] = []
        for ranking_mode in RANKING_MODES:
            for max_positions in MAX_POSITIONS_LIST:
                row = run_one(
                    weekly_dfs, eligibility,
                    ranking_mode, max_positions,
                    period_label, start, end,
                )
                rows.append(row)
                period_rows.append(row)
                print(f"  {ranking_mode} mp={max_positions} {period_label} MAR={row['mar']:.4f} n_trades={row['n_trades']}", flush=True)
        if period_rows:
            pd.DataFrame(period_rows).to_csv(csv_path, mode="a", header=not csv_path.exists(), index=False)

    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(csv_path, index=False)
    _write_artifacts(df, baseline_mar)
    print(f"[path_a_admission_ablation] Wrote artifacts/path_a_admission_ablation.csv, .md, path_a_admission_summary.md", flush=True)


if __name__ == "__main__":
    main()
