# pp_backtest/portfolio_sim.py — Position sizing layer v1: K=5, w=1/K, from ledger (Option 1)
# Không đụng entry logic; chỉ portfolio construction để đo MDD thực tế hơn.
from __future__ import annotations
import sys

import pandas as pd
import numpy as np

K = 5
W = 1.0 / K


def _week_end(d: pd.Timestamp) -> pd.Timestamp:
    """W-FRI: Friday that ends the week containing d. Mon=0, Fri=4."""
    dof = d.dayofweek
    if dof <= 4:
        return d + pd.Timedelta(days=4 - dof)
    return d - pd.Timedelta(days=dof - 4)


def run_portfolio_sim(ledger_path: str, k: int = K) -> dict:
    """
    Read ledger (symbol, entry_date, exit_date, ret), enforce max K concurrent positions,
    equal weight 1/K per position. Apply full ret at exit week. No mark-to-market intra-hold.
    """
    df = pd.read_csv(ledger_path)
    for col in ("entry_date", "exit_date", "ret"):
        if col not in df.columns:
            raise ValueError(f"Ledger missing column: {col}")
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df["entry_week"] = df["entry_date"].apply(_week_end)
    df["exit_week"] = df["exit_date"].apply(_week_end)
    df = df.sort_values(["entry_week", "symbol"]).reset_index(drop=True)

    weeks = sorted(set(df["entry_week"].tolist() + df["exit_week"].tolist()))
    if not weeks:
        return {"mdd": 0.0, "total_return": 0.0, "cagr": 0.0, "avg_exposure": 0.0, "worst_weekly_loss": 0.0, "n_trades_executed": 0}

    equity = 1.0
    open_slots = k
    open_positions: list[dict] = []
    weekly_returns: list[float] = []
    trades_taken: list[dict] = []
    idx = 0
    n = len(df)

    for w in weeks:
        # Exits first: positions that exit this week
        exiting = [p for p in open_positions if p["exit_week"] <= w]
        for p in exiting:
            open_positions.remove(p)
            open_slots += 1
        week_ret = (1.0 / k) * sum(p["ret"] for p in exiting) if exiting else 0.0
        weekly_returns.append(week_ret)
        equity *= 1.0 + week_ret

        # Entries: take up to open_slots for this week (FIFO by entry_week, then symbol)
        while idx < n and df.iloc[idx]["entry_week"] <= w:
            row = df.iloc[idx]
            idx += 1
            if row["entry_week"] == w and open_slots > 0:
                rec = {"entry_week": row["entry_week"], "exit_week": row["exit_week"], "ret": row["ret"]}
                open_positions.append(rec)
                trades_taken.append(rec)
                open_slots -= 1

    # Remaining positions: assume they exit at last week (no mark-to-market)
    # Already counted in weekly_returns when exit_week reached
    total_return = equity - 1.0
    peak = 1.0
    mdd = 0.0
    run = 1.0
    for r in weekly_returns:
        run *= 1.0 + r
        peak = max(peak, run)
        mdd = min(mdd, (run / peak) - 1.0)

    n_weeks = len(weekly_returns)
    n_years = n_weeks / 52.0 if n_weeks else 1.0
    cagr = (equity ** (1.0 / n_years) - 1.0) if n_years > 0 and equity > 0 else 0.0
    worst_weekly = min(weekly_returns) if weekly_returns else 0.0

    if trades_taken:
        exposure_per_week = [
            sum(1 for t in trades_taken if t["entry_week"] <= w and t["exit_week"] > w) / k
            for w in weeks
        ]
        avg_exposure_pct = float(np.mean(exposure_per_week) * 100)
    else:
        avg_exposure_pct = 0.0

    # Ensure numeric for JSON-style output
    worst_weekly = float(worst_weekly)

    return {
        "mdd": mdd,
        "total_return": total_return,
        "cagr": cagr,
        "avg_exposure_pct": avg_exposure_pct,
        "worst_weekly_loss": worst_weekly,
        "n_trades_executed": len(trades_taken),
        "n_weeks": n_weeks,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m pp_backtest.portfolio_sim <ledger_path>")
        sys.exit(1)
    out = run_portfolio_sim(sys.argv[1])
    print("Portfolio MDD:", f"{out['mdd']:.2%}")
    print("Total return:", f"{out['total_return']:.2%}")
    print("CAGR:", f"{out['cagr']:.2%}")
    print("Avg exposure (slots used / K):", f"{out['avg_exposure_pct']:.1f}%")
    print("Worst weekly loss:", f"{out['worst_weekly_loss']:.2%}")
    print("# trades executed (after K limit):", out["n_trades_executed"])