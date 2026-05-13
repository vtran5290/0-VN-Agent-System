"""
Incremental OHLCV panel update: fetch new bars since last date and append to ta_ohlcv_panel.parquet
Usage: python scripts/update_ohlcv_panel_incremental.py [--end 2026-05-13]
"""
from __future__ import annotations
import sys, io, os, time, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import date
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# load .env manually
env_file = REPO / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from src.data.fireant_client import get_client

PANEL_PATH = REPO / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX_PATH = REPO / "data/fireant_ssot/ta_vnindex.parquet"

def load_env():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--delay", type=float, default=0.15, help="Seconds between API calls")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()

def update_panel(end: str, delay: float, dry_run: bool):
    print(f"Loading panel from {PANEL_PATH}...")
    panel = pd.read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])

    last_date = panel["date"].max()
    start_fetch = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"  Panel last date: {last_date.date()}  |  fetching {start_fetch} to {end}")

    if start_fetch > end:
        print("Already up to date.")
        return

    # unit check: determine if panel is in thousands or raw VND
    med_close = panel.groupby("symbol")["close"].median().median()
    in_thousands = med_close < 500
    print(f"  Price unit: {'thousand VND (raw panel)' if in_thousands else 'VND'}")

    symbols = sorted(panel["symbol"].unique().tolist())
    print(f"  {len(symbols)} symbols to update")

    client = get_client()

    new_rows = []
    errors = []
    updated = 0
    empty = 0

    for i, sym in enumerate(symbols, 1):
        try:
            df = client.get_ohlcv(sym, start=start_fetch, end=end)
            if df is None or df.empty:
                empty += 1
                continue

            df = df.copy()
            df["symbol"] = sym
            df["date"] = pd.to_datetime(df["date"])

            # Compute value column in VND
            # Panel close is in thousands → price in VND = close * 1000
            if in_thousands:
                df["value"] = df["close"] * 1000 * df["volume"]
            else:
                df["value"] = df["close"] * df["volume"]

            new_rows.append(df[["symbol","date","open","high","low","close","volume","value"]])
            updated += 1

        except Exception as e:
            errors.append((sym, str(e)))

        if i % 100 == 0:
            print(f"  [{i}/{len(symbols)}] updated={updated} empty={empty} errors={len(errors)}")

        time.sleep(delay)

    print(f"\nFetch complete: {updated} updated, {empty} no new data, {len(errors)} errors")
    if errors[:5]:
        print("  Sample errors:", errors[:5])

    if not new_rows:
        print("No new data to append.")
        return

    new_df = pd.concat(new_rows, ignore_index=True)
    print(f"New rows: {len(new_df):,}  |  date range: {new_df['date'].min().date()} → {new_df['date'].max().date()}")
    print(f"Symbols with new data: {new_df['symbol'].nunique()}")

    if dry_run:
        print("DRY RUN — not writing to disk.")
        print(new_df.head(10).to_string())
        return

    # Append and deduplicate
    combined = pd.concat([panel, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["symbol","date"], keep="last")
    combined = combined.sort_values(["symbol","date"]).reset_index(drop=True)

    # Backup
    backup = PANEL_PATH.with_suffix(".parquet.bak")
    import shutil
    shutil.copy2(PANEL_PATH, backup)
    print(f"Backup saved: {backup}")

    combined.to_parquet(PANEL_PATH, index=False)
    print(f"Panel updated: {len(combined):,} rows, last date {combined['date'].max().date()}")

def update_vnindex(end: str, delay: float, dry_run: bool):
    print(f"\nUpdating VNINDEX...")
    vni = pd.read_parquet(VNIDX_PATH)
    vni["date"] = pd.to_datetime(vni["date"] if "date" in vni.columns else vni.index)

    last = vni["date"].max()
    start_fetch = (last + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    if start_fetch > end:
        print(f"  VNINDEX already up to date (last: {last.date()})")
        return

    client = get_client()
    df = client.get_ohlcv("VNINDEX", start=start_fetch, end=end)
    if df is None or df.empty:
        print("  No new VNINDEX data")
        return

    df["date"] = pd.to_datetime(df["date"])
    print(f"  New VNINDEX bars: {len(df)}")
    print(df[["date","close"]].to_string())

    if dry_run:
        print("  DRY RUN — not writing")
        return

    combined = pd.concat([vni, df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    combined.to_parquet(VNIDX_PATH, index=False)
    print(f"  VNINDEX updated: {len(combined)} rows, last {combined['date'].max().date()}")

def main():
    args = load_env()
    update_vnindex(args.end, args.delay, args.dry_run)
    update_panel(args.end, args.delay, args.dry_run)
    print("\nDone.")

if __name__ == "__main__":
    main()
