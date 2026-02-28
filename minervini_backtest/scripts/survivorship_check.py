from __future__ import annotations

"""
survivorship_check.py
=====================

Estimate survivorship bias in the current FA universe by inspecting when
each symbol first appears in `data/fa_minervini.csv`.

Buckets:
- <=2016        -> "pre_2017"
- 2017-2018    -> "2017_2018"
- >=2019       -> "post_2019"
"""

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description="Survivorship bias check for FA cohort universe")
    ap.add_argument(
        "--fa-csv",
        default="data/fa_minervini.csv",
        help="Path to FA CSV (default data/fa_minervini.csv)",
    )
    ap.add_argument(
        "--out",
        default="minervini_backtest/outputs/survivorship_check.csv",
        help="Output CSV path for per-symbol first_report_date and bucket",
    )
    args = ap.parse_args()

    fa_path = Path(args.fa_csv)
    if not fa_path.exists():
        raise FileNotFoundError(f"FA CSV not found: {fa_path}")

    df = pd.read_csv(fa_path)
    if "symbol" not in df.columns or "report_date" not in df.columns:
        raise ValueError("FA CSV must contain 'symbol' and 'report_date' columns.")

    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["report_date"] = pd.to_datetime(df["report_date"])

    first = df.groupby("symbol")["report_date"].min().reset_index()
    first["year"] = first["report_date"].dt.year

    def _bucket(y: int) -> str:
        if y <= 2016:
            return "pre_2017"
        if 2017 <= y <= 2018:
            return "2017_2018"
        return "post_2019"

    first["bucket"] = first["year"].apply(_bucket)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    first[["symbol", "report_date", "bucket"]].to_csv(out_path, index=False)

    total_symbols = len(first)
    n_pre_2017 = int((first["bucket"] == "pre_2017").sum())
    n_2017_2018 = int((first["bucket"] == "2017_2018").sum())
    n_post_2019 = int((first["bucket"] == "post_2019").sum())

    print(f"total_symbols,{total_symbols}")
    print(f"symbols_present_pre2017,{n_pre_2017}")
    print(f"symbols_first_seen_2017_2018,{n_2017_2018}")
    print(f"symbols_first_seen_post2019,{n_post_2019}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

