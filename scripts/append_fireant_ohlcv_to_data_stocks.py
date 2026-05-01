from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


from src.data.fireant_client import get_client


def _read_last_date(fp: Path) -> pd.Timestamp:
    # Read only the date column; we only need the last row's date.
    df = pd.read_csv(fp, usecols=["date"])
    df["date"] = pd.to_datetime(df["date"])
    if df.empty:
        raise ValueError(f"Empty CSV: {fp}")
    return pd.to_datetime(df["date"].iloc[-1])


def _append_new_rows(fp: Path, df_new: pd.DataFrame) -> int:
    if df_new.empty:
        return 0

    # Ensure canonical column order (matches repo CSV header).
    df_new = df_new[["date", "open", "high", "low", "close", "volume"]].copy()

    # Write date as YYYY-MM-DD to match existing files.
    df_new["date"] = pd.to_datetime(df_new["date"]).dt.strftime("%Y-%m-%d")

    df_new.to_csv(fp, mode="a", header=False, index=False)
    return len(df_new)


def update_dir(
    *,
    client,
    csv_dir: Path,
    end: str,
    limit: int | None,
    delay_s: float,
    dry_run: bool,
) -> dict:
    csv_dir = Path(csv_dir)
    files = sorted(csv_dir.glob("*.csv"))
    if limit is not None:
        files = files[:limit]

    processed = 0
    updated = 0
    skipped_uptodate = 0
    missing_or_empty = 0
    errors = 0

    end_ts = pd.to_datetime(end)

    for i, fp in enumerate(files, start=1):
        sym = fp.stem.upper()
        processed += 1

        try:
            last_date = _read_last_date(fp)
        except Exception:
            errors += 1
            continue

        start_ts = last_date + pd.Timedelta(days=1)
        if start_ts > end_ts:
            skipped_uptodate += 1
            continue

        try:
            df_new = client.get_ohlcv(sym, start=start_ts.strftime("%Y-%m-%d"), end=end)
        except Exception:
            errors += 1
            continue

        if df_new is None or df_new.empty:
            missing_or_empty += 1
            time.sleep(delay_s)
            continue

        df_new["date"] = pd.to_datetime(df_new["date"])
        df_new = df_new[df_new["date"] > last_date].sort_values("date")
        if df_new.empty:
            skipped_uptodate += 1
            time.sleep(delay_s)
            continue

        if dry_run:
            updated += 1
            print(f"[DRY] {sym} would append {len(df_new)} rows ({df_new.iloc[-1]['date'].strftime('%Y-%m-%d')})")
        else:
            _append_new_rows(fp, df_new)
            updated += 1
            print(f"[{i}/{len(files)}] {sym} appended {len(df_new)} rows (to {df_new.iloc[-1]['date'].strftime('%Y-%m-%d')})")

        time.sleep(delay_s)

    return {
        "dir": str(csv_dir),
        "processed": processed,
        "updated": updated,
        "skipped_uptodate": skipped_uptodate,
        "missing_or_empty": missing_or_empty,
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Append FireAnt daily OHLCV+volume to per-ticker CSV caches.")
    ap.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today)")
    ap.add_argument("--data-stocks", action="store_true", help="Update data/stocks/*.csv")
    ap.add_argument("--minervini-raw", action="store_true", help="Update minervini_backtest/data/raw/*.csv")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of tickers processed (debug)")
    ap.add_argument("--delay", type=float, default=0.12, help="Delay between API calls (seconds)")
    ap.add_argument("--timeout", type=int, default=180, help="HTTP timeout seconds")
    ap.add_argument("--dry-run", action="store_true", help="Do not modify files; only simulate appends")
    args = ap.parse_args()

    if not args.data_stocks and not args.minervini_raw:
        print("Nothing to do: enable at least one of --data-stocks / --minervini-raw", flush=True)
        return 2

    end = args.end or pd.Timestamp.today().strftime("%Y-%m-%d")

    client = get_client(timeout=args.timeout, cache_ttl=0)

    results = []
    repo = Path(__file__).resolve().parents[1]

    if args.data_stocks:
        results.append(
            update_dir(
                client=client,
                csv_dir=repo / "data" / "stocks",
                end=end,
                limit=args.limit,
                delay_s=args.delay,
                dry_run=args.dry_run,
            )
        )

    if args.minervini_raw:
        results.append(
            update_dir(
                client=client,
                csv_dir=repo / "minervini_backtest" / "data" / "raw",
                end=end,
                limit=args.limit,
                delay_s=args.delay,
                dry_run=args.dry_run,
            )
        )

    print("\nSUMMARY")
    for r in results:
        print(r)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

