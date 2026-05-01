#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import RESTV2_BASE, get_client  # noqa: E402
from scripts.research.bds_leader_scan import (  # noqa: E402
    _analog_probability,
    _compute_features,
    _current_lead_score,
    _sigmoid,
    fetch_symbols_universe,
)
from scripts.research.industry_wave_probability import (  # noqa: E402
    FEATURE_COLS,
    _fit_bin_model,
    _feature_engineering,
    _parse_industry_master,
    _predict_bin_model,
    _prepare_dataset,
)


@dataclass
class EvalResult:
    n: int = 0
    hits: int = 0

    @property
    def hit_rate(self) -> float:
        return float(self.hits / self.n) if self.n else float("nan")


def _infer_level3_parent(code_l4: str) -> str:
    return f"{(int(code_l4) // 10) * 10:04d}"


def _slice_to_date(df: pd.DataFrame, dt: pd.Timestamp) -> pd.DataFrame:
    return df[df["date"] <= dt].sort_values("date").reset_index(drop=True)


def _stock_success_label(df: pd.DataFrame, dt: pd.Timestamp) -> float | None:
    x = df[df["date"] >= dt].sort_values("date").reset_index(drop=True)
    if len(x) < 21:
        return None
    c0 = float(x.at[0, "close"])
    c20 = float(x.at[20, "close"])
    ret20 = c20 / c0 - 1.0
    mdd20 = float(x.loc[1:20, "close"].min() / c0 - 1.0)
    return 1.0 if (ret20 > 0.08 and mdd20 > -0.08) else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--n-random-dates", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-train-rows", type=int, default=900)
    ap.add_argument("--n-bins", type=int, default=8)
    ap.add_argument("--industry-p20-threshold", type=float, default=0.15)
    ap.add_argument("--stock-p20-threshold", type=float, default=0.20)
    ap.add_argument("--adv50-vnd-min", type=float, default=2_000_000_000.0)
    ap.add_argument(
        "--out-json",
        default=str(REPO / "data" / "research" / "random_backtest_p20_high.json"),
    )
    args = ap.parse_args()

    token = os.environ.get("FIREANT_TOKEN")
    client = get_client(token=token, timeout=30)

    raw_master = client._get(f"{RESTV2_BASE}/industries", params=None)  # type: ignore[attr-defined]
    raw_master_list = raw_master if isinstance(raw_master, list) else []
    master_df = _parse_industry_master(raw_master_list, level=4)
    master_all_df = pd.DataFrame(raw_master_list)
    master_all_df["industryCode"] = master_all_df["industryCode"].astype(str)
    master_all_df["level"] = pd.to_numeric(master_all_df["level"], errors="coerce")

    histories: dict[str, pd.DataFrame] = {}
    for code in master_df["industryCode"].astype(str):
        data = client._get(  # type: ignore[attr-defined]
            f"{RESTV2_BASE}/industries/{code}/historical-stats",
            params={"startDate": args.start, "endDate": args.end},
        )
        rows: list[dict[str, Any]] = []
        for it in data if isinstance(data, list) else []:
            rows.append(
                {
                    "industryCode": code,
                    "date": str(it.get("date", ""))[:10],
                    "open": it.get("indexOpen"),
                    "high": it.get("indexHigh"),
                    "low": it.get("indexLow"),
                    "close": it.get("indexClose"),
                    "volume": it.get("totalVolume"),
                }
            )
        df = pd.DataFrame(rows)
        if df.empty:
            histories[code] = pd.DataFrame()
            continue
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        histories[code] = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)

    vni = client.get_ohlcv("VNINDEX", start=args.start, end=args.end)
    vni = vni[["date", "close"]].rename(columns={"close": "vnindex_close"})
    vni["date"] = pd.to_datetime(vni["date"])

    dataset = _prepare_dataset(master_df, master_all_df, histories, vni)
    dataset = dataset.dropna(subset=list(FEATURE_COLS) + ["label_wave_20d"]).copy()
    all_dates = sorted(dataset["date"].unique().tolist())
    eligible_dates = all_dates[args.min_train_rows // max(len(master_df), 1) : -25]
    if len(eligible_dates) < args.n_random_dates:
        raise RuntimeError("Not enough eligible dates for random sampling.")

    rng = np.random.default_rng(args.seed)
    sample_dates = sorted(rng.choice(eligible_dates, size=args.n_random_dates, replace=False).tolist())

    uni = fetch_symbols_universe(client, limit=200)
    uni = uni[(uni["type"].str.lower() == "stock") & (uni["isListing"])].copy()
    uni["industryCode"] = uni["industryCode"].astype(str).str.zfill(4)

    symbol_cache: dict[str, pd.DataFrame] = {}

    industry_eval = EvalResult()
    stock_eval = EvalResult()
    per_date: list[dict[str, Any]] = []

    stock_features = [
        "close_vs_ma20",
        "close_vs_ma50",
        "dist_to_52w_high",
        "rs20",
        "rs60",
        "vol_thrust20",
        "accum20",
    ]

    for dt in sample_dates:
        dt = pd.Timestamp(dt)
        train = dataset[dataset["date"] < dt].dropna(subset=list(FEATURE_COLS) + ["label_wave_20d"])
        test = dataset[dataset["date"] == dt].dropna(subset=list(FEATURE_COLS) + ["label_wave_20d"])
        if len(train) < args.min_train_rows or test.empty:
            continue

        model = _fit_bin_model(train, "label_wave_20d", FEATURE_COLS, args.n_bins)
        test = test.copy()
        test["p20"] = _predict_bin_model(model, test, FEATURE_COLS)
        high_ind = test[test["p20"] >= args.industry_p20_threshold].copy()

        ind_hits = int(high_ind["label_wave_20d"].sum())
        ind_n = int(len(high_ind))
        industry_eval.n += ind_n
        industry_eval.hits += ind_hits

        dt_summary: dict[str, Any] = {
            "date": dt.strftime("%Y-%m-%d"),
            "industries_selected": ind_n,
            "industries_hit": ind_hits,
            "industries_hit_rate": float(ind_hits / ind_n) if ind_n else None,
            "stocks_selected": 0,
            "stocks_hit": 0,
            "stocks_hit_rate": None,
        }

        vni_dt = _slice_to_date(
            client.get_ohlcv("VNINDEX", start=args.start, end=dt.strftime("%Y-%m-%d")), dt
        )
        if vni_dt.empty:
            per_date.append(dt_summary)
            continue

        stock_rows = 0
        stock_hits = 0
        for _, ind_row in high_ind.iterrows():
            l4 = str(ind_row["industryCode"]).zfill(4)
            l3 = _infer_level3_parent(l4)
            stocks = uni[uni["industryCode"] == l3]
            for _, s in stocks.iterrows():
                sym = str(s["symbol"])
                if sym not in symbol_cache:
                    symbol_cache[sym] = client.get_ohlcv(sym, start=args.start, end=args.end)
                sdf = symbol_cache[sym]
                sdf = _slice_to_date(sdf, dt)
                if sdf.empty or len(sdf) < 260:
                    continue
                adv50 = float((sdf["close"] * 1000.0 * sdf["volume"]).rolling(50).mean().iloc[-1])
                if not np.isfinite(adv50) or adv50 < args.adv50_vnd_min:
                    continue

                feat = _compute_features(sdf, vni=vni_dt)
                cur = feat.iloc[-1]
                p_hist, _, _ = _analog_probability(feat, feature_cols=stock_features, top_k=20)
                p_now = _sigmoid(_current_lead_score(cur) / 3.0)
                p_stock = float(np.nanmean([p_now, p_hist])) if np.isfinite(p_hist) else float(p_now)
                if p_stock < args.stock_p20_threshold:
                    continue

                label = _stock_success_label(symbol_cache[sym], dt)
                if label is None:
                    continue
                stock_rows += 1
                stock_hits += int(label)

        stock_eval.n += stock_rows
        stock_eval.hits += stock_hits
        dt_summary["stocks_selected"] = stock_rows
        dt_summary["stocks_hit"] = stock_hits
        dt_summary["stocks_hit_rate"] = float(stock_hits / stock_rows) if stock_rows else None
        per_date.append(dt_summary)

    result = {
        "params": {
            "date_range": {"start": args.start, "end": args.end},
            "n_random_dates": args.n_random_dates,
            "seed": args.seed,
            "industry_p20_threshold": args.industry_p20_threshold,
            "stock_p20_threshold": args.stock_p20_threshold,
            "adv50_vnd_min": args.adv50_vnd_min,
            "adv_formula": "rolling_mean_50(close * 1000 * volume)",
        },
        "industry_eval": {
            "selected": industry_eval.n,
            "hits": industry_eval.hits,
            "hit_rate": industry_eval.hit_rate,
        },
        "stock_eval": {
            "selected": stock_eval.n,
            "hits": stock_eval.hits,
            "hit_rate": stock_eval.hit_rate,
        },
        "per_date": per_date,
    }

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
