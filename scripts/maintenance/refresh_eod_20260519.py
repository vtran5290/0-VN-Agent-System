#!/usr/bin/env python3
"""One-shot EOD refresh: VNINDEX CSV + panel + ta_vnindex through 2026-05-19."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client

TARGET = pd.Timestamp("2026-05-19")
VNINDEX_PATHS = [
    REPO / "minervini_backtest" / "data" / "raw" / "VNINDEX.csv",
    REPO / "data" / "fireant_exports" / "index_ohlcv" / "market" / "VNINDEX.csv",
]
VNINDEX_PARQUET = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
PANEL_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"


def _merge_vnindex_csv(path: Path, new_rows: pd.DataFrame) -> None:
    if path.exists():
        old = pd.read_csv(path)
        old["date"] = pd.to_datetime(old["date"])
    else:
        old = pd.DataFrame(columns=new_rows.columns)
    new_rows["date"] = pd.to_datetime(new_rows["date"])
    merged = (
        pd.concat([old, new_rows], ignore_index=True)
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(path, index=False)
    print(f"  VNINDEX {path.name}: last {merged['date'].iloc[-1].date()}")


def main() -> int:
    client = get_client()
    start = "2026-05-16"
    end = "2026-05-19"
    print(f"Fetching VNINDEX {start}..{end} (FireAnt)")
    vni = client.get_index_ohlcv("VNINDEX", start=start, end=end)
    if vni.empty:
        print("ERROR: no VNINDEX from API", file=sys.stderr)
        return 1
    for p in VNINDEX_PATHS:
        _merge_vnindex_csv(p, vni)

    if VNINDEX_PARQUET.exists():
        vp = pd.read_parquet(VNINDEX_PARQUET)
        vp["date"] = pd.to_datetime(vp["date"])
    else:
        vp = pd.DataFrame(columns=vni.columns)
    vp = (
        pd.concat([vp, vni], ignore_index=True)
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
    )
    vp.to_parquet(VNINDEX_PARQUET, index=False)
    print(f"  ta_vnindex.parquet: last {vp['date'].iloc[-1].date()}")

    panel = pd.read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel_last = panel["date"].max()
    if panel_last >= TARGET:
        print(f"Panel already through {panel_last.date()}")
        return 0

    symbols = sorted(panel[panel["date"] == panel_last]["symbol"].astype(str).str.upper().unique())
    print(f"Refreshing panel {len(symbols)} symbols for {panel_last.date()} -> {TARGET.date()}")
    start_p = (panel_last + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    end_p = TARGET.strftime("%Y-%m-%d")
    chunks: list[pd.DataFrame] = []
    n_fail = 0
    for i, sym in enumerate(symbols, 1):
        try:
            raw = client.get_ohlcv(sym, start=start_p, end=end_p)
            if raw is None or raw.empty:
                n_fail += 1
                continue
            raw = raw.copy()
            raw["symbol"] = sym
            chunks.append(raw)
        except Exception:
            n_fail += 1
        if i % 50 == 0:
            print(f"  ... {i}/{len(symbols)}")
        time.sleep(0.05)

    if chunks:
        add = pd.concat(chunks, ignore_index=True)
        add["date"] = pd.to_datetime(add["date"]).dt.normalize()
        panel = (
            pd.concat([panel, add], ignore_index=True)
            .drop_duplicates(subset=["symbol", "date"], keep="last")
            .sort_values(["symbol", "date"])
        )
        panel.to_parquet(PANEL_PATH, index=False)
    print(f"  panel: last {panel['date'].max().date()} rows_added={len(chunks)} fail={n_fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
