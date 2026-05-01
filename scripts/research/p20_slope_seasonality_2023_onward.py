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


def slope_state(v: float) -> str:
    if not np.isfinite(v):
        return "nan"
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return "flat"


def bucket_p20(v: float) -> str:
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
    ap.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--history-start", default="2022-01-01")
    ap.add_argument("--history-end", default="2026-12-31")
    ap.add_argument("--slope-lookback", type=int, default=5)
    ap.add_argument(
        "--out-csv",
        default=str(REPO / "data" / "research" / "p20_slope_seasonality_2023_onward.csv"),
    )
    ap.add_argument(
        "--out-json",
        default=str(REPO / "data" / "research" / "p20_slope_seasonality_2023_onward.json"),
    )
    args = ap.parse_args()

    panel = pd.read_csv(args.panel_csv)
    for c in ["date", "symbol", "p20", "fwd_ret20"]:
        if c not in panel.columns:
            raise ValueError(f"Missing column: {c}")
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel["symbol"] = panel["symbol"].astype(str).str.upper()
    panel["p20"] = pd.to_numeric(panel["p20"], errors="coerce")
    panel["fwd_ret20"] = pd.to_numeric(panel["fwd_ret20"], errors="coerce")
    panel = panel.dropna(subset=["date", "symbol", "p20"]).sort_values(["symbol", "date"]).copy()
    panel = panel[(panel["date"] >= pd.Timestamp(args.start)) & (panel["date"] <= pd.Timestamp(args.end))].copy()

    panel["p20_slope"] = panel.groupby("symbol")["p20"].transform(lambda s: s / s.shift(args.slope_lookback) - 1.0)
    panel["slope_state"] = panel["p20_slope"].map(slope_state)
    panel["p20_bucket"] = panel["p20"].map(bucket_p20)

    # map 50/100-day returns
    c = get_client(timeout=45)
    symbols = sorted(panel["symbol"].unique().tolist())
    cache: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        h = c.get_ohlcv(sym, start=args.history_start, end=args.history_end)
        if h.empty:
            cache[sym] = pd.DataFrame()
            continue
        x = h[["date", "close"]].copy()
        x["date"] = pd.to_datetime(x["date"], errors="coerce").dt.normalize()
        x["close"] = pd.to_numeric(x["close"], errors="coerce")
        x = x.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
        cache[sym] = x

    rows: list[dict[str, Any]] = []
    for _, r in panel.iterrows():
        sym = r["symbol"]
        dt = pd.Timestamp(r["date"]).normalize()
        h = cache.get(sym)
        if h is None or h.empty:
            continue
        dates = h["date"].tolist()
        try:
            i = dates.index(dt)
        except ValueError:
            continue
        c0 = float(h.at[i, "close"])
        ret20 = float(r["fwd_ret20"]) if np.isfinite(r["fwd_ret20"]) else np.nan
        ret50 = np.nan
        ret100 = np.nan
        if i + 50 < len(h):
            ret50 = float(h.at[i + 50, "close"] / c0 - 1.0)
        if i + 100 < len(h):
            ret100 = float(h.at[i + 100, "close"] / c0 - 1.0)

        q = pd.Timestamp(dt).quarter
        y = pd.Timestamp(dt).year
        hy = "H1" if q in (1, 2) else "H2"
        rows.append(
            {
                "date": dt,
                "year": y,
                "quarter": f"Q{q}",
                "half": hy,
                "year_quarter": f"{y}-Q{q}",
                "year_half": f"{y}-{hy}",
                "symbol": sym,
                "p20": float(r["p20"]),
                "p20_bucket": r["p20_bucket"],
                "p20_slope": float(r["p20_slope"]) if np.isfinite(r["p20_slope"]) else np.nan,
                "slope_state": r["slope_state"],
                "ret20": ret20,
                "ret50": ret50,
                "ret100": ret100,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No rows for seasonality analysis.")

    agg_rows: list[dict[str, Any]] = []
    # 1) quarter-level and half-level correlations
    for period_col in ["year_quarter", "year_half"]:
        for key, g in df.groupby(period_col):
            for hz, col in [(20, "ret20"), (50, "ret50"), (100, "ret100")]:
                z = g[["p20_slope", col]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(z) < 20:
                    continue
                agg_rows.append(
                    {
                        "period_type": period_col,
                        "period_key": key,
                        "horizon": hz,
                        "slice": "all",
                        "n": int(len(z)),
                        "corr_p20slope_ret": float(z["p20_slope"].corr(z[col])),
                        "profitable_rate": float((z[col] > 0).mean()),
                        "avg_ret": float(z[col].mean()),
                    }
                )

    # 2) quarter/half x slope_state x p20_bucket
    for period_col in ["year_quarter", "year_half"]:
        for key, g in df.groupby(period_col):
            for (st, b), gg in g.groupby(["slope_state", "p20_bucket"]):
                if st == "nan":
                    continue
                for hz, col in [(20, "ret20"), (50, "ret50"), (100, "ret100")]:
                    z = gg.dropna(subset=[col])
                    if len(z) < 10:
                        continue
                    agg_rows.append(
                        {
                            "period_type": period_col,
                            "period_key": key,
                            "horizon": hz,
                            "slice": f"{st}|{b}",
                            "n": int(len(z)),
                            "corr_p20slope_ret": np.nan,
                            "profitable_rate": float((z[col] > 0).mean()),
                            "avg_ret": float(z[col].mean()),
                        }
                    )

    out = pd.DataFrame(agg_rows).sort_values(["period_type", "period_key", "horizon", "slice"]).reset_index(drop=True)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)

    payload = {
        "source": "FireAnt",
        "method": "REST API + p20 slope seasonality by quarter/half-year",
        "date_range": {"start": args.start, "end": args.end},
        "slope_lookback_days": args.slope_lookback,
        "rows_used": int(len(df)),
        "out_csv": str(args.out_csv),
    }
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

