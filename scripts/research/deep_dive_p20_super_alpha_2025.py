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


def wave_label_from_idx(df: pd.DataFrame, idx: int, horizon: int = 20) -> float | None:
    if idx + horizon >= len(df):
        return None
    c0 = float(df.iloc[idx]["close"])
    c_h = float(df.iloc[idx + horizon]["close"])
    ret = c_h / c0 - 1.0
    mdd = float(df.iloc[idx + 1 : idx + horizon + 1]["close"].min() / c0 - 1.0)
    return 1.0 if (ret > 0.08 and mdd > -0.08) else 0.0


def run(args: argparse.Namespace) -> dict[str, Any]:
    src = Path(args.source_csv)
    if not src.exists():
        raise FileNotFoundError(src)
    df = pd.read_csv(src)
    req = {"date", "symbol", "stock_p20", "adv50_vnd"}
    miss = req - set(df.columns)
    if miss:
        raise ValueError(f"Missing columns: {sorted(miss)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["stock_p20"] = pd.to_numeric(df["stock_p20"], errors="coerce")
    df["adv50_vnd"] = pd.to_numeric(df["adv50_vnd"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "stock_p20"]).copy()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    d0 = pd.Timestamp(args.from_date)
    d1 = pd.Timestamp(args.to_date)
    df = df[(df["date"] >= d0) & (df["date"] <= d1)].copy()

    client = get_client(timeout=45)
    symbols = sorted(df["symbol"].unique().tolist())
    hist_end = (d1 + pd.Timedelta(days=45)).strftime("%Y-%m-%d")

    hit_rows: list[dict[str, Any]] = []
    perf_rows: list[dict[str, Any]] = []
    for sym in symbols:
        sdf = client.get_ohlcv(sym, start=args.history_start, end=hist_end)
        if sdf.empty:
            continue
        sdf = sdf.sort_values("date").reset_index(drop=True)
        sdf["date"] = pd.to_datetime(sdf["date"], errors="coerce")
        sdf["close"] = pd.to_numeric(sdf["close"], errors="coerce")
        sdf = sdf.dropna(subset=["date", "close"]).copy()
        if sdf.empty:
            continue
        idx_map = {pd.Timestamp(d).normalize(): i for i, d in enumerate(sdf["date"])}

        # Symbol-level realized run quality during Mar-Jul 2025
        sub_period = sdf[(sdf["date"] >= d0) & (sdf["date"] <= d1)].copy()
        if len(sub_period) >= 2:
            c_first = float(sub_period["close"].iloc[0])
            c_max = float(sub_period["close"].max())
            period_run = c_max / c_first - 1.0
        else:
            period_run = np.nan
        perf_rows.append({"symbol": sym, "period_max_run": period_run})

        sym_events = df[df["symbol"] == sym].copy()
        for _, r in sym_events.iterrows():
            dt = pd.Timestamp(r["date"]).normalize()
            idx = idx_map.get(dt)
            if idx is None:
                continue
            y = wave_label_from_idx(sdf, idx, horizon=args.horizon)
            if y is None:
                continue
            hit_rows.append(
                {
                    "symbol": sym,
                    "date": dt.strftime("%Y-%m-%d"),
                    "stock_p20": float(r["stock_p20"]),
                    "adv50_vnd": float(r["adv50_vnd"]) if np.isfinite(r["adv50_vnd"]) else np.nan,
                    "label_wave_20d": y,
                }
            )

    hits = pd.DataFrame(hit_rows)
    if hits.empty:
        raise RuntimeError("No evaluable events.")

    by_symbol = (
        hits.groupby("symbol", as_index=False)
        .agg(
            count=("symbol", "size"),
            mean_p20=("stock_p20", "mean"),
            sum_p20=("stock_p20", "sum"),
            value_weighted_p20=("stock_p20", lambda s: float((s * hits.loc[s.index, "adv50_vnd"].fillna(0)).sum())),
            hit_rate=("label_wave_20d", "mean"),
            hits=("label_wave_20d", "sum"),
        )
        .sort_values(["sum_p20", "count"], ascending=[False, False])
        .reset_index(drop=True)
    )
    by_symbol["hits"] = by_symbol["hits"].astype(int)
    by_symbol = by_symbol.merge(pd.DataFrame(perf_rows), on="symbol", how="left")

    # Compare selection logic for "super alpha catch"
    metrics = {
        "count": by_symbol.sort_values("count", ascending=False),
        "mean_p20": by_symbol.sort_values("mean_p20", ascending=False),
        "sum_p20": by_symbol.sort_values("sum_p20", ascending=False),
        "value_weighted_p20": by_symbol.sort_values("value_weighted_p20", ascending=False),
    }
    eval_rows = []
    for name, frame in metrics.items():
        top = frame.head(args.top_n_eval).copy()
        eval_rows.append(
            {
                "metric": name,
                "top_n": args.top_n_eval,
                "avg_hit_rate": float(top["hit_rate"].mean()),
                "avg_period_max_run": float(top["period_max_run"].mean()),
                "n_symbols": int(len(top)),
                "contains_VIC": bool((top["symbol"] == "VIC").any()),
                "contains_GEX": bool((top["symbol"] == "GEX").any()),
                "contains_DDV": bool((top["symbol"] == "DDV").any()),
                "contains_SBT": bool((top["symbol"] == "SBT").any()),
            }
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    by_symbol.to_csv(out_dir / "deep_dive_symbol_scores_2025_mar_jul.csv", index=False)
    hits.to_csv(out_dir / "deep_dive_event_labels_2025_mar_jul.csv", index=False)
    pd.DataFrame(eval_rows).to_csv(out_dir / "deep_dive_metric_compare_2025_mar_jul.csv", index=False)

    return {
        "source": "FireAnt",
        "method": "REST API",
        "date_range": {"from": args.from_date, "to": args.to_date},
        "values_native_or_proxy": "native stock OHLCV; no index proxy used for labels",
        "symbols_used": len(symbols),
        "events_evaluable": int(len(hits)),
        "top_n_eval": args.top_n_eval,
        "outputs": {
            "symbol_scores": str(out_dir / "deep_dive_symbol_scores_2025_mar_jul.csv"),
            "event_labels": str(out_dir / "deep_dive_event_labels_2025_mar_jul.csv"),
            "metric_compare": str(out_dir / "deep_dive_metric_compare_2025_mar_jul.csv"),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source-csv",
        default=str(REPO / "data" / "research" / "daily_top20_stock_p20_2025-03_to_07_adv2bn.csv"),
    )
    ap.add_argument("--from-date", default="2025-03-01")
    ap.add_argument("--to-date", default="2025-07-31")
    ap.add_argument("--history-start", default="2025-01-01")
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--top-n-eval", type=int, default=30)
    ap.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = ap.parse_args()
    out = run(args)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

