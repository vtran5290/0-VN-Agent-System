from __future__ import annotations

"""
Example:
    python -m regime.run_combined_regime --index-csv data/regime_log_2012_now.csv --out data/combined_regime_log_2012_now.csv
"""

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from .regime_engine import compute_regime
from .regime_types import RegimeConfig
from canslim.primary_trend import compute_primary_trend


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build combined primary+tactical market regime log from index CSV."
    )
    parser.add_argument(
        "--index-csv",
        required=True,
        help="Path to index CSV (either OHLCV or an existing tactical regime log with 'market_status').",
    )
    parser.add_argument(
        "--out",
        default="data/combined_regime_log.csv",
        help="Output CSV path (default: data/combined_regime_log.csv)",
    )
    return parser.parse_args()


def _load_index_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError("Input CSV must contain a 'date' column.")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure DataFrame has the columns required by compute_regime.
    If OHLCV columns are missing, try to fall back to using 'close' as all of O/H/L.
    """
    required = ["open", "high", "low", "close", "volume"]
    out = df.copy()
    if "close" not in out.columns:
        raise ValueError("Input CSV must have at least 'close' column.")

    for col in ["open", "high", "low"]:
        if col not in out.columns:
            out[col] = out["close"]
    if "volume" not in out.columns:
        out["volume"] = 0.0
    return out[["date", "open", "high", "low", "close", "volume"]]


def build_combined_regime(index_csv: str, out_path: str) -> pd.DataFrame:
    """
    Build a combined regime log:
      - Tactical regime (Tier-2) from compute_regime OR existing 'market_status' column.
      - Primary trend (Tier-1) from compute_primary_trend (MA+ breadth; breadth can be disabled).
      - Combined market_status_combined via primary gating:
            DOWN     -> 'downtrend'
            NEUTRAL  -> 'correction'
            UP       -> tactical market_status
    """
    df_idx = _load_index_df(index_csv)

    # 1. Tactical regime
    if "market_status" in df_idx.columns:
        tactical = df_idx.copy()
    else:
        ohlcv = _ensure_ohlcv(df_idx)
        cfg = RegimeConfig()
        tactical = compute_regime(ohlcv, cfg)

    # 2. Primary trend (breadth disabled by default: empty constituents)
    index_for_primary = df_idx[["date", "close"]].copy()
    primary = compute_primary_trend(index_for_primary, constituent_prices={})

    # 3. Merge on date
    merged = pd.merge(
        tactical,
        primary[
            [
                "date",
                "primary_state",
                "ma50",
                "ma200",
                "ma200_slope",
                "ma50_above_ma200",
                "breadth_pct",
                "breadth_pass",
            ]
        ],
        on="date",
        how="inner",
        suffixes=("", "_primary"),
    )

    # 4. Combined status
    tactical_status = merged["market_status"].astype(str)
    primary_state = merged["primary_state"].astype(str)

    combined = tactical_status.copy()
    combined[primary_state == "DOWN"] = "downtrend"
    combined[primary_state == "NEUTRAL"] = "correction"

    merged["market_status_combined"] = combined

    # 5. Write CSV
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, index=False)

    # Basic summary
    print(f"Combined regime log written to: {out}")
    print(f"Rows: {len(merged)}, date range: {merged['date'].min().date()} -> {merged['date'].max().date()}")

    return merged


def main() -> None:
    args = parse_args()
    build_combined_regime(args.index_csv, args.out)


if __name__ == "__main__":
    main()

