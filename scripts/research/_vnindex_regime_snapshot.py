#!/usr/bin/env python3
"""One-off VNINDEX full vs ex-VIN regime snapshot vs historical dist windows."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DIST_DROP = 0.002


def add_dist(df: pd.DataFrame, close_col: str = "close", vol_col: str = "volume") -> pd.DataFrame:
    out = df.copy()
    c = out[close_col].astype(float)
    v = out[vol_col].astype(float)
    pc, pv = c.shift(1), v.shift(1)
    down = c <= pc * (1.0 - DIST_DROP)
    vol_up = v > pv
    valid = c.notna() & pc.notna() & v.notna() & pv.notna() & (v > 0) & (pv > 0)
    dist = pd.Series(np.nan, index=out.index)
    dist[valid] = (down[valid] & vol_up[valid]).astype(float)
    out["dist_day"] = dist
    out["pct_chg"] = c / pc - 1
    out["ma20"] = c.rolling(20, min_periods=20).mean()
    out["ma50"] = c.rolling(50, min_periods=50).mean()
    out["ma200"] = c.rolling(200, min_periods=200).mean()
    out["ret_20d"] = c / c.shift(20) - 1
    out["ret_5d"] = c / c.shift(5) - 1
    return out


def roll_dist(s: pd.Series, w: int) -> pd.Series:
    return s.fillna(0).rolling(w).sum()


def snapshot(df: pd.DataFrame, label: str, close_col: str = "close", vol_col: str = "volume") -> dict:
    d = df.copy()
    d["dist_10"] = roll_dist(d["dist_day"], 10)
    d["dist_20"] = roll_dist(d["dist_day"], 20)
    d["dist_50"] = roll_dist(d["dist_day"], 50)
    row = d.iloc[-1]
    c = float(row[close_col])
    out = {
        "label": label,
        "asof": str(row["date"].date()),
        "close": round(c, 2),
        "pct_1d": round(float(row["pct_chg"]) * 100, 3) if pd.notna(row["pct_chg"]) else None,
        "dist_10d": int(row["dist_10"]),
        "dist_20d": int(row["dist_20"]),
        "dist_50d": int(row["dist_50"]),
        "above_ma20": bool(c > float(row["ma20"])) if pd.notna(row["ma20"]) else None,
        "above_ma50": bool(c > float(row["ma50"])) if pd.notna(row["ma50"]) else None,
        "above_ma200": bool(c > float(row["ma200"])) if pd.notna(row["ma200"]) else None,
        "ret_5d_pct": round(float(row["ret_5d"]) * 100, 2) if pd.notna(row["ret_5d"]) else None,
        "ret_20d_pct": round(float(row["ret_20d"]) * 100, 2) if pd.notna(row["ret_20d"]) else None,
        "last_dist_dates": d.loc[d["dist_day"] == 1, "date"].tail(5).dt.strftime("%Y-%m-%d").tolist(),
    }
    if "w_VIN" in row.index and pd.notna(row["w_VIN"]):
        out["w_VIN_pct"] = round(float(row["w_VIN"]) * 100, 2)
    return out


def window_stats(df: pd.DataFrame, start: str, end: str, close_col: str = "close") -> dict | None:
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    w = df.loc[mask].copy()
    if w.empty:
        return None
    w["dist_10"] = roll_dist(w["dist_day"], 10)
    w["dist_20"] = roll_dist(w["dist_day"], 20)
    peak = float(w[close_col].astype(float).max())
    last_c = float(w[close_col].iloc[-1])
    dd = (last_c / peak - 1) * 100 if peak > 0 else float("nan")
    return {
        "start": start,
        "end": end,
        "bars": len(w),
        "dist_days_total": int(w["dist_day"].fillna(0).sum()),
        "max_dist_10d": int(w["dist_10"].max()),
        "max_dist_20d": int(w["dist_20"].max()),
        "dd_from_window_peak_pct": round(dd, 2),
        "ret_window_pct": round((last_c / float(w[close_col].iloc[0]) - 1) * 100, 2) if len(w) > 1 else None,
    }


def main() -> None:
    vni = pd.read_parquet(REPO / "data/fireant_ssot/ta_vnindex.parquet")
    vni["date"] = pd.to_datetime(vni["date"])
    vni = add_dist(vni.sort_values("date").reset_index(drop=True))
    asof = str(vni.iloc[-1]["date"].date())

    ex_path = REPO / "data/research/vnindex_ex_vin_daily_series.csv"
    ex = None
    if ex_path.exists():
        ex = pd.read_csv(ex_path)
        ex["date"] = pd.to_datetime(ex["date"])
        ex = add_dist(ex, "close_ex_vin", "volume_ex_vin").sort_values("date").reset_index(drop=True)

    snaps = [snapshot(vni, "VNINDEX full")]
    if ex is not None:
        snaps.append(snapshot(ex, "VNINDEX ex-VIN", "close_ex_vin", "volume_ex_vin"))

    refs = [
        ("2023-08-09", "2023-08-01", "2023-09-30"),
        ("2024-03-04", "2024-03-01", "2024-04-30"),
        ("2024-06-07", "2024-06-01", "2024-07-31"),
        ("2024-09-10", "2024-09-01", "2024-10-31"),
        ("2026-current", "2026-03-01", asof),
    ]

    print("=== CURRENT SNAPSHOT ===")
    print(json.dumps(snaps, indent=2))

    print("\n=== FULL VNINDEX — REFERENCE WINDOWS ===")
    for tag, s, e in refs:
        print(tag, window_stats(vni, s, e))

    if ex is not None:
        print("\n=== EX-VIN — REFERENCE WINDOWS ===")
        for tag, s, e in refs:
            print(tag, window_stats(ex, s, e, "close_ex_vin"))

    win_start = "2026-03-24"
    w32 = vni[(vni["date"] >= win_start) & (vni["date"] <= vni["date"].max())]
    print("\n=== Window from 2026-03-24 FULL ===")
    print("bars", len(w32), "dist_days", int(w32["dist_day"].fillna(0).sum()))
    dd = w32.loc[w32["dist_day"] == 1, ["date", "close", "pct_chg", "volume"]].tail(8)
    print(dd.to_string(index=False) if not dd.empty else "(none)")

    if ex is not None:
        w32e = ex[(ex["date"] >= win_start) & (ex["date"] <= ex["date"].max())]
        print("\n=== Window from 2026-03-24 EX-VIN ===")
        print("bars", len(w32e), "dist_days", int(w32e["dist_day"].fillna(0).sum()))
        dde = w32e.loc[w32e["dist_day"] == 1, ["date", "close_ex_vin", "pct_chg", "volume_ex_vin"]].tail(8)
        print(dde.to_string(index=False) if not dde.empty else "(none)")

        vni2 = vni.set_index("date")
        ex2 = ex.set_index("date")
        j = vni2[["close"]].join(ex2[["close_ex_vin", "w_VIN"]], how="inner")
        j["ret20_full"] = j["close"] / j["close"].shift(20) - 1
        j["ret20_ex"] = j["close_ex_vin"] / j["close_ex_vin"].shift(20) - 1
        tail = j.tail(1).iloc[0]
        print("\n=== 20d return (latest) ===")
        print(
            f"full {tail['ret20_full']*100:.2f}%  ex_vin {tail['ret20_ex']*100:.2f}%  "
            f"gap { (tail['ret20_full']-tail['ret20_ex'])*100:.2f}%  w_VIN {tail['w_VIN']*100:.2f}%"
        )

    print("\n=== dist_20d at month-ends (FULL) ===")
    for d in [
        "2023-08-31",
        "2023-09-29",
        "2024-03-28",
        "2024-04-26",
        "2024-06-28",
        "2024-07-31",
        "2024-09-30",
        "2024-10-31",
        "2026-05-15",
    ]:
        sub = vni[vni["date"] <= pd.Timestamp(d)]
        if sub.empty:
            continue
        row = sub.iloc[-1]
        d10 = int(roll_dist(sub["dist_day"], 10).iloc[-1])
        d20 = int(roll_dist(sub["dist_day"], 20).iloc[-1])
        c = float(row["close"])
        ma50 = float(row["ma50"]) if pd.notna(row["ma50"]) else np.nan
        r20 = float(row["ret_20d"]) * 100 if pd.notna(row["ret_20d"]) else float("nan")
        ab50 = c > ma50 if pd.notna(ma50) else None
        print(f"{d} close={c:.1f} dist10={d10} dist20={d20} above_ma50={ab50} ret20d={r20:.1f}%")


if __name__ == "__main__":
    main()
