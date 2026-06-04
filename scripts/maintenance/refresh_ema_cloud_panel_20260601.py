"""One-shot: update ohlcv_panel_ext2012.parquet through 2026-06-01."""
from __future__ import annotations
import sys, time
from pathlib import Path
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.data.fireant_client import get_client

PANEL_PATH = REPO / "data/research/ema_cloud/ohlcv_panel_ext2012.parquet"
START_FETCH = "2026-05-30"
END_FETCH = "2026-06-01"

def main() -> int:
    client = get_client()
    panel = pd.read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel_last = panel["date"].max()
    print(f"Panel last: {panel_last.date()}, fetching {START_FETCH} -> {END_FETCH}")

    symbols = sorted(panel[panel["date"] == panel_last]["symbol"].astype(str).str.upper().unique())
    print(f"Symbols: {len(symbols)}")

    chunks = []
    n_fail = 0
    for i, sym in enumerate(symbols, 1):
        try:
            raw = client.get_ohlcv(sym, start=START_FETCH, end=END_FETCH)
            if raw is None or raw.empty:
                n_fail += 1
                continue
            raw = raw.copy()
            raw["symbol"] = sym
            chunks.append(raw)
        except Exception:
            n_fail += 1
        if i % 50 == 0:
            print(f"  ... {i}/{len(symbols)} updated={len(chunks)} fail={n_fail}")
        time.sleep(0.05)

    if not chunks:
        print(f"No new data. fail={n_fail}")
        return 1

    add = pd.concat(chunks, ignore_index=True)
    add["date"] = pd.to_datetime(add["date"]).dt.normalize()
    panel = (
        pd.concat([panel, add], ignore_index=True)
        .drop_duplicates(subset=["symbol", "date"], keep="last")
        .sort_values(["symbol", "date"])
    )
    panel.to_parquet(PANEL_PATH, index=False)
    last = panel["date"].max().date()
    rows_added = sum(len(c) for c in chunks)
    print(f"Panel updated: last={last}, rows_added={rows_added}, fail={n_fail}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
