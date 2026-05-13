#!/usr/bin/env python3
"""
Fetch OHLCV from FireAnt for 2012-01-01 to 2017-12-31 and extend the research panel.

Steps:
  1. Fetch each symbol in the liquid universe for 2012-2017
  2. Merge with existing ohlcv_panel_full.parquet (which starts 2018-01-02)
  3. Save as data/research/ema_cloud/ohlcv_panel_ext2012.parquet

Usage:
    .venv\\Scripts\\python.exe scripts/research/fetch_pre2018_ext.py
    .venv\\Scripts\\python.exe scripts/research/fetch_pre2018_ext.py --delay 0.20
    .venv\\Scripts\\python.exe scripts/research/fetch_pre2018_ext.py --merge-only
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

UNIVERSE_FILE = REPO / "config" / "universe_liquid_adv50_2b.txt"
OUT_DIR       = REPO / "data" / "research" / "ema_cloud"
FULL_PARQUET  = OUT_DIR / "ohlcv_panel_full.parquet"
PRE_PARQUET   = OUT_DIR / "ohlcv_pre2018.parquet"
EXT_PARQUET   = OUT_DIR / "ohlcv_panel_ext2012.parquet"

FETCH_START = "2012-01-01"
FETCH_END   = "2017-12-31"


def load_universe() -> list[str]:
    return [s.strip() for s in UNIVERSE_FILE.read_text().splitlines() if s.strip()]


def fetch_symbol(client, symbol: str, start: str, end: str) -> pd.DataFrame:
    try:
        df = client.get_ohlcv(symbol, start=start, end=end)
        if df is None or df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        if "value" not in df.columns:
            df["value"] = df["close"] * df["volume"] * 1000
        df["symbol"] = symbol
        cols = ["symbol", "date", "open", "high", "low", "close", "volume", "value"]
        return df[[c for c in cols if c in df.columns]]
    except Exception as exc:
        log.warning("  %s: %s", symbol, exc)
        return pd.DataFrame()


def fetch_pre2018(symbols: list[str], delay: float) -> pd.DataFrame:
    log.info("Fetching %s to %s for %d symbols (delay=%.2fs)...",
             FETCH_START, FETCH_END, len(symbols), delay)
    client = get_client(timeout=60)
    frames = []
    ok, empty = 0, 0
    for i, sym in enumerate(symbols, 1):
        df = fetch_symbol(client, sym, FETCH_START, FETCH_END)
        if not df.empty:
            frames.append(df)
            ok += 1
        else:
            empty += 1
        if i % 30 == 0:
            log.info("  %d/%d  ok=%d  empty=%d", i, len(symbols), ok, empty)
        time.sleep(delay)

    log.info("Fetch complete: %d symbols with data, %d no pre-2018 data", ok, empty)
    if not frames:
        log.warning("No pre-2018 data found — these symbols may all start 2018+")
        return pd.DataFrame()

    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= FETCH_START) & (panel["date"] <= FETCH_END)].copy()
    panel.sort_values(["symbol", "date"], inplace=True)
    panel.reset_index(drop=True, inplace=True)
    log.info("  pre-2018 panel: %d symbols, %d rows, %s to %s",
             panel["symbol"].nunique(), len(panel),
             panel["date"].min().date(), panel["date"].max().date())
    return panel


def merge_with_full(panel_pre: pd.DataFrame) -> pd.DataFrame:
    if not FULL_PARQUET.exists():
        log.error("ohlcv_panel_full.parquet not found at %s", FULL_PARQUET)
        raise FileNotFoundError(FULL_PARQUET)

    panel_full = pd.read_parquet(FULL_PARQUET)
    panel_full["date"] = pd.to_datetime(panel_full["date"])
    log.info("Loaded full panel: %d symbols, %d rows, %s to %s",
             panel_full["symbol"].nunique(), len(panel_full),
             panel_full["date"].min().date(), panel_full["date"].max().date())

    if panel_pre.empty:
        log.warning("No pre-2018 data to merge — returning full panel as-is")
        return panel_full

    # Trim pre-2018 to only rows before the full panel's start
    cutoff = panel_full["date"].min()
    pre_trimmed = panel_pre[panel_pre["date"] < cutoff].copy()
    log.info("Pre-2018 rows before %s: %d", cutoff.date(), len(pre_trimmed))

    combined = pd.concat([pre_trimmed, panel_full], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined.sort_values(["symbol", "date"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    log.info("Extended panel: %d symbols, %d rows, %s to %s",
             combined["symbol"].nunique(), len(combined),
             combined["date"].min().date(), combined["date"].max().date())
    return combined


def print_coverage(panel: pd.DataFrame) -> None:
    print("\nCoverage by year:")
    years = panel["date"].dt.year
    for yr in range(2012, 2027):
        sub = panel[years == yr]
        if len(sub):
            print(f"  {yr}: {sub['symbol'].nunique():3d} symbols, {len(sub):7d} rows")

    # Symbols with pre-2018 data
    pre = panel[panel["date"] < "2018-01-01"]
    print(f"\nSymbols with pre-2018 data: {pre['symbol'].nunique()}")
    min_dates = panel.groupby("symbol")["date"].min()
    early = min_dates[min_dates < "2018-01-01"].sort_values()
    print(f"Earliest start dates: {early.head(10).to_dict()}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--delay", type=float, default=0.15)
    p.add_argument("--merge-only", action="store_true",
                   help="Skip fetch, just merge existing PRE_PARQUET with FULL_PARQUET")
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.merge_only:
        if not PRE_PARQUET.exists():
            log.error("PRE_PARQUET not found: %s", PRE_PARQUET)
            sys.exit(1)
        panel_pre = pd.read_parquet(PRE_PARQUET)
        panel_pre["date"] = pd.to_datetime(panel_pre["date"])
    else:
        symbols = load_universe()
        log.info("Universe: %d symbols", len(symbols))
        panel_pre = fetch_pre2018(symbols, args.delay)
        if not panel_pre.empty:
            panel_pre.to_parquet(PRE_PARQUET)
            log.info("Saved pre-2018 raw: %s", PRE_PARQUET)

    panel_ext = merge_with_full(panel_pre)
    panel_ext.to_parquet(EXT_PARQUET)
    log.info("Saved: %s", EXT_PARQUET)
    print_coverage(panel_ext)
    print(f"\nExtended panel: {EXT_PARQUET}")


if __name__ == "__main__":
    main()
