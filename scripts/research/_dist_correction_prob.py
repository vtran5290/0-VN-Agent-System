#!/usr/bin/env python3
"""Historical P(correction/downtrend) given current distribution counts (full VNINDEX)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.research.vnindex_dist_v2.dist_rule import add_dist_day

HORIZONS = (10, 20, 50, 100)
# correction proxies
THRESHOLDS = {
    "dd_5pct": -0.05,
    "dd_10pct": -0.10,
    "below_ma50_20d": None,
}


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    d = add_dist_day(df, "close", "volume")
    c = d["close"].astype(float)
    d["ma50"] = c.rolling(50, min_periods=50).mean()
    d["dist_10"] = d["dist_day"].fillna(0).rolling(10).sum()
    d["dist_20"] = d["dist_day"].fillna(0).rolling(20).sum()
    d["ret_5d"] = c / c.shift(5) - 1
    d["ret_20d"] = c / c.shift(20) - 1
    return d


def forward_metrics(df: pd.DataFrame, i: int, h: int) -> dict:
    closes = df["close"].astype(float).values
    ma50 = df["ma50"].astype(float).values
    n = len(df)
    j = i + h
    if j >= n:
        return {}
    c0, cj = closes[i], closes[j]
    if not (np.isfinite(c0) and np.isfinite(cj) and c0 > 0):
        return {}
    ret = cj / c0 - 1
    path = closes[i : j + 1]
    peak = float(np.max(path))
    max_dd = float(np.min(path) / peak - 1) if peak > 0 else np.nan
    below_ma50 = bool(np.isfinite(ma50[j]) and cj < ma50[j])
    return {"ret": ret, "max_dd": max_dd, "below_ma50_end": below_ma50}


def summarize_matches(df: pd.DataFrame, mask: pd.Series, label: str) -> dict:
    idx = np.where(mask.values)[0]
    idx = [i for i in idx if i < len(df) - max(HORIZONS) - 1]
    out = {"label": label, "n_anchors": len(idx)}
    if not idx:
        return out
    for h in HORIZONS:
        rets, dds, ma50_flags = [], [], []
        for i in idx:
            m = forward_metrics(df, i, h)
            if not m:
                continue
            rets.append(m["ret"])
            dds.append(m["max_dd"])
            ma50_flags.append(m["below_ma50_end"])
        if not rets:
            continue
        a = np.array(rets)
        out[f"{h}d"] = {
            "n": int(len(a)),
            "prob_ret_negative": round(float((a < 0).mean()), 3),
            "prob_dd_worse_5pct": round(float((np.array(dds) <= -0.05).mean()), 3),
            "prob_dd_worse_10pct": round(float((np.array(dds) <= -0.10).mean()), 3),
            "prob_below_ma50_end": round(float(np.mean(ma50_flags)), 3),
            "mean_ret_pct": round(float(a.mean()) * 100, 2),
            "median_ret_pct": round(float(np.median(a)) * 100, 2),
            "p10_ret_pct": round(float(np.percentile(a, 10)) * 100, 2),
            "p25_ret_pct": round(float(np.percentile(a, 25)) * 100, 2),
        }
    return out


def main() -> None:
    vni = pd.read_parquet(REPO / "data/fireant_ssot/ta_vnindex.parquet")
    vni["date"] = pd.to_datetime(vni["date"])
    try:
        from src.intake.fireant_historical import fetch_historical
        from datetime import date

        end = date.today().isoformat()
        last = vni["date"].max()
        if last < pd.Timestamp(end):
            rows = fetch_historical("VNINDEX", (last - pd.Timedelta(days=5)).date().isoformat(), end)
            if rows:
                extra = pd.DataFrame(
                    [
                        {
                            "date": pd.Timestamp(r.d),
                            "open": float(r.o),
                            "high": float(r.h),
                            "low": float(r.l),
                            "close": float(r.c),
                            "volume": float(r.v) if r.v is not None else np.nan,
                        }
                        for r in rows
                    ]
                )
                vni = pd.concat([vni, extra], ignore_index=True)
                vni = vni.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    except Exception as exc:
        print("fetch warn", exc, file=sys.stderr)

    df = enrich(vni.reset_index(drop=True))
    row = df.iloc[-1]
    cur = {
        "asof": str(row["date"].date()),
        "close": round(float(row["close"]), 2),
        "dist_10d": int(row["dist_10"]),
        "dist_20d": int(row["dist_20"]),
        "today_dist": bool(row["dist_day"] == 1),
        "above_ma50": bool(float(row["close"]) > float(row["ma50"])) if pd.notna(row["ma50"]) else None,
        "ret_20d_pct": round(float(row["ret_20d"]) * 100, 2) if pd.notna(row["ret_20d"]) else None,
    }

    d10, d20 = cur["dist_10d"], cur["dist_20d"]
    scenarios = [
        ("exact_dist20", (df["dist_20"] == d20)),
        ("dist20_ge_current", (df["dist_20"] >= d20)),
        ("dist20_ge4", (df["dist_20"] >= 4)),
        ("dist20_ge5", (df["dist_20"] >= 5)),
        ("dist20_eq4_and_above_ma50", (df["dist_20"] == 4) & (df["close"] > df["ma50"])),
        ("dist20_ge4_and_above_ma50", (df["dist_20"] >= 4) & (df["close"] > df["ma50"])),
        ("correction_template_dist20_ge4_below_ma50", (df["dist_20"] >= 4) & (df["close"] <= df["ma50"])),
    ]
    results = {"current": cur, "scenarios": [summarize_matches(df, m, lab) for lab, m in scenarios]}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
