from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]  # minervini_backtest/
REPO_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from run import fetch_fireant  # noqa: E402

DATA_RAW = ROOT / "data" / "raw"
DATA_CURATED = ROOT / "data" / "curated"


def _read_symbols_prebreakout() -> list[str]:
    # Mirrors run_prebreakout_research.py _read_symbols().
    candidates = [
        REPO_ROOT / "config" / "universe_186.txt",
        REPO_ROOT / "config" / "watchlist_80.txt",
        REPO_ROOT / "config" / "watchlist.txt",
    ]
    for p in candidates:
        if p.exists():
            lines = p.read_text(encoding="utf-8").splitlines()
            out = [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
            if out:
                return out
    return []


def _load_existing(symbol: str) -> tuple[str | None, pd.DataFrame]:
    sym = symbol.upper()
    pq = DATA_CURATED / f"{sym}.parquet"
    if pq.exists():
        df = pd.read_parquet(pq)
        df["date"] = pd.to_datetime(df["date"])
        return "parquet", df
    csv = DATA_RAW / f"{sym}.csv"
    if csv.exists():
        df = pd.read_csv(csv)
        if "date" not in df.columns:
            # Expecting `date,open,high,low,close,volume`
            for c in ["Date", "DATE"]:
                if c in df.columns:
                    df = df.rename(columns={c: "date"})
        df["date"] = pd.to_datetime(df["date"])
        return "csv", df
    return None, pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])


def _write_back(symbol: str, kind: str | None, df: pd.DataFrame) -> None:
    sym = symbol.upper()
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2 = df2.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    if kind == "parquet" or (kind is None and DATA_CURATED.exists()):
        DATA_CURATED.mkdir(parents=True, exist_ok=True)
        out_pq = DATA_CURATED / f"{sym}.parquet"
        df2.to_parquet(out_pq, index=False)
    else:
        DATA_RAW.mkdir(parents=True, exist_ok=True)
        out_csv = DATA_RAW / f"{sym}.csv"
        df2.to_csv(out_csv, index=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch FireAnt OHLCV delta and merge into local curated/raw.")
    ap.add_argument("--start", required=True, help="Delta fetch start date (YYYY-MM-DD).")
    ap.add_argument("--end", required=True, help="Delta fetch end date (YYYY-MM-DD).")
    ap.add_argument("--max-symbols", type=int, default=0, help="0 = all (from prebreakout universe), else limit.")
    ap.add_argument("--symbols-file", default=None, help="Optional symbols file override (one symbol per line).")
    args = ap.parse_args()

    if args.symbols_file:
        sym_path = Path(args.symbols_file)
        if not sym_path.exists():
            print(f"[ERROR] symbols-file not found: {sym_path}")
            return 1
        symbols = [ln.strip().upper() for ln in sym_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    else:
        symbols = _read_symbols_prebreakout()

    symbols = sorted(list({s.upper() for s in symbols}))
    if args.max_symbols and args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]

    # Also update benchmarks explicitly; they may be parquet or raw.
    symbols = sorted(list(set(symbols + ["VNINDEX", "VN30"])))

    # Ensure data dirs exist.
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_CURATED.mkdir(parents=True, exist_ok=True)

    start_req = pd.Timestamp(args.start)
    end_req = pd.Timestamp(args.end)
    if end_req < start_req:
        print("[ERROR] --end must be >= --start")
        return 1

    updated = 0
    skipped_up_to_date = 0
    failed = 0

    for i, sym in enumerate(symbols, start=1):
        try:
            kind, existing = _load_existing(sym)
            if existing is None or existing.empty or "date" not in existing.columns:
                last_date = None
            else:
                last_date = pd.to_datetime(existing["date"]).max()
                if pd.isna(last_date):
                    last_date = None

            fetch_start = start_req
            if last_date is not None:
                fetch_start = max(fetch_start, pd.Timestamp(last_date) + pd.Timedelta(days=1))

            if fetch_start > end_req:
                skipped_up_to_date += 1
                continue

            print(f"[{i}/{len(symbols)}] Fetch {sym} {fetch_start.date()} -> {end_req.date()} (kind={kind})", flush=True)
            delta = fetch_fireant(sym, str(fetch_start.date()), str(end_req.date()))
            if delta is None or delta.empty:
                print(f"[warn] {sym}: no delta returned; skipping.")
                skipped_up_to_date += 1
                continue

            delta["date"] = pd.to_datetime(delta["date"])
            merged = pd.concat([existing, delta], ignore_index=True)
            # Keep only expected columns to avoid schema drift.
            for c in ["open", "high", "low", "close", "volume", "date"]:
                if c not in merged.columns:
                    merged[c] = np.nan
            merged = merged[["date", "open", "high", "low", "close", "volume"]]
            _write_back(sym, kind, merged)
            updated += 1
        except Exception as e:
            failed += 1
            print(f"[ERROR] {sym} failed: {e!r}", flush=True)

    print(json.dumps({"updated": updated, "skipped_up_to_date": skipped_up_to_date, "failed": failed, "symbols_total": len(symbols)}))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    import json

    raise SystemExit(main())

