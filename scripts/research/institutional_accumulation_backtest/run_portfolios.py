from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.portfolios import build_strategy_curves, summarize_metrics


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-mode", default="ohlcv_only")
    ap.parse_args()
    outcomes = pd.read_parquet("data/research/institutional_accumulation/forward_outcomes_panel.parquet")
    curves = build_strategy_curves(outcomes)
    metrics = summarize_metrics(curves)
    out_dir = Path("data/research/institutional_accumulation")
    out_dir.mkdir(parents=True, exist_ok=True)
    curves.to_csv(out_dir / "tier_strategy_equity_curves.csv", index=False)
    metrics.to_csv(out_dir / "portfolio_metrics_summary.csv", index=False)
    print("Wrote portfolio outputs")


if __name__ == "__main__":
    main()
