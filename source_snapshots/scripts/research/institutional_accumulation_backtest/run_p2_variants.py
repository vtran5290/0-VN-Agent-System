from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.p2_variants import run_p2_variants


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data/research/institutional_accumulation")
    ap.add_argument("--outcomes-path", default="data/research/institutional_accumulation/forward_outcomes_panel.parquet")
    args = ap.parse_args()

    outcomes_path = Path(args.outcomes_path)
    out_dir = Path(args.out_dir)
    outcomes = pd.read_parquet(outcomes_path)
    run_p2_variants(outcomes, out_dir)
    print(f"Wrote P2 variant CSVs from {outcomes_path} rows={len(outcomes)} tickers={outcomes['ticker'].nunique() if 'ticker' in outcomes.columns else 0}")


if __name__ == "__main__":
    main()
