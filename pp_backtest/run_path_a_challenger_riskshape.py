"""
Challenger-only risk-shaping test.
- ranking_mode = simple_composite (fixed).
- Vary: max_positions (8, 10, 12), max_heat (0.03, 0.04), risk_per_trade (0.004, 0.005).
- Periods: 2024-2026Q1, 2022-2024, full sample.
- Outputs: path_a_challenger_riskshape.csv, .md, path_a_challenger_riskshape_summary.md
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

from pp_backtest.run_weekly_ema21_portfolio import build_weekly_dfs, load_universe
from pp_backtest.config import BacktestConfig
from pp_backtest.eligibility import get_global_eligibility
from pp_backtest.eligibility import EligibilityMap
from pp_backtest.portfolio_sim import (
    PortfolioConfig,
    run_portfolio_backtest,
    DEFAULT_INITIAL_EQUITY_VND,
)

RANKING_MODE = "simple_composite"
MAX_POSITIONS_LIST = [8, 10, 12]
MAX_HEAT_LIST = [0.03, 0.04]
RISK_PER_TRADE_LIST = [0.004, 0.005]

PERIODS: List[Tuple[str, str, str]] = [
    ("2024-01-01", "2026-02-21", "2024-2026Q1"),
    ("2022-01-01", "2024-12-31", "2022-2024"),
    ("2012-01-01", "2026-02-21", "full_sample"),
]
# Set SKIP_FULL_SAMPLE=1 to run only 2024-2026 and 2022-2024 (faster).
SKIP_FULL_SAMPLE = bool(int(__import__("os").environ.get("SKIP_FULL_SAMPLE", "0")))


def _get_eligibility(weekly_dfs: dict) -> EligibilityMap:
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


def main() -> None:
    periods = [p for p in PERIODS if p[2] != "full_sample" or not SKIP_FULL_SAMPLE]
    if SKIP_FULL_SAMPLE:
        print("[challenger_riskshape] SKIP_FULL_SAMPLE=1: running 2024-2026Q1 and 2022-2024 only.", flush=True)
    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)
    if not symbols:
        print("[challenger_riskshape] No symbols; aborting.")
        return

    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "path_a_challenger_riskshape.csv"
    rows: List[dict] = []
    for start, end, period_label in periods:
        cfg = BacktestConfig()
        cfg.start = start
        cfg.end = end
        print(f"[challenger_riskshape] Building data {period_label}...", flush=True)
        weekly_dfs, _ = build_weekly_dfs(cfg, symbols)
        if not weekly_dfs:
            print(f"  No data for {period_label}; skip.")
            continue
        eligibility = _get_eligibility(weekly_dfs)
        period_days = (pd.to_datetime(end) - pd.to_datetime(start)).days
        period_months = max(1, period_days / 30.0)

        for max_positions in MAX_POSITIONS_LIST:
            for max_heat in MAX_HEAT_LIST:
                for risk_per_trade in RISK_PER_TRADE_LIST:
                    pconfig = PortfolioConfig(
                        risk_per_trade=risk_per_trade,
                        max_heat=max_heat,
                        max_positions=max_positions,
                        max_symbol_weight=0.10,
                        liquidity_participation_cap=0.05,
                        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
                        fee_bps_per_side=15.0,
                    )
                    trades_df, stats = run_portfolio_backtest(
                        weekly_dfs, pconfig, eligibility=eligibility, ranking_mode=RANKING_MODE
                    )
                    n_trades = len(trades_df)
                    trades_per_month = n_trades / period_months if period_months else np.nan
                    row = {
                        "max_positions": max_positions,
                        "max_heat": max_heat,
                        "risk_per_trade": risk_per_trade,
                        "period": period_label,
                        "start": start,
                        "end": end,
                        "cagr": stats.get("cagr", np.nan),
                        "mdd": stats.get("mdd", np.nan),
                        "mar": stats.get("mar", np.nan),
                        "n_trades": n_trades,
                        "trades_per_month": trades_per_month,
                        "chosen_rate": stats.get("chosen_rate", np.nan),
                        "rejected_max_positions": stats.get("rejected_max_positions", 0),
                        "avg_heat": stats.get("avg_heat", np.nan),
                        "avg_gross_exposure": stats.get("avg_gross_exposure", np.nan),
                    }
                    rows.append(row)
                    print(
                        f"  mp={max_positions} heat={max_heat} rpt={risk_per_trade} {period_label} "
                        f"MAR={stats.get('mar', np.nan):.4f} MDD={stats.get('mdd', np.nan):.2%} n_trades={n_trades}",
                        flush=True,
                    )
        if rows:
            pd.DataFrame(rows).to_csv(csv_path, index=False)

    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(csv_path, index=False)
    md_path = artifacts_dir / "path_a_challenger_riskshape.md"
    summary_path = artifacts_dir / "path_a_challenger_riskshape_summary.md"

    df.to_csv(csv_path, index=False)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Challenger Risk-Shaping Test\n\n")
        f.write("ranking_mode=simple_composite only. Grid: max_positions ∈ {8,10,12}, max_heat ∈ {0.03,0.04}, risk_per_trade ∈ {0.004,0.005}.\n\n")
        for period in ["2024-2026Q1", "2022-2024", "full_sample"]:
            sub = df[df["period"] == period].sort_values("mar", ascending=False)
            if sub.empty:
                continue
            f.write(f"## Top 10 by MAR — {period}\n\n")
            f.write("| max_positions | max_heat | risk_per_trade | MAR | MDD | CAGR | n_trades | chosen_rate | rejected_max_pos |\n")
            f.write("|---------------|----------|----------------|-----|-----|------|----------|-------------|------------------|\n")
            for _, r in sub.head(10).iterrows():
                f.write(f"| {int(r['max_positions'])} | {r['max_heat']} | {r['risk_per_trade']} | {r['mar']:.4f} | {r['mdd']:.2%} | {r['cagr']:.2%} | {int(r['n_trades'])} | {r['chosen_rate']:.4g} | {int(r['rejected_max_positions'])} |\n")
            f.write("\n")

    # Summary: compare to current Challenger (12, 0.04, 0.005)
    baseline = df[(df["max_positions"] == 12) & (df["max_heat"] == 0.04) & (df["risk_per_trade"] == 0.005)]
    baseline_full = baseline[baseline["period"] == "full_sample"]
    baseline_mdd_full = baseline_full["mdd"].iloc[0] if not baseline_full.empty else np.nan
    baseline_mar_full = baseline_full["mar"].iloc[0] if not baseline_full.empty else np.nan

    baseline_mdd_val = float(baseline_mdd_full) if pd.notna(baseline_mdd_full) else -0.30
    full_df = df[df["period"] == "full_sample"]
    if not full_df.empty and full_df["mar"].notna().any():
        # Best by MAR
        best_mar_row = full_df.loc[full_df["mar"].idxmax()]
        # Best by MAR among configs with MDD better (less deep) than baseline by at least 2 ppts
        better_mdd = full_df[full_df["mdd"].fillna(-1) > baseline_mdd_val + 0.02]  # MDD less deep (e.g. -18% vs -25%)
        if not better_mdd.empty:
            best_mar_better_mdd = better_mdd.loc[better_mdd["mar"].idxmax()]
        else:
            best_mar_better_mdd = None
    else:
        best_mar_row = None
        best_mar_better_mdd = None

    can_keep_behavior_lower_mdd = best_mar_better_mdd is not None and (pd.isna(baseline_mar_full) or float(best_mar_better_mdd["mar"]) >= float(baseline_mar_full) * 0.8)
    best_config = best_mar_row
    if best_config is not None:
        best_config_str = f"max_positions={int(best_config['max_positions'])}, max_heat={best_config['max_heat']}, risk_per_trade={best_config['risk_per_trade']}"
    else:
        best_config_str = "N/A"
    satisfies_spirit = (
        best_mar_better_mdd is not None
        and float(best_mar_better_mdd.get("mdd", -0.5)) > (baseline_mdd_val + 0.05)
        and (pd.isna(baseline_mar_full) or float(best_mar_better_mdd.get("mar", 0)) >= float(baseline_mar_full) * 0.9)
    )
    stay_under_watch = not satisfies_spirit

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Path A Challenger Risk-Shaping — Summary\n\n")
        f.write("## 1. Can Challenger keep better recent/rolling behavior with lower MDD?\n\n")
        f.write("Yes.\n" if can_keep_behavior_lower_mdd else "Partially: some risk-shaped configs reduce MDD but may give up some MAR.\n")
        f.write("\n## 2. Best risk-shaped Challenger config\n\n")
        f.write(f"- **Best by full-sample MAR:** {best_config_str}\n")
        if best_mar_better_mdd is not None:
            f.write(f"- **Best MAR among configs with materially better MDD:** max_positions={int(best_mar_better_mdd['max_positions'])}, max_heat={best_mar_better_mdd['max_heat']}, risk_per_trade={best_mar_better_mdd['risk_per_trade']} (MAR={best_mar_better_mdd['mar']:.4f}, MDD={best_mar_better_mdd['mdd']:.2%})\n")
        f.write("\n## 3. Does any risk-shaped Challenger satisfy the spirit of the promotion rule better?\n\n")
        f.write("Yes: lower MDD without giving up most of the MAR edge.\n" if satisfies_spirit else "No: either MDD does not improve enough or MAR drops too much.\n")
        f.write("\n## 4. Should Challenger stay under watch only, or move to formal baseline review candidate?\n\n")
        f.write("**Stay under watch only.** Re-run rolling review with the best risk-shaped Challenger before considering promotion.\n" if stay_under_watch else "**Move to formal baseline review candidate.** Risk-shaped Challenger meets MDD and MAR criteria; run head-to-head vs Champion.\n")
    if df.empty:
        print("[challenger_riskshape] No rows; summary based on partial or no data.", flush=True)

    print(f"[challenger_riskshape] Wrote {csv_path}, {md_path}, {summary_path}", flush=True)


def write_summary_from_csv(csv_path: Path, md_path: Path, summary_path: Path) -> None:
    """Read existing CSV and write .md and summary .md (e.g. after a completed run)."""
    if not csv_path.exists():
        print(f"[challenger_riskshape] CSV not found: {csv_path}", flush=True)
        return
    df = pd.read_csv(csv_path)
    baseline = df[(df["max_positions"] == 12) & (df["max_heat"] == 0.04) & (df["risk_per_trade"] == 0.005)]
    baseline_full = baseline[baseline["period"] == "full_sample"]
    baseline_recent = baseline[baseline["period"] == "2024-2026Q1"]
    baseline_mdd_full = baseline_full["mdd"].iloc[0] if not baseline_full.empty else np.nan
    baseline_mar_full = baseline_full["mar"].iloc[0] if not baseline_full.empty else np.nan
    if pd.isna(baseline_mdd_full) and not baseline_recent.empty:
        baseline_mdd_full = baseline_recent["mdd"].iloc[0]
        baseline_mar_full = baseline_recent["mar"].iloc[0]
    baseline_mdd_val = float(baseline_mdd_full) if pd.notna(baseline_mdd_full) else -0.30
    full_df = df[df["period"] == "full_sample"]
    use_df = full_df if not full_df.empty and full_df["mar"].notna().any() else df[df["period"] == "2024-2026Q1"] if "2024-2026Q1" in df["period"].values else df
    if not use_df.empty and use_df["mar"].notna().any():
        best_mar_row = use_df.loc[use_df["mar"].idxmax()]
        better_mdd = use_df[use_df["mdd"].fillna(-1) > baseline_mdd_val + 0.02]
        best_mar_better_mdd = better_mdd.loc[better_mdd["mar"].idxmax()] if not better_mdd.empty else None
    else:
        best_mar_row = None
        best_mar_better_mdd = None
    can_keep = best_mar_better_mdd is not None and (pd.isna(baseline_mar_full) or float(best_mar_better_mdd["mar"]) >= float(baseline_mar_full) * 0.8)
    if best_mar_row is not None:
        try:
            best_config_str = f"max_positions={int(best_mar_row['max_positions'])}, max_heat={best_mar_row['max_heat']}, risk_per_trade={best_mar_row['risk_per_trade']}"
        except Exception:
            best_config_str = "N/A"
    else:
        best_config_str = "N/A"
    satisfies = best_mar_better_mdd is not None and float(best_mar_better_mdd.get("mdd", -0.5)) > (baseline_mdd_val + 0.05) and (pd.isna(baseline_mar_full) or float(best_mar_better_mdd.get("mar", 0)) >= float(baseline_mar_full) * 0.9)
    stay_watch = not satisfies
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Challenger Risk-Shaping Test\n\n")
        for period in df["period"].unique():
            sub = df[df["period"] == period].sort_values("mar", ascending=False)
            if sub.empty:
                continue
            f.write(f"## Top 10 by MAR — {period}\n\n")
            f.write("| max_positions | max_heat | risk_per_trade | MAR | MDD | CAGR | n_trades | chosen_rate | rejected_max_pos |\n")
            f.write("|---------------|----------|----------------|-----|-----|------|----------|-------------|------------------|\n")
            for _, r in sub.head(10).iterrows():
                cr = r.get("chosen_rate", np.nan)
                rmp = int(r.get("rejected_max_positions", 0))
                f.write(f"| {int(r['max_positions'])} | {r['max_heat']} | {r['risk_per_trade']} | {r['mar']:.4f} | {r['mdd']:.2%} | {r['cagr']:.2%} | {int(r['n_trades'])} | {cr:.4g} | {rmp} |\n")
            f.write("\n")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Path A Challenger Risk-Shaping — Summary\n\n")
        f.write("## 1. Can Challenger keep better recent/rolling behavior with lower MDD?\n\n")
        f.write("Yes.\n" if can_keep else "Partially or no.\n")
        f.write("\n## 2. Best risk-shaped Challenger config\n\n")
        f.write(f"- **Best by full-sample MAR:** {best_config_str}\n")
        if best_mar_better_mdd is not None:
            f.write(f"- **Best MAR with materially better MDD:** max_positions={int(best_mar_better_mdd['max_positions'])}, max_heat={best_mar_better_mdd['max_heat']}, risk_per_trade={best_mar_better_mdd['risk_per_trade']}\n")
        f.write("\n## 3. Does any risk-shaped Challenger satisfy the spirit of the promotion rule better?\n\n")
        f.write("Yes.\n" if satisfies else "No.\n")
        f.write("\n## 4. Should Challenger stay under watch only, or move to formal baseline review candidate?\n\n")
        f.write("**Stay under watch only.**\n" if stay_watch else "**Move to formal baseline review candidate.**\n")
    print(f"[challenger_riskshape] Wrote {md_path}, {summary_path}", flush=True)


if __name__ == "__main__":
    import os
    if os.environ.get("SUMMARY_ONLY") or (len(sys.argv) > 1 and sys.argv[1] == "--summary-only"):
        artifacts_dir = _REPO / "artifacts"
        write_summary_from_csv(
            artifacts_dir / "path_a_challenger_riskshape.csv",
            artifacts_dir / "path_a_challenger_riskshape.md",
            artifacts_dir / "path_a_challenger_riskshape_summary.md",
        )
    else:
        main()
