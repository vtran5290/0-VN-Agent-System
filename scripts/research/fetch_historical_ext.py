#!/usr/bin/env python3
"""
Fetch historical OHLCV from FireAnt API for 2018-2022 and extend the panel cache.

Steps:
  1. Read universe from config/universe_liquid_adv50_2b.txt
  2. Fetch 2018-01-01 to 2022-12-31 for each symbol via FireAnt API
  3. Compute value = close × volume × 1000 (same as existing panel)
  4. Save raw fetch as data/research/ema_cloud/ohlcv_panel_2018_2022.parquet
  5. Merge with existing ohlcv_panel_cache.parquet
  6. Save merged as data/research/ema_cloud/ohlcv_panel_full.parquet

Usage:
    .venv\\Scripts\\python.exe scripts/research/fetch_historical_ext.py
    .venv\\Scripts\\python.exe scripts/research/fetch_historical_ext.py --delay 0.20
    .venv\\Scripts\\python.exe scripts/research/fetch_historical_ext.py --merge-only
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

UNIVERSE_FILE  = REPO / "config" / "universe_liquid_adv50_2b.txt"
OUT_DIR        = REPO / "data" / "research" / "ema_cloud"
CACHE_PARQUET  = OUT_DIR / "ohlcv_panel_cache.parquet"
EXT_PARQUET    = OUT_DIR / "ohlcv_panel_2018_2022.parquet"
FULL_PARQUET   = OUT_DIR / "ohlcv_panel_full.parquet"

FETCH_START = "2018-01-01"
FETCH_END   = "2022-12-31"


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


def fetch_2018_2022(symbols: list[str], delay: float) -> pd.DataFrame:
    log.info("Fetching 2018-2022 for %d symbols (delay=%.2fs each)...", len(symbols), delay)
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
        if i % 25 == 0:
            log.info("  %d/%d  ok=%d  empty=%d", i, len(symbols), ok, empty)
        time.sleep(delay)

    log.info("Fetch complete: %d symbols with data, %d empty", ok, empty)
    if not frames:
        raise RuntimeError("No data returned — check FIREANT_TOKEN")

    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= FETCH_START) & (panel["date"] <= FETCH_END)].copy()
    panel.sort_values(["symbol", "date"], inplace=True)
    panel.reset_index(drop=True, inplace=True)
    log.info("  2018-2022 panel: %d symbols, %d rows", panel["symbol"].nunique(), len(panel))
    return panel


def merge_panels(panel_ext: pd.DataFrame, panel_existing: pd.DataFrame) -> pd.DataFrame:
    """Merge 2018-2022 (ext) with 2023-2026 (existing), no date overlaps."""
    cutoff = panel_existing["date"].min()
    log.info("Existing panel starts: %s  — keeping ext rows before that", cutoff.date())

    ext_trimmed = panel_ext[panel_ext["date"] < cutoff].copy()
    log.info("  ext rows before cutoff: %d", len(ext_trimmed))

    combined = pd.concat([ext_trimmed, panel_existing], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined.sort_values(["symbol", "date"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    log.info("  merged panel: %d symbols, %d rows  (%s to %s)",
             combined["symbol"].nunique(), len(combined),
             combined["date"].min().date(), combined["date"].max().date())
    return combined


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--delay", type=float, default=0.15,
                   help="Seconds between API calls (default 0.15)")
    p.add_argument("--merge-only", action="store_true",
                   help="Skip fetch, just merge existing EXT_PARQUET with CACHE_PARQUET")
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.merge_only:
        if not EXT_PARQUET.exists():
            log.error("EXT_PARQUET not found: %s", EXT_PARQUET)
            sys.exit(1)
        panel_ext = pd.read_parquet(EXT_PARQUET)
        panel_ext["date"] = pd.to_datetime(panel_ext["date"])
    else:
        symbols = load_universe()
        log.info("Universe: %d symbols", len(symbols))

        panel_ext = fetch_2018_2022(symbols, args.delay)
        panel_ext.to_parquet(EXT_PARQUET)
        log.info("Saved: %s", EXT_PARQUET)

    # Merge with existing panel
    if not CACHE_PARQUET.exists():
        log.warning("Existing cache not found — saving ext panel as full panel")
        panel_ext.to_parquet(FULL_PARQUET)
        log.info("Saved: %s", FULL_PARQUET)
        return

    panel_existing = pd.read_parquet(CACHE_PARQUET)
    panel_existing["date"] = pd.to_datetime(panel_existing["date"])

    panel_full = merge_panels(panel_ext, panel_existing)
    panel_full.to_parquet(FULL_PARQUET)
    log.info("Saved: %s", FULL_PARQUET)

    # Print coverage summary
    print("\nCoverage by year:")
    for yr in range(2018, 2027):
        sub = panel_full[panel_full["date"].dt.year == yr]
        if len(sub):
            print(f"  {yr}: {sub['symbol'].nunique():3d} symbols, {len(sub):6d} rows")

    print(f"\nFull panel: {FULL_PARQUET}")
    print("Next step: update vn_quant_phase6.py CACHE_PARQUET to point to ohlcv_panel_full.parquet")
    print("Then re-run phase6 to test C06 on the 2018-2022 bear market periods.")


if __name__ == "__main__":
    main()
