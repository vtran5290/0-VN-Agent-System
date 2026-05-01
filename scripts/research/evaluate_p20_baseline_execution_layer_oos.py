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


def eval_rows(x: pd.DataFrame) -> dict[str, float]:
    if x.empty:
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
    return {
        "n": float(len(x)),
        "hit_rate": float(x["label_wave20"].mean()),
        "avg_ret20": float(x["fwd_ret20"].mean()),
        "avg_mdd20": float(x["fwd_mdd20"].mean()),
    }


def pick_baseline(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    x = df.sort_values(["date", "p20"], ascending=[True, False]).copy()
    x["rank"] = x.groupby("date")["p20"].rank(method="first", ascending=False).astype(int)
    return x.groupby("date", as_index=False).head(top_n).copy()


def pick_threshold(df: pd.DataFrame, top_n: int, p20_min: float) -> pd.DataFrame:
    x = df[df["p20"] >= p20_min].sort_values(["date", "p20"], ascending=[True, False]).copy()
    x["rank"] = x.groupby("date")["p20"].rank(method="first", ascending=False).astype(int)
    return x.groupby("date", as_index=False).head(top_n).copy()


def pick_weighted(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """
    Keep baseline ranking, but apply simple position-size proxy to estimate portfolio return:
    weight ~ clipped p20, normalized per day.
    """
    x = pick_baseline(df, top_n)
    x["w_raw"] = x["p20"].clip(lower=0.05, upper=0.95)
    x["w"] = x["w_raw"] / x.groupby("date")["w_raw"].transform("sum")
    x["ret20_weighted"] = x["w"] * x["fwd_ret20"]
    x["mdd20_weighted"] = x["w"] * x["fwd_mdd20"]
    return x


def monthly_folds(df: pd.DataFrame, train_months: int, embargo_days: int) -> list[dict[str, Any]]:
    months = sorted(df["date"].dt.to_period("M").unique().tolist())
    out = []
    for i in range(train_months, len(months)):
        tr_m = set(months[i - train_months : i])
        te_m = months[i]
        tr = df[df["date"].dt.to_period("M").isin(tr_m)].copy()
        te = df[df["date"].dt.to_period("M") == te_m].copy()
        if tr.empty or te.empty:
            continue
        tr_end = tr["date"].max()
        te = te[te["date"] > tr_end + pd.Timedelta(days=embargo_days)].copy()
        if te.empty:
            continue
        out.append({"test_month": str(te_m), "train": tr, "test": te})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--train-months", type=int, default=12)
    ap.add_argument("--embargo-days", type=int, default=20)
    ap.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = ap.parse_args()

    df = pd.read_csv(args.panel_csv)
    for c in ["date", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]:
        if c not in df.columns:
            raise ValueError(f"Missing column: {c}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    df = df[(df["date"] >= pd.Timestamp(args.start)) & (df["date"] <= pd.Timestamp(args.end))].copy()

    folds = monthly_folds(df, args.train_months, args.embargo_days)
    monthly_rows = []
    for fd in folds:
        tr = fd["train"]
        te = fd["test"]
        # Tune only threshold on train (minimal execution layer tuning).
        candidates = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
        best_thr = 0.50
        best_obj = -1e9
        for thr in candidates:
            p = pick_threshold(tr, args.top_n, thr)
            m = eval_rows(p)
            if m["n"] < max(60, args.top_n * 4):
                continue
            obj = float(m["hit_rate"]) + 0.20 * float(m["avg_ret20"]) - 0.03 * abs(float(m["avg_mdd20"]))
            if obj > best_obj:
                best_obj = obj
                best_thr = thr

        b = pick_baseline(te, args.top_n)
        t = pick_threshold(te, args.top_n, best_thr)
        w = pick_weighted(te, args.top_n)

        mb = eval_rows(b)
        mt = eval_rows(t)
        # weighted portfolio proxy metrics
        if w.empty:
            mw = {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
        else:
            by_d = w.groupby("date", as_index=False).agg(ret20=("ret20_weighted", "sum"), mdd20=("mdd20_weighted", "sum"))
            mw = {
                "n": float(len(w)),
                "hit_rate": float((by_d["ret20"] > 0).mean()),
                "avg_ret20": float(by_d["ret20"].mean()),
                "avg_mdd20": float(by_d["mdd20"].mean()),
            }

        monthly_rows.append(
            {
                "test_month": fd["test_month"],
                "threshold_selected": best_thr,
                "baseline_n": int(mb["n"]),
                "baseline_hit_rate": mb["hit_rate"],
                "baseline_avg_ret20": mb["avg_ret20"],
                "threshold_n": int(mt["n"]),
                "threshold_hit_rate": mt["hit_rate"],
                "threshold_avg_ret20": mt["avg_ret20"],
                "threshold_coverage": float(mt["n"] / mb["n"]) if mb["n"] > 0 else np.nan,
                "weighted_n": int(mw["n"]),
                "weighted_win_day_rate": mw["hit_rate"],
                "weighted_avg_ret20": mw["avg_ret20"],
                "weighted_avg_mdd20": mw["avg_mdd20"],
            }
        )

    out = pd.DataFrame(monthly_rows)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "p20_execution_layer_monthly_oos.csv"
    out.to_csv(out_csv, index=False)

    # aggregate
    base_ok = out[out["baseline_n"] > 0]
    thr_ok = out[out["threshold_n"] > 0]
    summary = {
        "source": "FireAnt",
        "method": "panel OOS execution-layer test",
        "date_range": {"start": args.start, "end": args.end},
        "top_n": args.top_n,
        "folds": int(len(out)),
        "overall": {
            "baseline_hit_rate": float(np.average(base_ok["baseline_hit_rate"], weights=base_ok["baseline_n"]))
            if not base_ok.empty
            else np.nan,
            "baseline_avg_ret20": float(np.average(base_ok["baseline_avg_ret20"], weights=base_ok["baseline_n"]))
            if not base_ok.empty
            else np.nan,
            "threshold_hit_rate": float(np.average(thr_ok["threshold_hit_rate"], weights=thr_ok["threshold_n"]))
            if not thr_ok.empty
            else np.nan,
            "threshold_avg_ret20": float(np.average(thr_ok["threshold_avg_ret20"], weights=thr_ok["threshold_n"]))
            if not thr_ok.empty
            else np.nan,
            "threshold_coverage_mean": float(out["threshold_coverage"].mean()) if not out.empty else np.nan,
            "weighted_win_day_rate_mean": float(out["weighted_win_day_rate"].mean()) if not out.empty else np.nan,
            "weighted_avg_ret20_mean": float(out["weighted_avg_ret20"].mean()) if not out.empty else np.nan,
        },
        "output_csv": str(out_csv),
    }
    out_json = out_dir / "p20_execution_layer_summary.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

