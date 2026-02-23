# minervini_backtest/scripts/import_csv_to_parquet.py — Ingest CSV OHLCV (per symbol or single file) → parquet in data/curated
"""
Usage:
  From repo root:
    python minervini_backtest/scripts/import_csv_to_parquet.py [--raw DIR] [--curated DIR] [--single FILE]
  CSV format: Date, Open, High, Low, Close, Volume (or lowercase). One file per symbol, or --single with Symbol column.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
MB_ROOT = Path(__file__).resolve().parent.parent
RAW = MB_ROOT / "data" / "raw"
CURATED = MB_ROOT / "data" / "curated"


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if c.lower() in ("date", "open", "high", "low", "close", "volume")]
    rename = {c: c.lower() for c in cols}
    out = df.rename(columns=rename)
    required = ["date", "open", "high", "low", "close", "volume"]
    for r in required:
        if r not in out.columns and r.capitalize() in df.columns:
            out[r] = df[r.capitalize()]
    out["date"] = pd.to_datetime(out["date"])
    return out[required] if all(x in out.columns for x in required) else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(RAW), help="Directory with one CSV per symbol (filename = symbol)")
    ap.add_argument("--curated", default=str(CURATED), help="Output directory for parquet files")
    ap.add_argument("--single", default=None, help="Single CSV path; must have Symbol column or use filename as symbol")
    args = ap.parse_args()
    raw_dir = Path(args.raw)
    out_dir = Path(args.curated)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.single:
        fp = Path(args.single)
        if not fp.exists():
            print(f"File not found: {fp}")
            return
        df = pd.read_csv(fp)
        if "Symbol" in df.columns or "symbol" in df.columns:
            sym_col = "Symbol" if "Symbol" in df.columns else "symbol"
            for sym, g in df.groupby(sym_col):
                g = normalize_df(g.drop(columns=[sym_col]))
                out_path = out_dir / f"{str(sym).upper()}.parquet"
                g.to_parquet(out_path, index=False)
                print(f"Wrote {out_path} ({len(g)} rows)")
        else:
            df = normalize_df(df)
            stem = fp.stem.upper()
            out_path = out_dir / f"{stem}.parquet"
            df.to_parquet(out_path, index=False)
            print(f"Wrote {out_path} ({len(df)} rows)")
        return

    if not raw_dir.exists():
        print(f"Raw dir not found: {raw_dir}. Create it and put one CSV per symbol (Date,Open,High,Low,Close,Volume).")
        return
    for csv_path in raw_dir.glob("*.csv"):
        try:
            df = pd.read_csv(csv_path)
            df = normalize_df(df)
            symbol = csv_path.stem.upper()
            out_path = out_dir / f"{symbol}.parquet"
            df.to_parquet(out_path, index=False)
            print(f"{symbol}: {len(df)} rows -> {out_path}")
        except Exception as e:
            print(f"Skip {csv_path}: {e}")


if __name__ == "__main__":
    main()
