# minervini_backtest/scripts/data_sanity.py — Data integrity checks before trusting any PF
"""
Rule: use adjusted O/H/L/C when dividends/splits exist; raw volume OK.
Checks: increasing unique dates, no negative volume, OHLC logical, optional gap check.
Run: python minervini_backtest/scripts/data_sanity.py [data/curated/*.parquet | data/raw/*.csv]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

MB_ROOT = Path(__file__).resolve().parent.parent
CURATED = MB_ROOT / "data" / "curated"
RAW = MB_ROOT / "data" / "raw"


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ["date", "open", "high", "low", "close", "volume"]:
        if c not in out.columns and c.capitalize() in df.columns:
            out[c] = df[c.capitalize()]
    out["date"] = pd.to_datetime(out["date"])
    return out


def check_one(df: pd.DataFrame, name: str) -> list[str]:
    """Returns list of error messages (empty if OK)."""
    errs = []
    df = normalize_df(df)
    required = ["date", "open", "high", "low", "close", "volume"]
    for c in required:
        if c not in df.columns:
            errs.append(f"{name}: missing column {c}")
            return errs

    # Increasing, unique dates
    if not df["date"].is_monotonic_increasing:
        errs.append(f"{name}: dates not increasing")
    if df["date"].duplicated().any():
        errs.append(f"{name}: duplicate dates ({df['date'].duplicated().sum()})")

    # No negative volume
    if (df["volume"] < 0).any():
        errs.append(f"{name}: negative volume present")

    # OHLC logical: Low <= min(O,C) <= max(O,C) <= High
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    if not (l <= np.minimum(o, c)).all():
        errs.append(f"{name}: Low > min(Open,Close) somewhere")
    if not (np.maximum(o, c) <= h).all():
        errs.append(f"{name}: High < max(Open,Close) somewhere")
    if (h < l).any():
        errs.append(f"{name}: High < Low somewhere")

    return errs


def main():
    paths = sys.argv[1:]
    if not paths:
        # Default: all parquet then all csv
        paths = list(CURATED.glob("*.parquet")) if CURATED.exists() else []
        if not paths and RAW.exists():
            paths = list(RAW.glob("*.csv"))
    if not paths:
        print("Usage: data_sanity.py [file1.parquet file2.csv ...]")
        print("  Or run from minervini_backtest with no args to check data/curated and data/raw.")
        return

    all_ok = True
    for fp in paths:
        fp = Path(fp)
        if not fp.exists():
            print(f"Skip (not found): {fp}")
            continue
        try:
            if fp.suffix.lower() == ".parquet":
                df = pd.read_parquet(fp)
            else:
                df = pd.read_csv(fp)
        except Exception as e:
            print(f"FAIL {fp.name}: read error — {e}")
            all_ok = False
            continue
        errs = check_one(df, fp.name)
        if errs:
            for e in errs:
                print(f"FAIL {fp.name}: {e}")
            all_ok = False
        else:
            print(f"OK   {fp.name}: rows={len(df)}, date range={df['date'].min()} .. {df['date'].max()}")
    if all_ok:
        print("\nData sanity: all checks passed.")
    else:
        print("\nData sanity: some checks failed. Fix before trusting backtest.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
