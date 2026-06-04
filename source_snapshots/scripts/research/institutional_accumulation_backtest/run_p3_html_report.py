from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.p3_reporting import write_p3_html_report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/research/institutional_accumulation")
    ap.add_argument(
        "--html-path",
        default="reports/research/institutional_accumulation/p3_portfolio_simulation.html",
    )
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    html_path = Path(args.html_path)

    p2_summary = None
    p2_path = data_dir / "p2_diagnostic_summary.csv"
    if p2_path.is_file():
        p2_summary = pd.read_csv(p2_path)

    write_p3_html_report(
        html_path,
        portfolio_metrics=pd.read_csv(data_dir / "p3_portfolio_metrics.csv"),
        diagnostic_summary=pd.read_csv(data_dir / "p3_diagnostic_summary.csv"),
        turnover_capacity=pd.read_csv(data_dir / "p3_turnover_capacity.csv"),
        yearly_returns=pd.read_csv(data_dir / "p3_yearly_returns.csv"),
        regime_returns=pd.read_csv(data_dir / "p3_regime_returns.csv"),
        equity_curves=pd.read_csv(data_dir / "p3_portfolio_equity_curves.csv"),
        p2_summary=p2_summary,
    )
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
