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


def parse_periods(spec: str) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    out: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for part in [x.strip() for x in spec.split(",") if x.strip()]:
        # label:start:end
        label, s, e = part.split(":")
        out.append((label, pd.Timestamp(s), pd.Timestamp(e)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--panel-csv",
        default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"),
    )
    ap.add_argument("--history-start", default="2022-01-01")
    ap.add_argument("--history-end", default="2026-12-31")
    ap.add_argument(
        "--periods",
        default="P_2023:2023-01-01:2023-12-31,P_2024:2024-01-01:2024-12-31,P_2025:2025-01-01:2025-12-31,P_2025_MarJul:2025-03-01:2025-07-31,P_2026_YTD:2026-01-01:2026-04-30",
    )
    ap.add_argument("--out-csv", default=str(REPO / "data" / "research" / "p20_monotonicity_full_universe.csv"))
    ap.add_argument("--out-json", default=str(REPO / "data" / "research" / "p20_monotonicity_full_universe.json"))
    args = ap.parse_args()

    panel = pd.read_csv(args.panel_csv)
    req = ["date", "symbol", "p20", "fwd_ret20", "label_wave20"]
    miss = [c for c in req if c not in panel.columns]
    if miss:
        raise ValueError(f"Missing required columns: {miss}")
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel["symbol"] = panel["symbol"].astype(str).str.upper()
    panel["p20"] = pd.to_numeric(panel["p20"], errors="coerce")
    panel["fwd_ret20"] = pd.to_numeric(panel["fwd_ret20"], errors="coerce")
    panel["label_wave20"] = pd.to_numeric(panel["label_wave20"], errors="coerce")
    panel = panel.dropna(subset=["date", "symbol", "p20", "fwd_ret20"]).copy()

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

    rows = []
    for _, r in panel.iterrows():
        sym = r["symbol"]
        dt = pd.Timestamp(r["date"]).normalize()
        p20 = float(r["p20"])
        f20 = float(r["fwd_ret20"])
        lab20 = float(r["label_wave20"]) if np.isfinite(r["label_wave20"]) else np.nan
        h = cache.get(sym)
        if h is None or h.empty:
            continue
        dates = h["date"].tolist()
        try:
            i = dates.index(dt)
        except ValueError:
            continue
        c0 = float(h.at[i, "close"])
        f50 = np.nan
        f100 = np.nan
        if i + 50 < len(h):
            f50 = float(h.at[i + 50, "close"] / c0 - 1.0)
        if i + 100 < len(h):
            f100 = float(h.at[i + 100, "close"] / c0 - 1.0)
        rows.append(
            {
                "date": dt,
                "symbol": sym,
                "p20": p20,
                "p20_bucket": bucket_p20(p20),
                "ret20": f20,
                "ret50": f50,
                "ret100": f100,
                "wave20": lab20,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No rows after mapping horizons.")

    periods = parse_periods(args.periods)
    out_rows = []
    for label, s, e in periods:
        sub = df[(df["date"] >= s) & (df["date"] <= e)].copy()
        if sub.empty:
            continue
        for b, g in sub.groupby("p20_bucket"):
            for hz, col in [(20, "ret20"), (50, "ret50"), (100, "ret100")]:
                gg = g.dropna(subset=[col]).copy()
                if gg.empty:
                    continue
                profitable = float((gg[col] > 0).mean())
                win8 = float((gg[col] > 0.08).mean())
                out_rows.append(
                    {
                        "period": label,
                        "horizon": hz,
                        "p20_bucket": b,
                        "n": int(len(gg)),
                        "profitable_rate": profitable,
                        "winner8_rate": win8,
                        "avg_ret": float(gg[col].mean()),
                        "median_ret": float(gg[col].median()),
                    }
                )
    out = pd.DataFrame(out_rows).sort_values(["period", "horizon", "p20_bucket"]).reset_index(drop=True)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out_csv, index=False)

    payload = {
        "source": "FireAnt",
        "method": "REST API + horizon mapping on full ADV>=2bn panel universe",
        "panel_source": str(args.panel_csv),
        "periods": [{"label": l, "start": str(s.date()), "end": str(e.date())} for l, s, e in periods],
        "rows_panel_input": int(len(panel)),
        "rows_horizon_mapped": int(len(df)),
        "out_csv": str(args.out_csv),
    }
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

