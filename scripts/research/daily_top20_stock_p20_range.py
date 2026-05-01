#!/usr/bin/env python3
"""
For each trading day in [from, to], rank listing stocks by stock_p20 (same definition
as scripts/research/backtest_random_p20_high.py: mean of sigmoid(current score) and
analog historical hit rate), and export top-N per day.

FACTS (method):
- source = FireAnt
- method = REST API (symbols/search + historical OHLCV + VNINDEX OHLCV)
- stock_p20 = nanmean(p_now, p_hist) with p_now = sigmoid(current_lead_score/3),
  p_hist from analog mean(label_lead20) over top-K past rows by L2 distance in z-space
  (mirrors scripts/research/bds_leader_scan._analog_probability).
- ADV50 = rolling_mean_50(close * 1000 * volume) VND/day (FireAnt close in thousands VND).

Limitations: universe = FireAnt symbols/search listing stocks; analog needs >=320
rows ending each evaluation date; first run is API-heavy.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402

from scripts.research.bds_leader_scan import (  # noqa: E402
    _compute_features,
    _sigmoid,
    fetch_symbols_universe,
)

STOCK_FEATURES = [
    "close_vs_ma20",
    "close_vs_ma50",
    "dist_to_52w_high",
    "rs20",
    "rs60",
    "vol_thrust20",
    "accum20",
]


def _z(v: float, lo: float = -3, hi: float = 3) -> float:
    if not math.isfinite(v):
        return 0.0
    return float(np.clip(v, lo, hi))


def _current_lead_score_row(cur: np.ndarray) -> float:
    """cur order matches STOCK_FEATURES."""
    cvm20, cvm50, d52, rs20, rs60, vt, acc = (float(cur[i]) for i in range(7))
    score = 0.0
    score += 0.9 * _z(cvm20 * 10)
    score += 1.0 * _z(cvm50 * 10)
    score += 0.8 * _z((d52 + 0.10) * 10)
    score += 1.1 * _z(rs20 * 10)
    score += 0.8 * _z(rs60 * 10)
    score += 0.6 * _z((vt - 1.0) * 2.0)
    score += 0.5 * _z(acc / 3.0)
    return score


def _analog_p_hist_numpy(
    feat_np: np.ndarray,
    lab: np.ndarray,
    top_k: int,
    min_rows: int,
) -> float:
    """Match bds_leader_scan._analog_probability logic (vectorized). feat_np ends at current bar."""
    n = feat_np.shape[0]
    if n < min_rows:
        return float("nan")
    hist = feat_np[:-21, :]
    labh = lab[:-21]
    mfeat = np.isfinite(hist).all(axis=1) & np.isfinite(labh)
    hist2 = hist[mfeat]
    lab2 = labh[mfeat]
    if len(hist2) < max(80, top_k):
        return float("nan")
    cur = feat_np[-1, :].astype(float, copy=False)
    mu = hist2.mean(axis=0)
    sd = hist2.std(axis=0)
    sd = np.where((sd > 1e-9) & np.isfinite(sd), sd, 1.0)
    curv = (cur - mu) / sd
    curv = np.nan_to_num(curv, nan=0.0, posinf=0.0, neginf=0.0)
    hv = (hist2 - mu) / sd
    hv = np.nan_to_num(hv, nan=0.0, posinf=0.0, neginf=0.0)
    d2 = ((hv - curv) ** 2).sum(axis=1)
    k = min(top_k, len(d2))
    idx = np.argpartition(d2, k - 1)[:k]
    return float(np.mean(lab2[idx]))


def _scores_for_symbol(
    sym: str,
    feat: pd.DataFrame,
    sym_meta: dict[str, dict[str, Any]],
    trade_dates_ns: np.ndarray,
    min_rows: int,
    analog_top_k: int,
) -> list[dict[str, Any]]:
    """All trade dates for one symbol (vector-friendly inner loop)."""
    need_cols = STOCK_FEATURES + ["label_lead20", "close", "volume"]
    for c in need_cols:
        if c not in feat.columns:
            return []
    dates = feat["date"].values.astype("datetime64[ns]")
    X = feat[STOCK_FEATURES].to_numpy(dtype=float)
    lab = feat["label_lead20"].to_numpy(dtype=float)
    close = feat["close"].to_numpy(dtype=float)
    vol = feat["volume"].to_numpy(dtype=float)
    val = close * 1000.0 * vol

    m = sym_meta.get(sym, {})
    name = str(m.get("name") or "")
    exch = str(m.get("exchange") or "")
    ind = str(m.get("industryCode") or "")

    # rolling adv50 at each index (same length as feat)
    adv50 = pd.Series(val).rolling(50, min_periods=50).mean().to_numpy(dtype=float)

    out: list[dict[str, Any]] = []
    # For each trade date, find row index (last bar <= that date)
    for td in trade_dates_ns:
        idx = int(np.searchsorted(dates, td, side="right") - 1)
        if idx < min_rows - 1:
            continue
        sub_x = X[: idx + 1]
        sub_lab = lab[: idx + 1]
        if sub_x.shape[0] < min_rows:
            continue
        p_hist = _analog_p_hist_numpy(sub_x, sub_lab, analog_top_k, min_rows)
        cur = sub_x[-1]
        p_now = float(_sigmoid(_current_lead_score_row(cur) / 3.0))
        p20 = float(np.nanmean([p_now, p_hist])) if np.isfinite(p_hist) else p_now
        if not np.isfinite(p20):
            continue
        adv = float(adv50[idx]) if idx < len(adv50) and np.isfinite(adv50[idx]) else float("nan")
        c_last = float(close[idx]) if np.isfinite(close[idx]) else float("nan")
        dstr = str(np.datetime_as_string(td, unit="D"))
        out.append(
            {
                "date": dstr,
                "symbol": sym,
                "name": name,
                "exchange": exch,
                "industryCode": ind,
                "stock_p20": p20,
                "p_now": p_now,
                "p_hist": float(p_hist) if np.isfinite(p_hist) else float("nan"),
                "adv50_vnd": adv,
                "close": c_last,
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", default="2025-03-01")
    ap.add_argument("--to", dest="date_to", default="2025-07-31")
    ap.add_argument("--history-start", default="2010-01-01", help="OHLCV fetch start for warm windows.")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--min-rows-analog", type=int, default=320)
    ap.add_argument("--analog-top-k", type=int, default=20)
    ap.add_argument("--page-size", type=int, default=200)
    ap.add_argument("--workers", type=int, default=10, help="Threads for per-symbol scoring.")
    ap.add_argument("--min-adv50-vnd", type=float, default=0.0, help="Filter rows with ADV50 >= threshold.")
    ap.add_argument(
        "--out-csv",
        default=str(REPO / "data" / "research" / "daily_top20_stock_p20_2025-03_to_07.csv"),
    )
    ap.add_argument(
        "--out-xlsx",
        default=str(REPO / "data" / "research" / "daily_top20_stock_p20_2025-03_to_07.xlsx"),
    )
    args = ap.parse_args()

    client = get_client(timeout=45)

    d0 = pd.Timestamp(args.date_from)
    d1 = pd.Timestamp(args.date_to)

    vni = client.get_ohlcv("VNINDEX", start=args.history_start, end=args.date_to)
    if vni.empty:
        raise SystemExit("VNINDEX empty")
    vni = vni.sort_values("date").reset_index(drop=True)
    vni["date"] = pd.to_datetime(vni["date"])
    for c in ["open", "high", "low", "close", "volume"]:
        if c in vni.columns:
            vni[c] = pd.to_numeric(vni[c], errors="coerce")

    cal = vni[(vni["date"] >= d0) & (vni["date"] <= d1)]["date"].drop_duplicates().sort_values()
    trade_dates = [pd.Timestamp(x) for x in cal.tolist()]
    trade_dates_ns = np.array([np.datetime64(d, "ns") for d in trade_dates], dtype="datetime64[ns]")
    if not trade_dates:
        raise SystemExit("No VNINDEX trading days in range")

    uni = fetch_symbols_universe(client, limit=args.page_size)
    uni = uni[(uni["type"].str.lower() == "stock") & (uni["isListing"])].copy()
    uni = uni.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    if uni.empty:
        raise SystemExit("Empty listing universe")

    warnings: list[str] = []
    feat_cache: dict[str, pd.DataFrame] = {}

    sym_meta: dict[str, dict[str, Any]] = {}
    for _, r in uni.iterrows():
        sym = str(r["symbol"]).upper().strip()
        sym_meta[sym] = {
            "name": r.get("name"),
            "exchange": r.get("exchange"),
            "industryCode": str(r.get("industryCode") or ""),
        }
        try:
            sdf = client.get_ohlcv(sym, start=args.history_start, end=args.date_to)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"fetch_fail:{sym}:{exc}")
            continue
        if sdf.empty or len(sdf) < args.min_rows_analog + 30:
            continue
        sdf = sdf.sort_values("date").reset_index(drop=True)
        sdf["date"] = pd.to_datetime(sdf["date"])
        for c in ["open", "high", "low", "close", "volume"]:
            if c in sdf.columns:
                sdf[c] = pd.to_numeric(sdf[c], errors="coerce")
        sdf = sdf.dropna(subset=["date", "close", "high", "low", "volume"])
        vni_sub = vni[vni["date"] <= sdf["date"].max()].copy()
        try:
            feat = _compute_features(sdf, vni=vni_sub)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"features_fail:{sym}:{exc}")
            continue
        feat_cache[sym] = feat

    by_date: dict[str, list[dict[str, Any]]] = {d.strftime("%Y-%m-%d"): [] for d in trade_dates}

    def _job(sym: str) -> list[dict[str, Any]]:
        return _scores_for_symbol(
            sym,
            feat_cache[sym],
            sym_meta,
            trade_dates_ns,
            args.min_rows_analog,
            args.analog_top_k,
        )

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_job, s): s for s in feat_cache}
        for fut in as_completed(futs):
            try:
                rows = fut.result()
            except Exception as exc:  # pragma: no cover
                warnings.append(f"score_fail:{futs[fut]}:{exc}")
                continue
            for row in rows:
                by_date[row["date"]].append(row)

    out_rows: list[dict[str, Any]] = []
    for dstr in sorted(by_date.keys()):
        day_scores = [
            x
            for x in by_date[dstr]
            if np.isfinite(x.get("adv50_vnd", np.nan)) and float(x["adv50_vnd"]) >= float(args.min_adv50_vnd)
        ]
        day_scores = sorted(day_scores, key=lambda x: x["stock_p20"], reverse=True)
        for rank, row in enumerate(day_scores[: args.top_n], start=1):
            row = dict(row)
            row["rank"] = rank
            out_rows.append(row)

    out_df = pd.DataFrame(out_rows)
    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    xlsx_path = Path(args.out_xlsx)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_excel(xlsx_path, index=False)

    meta = {
        "source": "FireAnt",
        "method": "REST API",
        "universe": "listing stocks from symbols/search",
        "date_range": {"from": args.date_from, "to": args.date_to},
        "trading_days": len(trade_dates),
        "symbols_with_features": len(feat_cache),
        "rows_written": len(out_df),
        "top_n": args.top_n,
        "min_adv50_vnd": args.min_adv50_vnd,
        "stock_p20_definition": "mean(p_now, p_hist) per backtest_random_p20_high.py",
        "warnings_sample": warnings[:30],
        "warnings_total": len(warnings),
        "out_csv": str(out_path),
        "out_xlsx": str(xlsx_path),
    }
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
