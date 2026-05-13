#!/usr/bin/env python3
"""VNINDEX low-distribution regime forward-return study.

User context: from 2026-03-23 to "today" the index has only ~1 distribution
day. We rebuild the same condition over 2012-now and report the empirical
distribution of forward returns at 20/50/100/150/200 trading-day horizons,
expressed both in percent and absolute index points (anchored to current
close so the user can read points directly relevant to today).

Distribution day rule (O'Neil/Morales): close <= prior_close * (1 - 0.2%)
AND volume > prior volume.

Data: FireAnt HistoricalQuotes for VNINDEX merged with the existing CSV
fallback at ``minervini_backtest/data/raw/VNINDEX.csv``. No interpretation
of FireAnt index data is layered on top -- we pass through OHLCV.

Run: ``python scripts/research/vnindex_low_dist_forward_returns.py``
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.intake.fireant_historical import fetch_historical  # noqa: E402

CSV_FALLBACK = _REPO / "minervini_backtest" / "data" / "raw" / "VNINDEX.csv"
OUT_JSON = _REPO / "data" / "research" / "vnindex_low_dist_forward_returns.json"
OUT_CSV_ANCHORS = _REPO / "data" / "research" / "vnindex_low_dist_anchors.csv"

DIST_DROP = 0.002
HORIZONS = (20, 50, 100, 150, 200)
PERCENTILES = (5, 10, 25, 50, 75, 90, 95)


def _load_csv() -> pd.DataFrame:
    df = pd.read_csv(CSV_FALLBACK)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _fetch_recent(start: str, end: str) -> pd.DataFrame:
    rows = fetch_historical("VNINDEX", start, end)
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(
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
    return df.sort_values("date").reset_index(drop=True)


def load_vnindex(end_date: str) -> pd.DataFrame:
    base = _load_csv()
    last_csv = base["date"].max()
    fetch_start = (last_csv - pd.Timedelta(days=5)).date().isoformat()
    try:
        recent = _fetch_recent(fetch_start, end_date)
    except Exception:
        recent = pd.DataFrame(columns=base.columns)
    if not recent.empty:
        merged = pd.concat([base, recent], ignore_index=True)
        merged = merged.drop_duplicates(subset=["date"], keep="last")
    else:
        merged = base.copy()
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["close"].astype(float)
    v = out["volume"].astype(float)
    prev_c = c.shift(1)
    prev_v = v.shift(1)
    down = c <= prev_c * (1.0 - DIST_DROP)
    vol_up = v > prev_v
    valid = c.notna() & prev_c.notna() & v.notna() & prev_v.notna() & (v > 0) & (prev_v > 0)
    dist = pd.Series(np.nan, index=out.index, dtype=float)
    dist[valid] = (down[valid] & vol_up[valid]).astype(float)
    out["dist_day"] = dist
    out["pct_change"] = c / prev_c - 1.0
    out["ma50"] = c.rolling(50, min_periods=50).mean()
    out["ma200"] = c.rolling(200, min_periods=200).mean()
    return out


def trading_days_between(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    mask = (df["date"] >= start) & (df["date"] <= end)
    return df.loc[mask].reset_index(drop=True)


def percentile_dict(arr: np.ndarray) -> dict[str, float]:
    if arr.size == 0:
        return {f"p{p}": float("nan") for p in PERCENTILES}
    qs = np.percentile(arr, PERCENTILES)
    return {f"p{p}": float(qs[i]) for i, p in enumerate(PERCENTILES)}


def summarize(values: np.ndarray) -> dict:
    if values.size == 0:
        return {
            "n": 0,
            "mean": float("nan"),
            "median": float("nan"),
            "std": float("nan"),
            "win_rate": float("nan"),
            **{f"p{p}": float("nan") for p in PERCENTILES},
        }
    return {
        "n": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "std": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "win_rate": float((values > 0).mean()),
        **percentile_dict(values),
    }


def collect_forward_returns(df: pd.DataFrame, anchor_idx: list[int], horizons=HORIZONS) -> dict[int, np.ndarray]:
    out: dict[int, np.ndarray] = {h: np.array([]) for h in horizons}
    closes = df["close"].astype(float).values
    n = len(df)
    for h in horizons:
        arr = []
        for i in anchor_idx:
            j = i + h
            if j >= n:
                continue
            c0 = closes[i]
            cj = closes[j]
            if not (np.isfinite(c0) and np.isfinite(cj) and c0 > 0):
                continue
            arr.append(cj / c0 - 1.0)
        out[h] = np.array(arr, dtype=float)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-window", default="2026-03-24", help="reference window start (current low-dist window). Default 24/3 = day after 23/3 shake-out")
    ap.add_argument("--end", default=date.today().isoformat(), help="end date for dataset & current window end")
    ap.add_argument("--history-start", default="2012-01-01")
    ap.add_argument("--max-dist-in-window", type=int, default=1)
    ap.add_argument("--min-anchor-spacing", type=int, default=20, help="min trading days between sampled anchors (decorrelation)")
    ap.add_argument("--also-window-len", type=int, default=None, help="optional: override window length L for sensitivity tests")
    args = ap.parse_args()

    df = load_vnindex(args.end)
    df = add_indicators(df)

    hist_start = pd.Timestamp(args.history_start)
    df_hist = df[df["date"] >= hist_start].reset_index(drop=True)

    win_start = pd.Timestamp(args.start_window)
    win_end = pd.Timestamp(args.end)
    win = trading_days_between(df_hist, win_start, win_end)
    win_dist_count = int(win["dist_day"].fillna(0).sum())
    win_len = int(len(win))
    win_dist_dates = win.loc[win["dist_day"] == 1, ["date", "close", "pct_change", "volume"]].copy()
    win_dist_dates["date"] = win_dist_dates["date"].dt.date.astype(str)

    last_idx = df_hist.index[-1]
    last_close = float(df_hist.at[last_idx, "close"])
    last_date = df_hist.at[last_idx, "date"]

    closes = df_hist["close"].astype(float).values
    dist = df_hist["dist_day"].astype(float).values
    ma50 = df_hist["ma50"].astype(float).values
    ma200 = df_hist["ma200"].astype(float).values

    n = len(df_hist)
    L = args.also_window_len if args.also_window_len is not None else win_len
    threshold = args.max_dist_in_window

    candidate_idx: list[int] = []
    for i in range(L - 1, n):
        window_dist = dist[i - L + 1 : i + 1]
        if np.isnan(window_dist).any():
            continue
        if int(window_dist.sum()) <= threshold:
            candidate_idx.append(i)

    sampled_idx_dense = candidate_idx[:]
    sampled_idx_sparse: list[int] = []
    last_pick = -10**9
    for i in candidate_idx:
        if i - last_pick >= args.min_anchor_spacing:
            sampled_idx_sparse.append(i)
            last_pick = i

    today_idx = n - 1
    sampled_idx_sparse_excl_today = [i for i in sampled_idx_sparse if i != today_idx]
    sampled_idx_dense_excl_today = [i for i in sampled_idx_dense if i != today_idx]

    fwd_dense = collect_forward_returns(df_hist, sampled_idx_dense_excl_today)
    fwd_sparse = collect_forward_returns(df_hist, sampled_idx_sparse_excl_today)

    summary = {
        "facts": {
            "data_source": "FireAnt HistoricalQuotes (VNINDEX) merged with local CSV (2012-now)",
            "history_start": args.history_start,
            "end_date": args.end,
            "last_bar_date": str(last_date.date()),
            "last_close": last_close,
            "current_window": {
                "start": args.start_window,
                "end": args.end,
                "trading_days": win_len,
                "distribution_days": win_dist_count,
            },
            "rule": {
                "distribution_day": "close <= prev_close * (1 - 0.2%) AND volume > prev_volume",
                "anchor_condition": f"trailing {win_len} trading days have <= {threshold} distribution day(s)",
                "decorrelation_spacing_days": args.min_anchor_spacing,
            },
        },
        "anchors": {
            "candidates_total": len(candidate_idx),
            "sparse_total": len(sampled_idx_sparse),
        },
        "forward_returns_dense": {},
        "forward_returns_sparse": {},
        "forward_points_at_today": {},
    }

    for h in HORIZONS:
        s_dense = summarize(fwd_dense[h])
        s_sparse = summarize(fwd_sparse[h])
        summary["forward_returns_dense"][f"{h}d"] = s_dense
        summary["forward_returns_sparse"][f"{h}d"] = s_sparse
        pts_dense = {
            k: (last_close * v if isinstance(v, float) and np.isfinite(v) else float("nan"))
            for k, v in s_dense.items()
            if k in ("mean", "median", *[f"p{p}" for p in PERCENTILES])
        }
        pts_sparse = {
            k: (last_close * v if isinstance(v, float) and np.isfinite(v) else float("nan"))
            for k, v in s_sparse.items()
            if k in ("mean", "median", *[f"p{p}" for p in PERCENTILES])
        }
        summary["forward_points_at_today"][f"{h}d"] = {
            "anchor_close": last_close,
            "delta_points_dense": pts_dense,
            "delta_points_sparse": pts_sparse,
            "absolute_index_dense": {k: last_close + v for k, v in pts_dense.items()},
            "absolute_index_sparse": {k: last_close + v for k, v in pts_sparse.items()},
        }

    by_trend = {}
    for label, mask_fn in (
        ("above_ma50_and_ma200", lambda i: ma50[i] is not None and np.isfinite(ma50[i]) and np.isfinite(ma200[i]) and closes[i] > ma50[i] and closes[i] > ma200[i]),
        ("below_ma50", lambda i: np.isfinite(ma50[i]) and closes[i] <= ma50[i]),
    ):
        sub = [i for i in sampled_idx_sparse_excl_today if mask_fn(i)]
        fwd = collect_forward_returns(df_hist, sub)
        by_trend[label] = {
            "n_anchors": len(sub),
            **{f"{h}d": summarize(fwd[h]) for h in HORIZONS},
        }
    summary["forward_returns_sparse_by_trend"] = by_trend

    anchors_df = pd.DataFrame(
        {
            "date": df_hist.loc[sampled_idx_sparse, "date"].dt.date.astype(str).values,
            "close": df_hist.loc[sampled_idx_sparse, "close"].values,
            "dist_count_in_window": [int(dist[i - L + 1 : i + 1].sum()) for i in sampled_idx_sparse],
            "above_ma50": [bool(np.isfinite(ma50[i]) and closes[i] > ma50[i]) for i in sampled_idx_sparse],
            "above_ma200": [bool(np.isfinite(ma200[i]) and closes[i] > ma200[i]) for i in sampled_idx_sparse],
        }
    )
    OUT_CSV_ANCHORS.parent.mkdir(parents=True, exist_ok=True)
    anchors_df.to_csv(OUT_CSV_ANCHORS, index=False)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    print("=" * 78)
    print("VNINDEX low-distribution regime — forward return study")
    print("=" * 78)
    print(f"Last bar: {last_date.date()}  close={last_close:.2f}")
    cw = summary["facts"]["current_window"]
    print(f"Current window {cw['start']} -> {cw['end']}: {cw['trading_days']} trading days, {cw['distribution_days']} distribution day(s).")
    if not win_dist_dates.empty:
        print("Distribution days in current window:")
        for _, row in win_dist_dates.iterrows():
            print(f"   {row['date']}  close={row['close']:.2f}  pct={row['pct_change']*100:.3f}%  vol={row['volume']:.0f}")
    print(f"Anchor rule: trailing {win_len} TD with <= {threshold} dist day. Decorrelation: >= {args.min_anchor_spacing} TD apart.")
    print(f"Candidate anchors: {len(candidate_idx)}  | Sparse anchors: {len(sampled_idx_sparse)}")
    print()
    print("Forward returns (sparse anchors, decorrelated):")
    print(f"{'Horizon':<8}{'n':>5}{'mean%':>10}{'med%':>10}{'win%':>9}{'p10%':>10}{'p25%':>10}{'p75%':>10}{'p90%':>10}")
    for h in HORIZONS:
        s = summary["forward_returns_sparse"][f"{h}d"]
        if s["n"] == 0:
            continue
        print(
            f"{h:<8}{s['n']:>5}"
            f"{s['mean']*100:>10.2f}{s['median']*100:>10.2f}{s['win_rate']*100:>9.1f}"
            f"{s['p10']*100:>10.2f}{s['p25']*100:>10.2f}{s['p75']*100:>10.2f}{s['p90']*100:>10.2f}"
        )
    print()
    print(f"Translated to points at last_close={last_close:.2f}:")
    print(f"{'Horizon':<8}{'mean dpt':>11}{'med dpt':>11}{'p10 dpt':>11}{'p25 dpt':>11}{'p75 dpt':>11}{'p90 dpt':>11}")
    for h in HORIZONS:
        s = summary["forward_returns_sparse"][f"{h}d"]
        if s["n"] == 0:
            continue
        m = s["mean"] * last_close
        md = s["median"] * last_close
        p10 = s["p10"] * last_close
        p25 = s["p25"] * last_close
        p75 = s["p75"] * last_close
        p90 = s["p90"] * last_close
        print(f"{h:<8}{m:>11.1f}{md:>11.1f}{p10:>11.1f}{p25:>11.1f}{p75:>11.1f}{p90:>11.1f}")

    print()
    print("Forward returns (DENSE anchors, every qualifying day -- correlated, larger n):")
    for h in HORIZONS:
        s = summary["forward_returns_dense"][f"{h}d"]
        if s["n"] == 0:
            continue
        print(
            f"  {h}d  n={s['n']:>4}  mean={s['mean']*100:.2f}%  median={s['median']*100:.2f}%  win={s['win_rate']*100:.1f}%"
        )

    print()
    print("By trend state at anchor (sparse):")
    for k, payload in by_trend.items():
        print(f"  {k}: n_anchors={payload['n_anchors']}")
        for h in HORIZONS:
            s = payload[f"{h}d"]
            if s["n"] == 0:
                continue
            print(f"     {h}d n={s['n']} mean={s['mean']*100:.2f}% median={s['median']*100:.2f}% win={s['win_rate']*100:.1f}%")

    print()
    print(f"JSON: {OUT_JSON}")
    print(f"CSV anchors: {OUT_CSV_ANCHORS}")


if __name__ == "__main__":
    main()
