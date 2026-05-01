"""
Path A monitoring snapshot: run Champion and Challenger on a recent period (default 2024-01-01 to 2026-02-21),
write artifacts/path_a_monitoring_snapshot.csv and .md for lightweight tracking.
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

from pp_backtest.run_weekly_ema21_portfolio import (
    build_weekly_dfs,
    load_universe,
    get_path_a_config,
)
from pp_backtest.config import BacktestConfig
from pp_backtest.eligibility import get_global_eligibility
from pp_backtest.eligibility import EligibilityMap
from pp_backtest.portfolio_sim import (
    PortfolioConfig,
    run_portfolio_backtest,
    DEFAULT_INITIAL_EQUITY_VND,
)

DEFAULT_START = "2024-01-01"
DEFAULT_END = "2026-02-21"
SNAPSHOT_CONFIGS = ["champion", "challenger"]


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


def main(start: str = DEFAULT_START, end: str = DEFAULT_END) -> None:
    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)
    if not symbols:
        print("[path_a_monitoring_snapshot] No symbols; aborting.")
        return

    cfg = BacktestConfig()
    cfg.start = start
    cfg.end = end
    weekly_dfs, _ = build_weekly_dfs(cfg, symbols)
    if not weekly_dfs:
        print("[path_a_monitoring_snapshot] No weekly data; aborting.")
        return
    eligibility = _get_eligibility(weekly_dfs)
    period_days = (pd.to_datetime(end) - pd.to_datetime(start)).days
    period_months = max(1, period_days / 30.0)

    rows = []
    for config_name in SNAPSHOT_CONFIGS:
        ranking_mode, max_positions = get_path_a_config(config_name)
        pconfig = PortfolioConfig(
            risk_per_trade=0.005,
            max_heat=0.04,
            max_positions=max_positions,
            max_symbol_weight=0.10,
            liquidity_participation_cap=0.05,
            initial_equity=DEFAULT_INITIAL_EQUITY_VND,
            fee_bps_per_side=15.0,
        )
        trades_df, stats = run_portfolio_backtest(
            weekly_dfs, pconfig, eligibility=eligibility, ranking_mode=ranking_mode
        )
        n_trades = len(trades_df)
        trades_per_month = n_trades / period_months if period_months else np.nan
        rows.append({
            "config_name": config_name,
            "ranking_mode": ranking_mode,
            "max_positions": max_positions,
            "period": f"{start}_to_{end}",
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
            "skipped_regime_off": stats.get("skipped_regime_off", 0),
            "skipped_no_new_positions": stats.get("skipped_no_new_positions", 0),
            "skipped_liquidity": stats.get("skipped_liquidity", 0),
        })
        print(f"[path_a_monitoring_snapshot] {config_name} MAR={rows[-1]['mar']:.4f} n_trades={n_trades}", flush=True)

    df = pd.DataFrame(rows)
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "path_a_monitoring_snapshot.csv"
    md_path = artifacts_dir / "path_a_monitoring_snapshot.md"
    df.to_csv(csv_path, index=False)

    champ = df[df["config_name"] == "champion"].iloc[0] if not df[df["config_name"] == "champion"].empty else None
    chal = df[df["config_name"] == "challenger"].iloc[0] if not df[df["config_name"] == "challenger"].empty else None
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Monitoring Snapshot\n\n")
        f.write(f"Period: {start} to {end}\n\n")
        f.write("## 1. Champion vs Challenger (recent period)\n\n")
        f.write("| config_name | MAR | CAGR | MDD | n_trades | chosen_rate | rejected_max_positions |\n")
        f.write("|-------------|-----|------|-----|----------|-------------|------------------------|\n")
        for _, r in df.iterrows():
            f.write(f"| {r['config_name']} | {r['mar']:.4f} | {r['cagr']:.2%} | {r['mdd']:.2%} | {int(r['n_trades'])} | {r['chosen_rate']:.4g} | {int(r['rejected_max_positions'])} |\n")
        f.write("\n## 2. chosen_rate difference\n\n")
        if champ is not None and chal is not None:
            diff = chal["chosen_rate"] - champ["chosen_rate"]
            f.write(f"- Challenger chosen_rate − Champion chosen_rate = {diff:.4g}\n")
            f.write(f"- Champion: {champ['chosen_rate']:.4g}; Challenger: {chal['chosen_rate']:.4g}\n")
        f.write("\n## 3. rejected_max_positions difference\n\n")
        if champ is not None and chal is not None:
            diff = int(champ["rejected_max_positions"]) - int(chal["rejected_max_positions"])
            f.write(f"- Champion rejected_max_positions − Challenger = {diff} (Challenger has more slots, so fewer rejections expected)\n")
            f.write(f"- Champion: {int(champ['rejected_max_positions'])}; Challenger: {int(chal['rejected_max_positions'])}\n")
        f.write("\n## 4. Recommendation\n\n")
        f.write("- **Keep Champion as primary** (extension_first, 8 slots) for production.\n")
        f.write("- **Keep Challenger under watch** (simple_composite, 12 slots) as research branch; re-run this snapshot periodically to compare recent-period MAR and admission pressure.\n")

    print(f"[path_a_monitoring_snapshot] Wrote {csv_path}, {md_path}", flush=True)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Path A monitoring snapshot: Champion + Challenger on recent period.")
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END)
    args = p.parse_args()
    main(start=args.start, end=args.end)
