#!/usr/bin/env python3
"""Build ex-VIN VNINDEX daily series and run the low-distribution forward-return study.

Methodology (cap-weighted decomposition):
    For each day t, we know VNINDEX(t) and total HOSE volume V_total(t).
    We compute the VIN basket's daily market cap M_VIN(t) = sum_i close_i(t) * shares_i(t)
    for i in {VIC, VHM, VRE}. VPL is excluded (< 252 daily bars per project baseline).

    Under the standard "constant divisor" approximation for a cap-weighted index
    (HOSE divisor is adjusted only for corporate actions, otherwise stable):
        cap_full(t) ~ D * VNINDEX(t)
    Calibrate D using the 2026-03-16 snapshot (artifacts/vnindex_ex_vin_result.json):
        cap_VIN(t0) / cap_full(t0) = w(t0)
        => D = cap_VIN_my(t0) / (w_my(t0) * VNINDEX(t0))
    where w_my(t0) is recomputed for the {VIC, VHM, VRE} basket only (not the full
    4-symbol snapshot).

    Then VNINDEX_ex_VIN(t) = VNINDEX(t) * (1 - w(t))
    Volume_ex_VIN(t) = volume_VNINDEX(t) - volume_VIC(t) - volume_VHM(t) - volume_VRE(t)
    (volumes are HOSE matched-share counts; we subtract VIN basket's matched shares.)

    Distribution day rule applied on the ex-VIN series with the same -0.2% / volume-up
    definition used in the full-VNINDEX study.

Caveats:
    - Constant-divisor assumption introduces small error for older years
      (HOSE divisor has been adjusted for new listings); error is greatest for w
      attribution in 2012-2017 where VIN basket weight was small (so error is
      small in absolute return terms).
    - Volume subtraction assumes data/stocks/*.csv volumes are matched (order-book)
      shares in the same convention as VNINDEX volume.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.intake.fireant_historical import fetch_historical  # noqa: E402

VIN_BASKET = ["VIC", "VHM", "VRE"]
SNAPSHOT_PATH = _REPO / "artifacts" / "vnindex_ex_vin_result.json"
QUARTERLY_FA = _REPO / "data" / "fireant_exports" / "financials" / "all_financial_data_quarterly_2016Q1_2026Q2.parquet"
VNINDEX_CSV = _REPO / "minervini_backtest" / "data" / "raw" / "VNINDEX.csv"
STOCK_CSV_LEGACY = _REPO / "minervini_backtest" / "data" / "raw"
STOCK_CSV_NEW = _REPO / "data" / "stocks"

OUT_DIR = _REPO / "data" / "research"
OUT_SERIES_CSV = OUT_DIR / "vnindex_ex_vin_daily_series.csv"
OUT_JSON = OUT_DIR / "vnindex_low_dist_forward_returns_ex_vin.json"
OUT_ANCHORS_CSV = OUT_DIR / "vnindex_low_dist_anchors_ex_vin.csv"

DIST_DROP = 0.002
HORIZONS = (20, 50, 100, 150, 200)
PERCENTILES = (5, 10, 25, 50, 75, 90, 95)


def _load_vnindex(end: str) -> pd.DataFrame:
    base = pd.read_csv(VNINDEX_CSV)
    base["date"] = pd.to_datetime(base["date"])
    base = base.sort_values("date").reset_index(drop=True)
    last_csv = base["date"].max()
    fetch_start = (last_csv - pd.Timedelta(days=5)).date().isoformat()
    try:
        rows = fetch_historical("VNINDEX", fetch_start, end)
        if rows:
            recent = pd.DataFrame(
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
            base = pd.concat([base, recent], ignore_index=True)
            base = base.drop_duplicates(subset=["date"], keep="last")
    except Exception:
        pass
    base = base.sort_values("date").reset_index(drop=True)
    return base


def _load_stock(symbol: str, end: str | None = None) -> pd.DataFrame:
    """Returns DataFrame with close in **thousand VND** (consistent with snapshot units).

    minervini_backtest CSVs store close in raw VND (e.g. 144700); we scale by 1/1000.
    data/stocks/ CSVs store close in thousand VND already (e.g. 144.7).
    Optionally extends with the latest FireAnt rows up to ``end``.
    """
    legacy = STOCK_CSV_LEGACY / f"{symbol}.csv"
    new = STOCK_CSV_NEW / f"{symbol}.csv"
    if legacy.exists():
        df = pd.read_csv(legacy)
        df["close"] = df["close"].astype(float) / 1000.0
    elif new.exists():
        df = pd.read_csv(new)
    else:
        return pd.DataFrame(columns=["date", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if end is not None and not df.empty:
        last = df["date"].max()
        if last < pd.Timestamp(end):
            fetch_start = (last - pd.Timedelta(days=5)).date().isoformat()
            try:
                rows = fetch_historical(symbol, fetch_start, end)
                if rows:
                    extra = pd.DataFrame(
                        [
                            {
                                "date": pd.Timestamp(r.d),
                                "open": float(r.o) / 1000.0,
                                "high": float(r.h) / 1000.0,
                                "low": float(r.l) / 1000.0,
                                "close": float(r.c) / 1000.0,
                                "volume": float(r.v) if r.v is not None else float("nan"),
                            }
                            for r in rows
                        ]
                    )
                    df = pd.concat([df, extra], ignore_index=True)
                    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
            except Exception:
                pass
    return df


def _load_shares_quarterly() -> pd.DataFrame:
    df = pd.read_parquet(QUARTERLY_FA)
    sub = df[df["symbol"].isin(VIN_BASKET)][[
        "symbol", "year", "quarter", "financialValues_ShareAtPeriodEnd"
    ]].rename(columns={"financialValues_ShareAtPeriodEnd": "shares"})
    sub = sub.dropna(subset=["shares"])
    sub["quarter_end"] = pd.to_datetime(
        sub["year"].astype(str) + "-" + (sub["quarter"] * 3).astype(str) + "-01",
    ) + pd.tseries.offsets.MonthEnd(0)
    return sub.sort_values(["symbol", "quarter_end"]).reset_index(drop=True)


def build_daily_shares(symbol: str, sh_q: pd.DataFrame, daily_dates: pd.DatetimeIndex) -> pd.Series:
    sub = sh_q[sh_q["symbol"] == symbol].copy()
    if sub.empty:
        return pd.Series(np.nan, index=daily_dates, name="shares")
    s = sub.set_index("quarter_end")["shares"]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    daily = s.reindex(daily_dates, method="ffill")
    daily = daily.bfill()
    return daily


def build_ex_vin_series(end: str) -> pd.DataFrame:
    vni = _load_vnindex(end)
    daily_dates = pd.DatetimeIndex(vni["date"])
    cap_VIN = pd.Series(0.0, index=daily_dates)
    vol_VIN = pd.Series(0.0, index=daily_dates)
    sh_q = _load_shares_quarterly()
    listed_at: dict[str, pd.Timestamp] = {}
    for sym in VIN_BASKET:
        df = _load_stock(sym, end=end)
        if df.empty:
            print(f"WARN: {sym} OHLCV missing", file=sys.stderr)
            continue
        listed_at[sym] = df["date"].min()
        df_idx = df.set_index("date")[["close", "volume"]].sort_index()
        df_idx = df_idx.reindex(daily_dates)
        shares = build_daily_shares(sym, sh_q, daily_dates)
        c = df_idx["close"].astype(float).fillna(0.0)
        v = df_idx["volume"].astype(float).fillna(0.0)
        sh = shares.fillna(0.0)
        cap_VIN = cap_VIN.add(c * sh, fill_value=0.0)
        vol_VIN = vol_VIN.add(v, fill_value=0.0)

    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    snap_date = pd.Timestamp(snap["asof"])
    while snap_date not in daily_dates:
        snap_date -= pd.Timedelta(days=1)
        if snap_date < pd.Timestamp("2020-01-01"):
            raise RuntimeError("snapshot calibration date not found in VNINDEX series")
    cap_VIN_full4_t0 = float(snap["total_market_cap_full"]) - float(snap["total_market_cap_ex_vin"])
    cap_full_t0 = float(snap["total_market_cap_full"])
    w_full4_t0 = cap_VIN_full4_t0 / cap_full_t0
    cap_VIN_my_t0 = float(cap_VIN.loc[snap_date])
    if cap_VIN_my_t0 <= 0:
        raise RuntimeError("VIN basket cap is zero at snapshot date — units mismatch?")
    w_my_t0 = cap_VIN_my_t0 / cap_full_t0
    vni_t0 = float(vni.loc[vni["date"] == snap_date, "close"].iloc[0])
    D = cap_full_t0 / vni_t0

    cap_full_implied = D * vni.set_index("date")["close"].astype(float)
    w_VIN = cap_VIN / cap_full_implied
    w_VIN = w_VIN.clip(lower=0.0, upper=0.99)
    close_ex = vni.set_index("date")["close"].astype(float) * (1.0 - w_VIN)
    vol_ex = vni.set_index("date")["volume"].astype(float) - vol_VIN
    vol_ex = vol_ex.clip(lower=0.0)
    out = pd.DataFrame(
        {
            "date": vni["date"].values,
            "vnindex_close": vni["close"].values,
            "vnindex_volume": vni["volume"].values,
            "cap_VIN_basket": cap_VIN.values,
            "w_VIN": w_VIN.values,
            "close_ex_vin": close_ex.values,
            "volume_ex_vin": vol_ex.values,
        }
    )
    print(
        f"Calibration: snap_date={snap_date.date()}  VNINDEX={vni_t0:.2f}  "
        f"cap_full(snap)={cap_full_t0:.3e}  D={D:.3e}  "
        f"w_VIN(my 3-sym)={w_my_t0*100:.2f}%  w_VIN(full 4-sym)={w_full4_t0*100:.2f}%",
        file=sys.stderr,
    )
    return out


def add_indicators(df: pd.DataFrame, close_col: str, vol_col: str) -> pd.DataFrame:
    out = df.copy()
    c = out[close_col].astype(float)
    v = out[vol_col].astype(float)
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


def percentile_dict(arr: np.ndarray) -> dict[str, float]:
    if arr.size == 0:
        return {f"p{p}": float("nan") for p in PERCENTILES}
    qs = np.percentile(arr, PERCENTILES)
    return {f"p{p}": float(qs[i]) for i, p in enumerate(PERCENTILES)}


def summarize(values: np.ndarray) -> dict:
    if values.size == 0:
        return {"n": 0, "mean": float("nan"), "median": float("nan"),
                "std": float("nan"), "win_rate": float("nan"),
                **{f"p{p}": float("nan") for p in PERCENTILES}}
    return {
        "n": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "std": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "win_rate": float((values > 0).mean()),
        **percentile_dict(values),
    }


def collect_forward_returns(closes: np.ndarray, idx: list[int], horizons=HORIZONS) -> dict[int, np.ndarray]:
    n = len(closes)
    out: dict[int, np.ndarray] = {}
    for h in horizons:
        arr = []
        for i in idx:
            j = i + h
            if j >= n:
                continue
            c0, cj = closes[i], closes[j]
            if not (np.isfinite(c0) and np.isfinite(cj) and c0 > 0):
                continue
            arr.append(cj / c0 - 1.0)
        out[h] = np.array(arr, dtype=float)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-window", default="2026-03-24")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--history-start", default="2012-01-01")
    ap.add_argument("--max-dist-in-window", type=int, default=1)
    ap.add_argument("--min-anchor-spacing", type=int, default=20)
    args = ap.parse_args()

    series = build_ex_vin_series(args.end)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    series.to_csv(OUT_SERIES_CSV, index=False)

    df = series.copy()
    df = df[df["date"] >= pd.Timestamp(args.history_start)].reset_index(drop=True)
    df = add_indicators(df, "close_ex_vin", "volume_ex_vin")

    win_start = pd.Timestamp(args.start_window)
    win_end = pd.Timestamp(args.end)
    win = df[(df["date"] >= win_start) & (df["date"] <= win_end)].reset_index(drop=True)
    win_dist_count = int(win["dist_day"].fillna(0).sum())
    win_len = int(len(win))
    last_idx = df.index[-1]
    last_close_ex = float(df.at[last_idx, "close_ex_vin"])
    last_close_full = float(df.at[last_idx, "vnindex_close"])
    last_w = float(df.at[last_idx, "w_VIN"])
    last_date = df.at[last_idx, "date"]

    win_dist_dates = win.loc[win["dist_day"] == 1, ["date", "close_ex_vin", "pct_change", "volume_ex_vin"]].copy()
    win_dist_dates["date"] = win_dist_dates["date"].dt.date.astype(str)

    closes = df["close_ex_vin"].astype(float).values
    dist = df["dist_day"].astype(float).values
    ma50 = df["ma50"].astype(float).values
    ma200 = df["ma200"].astype(float).values

    n = len(df)
    L = win_len
    threshold = args.max_dist_in_window

    candidate_idx: list[int] = []
    for i in range(L - 1, n):
        window_dist = dist[i - L + 1 : i + 1]
        if np.isnan(window_dist).any():
            continue
        if int(window_dist.sum()) <= threshold:
            candidate_idx.append(i)

    sampled_idx_sparse: list[int] = []
    last_pick = -10**9
    for i in candidate_idx:
        if i - last_pick >= args.min_anchor_spacing:
            sampled_idx_sparse.append(i)
            last_pick = i

    today_idx = n - 1
    sparse_excl_today = [i for i in sampled_idx_sparse if i != today_idx]
    candidate_excl_today = [i for i in candidate_idx if i != today_idx]

    fwd_dense = collect_forward_returns(closes, candidate_excl_today)
    fwd_sparse = collect_forward_returns(closes, sparse_excl_today)

    closes_full = df["vnindex_close"].astype(float).values
    fwd_full_at_same_anchors = collect_forward_returns(closes_full, sparse_excl_today)

    summary = {
        "facts": {
            "data_source": "FireAnt + local CSV (VNINDEX, VIC, VHM, VRE) + FireAnt quarterly fundamentals",
            "ex_vin_basket": VIN_BASKET,
            "vpl_excluded_reason": "< 252 daily bars (per VIN_EMA_CLOUD_BASELINE.md)",
            "calibration_snapshot": str(SNAPSHOT_PATH.relative_to(_REPO)),
            "history_start": args.history_start,
            "end_date": args.end,
            "last_bar_date": str(last_date.date()),
            "last_close_full": last_close_full,
            "last_close_ex_vin": last_close_ex,
            "last_w_VIN": last_w,
            "current_window_ex_vin": {
                "start": args.start_window,
                "end": args.end,
                "trading_days": win_len,
                "distribution_days_ex_vin": win_dist_count,
                "distribution_dates": win_dist_dates.to_dict(orient="records"),
            },
        },
        "anchors": {"candidates_total": len(candidate_idx), "sparse_total": len(sampled_idx_sparse)},
        "forward_returns_dense_ex_vin": {f"{h}d": summarize(fwd_dense[h]) for h in HORIZONS},
        "forward_returns_sparse_ex_vin": {f"{h}d": summarize(fwd_sparse[h]) for h in HORIZONS},
        "forward_returns_full_at_same_anchors": {f"{h}d": summarize(fwd_full_at_same_anchors[h]) for h in HORIZONS},
        "forward_points_at_today_ex_vin": {},
    }

    for h in HORIZONS:
        s = summary["forward_returns_sparse_ex_vin"][f"{h}d"]
        pts = {k: (last_close_ex * v if isinstance(v, float) and np.isfinite(v) else float("nan"))
               for k, v in s.items() if k in ("mean", "median", *[f"p{p}" for p in PERCENTILES])}
        summary["forward_points_at_today_ex_vin"][f"{h}d"] = {
            "anchor_close_ex_vin": last_close_ex,
            "delta_points": pts,
            "absolute_index": {k: last_close_ex + v for k, v in pts.items()},
        }

    anchors_df = pd.DataFrame({
        "date": df.loc[sampled_idx_sparse, "date"].dt.date.astype(str).values,
        "close_ex_vin": df.loc[sampled_idx_sparse, "close_ex_vin"].values,
        "vnindex_close": df.loc[sampled_idx_sparse, "vnindex_close"].values,
        "w_VIN": df.loc[sampled_idx_sparse, "w_VIN"].values,
        "dist_in_window_ex_vin": [int(dist[i - L + 1 : i + 1].sum()) for i in sampled_idx_sparse],
        "above_ma50_ex_vin": [bool(np.isfinite(ma50[i]) and closes[i] > ma50[i]) for i in sampled_idx_sparse],
        "above_ma200_ex_vin": [bool(np.isfinite(ma200[i]) and closes[i] > ma200[i]) for i in sampled_idx_sparse],
    })
    anchors_df.to_csv(OUT_ANCHORS_CSV, index=False)
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    print("=" * 78)
    print("VNINDEX EX-VIN low-distribution regime - forward return study")
    print("=" * 78)
    print(f"Last bar: {last_date.date()}  VNINDEX={last_close_full:.2f}  EX-VIN level (calibrated)={last_close_ex:.2f}  w_VIN={last_w*100:.2f}%")
    cw = summary["facts"]["current_window_ex_vin"]
    print(f"Current window {cw['start']} -> {cw['end']} on EX-VIN: {cw['trading_days']} trading days, {cw['distribution_days_ex_vin']} distribution day(s) (ex-VIN rule).")
    if not win_dist_dates.empty:
        print("Ex-VIN dist days in window:")
        for _, row in win_dist_dates.iterrows():
            print(f"   {row['date']}  close_ex={row['close_ex_vin']:.2f}  pct={row['pct_change']*100:.3f}%  vol_ex={row['volume_ex_vin']:.0f}")
    print(f"Anchor rule: trailing {win_len} TD with <= {threshold} dist day on ex-VIN. Decorrelation: >= {args.min_anchor_spacing} TD apart.")
    print(f"Candidate anchors: {len(candidate_idx)}  | Sparse anchors: {len(sampled_idx_sparse)}")
    print()
    print("EX-VIN forward returns (sparse, decorrelated):")
    print(f"{'H':<6}{'n':>4}{'mean%':>9}{'med%':>9}{'win%':>8}{'p10%':>9}{'p25%':>9}{'p75%':>9}{'p90%':>9}")
    for h in HORIZONS:
        s = summary["forward_returns_sparse_ex_vin"][f"{h}d"]
        if s["n"] == 0: continue
        print(f"{h:<6}{s['n']:>4}{s['mean']*100:>9.2f}{s['median']*100:>9.2f}{s['win_rate']*100:>8.1f}{s['p10']*100:>9.2f}{s['p25']*100:>9.2f}{s['p75']*100:>9.2f}{s['p90']*100:>9.2f}")
    print()
    print(f"FULL VNINDEX returns at the SAME anchor dates (so we can compare apples to apples):")
    print(f"{'H':<6}{'n':>4}{'mean%':>9}{'med%':>9}{'win%':>8}{'p10%':>9}{'p25%':>9}{'p75%':>9}{'p90%':>9}")
    for h in HORIZONS:
        s = summary["forward_returns_full_at_same_anchors"][f"{h}d"]
        if s["n"] == 0: continue
        print(f"{h:<6}{s['n']:>4}{s['mean']*100:>9.2f}{s['median']*100:>9.2f}{s['win_rate']*100:>8.1f}{s['p10']*100:>9.2f}{s['p25']*100:>9.2f}{s['p75']*100:>9.2f}{s['p90']*100:>9.2f}")
    print()
    print(f"Translated to points anchored at last_close_ex_vin={last_close_ex:.2f}:")
    print(f"{'H':<6}{'mean dpt':>10}{'med dpt':>10}{'p10 dpt':>10}{'p25 dpt':>10}{'p75 dpt':>10}{'p90 dpt':>10}")
    for h in HORIZONS:
        s = summary["forward_returns_sparse_ex_vin"][f"{h}d"]
        if s["n"] == 0: continue
        print(f"{h:<6}{s['mean']*last_close_ex:>10.1f}{s['median']*last_close_ex:>10.1f}{s['p10']*last_close_ex:>10.1f}{s['p25']*last_close_ex:>10.1f}{s['p75']*last_close_ex:>10.1f}{s['p90']*last_close_ex:>10.1f}")
    print()
    print(f"Series CSV: {OUT_SERIES_CSV}")
    print(f"Anchors CSV: {OUT_ANCHORS_CSV}")
    print(f"JSON: {OUT_JSON}")


if __name__ == "__main__":
    main()
