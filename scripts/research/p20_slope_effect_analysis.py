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


def slope_state(v: float) -> str:
    if not np.isfinite(v):
        return "nan"
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return "flat"


def parse_periods(spec: str) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    out: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for part in [x.strip() for x in spec.split(",") if x.strip()]:
        label, s, e = part.split(":")
        out.append((label, pd.Timestamp(s), pd.Timestamp(e)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    ap.add_argument("--history-start", default="2022-01-01")
    ap.add_argument("--history-end", default="2026-12-31")
    ap.add_argument("--slope-lookback", type=int, default=5, help="Trading-day lookback for p20 slope.")
    ap.add_argument(
        "--periods",
        default="P_2023:2023-01-01:2023-12-31,P_2024:2024-01-01:2024-12-31,P_2025:2025-01-01:2025-12-31,P_2025_MarJul:2025-03-01:2025-07-31,P_2026_YTD:2026-01-01:2026-04-30",
    )
    ap.add_argument("--out-csv", default=str(REPO / "data" / "research" / "p20_slope_effect_analysis.csv"))
    ap.add_argument("--out-json", default=str(REPO / "data" / "research" / "p20_slope_effect_analysis.json"))
    args = ap.parse_args()

    panel = pd.read_csv(args.panel_csv)
    req = ["date", "symbol", "p20", "fwd_ret20"]
    miss = [c for c in req if c not in panel.columns]
    if miss:
        raise ValueError(f"Missing required columns: {miss}")
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel["symbol"] = panel["symbol"].astype(str).str.upper()
    panel["p20"] = pd.to_numeric(panel["p20"], errors="coerce")
    panel["fwd_ret20"] = pd.to_numeric(panel["fwd_ret20"], errors="coerce")
    panel = panel.dropna(subset=["date", "symbol", "p20"]).sort_values(["symbol", "date"]).copy()

    # p20 slope at date t uses only prior data (no look-ahead)
    panel["p20_slope"] = panel.groupby("symbol")["p20"].transform(
        lambda s: s / s.shift(args.slope_lookback) - 1.0
    )
    panel["slope_state"] = panel["p20_slope"].map(slope_state)
    panel["p20_bucket"] = panel["p20"].map(bucket_p20)

    # Map 50/100d returns from FireAnt OHLCV
    symbols = sorted(panel["symbol"].unique().tolist())
    c = get_client(timeout=45)
    cache: dict[str, pd.DataFrame] = {}
    for s in symbols:
        h = c.get_ohlcv(s, start=args.history_start, end=args.history_end)
        if h.empty:
            cache[s] = pd.DataFrame()
            continue
        x = h[["date", "close"]].copy()
        x["date"] = pd.to_datetime(x["date"], errors="coerce").dt.normalize()
        x["close"] = pd.to_numeric(x["close"], errors="coerce")
        x = x.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
        cache[s] = x

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
        r50 = np.nan
        r100 = np.nan
        if i + 50 < len(h):
            r50 = float(h.at[i + 50, "close"] / c0 - 1.0)
        if i + 100 < len(h):
            r100 = float(h.at[i + 100, "close"] / c0 - 1.0)
        rows.append(
            {
                "date": dt,
                "symbol": sym,
                "p20": float(r["p20"]),
                "p20_bucket": r["p20_bucket"],
                "p20_slope": float(r["p20_slope"]) if np.isfinite(r["p20_slope"]) else np.nan,
                "slope_state": r["slope_state"],
                "ret20": float(r["fwd_ret20"]) if np.isfinite(r["fwd_ret20"]) else np.nan,
                "ret50": r50,
                "ret100": r100,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No mapped rows for slope analysis.")

    periods = parse_periods(args.periods)
    out_rows = []
    corr_rows = []
    for label, s, e in periods:
        sub = df[(df["date"] >= s) & (df["date"] <= e)].copy()
        if sub.empty:
            continue
        # overall correlation between slope and forward returns
        for hz, col in [(20, "ret20"), (50, "ret50"), (100, "ret100")]:
            z = sub[["p20_slope", col]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(z) < 30:
                continue
            corr_rows.append(
                {
                    "period": label,
                    "horizon": hz,
                    "n": int(len(z)),
                    "corr_p20slope_ret": float(z["p20_slope"].corr(z[col])),
                }
            )
        # bucket + slope state profitability
        for (b, st), g in sub.groupby(["p20_bucket", "slope_state"]):
            if st == "nan":
                continue
            for hz, col in [(20, "ret20"), (50, "ret50"), (100, "ret100")]:
                gg = g.dropna(subset=[col])
                if gg.empty:
                    continue
                out_rows.append(
                    {
                        "period": label,
                        "horizon": hz,
                        "p20_bucket": b,
                        "slope_state": st,
                        "n": int(len(gg)),
                        "profitable_rate": float((gg[col] > 0).mean()),
                        "winner8_rate": float((gg[col] > 0.08).mean()),
                        "avg_ret": float(gg[col].mean()),
                        "median_ret": float(gg[col].median()),
                    }
                )

    out = pd.DataFrame(out_rows).sort_values(["period", "horizon", "p20_bucket", "slope_state"]).reset_index(drop=True)
    cor = pd.DataFrame(corr_rows).sort_values(["period", "horizon"]).reset_index(drop=True)

    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)
    corr_csv = Path(args.out_csv).with_name("p20_slope_correlation_summary.csv")
    cor.to_csv(corr_csv, index=False)

    payload = {
        "source": "FireAnt",
        "method": "REST API + full-universe p20 slope effect test",
        "panel_source": str(args.panel_csv),
        "slope_lookback_days": args.slope_lookback,
        "periods": [{"label": l, "start": str(s.date()), "end": str(e.date())} for l, s, e in periods],
        "rows_used": int(len(df)),
        "out_csv_bucket_slope": str(args.out_csv),
        "out_csv_corr": str(corr_csv),
    }
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

