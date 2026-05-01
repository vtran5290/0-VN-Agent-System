#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.data.fireant_client import RESTV2_BASE, get_client  # noqa: E402


def _safe_pct(a: float, b: float) -> float:
    if b == 0 or not np.isfinite(b):
        return np.nan
    return a / b - 1.0


def _date_range(years_back: int) -> Tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=int(years_back * 365.25))
    return start.isoformat(), end.isoformat()


def fetch_symbols_universe(client: Any, limit: int = 200) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    offset = 0
    seen = set()
    while True:
        data = client._get(  # type: ignore[attr-defined]
            f"{RESTV2_BASE}/symbols/search",
            params={"keywords": "", "offset": offset, "limit": limit},
        )
        if not isinstance(data, list) or not data:
            break
        for it in data:
            sym = str(it.get("symbol") or "").upper().strip()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            rows.append(
                {
                    "symbol": sym,
                    "name": it.get("name"),
                    "exchange": it.get("exchange"),
                    "type": it.get("type"),
                    "isListing": bool(it.get("isListing", False)),
                    "industryCode": str(it.get("industryCode") or ""),
                    "icbCode": str(it.get("icbCode") or ""),
                }
            )
        offset += limit
        if len(data) < limit:
            break
    return pd.DataFrame(rows)


def _compute_features(df: pd.DataFrame, vni: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x = x.merge(vni[["date", "close"]].rename(columns={"close": "vni_close"}), on="date", how="left")
    x = x.sort_values("date").reset_index(drop=True)
    x["ret1"] = x["close"].pct_change()
    x["ma20"] = x["close"].rolling(20).mean()
    x["ma50"] = x["close"].rolling(50).mean()
    x["ma200"] = x["close"].rolling(200).mean()
    x["close_vs_ma20"] = x["close"] / x["ma20"] - 1.0
    x["close_vs_ma50"] = x["close"] / x["ma50"] - 1.0
    x["close_vs_ma200"] = x["close"] / x["ma200"] - 1.0
    x["dist_to_52w_high"] = x["close"] / x["high"].rolling(252).max() - 1.0
    x["ret20"] = x["close"] / x["close"].shift(20) - 1.0
    x["ret60"] = x["close"] / x["close"].shift(60) - 1.0
    x["vni_ret20"] = x["vni_close"] / x["vni_close"].shift(20) - 1.0
    x["vni_ret60"] = x["vni_close"] / x["vni_close"].shift(60) - 1.0
    x["rs20"] = x["ret20"] - x["vni_ret20"]
    x["rs60"] = x["ret60"] - x["vni_ret60"]
    x["vol_thrust20"] = x["volume"] / x["volume"].rolling(20).median()
    x["vol_thrust20"] = x["vol_thrust20"].replace([np.inf, -np.inf], np.nan)

    up_heavy = (x["close"] > x["close"].shift(1)) & (x["volume"] > 1.5 * x["volume"].rolling(20).mean())
    dn_heavy = (x["close"] < x["close"].shift(1)) & (x["volume"] > 1.5 * x["volume"].rolling(20).mean())
    x["accum20"] = up_heavy.rolling(20).sum() - dn_heavy.rolling(20).sum()
    x["accum60"] = up_heavy.rolling(60).sum() - dn_heavy.rolling(60).sum()

    fwd20 = x["close"].shift(-20) / x["close"] - 1.0
    fut_min20 = x["close"].shift(-1).rolling(20, min_periods=20).min().shift(-19)
    fwd_mdd20 = fut_min20 / x["close"] - 1.0
    x["label_lead20"] = ((fwd20 > 0.08) & (fwd_mdd20 > -0.08)).astype(float)
    x["fwd20"] = fwd20
    x["fwd_mdd20"] = fwd_mdd20
    return x


def _z(v: float, lo: float = -3, hi: float = 3) -> float:
    if not np.isfinite(v):
        return 0.0
    return float(np.clip(v, lo, hi))


def _current_lead_score(row: pd.Series) -> float:
    score = 0.0
    score += 0.9 * _z(row.get("close_vs_ma20", np.nan) * 10)
    score += 1.0 * _z(row.get("close_vs_ma50", np.nan) * 10)
    score += 0.8 * _z((row.get("dist_to_52w_high", np.nan) + 0.10) * 10)
    score += 1.1 * _z(row.get("rs20", np.nan) * 10)
    score += 0.8 * _z(row.get("rs60", np.nan) * 10)
    score += 0.6 * _z((row.get("vol_thrust20", np.nan) - 1.0) * 2.0)
    score += 0.5 * _z(row.get("accum20", np.nan) / 3.0)
    return score


def _analog_probability(df: pd.DataFrame, feature_cols: List[str], top_k: int = 20) -> Tuple[float, float, float]:
    if df.empty or len(df) < 320:
        return np.nan, np.nan, np.nan
    cur = df.iloc[-1]
    hist = df.iloc[:-21].copy()
    hist = hist.dropna(subset=feature_cols + ["label_lead20", "fwd20", "fwd_mdd20"])
    if len(hist) < max(80, top_k):
        return np.nan, np.nan, np.nan

    x_hist = hist[feature_cols].copy()
    mu = x_hist.mean()
    sd = x_hist.std().replace(0, np.nan)
    curv = ((cur[feature_cols] - mu) / sd).astype(float)
    curv = pd.Series(np.where(np.isfinite(curv), curv, np.nan), index=curv.index).fillna(0.0)
    hv = ((x_hist - mu) / sd).astype(float)
    hv = hv.apply(lambda s: pd.Series(np.where(np.isfinite(s), s, np.nan), index=s.index))
    hv = hv.fillna(0.0)
    d2 = ((hv - curv) ** 2).sum(axis=1)
    pick = hist.loc[d2.nsmallest(top_k).index].copy()
    if pick.empty:
        return np.nan, np.nan, np.nan
    p = float(pick["label_lead20"].mean())
    exp_ret = float(pick["fwd20"].mean())
    exp_dd = float(pick["fwd_mdd20"].mean())
    return p, exp_ret, exp_dd


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def run_scan(args: argparse.Namespace) -> Dict[str, Any]:
    client = get_client(timeout=args.timeout)
    start, end = _date_range(args.history_years)
    vni = client.get_ohlcv("VNINDEX", start=start, end=end)
    if vni.empty:
        return {"errors": ["vnindex_empty"], "ranking": []}
    vni = vni.sort_values("date").reset_index(drop=True)

    uni = fetch_symbols_universe(client, limit=args.page_size)
    if uni.empty:
        return {"errors": ["symbol_universe_empty"], "ranking": []}

    match_mask = uni["industryCode"] == args.industry_code
    if args.icb_code:
        match_mask = match_mask | (uni["icbCode"] == args.icb_code)

    target = uni[
        (uni["type"].str.lower() == "stock")
        & (uni["isListing"])
        & match_mask
    ].copy()
    target = target.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    if target.empty:
        return {
            "errors": [f"no_symbols_for_icb_or_industry:{args.icb_code}|{args.industry_code}"],
            "ranking": [],
        }

    rows: List[Dict[str, Any]] = []
    feature_cols = [
        "close_vs_ma20",
        "close_vs_ma50",
        "dist_to_52w_high",
        "rs20",
        "rs60",
        "vol_thrust20",
        "accum20",
    ]
    warnings: List[str] = []
    for _, r in target.iterrows():
        sym = str(r["symbol"])
        try:
            df = client.get_ohlcv(sym, start=start, end=end)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"fetch_fail:{sym}:{exc}")
            continue
        if df.empty or len(df) < 260:
            warnings.append(f"insufficient_history:{sym}")
            continue
        feat = _compute_features(df, vni=vni)
        cur = feat.iloc[-1]
        lead_now_score = _current_lead_score(cur)
        p_hist, exp_ret_hist, exp_dd_hist = _analog_probability(feat, feature_cols=feature_cols, top_k=args.analog_top_k)
        p_now = _sigmoid(lead_now_score / 3.0)
        lead_prob = float(np.nanmean([p_now, p_hist])) if np.isfinite(p_hist) else float(p_now)

        med_val20 = float((feat["close"] * feat["volume"]).rolling(20).median().iloc[-1])
        rows.append(
            {
                "date": pd.to_datetime(cur["date"]).strftime("%Y-%m-%d"),
                "symbol": sym,
                "name": r.get("name"),
                "exchange": r.get("exchange"),
                "icbCode": r.get("icbCode"),
                "industryCode": r.get("industryCode"),
                "lead_prob_20d": lead_prob,
                "lead_prob_from_current_action": p_now,
                "lead_prob_from_historical_analogs": p_hist,
                "expected_return_20d_from_analogs": exp_ret_hist,
                "expected_drawdown_20d_from_analogs": exp_dd_hist,
                "close_vs_ma20": cur.get("close_vs_ma20"),
                "close_vs_ma50": cur.get("close_vs_ma50"),
                "dist_to_52w_high": cur.get("dist_to_52w_high"),
                "rs20": cur.get("rs20"),
                "rs60": cur.get("rs60"),
                "vol_thrust20": cur.get("vol_thrust20"),
                "accum20": cur.get("accum20"),
                "median_traded_value_20d": med_val20,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return {"errors": ["no_stock_rows_after_scan"], "warnings": warnings, "ranking": []}
    out = out.sort_values("lead_prob_20d", ascending=False).reset_index(drop=True)

    out_csv = Path(args.out_csv)
    out_json = Path(args.out_json)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)

    payload = {
        "meta": {
            "source": "FireAnt",
            "method": "REST API",
            "date_range": {"start": start, "end": end, "asof": out.iloc[0]["date"]},
            "target_group": {
                "icb_code": args.icb_code,
                "industry_code": args.industry_code,
                "note": "default maps to BDS detailed group under Finance",
            },
            "universe_size": int(len(target)),
            "scanned_size": int(len(out)),
            "warnings": warnings,
            "errors": [],
            "limitations": [
                "Model is heuristic ranker, not a guaranteed forecast.",
                "Analogs are self-history per ticker; regime shift may reduce relevance.",
                "No fundamental/news catalyst in this version.",
            ],
            "integrity_flags": {
                "high_zero_volume": bool((out["median_traded_value_20d"] <= 0).mean() > 0.1),
                "missing_bars": False,
            },
        },
        "ranking": out.to_dict(orient="records"),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {
        "csv": str(out_csv),
        "json": str(out_json),
        "universe": int(len(target)),
        "scanned": int(len(out)),
        "top_symbols": out["symbol"].head(10).tolist(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan BDS stocks for wave-leading probability.")
    parser.add_argument("--icb-code", default=None, help="Optional detailed ICB code filter (e.g. 35101010).")
    parser.add_argument("--industry-code", default="8630", help="Industry code filter (default 8630 BDS investment/services).")
    parser.add_argument("--history-years", type=int, default=6, help="Lookback years for price/volume analogs.")
    parser.add_argument("--analog-top-k", type=int, default=20, help="Top-K analog setups per ticker.")
    parser.add_argument("--page-size", type=int, default=200, help="symbols/search pagination size.")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout seconds.")
    parser.add_argument(
        "--out-csv",
        default=str(_REPO / "data" / "research" / "bds_leader_scan.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--out-json",
        default=str(_REPO / "data" / "research" / "bds_leader_scan.json"),
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    res = run_scan(args)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
