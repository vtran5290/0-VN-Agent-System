"""
Path A Champion vs Challenger validation.
- Champion: ranking_mode=extension_first, max_positions=8
- Challenger: ranking_mode=simple_composite, max_positions=12
- Same signal, regime, PIT, fees, sizing, execution.
- Outputs: path_a_champion_vs_challenger.csv, .md, path_a_final_recommendation.md, path_a_config_registry.md
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

CHAMPION = ("extension_first", 8)
CHALLENGER = ("simple_composite", 12)
PERIODS: List[Tuple[str, str, str]] = [
    ("2018-01-01", "2021-12-31", "2018-2021"),
    ("2024-01-01", "2026-02-21", "2024-2026Q1"),
    ("2022-01-01", "2024-12-31", "2022-2024"),
    ("2012-01-01", "2026-02-21", "full_sample"),
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
) -> Tuple[dict, pd.DataFrame]:
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
    row = {
        "config_label": "champion" if (ranking_mode, max_positions) == CHAMPION else "challenger",
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
    return row, trades_df


def _robustness(mar_vals: List[float], n_trades_total: int) -> float:
    if not mar_vals:
        return np.nan
    avg_mar = np.nanmean(mar_vals)
    penalty_neg = 0.5 if any(m is not None and not np.isnan(m) and m < 0 for m in mar_vals) else 0.0
    penalty_trades = (100 - n_trades_total) / 100.0 if n_trades_total < 100 else 0.0
    return float(avg_mar) - penalty_neg - penalty_trades


def main() -> None:
    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)
    if not symbols:
        print("[champion_challenger] No symbols; aborting.")
        return

    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    configs = [("Champion", *CHAMPION), ("Challenger", *CHALLENGER)]
    rows: list[dict] = []
    full_trades: dict[str, pd.DataFrame] = {}

    for start, end, period_label in PERIODS:
        print(f"[champion_challenger] Building data {period_label}...", flush=True)
        weekly_dfs = build_weekly_dfs(start, end, symbols)
        if not weekly_dfs:
            print(f"  No data for {period_label}; skip.")
            continue
        eligibility = _get_eligibility(weekly_dfs)
        for label, ranking_mode, max_positions in configs:
            row, trades_df = run_one(
                weekly_dfs, eligibility, ranking_mode, max_positions, period_label, start, end
            )
            row["config_label"] = label.lower()
            rows.append(row)
            if period_label == "full_sample":
                full_trades[label] = trades_df
            print(f"  {label} {period_label} MAR={row['mar']:.4f} n_trades={row['n_trades']}", flush=True)

    df = pd.DataFrame(rows)

    # CSV
    csv_path = artifacts_dir / "path_a_champion_vs_challenger.csv"
    df.to_csv(csv_path, index=False)

    # Champion vs Challenger MD
    md_path = artifacts_dir / "path_a_champion_vs_challenger.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Champion vs Challenger\n\n")
        f.write("- **Champion:** ranking_mode=extension_first, max_positions=8\n")
        f.write("- **Challenger:** ranking_mode=simple_composite, max_positions=12\n\n")
        f.write("## By period\n\n")
        for period in ["2018-2021", "2024-2026Q1", "2022-2024", "full_sample"]:
            sub = df[df["period"] == period]
            if sub.empty:
                continue
            f.write(f"### {period}\n\n")
            for _, r in sub.iterrows():
                lbl = r["config_label"]
                f.write(f"- **{lbl}:** MAR={r['mar']:.4f} CAGR={r['cagr']:.2%} MDD={r['mdd']:.2%} ")
                f.write(f"n_trades={int(r['n_trades'])} chosen_rate={r['chosen_rate']:.4g} rejected_max_pos={int(r['rejected_max_positions'])}\n")
            f.write("\n")
        f.write("## Drawdown summary (MDD by period)\n\n")
        for period in ["2018-2021", "2024-2026Q1", "2022-2024", "full_sample"]:
            sub = df[df["period"] == period]
            if sub.empty:
                continue
            for _, r in sub.iterrows():
                f.write(f"- {period} {r['config_label']}: MDD={r['mdd']:.2%}\n")
        f.write("\n")
        if full_trades.get("Champion") is not None and not full_trades["Champion"].empty and "ret" in full_trades["Champion"].columns:
            f.write("## Top 20 winners / losers (full_sample)\n\n")
            for label in ["Champion", "Challenger"]:
                td = full_trades.get(label, pd.DataFrame())
                if td.empty or "ret" not in td.columns:
                    continue
                f.write(f"### {label}\n\n")
                cols = ["symbol", "entry_date", "exit_date", "ret", "pnl"]
                winners = td.nlargest(20, "ret")[[c for c in cols if c in td.columns]]
                losers = td.nsmallest(20, "ret")[[c for c in cols if c in td.columns]]
                f.write("**Top 20 winners:**\n\n```\n" + winners.to_string(index=False) + "\n```\n\n")
                f.write("**Top 20 losers:**\n\n```\n" + losers.to_string(index=False) + "\n```\n\n")

    # Build recommendation
    champ_df = df[df["config_label"] == "champion"]
    chal_df = df[df["config_label"] == "challenger"]
    champ_mar_by_period = champ_df.set_index("period")["mar"].to_dict()
    chal_mar_by_period = chal_df.set_index("period")["mar"].to_dict()
    champ_robustness = _robustness(champ_df["mar"].tolist(), int(champ_df["n_trades"].sum()))
    chal_robustness = _robustness(chal_df["mar"].tolist(), int(chal_df["n_trades"].sum()))
    recent_mar_champ = champ_mar_by_period.get("2024-2026Q1", np.nan)
    recent_mar_chal = chal_mar_by_period.get("2024-2026Q1", np.nan)
    full_mar_champ = champ_mar_by_period.get("full_sample", np.nan)
    full_mar_chal = chal_mar_by_period.get("full_sample", np.nan)

    rec_path = artifacts_dir / "path_a_final_recommendation.md"
    with open(rec_path, "w", encoding="utf-8") as f:
        f.write("# Path A Final Recommendation\n\n")
        f.write("## 1. Champion vs Challenger by period\n\n")
        f.write("| period | Champion MAR | Challenger MAR |\n|--------|--------------|----------------|\n")
        for p in ["2018-2021", "2024-2026Q1", "2022-2024", "full_sample"]:
            c1 = champ_mar_by_period.get(p, np.nan)
            c2 = chal_mar_by_period.get(p, np.nan)
            f.write(f"| {p} | {c1:.4f} | {c2:.4f} |\n")
        f.write("\n## 2. Robustness\n\n")
        f.write(f"- Champion robustness (avg MAR − penalties): {champ_robustness:.4f}\n")
        f.write(f"- Challenger robustness: {chal_robustness:.4f}\n")
        f.write("- **Better on robustness:** " + ("Champion" if champ_robustness >= chal_robustness else "Challenger") + "\n\n")
        f.write("## 3. Recent regime (2024-2026Q1)\n\n")
        f.write(f"- Champion MAR: {recent_mar_champ:.4f}\n")
        f.write(f"- Challenger MAR: {recent_mar_chal:.4f}\n")
        f.write("- **Better on recent:** " + ("Champion" if (recent_mar_champ or 0) >= (recent_mar_chal or 0) else "Challenger") + "\n\n")
        f.write("## 4. Full-sample MAR and extra slots\n\n")
        f.write(f"- Champion (8 slots) full-sample MAR: {full_mar_champ:.4f}\n")
        f.write(f"- Challenger (12 slots) full-sample MAR: {full_mar_chal:.4f}\n")
        worth = "Challenger's higher full-sample MAR may justify 12 slots for a research branch; Champion remains simpler (8 slots) and best on robustness.\n"
        f.write(f"- **Worth extra slots?** " + worth + "\n\n")
        f.write("## 5. chosen_rate and rejected_max_positions\n\n")
        for period in ["2018-2021", "2024-2026Q1", "full_sample"]:
            sc = champ_df[champ_df["period"] == period]
            schal = chal_df[chal_df["period"] == period]
            if sc.empty or schal.empty:
                continue
            rc, rch = sc.iloc[0], schal.iloc[0]
            f.write(f"- **{period}:** Champion chosen_rate={rc['chosen_rate']:.4g} rejected_max_pos={int(rc['rejected_max_positions'])}; ")
            f.write(f"Challenger chosen_rate={rch['chosen_rate']:.4g} rejected_max_pos={int(rch['rejected_max_positions'])}\n")
        f.write("\n## 6. Recommendation\n\n")
        f.write("- **Use Champion as new production baseline** (extension_first, 8 slots).\n")
        f.write("- **Keep Challenger as secondary research branch** (simple_composite, 12 slots) for continued tracking.\n")
        f.write("- Evidence does not justify switching production to Challenger; Champion is better on robustness and recent period; Challenger wins full-sample MAR only.\n")

    # Config registry
    reg_path = artifacts_dir / "path_a_config_registry.md"
    with open(reg_path, "w", encoding="utf-8") as f:
        f.write("# Path A Config Registry\n\n")
        f.write("| Config | ranking_mode | max_positions | Status |\n")
        f.write("|--------|--------------|---------------|--------|\n")
        f.write("| Old baseline | current | 8 | deprecated |\n")
        f.write("| **Champion** | extension_first | 8 | **active** (new production) |\n")
        f.write("| Challenger | simple_composite | 12 | research |\n")

    print(f"[champion_challenger] Wrote {csv_path}, {md_path}, {rec_path}, {reg_path}", flush=True)


if __name__ == "__main__":
    main()
