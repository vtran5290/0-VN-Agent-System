#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.bds_leader_scan import _compute_features, _sigmoid, fetch_symbols_universe  # noqa: E402
from src.data.fireant_client import get_client  # noqa: E402

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
    if not np.isfinite(v):
        return 0.0
    return float(np.clip(v, lo, hi))


def _current_lead_score_row(cur: np.ndarray) -> float:
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


def _analog_p_hist_numpy(feat_np: np.ndarray, lab: np.ndarray, top_k: int, min_rows: int) -> float:
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


def main() -> None:
    p = argparse.ArgumentParser(description="Export daily April-2026 table for symbols with April ADV >= threshold.")
    p.add_argument("--from", dest="date_from", default="2026-04-01")
    p.add_argument("--to", dest="date_to", default="2026-04-30")
    p.add_argument("--history-start", default="2026-03-01")
    p.add_argument("--adv-min-vnd", type=float, default=2_000_000_000.0)
    p.add_argument("--min-rows-analog", type=int, default=320)
    p.add_argument("--analog-top-k", type=int, default=20)
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--page-size", type=int, default=200)
    p.add_argument(
        "--out-xlsx",
        default=str(REPO / "data" / "research" / "apr2026_daily_table_adv2bn.xlsx"),
    )
    p.add_argument(
        "--out-csv",
        default=str(REPO / "data" / "research" / "apr2026_daily_table_adv2bn.csv"),
    )
    args = p.parse_args()

    d0 = pd.Timestamp(args.date_from)
    d1 = pd.Timestamp(args.date_to)

    client = get_client(timeout=45)
    vni = client.get_ohlcv("VNINDEX", start=args.history_start, end=args.date_to)
    if vni.empty:
        raise RuntimeError("VNINDEX empty.")
    vni["date"] = pd.to_datetime(vni["date"], errors="coerce")
    cal = vni[(vni["date"] >= d0) & (vni["date"] <= d1)]["date"].dropna().drop_duplicates().sort_values()
    trade_dates_sorted = pd.to_datetime(cal).dt.normalize().tolist()
    trade_dates = set(trade_dates_sorted)
    if not trade_dates:
        raise RuntimeError("No VNINDEX trading days in selected range.")

    uni = fetch_symbols_universe(client, limit=args.page_size)
    uni = uni[(uni["type"].str.lower() == "stock") & (uni["isListing"])].copy()
    uni = uni.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    meta = {
        str(r["symbol"]).upper(): {
            "name": r.get("name"),
            "exchange": r.get("exchange"),
            "industryCode": str(r.get("industryCode") or ""),
        }
        for _, r in uni.iterrows()
    }

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    def _one(sym: str) -> tuple[list[dict[str, Any]], str | None]:
        try:
            df = client.get_ohlcv(sym, start=args.history_start, end=args.date_to)
        except Exception as exc:  # pragma: no cover
            return [], f"fetch_fail:{sym}:{exc}"
        if df.empty:
            return [], None

        x = df.copy()
        x["date"] = pd.to_datetime(x["date"], errors="coerce")
        for c in ["open", "high", "low", "close", "volume"]:
            x[c] = pd.to_numeric(x[c], errors="coerce")
        x = x.dropna(subset=["date", "high", "low", "close", "volume"]).sort_values("date").reset_index(drop=True)
        x["date_n"] = x["date"].dt.normalize()
        x_apr = x[(x["date_n"] >= d0.normalize()) & (x["date_n"] <= d1.normalize())]
        if x_apr.empty:
            return [], None
        # FireAnt close is in thousand VND for equities => *1000
        x_apr = x_apr[x_apr["date_n"].isin(trade_dates)].copy()
        x_apr["traded_value_vnd"] = x_apr["close"] * 1000.0 * x_apr["volume"]
        adv_apr = float(x_apr["traded_value_vnd"].mean()) if len(x_apr) else float("nan")
        if not np.isfinite(adv_apr) or adv_apr < args.adv_min_vnd:
            return [], None

        vni_sub = vni[vni["date"] <= x["date"].max()].copy()
        feat = _compute_features(x, vni=vni_sub)
        feat = feat.sort_values("date").reset_index(drop=True)
        feat["date_n"] = pd.to_datetime(feat["date"]).dt.normalize()
        dates = feat["date"].values.astype("datetime64[ns]")
        X = feat[STOCK_FEATURES].to_numpy(dtype=float)
        lab = feat["label_lead20"].to_numpy(dtype=float)

        m = meta.get(sym, {})
        out: list[dict[str, Any]] = []
        by_date = {pd.Timestamp(r["date_n"]): r for _, r in x_apr.iterrows()}
        for td in trade_dates_sorted:
            tdn = pd.Timestamp(td)
            r = by_date.get(tdn)
            if r is None:
                continue
            idx = int(np.searchsorted(dates, np.datetime64(tdn, "ns"), side="right") - 1)
            p_now = float("nan")
            p_hist = float("nan")
            p20 = float("nan")
            if idx >= args.min_rows_analog - 1:
                sub_x = X[: idx + 1]
                sub_lab = lab[: idx + 1]
                p_hist = _analog_p_hist_numpy(sub_x, sub_lab, args.analog_top_k, args.min_rows_analog)
                cur = sub_x[-1]
                p_now = float(_sigmoid(_current_lead_score_row(cur) / 3.0))
                p20 = float(np.nanmean([p_now, p_hist])) if np.isfinite(p_hist) else p_now
            out.append(
                {
                    "date": pd.Timestamp(r["date_n"]).strftime("%Y-%m-%d"),
                    "symbol": sym,
                    "name": m.get("name"),
                    "exchange": m.get("exchange"),
                    "industryCode": m.get("industryCode"),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                    "traded_value_vnd": float(r["traded_value_vnd"]),
                    "adv_apr_vnd": adv_apr,
                    "p_now": p_now,
                    "p_hist": p_hist,
                    "p20": p20,
                }
            )
        return out, None

    symbols = sorted(meta.keys())
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_one, s): s for s in symbols}
        for fut in as_completed(futs):
            part, warn = fut.result()
            if warn:
                warnings.append(warn)
            if part:
                rows.extend(part)

    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("No rows after ADV filter.")
    out = out.sort_values(["date", "p20", "traded_value_vnd"], ascending=[True, False, False]).reset_index(drop=True)

    out_csv = Path(args.out_csv)
    out_xlsx = Path(args.out_xlsx)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    out.to_excel(out_xlsx, index=False)

    summary = {
        "source": "FireAnt",
        "method": "REST API",
        "date_range": {"from": args.date_from, "to": args.date_to},
        "value_formula_vnd": "close * 1000 * volume",
        "p20_formula": "mean(p_now, p_hist_analog_top_k)",
        "adv_filter_vnd_per_day": args.adv_min_vnd,
        "symbols_selected": int(out["symbol"].nunique()),
        "trading_days": int(out["date"].nunique()),
        "rows_written": int(len(out)),
        "out_csv": str(out_csv),
        "out_xlsx": str(out_xlsx),
        "warnings_total": len(warnings),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

