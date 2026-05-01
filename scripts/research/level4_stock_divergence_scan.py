#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.research.bds_leader_scan import (  # noqa: E402
    _analog_probability,
    _compute_features,
    _current_lead_score,
    _sigmoid,
    _date_range,
    fetch_symbols_universe,
)
from src.data.fireant_client import get_client  # noqa: E402


FEATURE_COLS = [
    "close_vs_ma20",
    "close_vs_ma50",
    "dist_to_52w_high",
    "rs20",
    "rs60",
    "vol_thrust20",
    "accum20",
]


def _load_level4_probability_map(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rank = pd.DataFrame(payload.get("ranking", []))
    if rank.empty:
        raise ValueError(f"Empty ranking in {path}")
    rank["industryCode"] = rank["industryCode"].astype(str).str.zfill(4)
    return rank[["industryCode", "industryName", "p_wave_20d"]].copy()


def _build_level3_to_level4_proxy(level4_df: pd.DataFrame, value_share_csv: Path) -> pd.DataFrame:
    val = pd.read_csv(value_share_csv)
    val["industryCode"] = val["industryCode"].astype(str).str.zfill(4)
    val["parent3"] = val["industryCode"].str[:3] + "0"
    val["avg_daily_value_bn_vnd"] = pd.to_numeric(val["avg_daily_value_bn_vnd"], errors="coerce").fillna(0.0)
    val = val.sort_values(["parent3", "avg_daily_value_bn_vnd"], ascending=[True, False])
    top = val.drop_duplicates(subset=["parent3"], keep="first")
    merged = top.merge(level4_df, on="industryCode", how="left", suffixes=("_value", "_rank"))
    name_col = "industryName"
    if name_col not in merged.columns:
        if "industryName_rank" in merged.columns:
            name_col = "industryName_rank"
        elif "industryName_value" in merged.columns:
            name_col = "industryName_value"
    merged = merged.rename(
        columns={
            "parent3": "industryCode_l3",
            "industryCode": "proxy_industryCode_l4",
            name_col: "proxy_industryName_l4",
            "p_wave_20d": "industry_p20_l4",
        }
    )
    return merged[
        ["industryCode_l3", "proxy_industryCode_l4", "proxy_industryName_l4", "industry_p20_l4", "avg_daily_value_bn_vnd"]
    ]


def run(args: argparse.Namespace) -> Dict[str, Any]:
    client = get_client(timeout=args.timeout)
    start, end = _date_range(args.history_years)
    vnindex = client.get_ohlcv("VNINDEX", start=start, end=end)
    if vnindex.empty:
        return {"errors": ["vnindex_empty"], "ranking": []}
    vnindex = vnindex.sort_values("date").reset_index(drop=True)

    level4 = _load_level4_probability_map(Path(args.industry_prob_json))
    l3_l4 = _build_level3_to_level4_proxy(level4, Path(args.industry_value_share_csv))

    uni = fetch_symbols_universe(client, limit=args.page_size)
    uni = uni[(uni["type"].str.lower() == "stock") & (uni["isListing"])].copy()
    uni["industryCode"] = uni["industryCode"].astype(str).str.zfill(4)
    uni = uni.merge(l3_l4, left_on="industryCode", right_on="industryCode_l3", how="inner")
    uni = uni.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    if uni.empty:
        return {"errors": ["symbol_universe_empty_after_l3_l4_map"], "ranking": []}

    # Pre-filter liquidity from recent bars to avoid heavy full-history scans.
    end_dt = date.today()
    start_liq = end_dt - timedelta(days=120)
    liquid_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for _, r in uni.iterrows():
        sym = str(r["symbol"])
        try:
            q = client.get_ohlcv(sym, start=start_liq.isoformat(), end=end_dt.isoformat())
        except Exception as exc:  # pragma: no cover
            warnings.append(f"liq_fetch_fail:{sym}:{exc}")
            continue
        if q.empty:
            continue
        tv = pd.to_numeric(q["close"], errors="coerce") * pd.to_numeric(q["volume"], errors="coerce")
        adv_raw = float(tv.tail(20).median()) if len(tv) >= 20 else float(tv.median())
        adv_vnd = adv_raw * 1000.0  # project convention: raw values are in thousand VND
        if np.isfinite(adv_vnd) and adv_vnd >= args.min_adv_vnd:
            d = r.to_dict()
            d["adv20_vnd"] = adv_vnd
            liquid_rows.append(d)

    liquid = pd.DataFrame(liquid_rows)
    if liquid.empty:
        return {"errors": ["no_symbol_passed_adv_filter"], "warnings": warnings, "ranking": []}

    rows: List[Dict[str, Any]] = []
    for _, r in liquid.iterrows():
        sym = str(r["symbol"])
        try:
            df = client.get_ohlcv(sym, start=start, end=end)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"full_fetch_fail:{sym}:{exc}")
            continue
        if df.empty or len(df) < 260:
            warnings.append(f"insufficient_history:{sym}")
            continue
        feat = _compute_features(df, vni=vnindex)
        cur = feat.iloc[-1]
        lead_now_score = _current_lead_score(cur)
        p_hist, exp_ret_hist, exp_dd_hist = _analog_probability(feat, feature_cols=FEATURE_COLS, top_k=args.analog_top_k)
        p_now = _sigmoid(lead_now_score / 3.0)
        stock_p20 = float(np.nanmean([p_now, p_hist])) if np.isfinite(p_hist) else float(p_now)
        industry_p20 = float(r["industry_p20_l4"]) if pd.notna(r["industry_p20_l4"]) else np.nan

        rows.append(
            {
                "date": pd.to_datetime(cur["date"]).strftime("%Y-%m-%d"),
                "symbol": sym,
                "name": r.get("name"),
                "exchange": r.get("exchange"),
                "industryCode_l3": r.get("industryCode"),
                "proxy_industryCode_l4": r.get("proxy_industryCode_l4"),
                "proxy_industryName_l4": r.get("proxy_industryName_l4"),
                "stock_p20": stock_p20,
                "industry_p20_l4": industry_p20,
                "p20_gap": stock_p20 - industry_p20 if np.isfinite(industry_p20) else np.nan,
                "adv20_vnd": float(r["adv20_vnd"]),
                "lead_prob_from_current_action": float(p_now),
                "lead_prob_from_historical_analogs": float(p_hist) if np.isfinite(p_hist) else np.nan,
                "expected_return_20d_from_analogs": float(exp_ret_hist) if np.isfinite(exp_ret_hist) else np.nan,
                "expected_drawdown_20d_from_analogs": float(exp_dd_hist) if np.isfinite(exp_dd_hist) else np.nan,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return {"errors": ["no_stock_rows_after_scan"], "warnings": warnings, "ranking": []}

    out = out.sort_values(["p20_gap", "stock_p20", "adv20_vnd"], ascending=[False, False, False]).reset_index(drop=True)
    divergence = out[
        (out["industry_p20_l4"] <= args.max_industry_p20_for_low)
        & (out["stock_p20"] >= args.min_stock_p20_for_high)
        & (out["p20_gap"] >= args.min_gap)
    ].copy()

    out_csv = Path(args.out_csv)
    div_csv = Path(args.out_divergence_csv)
    out_json = Path(args.out_json)
    for p in [out_csv, div_csv, out_json]:
        p.parent.mkdir(parents=True, exist_ok=True)

    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    divergence.to_csv(div_csv, index=False, encoding="utf-8-sig")

    payload = {
        "meta": {
            "source": "FireAnt",
            "method": "REST API",
            "date_range": {"start": start, "end": end, "asof": out.iloc[0]["date"]},
            "notes": [
                "industry level-4 is proxy-mapped from symbol level-3 code by dominant traded-value child in level-4",
                "adv20_vnd = median_traded_value_20d_raw * 1000",
            ],
            "filters": {
                "min_adv_vnd": args.min_adv_vnd,
                "industry_low_threshold": args.max_industry_p20_for_low,
                "stock_high_threshold": args.min_stock_p20_for_high,
                "min_gap": args.min_gap,
            },
            "universe_size_before_adv": int(len(uni)),
            "universe_size_after_adv": int(len(liquid)),
            "scanned_size": int(len(out)),
            "divergence_size": int(len(divergence)),
            "warnings": warnings,
            "errors": [],
        },
        "ranking_all": out.to_dict(orient="records"),
        "ranking_divergence": divergence.to_dict(orient="records"),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {
        "csv_all": str(out_csv),
        "csv_divergence": str(div_csv),
        "json": str(out_json),
        "universe_after_adv": int(len(liquid)),
        "scanned": int(len(out)),
        "divergence": int(len(divergence)),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan level-4 industry divergences: high stock_p20 vs low industry_p20.")
    p.add_argument("--history-years", type=int, default=6)
    p.add_argument("--analog-top-k", type=int, default=20)
    p.add_argument("--page-size", type=int, default=300)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--min-adv-vnd", type=float, default=2_000_000_000)
    p.add_argument("--max-industry-p20-for-low", type=float, default=0.20)
    p.add_argument("--min-stock-p20-for-high", type=float, default=0.35)
    p.add_argument("--min-gap", type=float, default=0.12)
    p.add_argument(
        "--industry-prob-json",
        default=str(_REPO / "data" / "research" / "industry_wave_probability_l4_since2012_nb11_mt900.json"),
    )
    p.add_argument(
        "--industry-value-share-csv",
        default=str(_REPO / "data" / "research" / "industry_value_share_1m_level4.csv"),
    )
    p.add_argument(
        "--out-csv",
        default=str(_REPO / "data" / "research" / "level4_stock_scan_adv2b_all.csv"),
    )
    p.add_argument(
        "--out-divergence-csv",
        default=str(_REPO / "data" / "research" / "level4_stock_scan_adv2b_divergence.csv"),
    )
    p.add_argument(
        "--out-json",
        default=str(_REPO / "data" / "research" / "level4_stock_scan_adv2b_divergence.json"),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    res = run(args)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
