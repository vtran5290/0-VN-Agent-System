#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402


def p20_bucket(v: float) -> str:
    if not np.isfinite(v):
        return "nan"
    if v < 0.45:
        return "<0.45"
    if v < 0.55:
        return "0.45-0.55"
    if v < 0.65:
        return "0.55-0.65"
    if v < 0.75:
        return "0.65-0.75"
    return ">=0.75"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--signal-csv",
        default=str(REPO / "data" / "research" / "daily_top20_stock_p20_2025-03_to_07_adv2bn.csv"),
    )
    ap.add_argument("--history-start", default="2024-01-01")
    ap.add_argument("--history-end", default="2026-12-31")
    ap.add_argument("--out-csv", default=str(REPO / "data" / "research" / "p20_horizon_stack_analysis.csv"))
    ap.add_argument("--out-json", default=str(REPO / "data" / "research" / "p20_horizon_stack_analysis.json"))
    args = ap.parse_args()

    sig = pd.read_csv(args.signal_csv)
    sig["date"] = pd.to_datetime(sig["date"], errors="coerce")
    sig["stock_p20"] = pd.to_numeric(sig["stock_p20"], errors="coerce")
    sig["symbol"] = sig["symbol"].astype(str).str.upper()
    sig = sig.dropna(subset=["date", "symbol", "stock_p20"]).copy()

    symbols = sorted(sig["symbol"].unique().tolist())
    c = get_client(timeout=45)
    cache: dict[str, pd.DataFrame] = {}
    for s in symbols:
        h = c.get_ohlcv(s, start=args.history_start, end=args.history_end)
        if h.empty:
            cache[s] = pd.DataFrame()
            continue
        x = h[["date", "close"]].copy()
        x["date"] = pd.to_datetime(x["date"], errors="coerce")
        x["close"] = pd.to_numeric(x["close"], errors="coerce")
        x = x.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
        cache[s] = x

    rows: list[dict[str, Any]] = []
    horizons = [20, 50, 100]
    for _, r in sig.iterrows():
        sym = r["symbol"]
        dt = pd.Timestamp(r["date"]).normalize()
        p20 = float(r["stock_p20"])
        h = cache.get(sym)
        if h is None or h.empty:
            continue
        dates = h["date"].dt.normalize().to_list()
        try:
            i = dates.index(dt)
        except ValueError:
            continue
        c0 = float(h.at[i, "close"])
        for hz in horizons:
            j = i + hz
            if j >= len(h):
                continue
            c1 = float(h.at[j, "close"])
            ret = c1 / c0 - 1.0
            rows.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "symbol": sym,
                    "p20": p20,
                    "p20_bucket": p20_bucket(p20),
                    "horizon": hz,
                    "ret": ret,
                    "profitable": 1.0 if ret > 0 else 0.0,
                    "winner_8pct": 1.0 if ret > 0.08 else 0.0,
                }
            )

    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("No evaluable rows.")

    summary = (
        out.groupby(["horizon", "p20_bucket"], as_index=False)
        .agg(
            n=("ret", "size"),
            profitable_rate=("profitable", "mean"),
            winner8_rate=("winner_8pct", "mean"),
            avg_ret=("ret", "mean"),
            median_ret=("ret", "median"),
        )
        .sort_values(["horizon", "p20_bucket"])
    )

    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out_csv, index=False)
    payload = {
        "source": "FireAnt",
        "method": "REST API + forward return mapping by trading-day horizon",
        "signal_source": str(args.signal_csv),
        "date_range_signal": {
            "start": sig["date"].min().strftime("%Y-%m-%d"),
            "end": sig["date"].max().strftime("%Y-%m-%d"),
        },
        "horizons": horizons,
        "rows_evaluable": int(len(out)),
        "summary_csv": str(args.out_csv),
    }
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

