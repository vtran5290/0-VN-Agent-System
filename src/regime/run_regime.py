from __future__ import annotations

"""
Example:
    python -m regime.run_regime --symbol VN30 --start 2019-10-01 --end 2020-12-31 --out data/regime_log_2019_2020.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from canslim.fireant_fetcher import fetch_ohlcv
from .regime_engine import compute_regime
from .regime_types import RegimeConfig


KEY_COLS = [
    "date",
    "close",
    "market_status",
    "rally_day_count",
    "ftd_date",
    "ftd_valid",
    "distribution_count_20d",
    "ma50_break_flag",
    "allow_new_buys",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run O'Neil-style market regime engine.")
    parser.add_argument("--symbol", default="VN30", help="Index symbol (default: VN30)")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--out",
        default="data/regime_log.csv",
        help="Output CSV path (default: data/regime_log.csv)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = fetch_ohlcv(args.symbol, args.start, args.end, resolution="D")
    if df.empty:
        print("No data returned from fetch_ohlcv; exiting.")
        return

    cfg = RegimeConfig(index_symbol=args.symbol)
    regime_df = compute_regime(df, cfg)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    regime_df.to_csv(out_path, index=False)

    # Basic summary
    n_rows = len(regime_df)
    date_min = pd.to_datetime(regime_df["date"]).min()
    date_max = pd.to_datetime(regime_df["date"]).max()
    print(f"Regime log written to: {out_path}")
    print(f"Rows: {n_rows}, date range: {date_min.date()} -> {date_max.date()}")

    cols = [c for c in KEY_COLS if c in regime_df.columns]
    print("\nHEAD (first 5 rows):")
    print(regime_df[cols].head(5).to_string(index=False))

    print("\nTAIL (last 5 rows):")
    print(regime_df[cols].tail(5).to_string(index=False))


if __name__ == "__main__":
    main()

