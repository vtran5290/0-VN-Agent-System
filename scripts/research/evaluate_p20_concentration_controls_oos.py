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


def _metrics(x: pd.DataFrame) -> dict[str, float]:
    if x.empty:
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
    return {
        "n": float(len(x)),
        "hit_rate": float(x["label_wave20"].mean()),
        "avg_ret20": float(x["fwd_ret20"].mean()),
        "avg_mdd20": float(x["fwd_mdd20"].mean()),
    }


def _pick_baseline(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    x = df.sort_values(["date", "p20"], ascending=[True, False]).copy()
    x["rank"] = x.groupby("date")["p20"].rank(method="first", ascending=False).astype(int)
    return x.groupby("date", as_index=False).head(top_n).copy()


def _pick_industry_capped(df: pd.DataFrame, top_n: int, max_per_industry: int) -> pd.DataFrame:
    out = []
    for dt, g in df.groupby("date"):
        s = g.sort_values("p20", ascending=False).copy()
        counts: dict[str, int] = {}
        chosen = []
        for _, r in s.iterrows():
            ind = str(r.get("industryCode", "NA"))
            c = counts.get(ind, 0)
            if c >= max_per_industry:
                continue
            chosen.append(r.to_dict())
            counts[ind] = c + 1
            if len(chosen) >= top_n:
                break
        if chosen:
            out.extend(chosen)
    x = pd.DataFrame(out)
    if x.empty:
        return x
    x["rank"] = x.groupby("date")["p20"].rank(method="first", ascending=False).astype(int)
    return x


def _pick_weight_capped(df: pd.DataFrame, top_n: int, max_weight: float) -> pd.DataFrame:
    x = _pick_baseline(df, top_n).copy()
    if x.empty:
        return x
    x["w_raw"] = x["p20"].clip(lower=0.05, upper=0.95)
    x["w"] = x["w_raw"] / x.groupby("date")["w_raw"].transform("sum")
    x["w_capped"] = np.minimum(x["w"], max_weight)
    # re-normalize capped weights per day
    x["w_capped"] = x["w_capped"] / x.groupby("date")["w_capped"].transform("sum")
    x["ret20_weighted"] = x["w_capped"] * x["fwd_ret20"]
    x["mdd20_weighted"] = x["w_capped"] * x["fwd_mdd20"]
    return x


def _folds(df: pd.DataFrame, train_months: int, embargo_days: int) -> list[dict[str, Any]]:
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
    req = ["date", "symbol", "industryCode", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]
    miss = [c for c in req if c not in df.columns]
    if miss:
        raise ValueError(f"Missing columns: {miss}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=req).copy()
    df = df[(df["date"] >= pd.Timestamp(args.start)) & (df["date"] <= pd.Timestamp(args.end))].copy()
    df["industryCode"] = df["industryCode"].astype(str)

    folds = _folds(df, args.train_months, args.embargo_days)
    rows = []
    for fd in folds:
        tr = fd["train"]
        te = fd["test"]
        # tune only simple caps on train
        ind_caps = [2, 3, 4, 5]
        weight_caps = [0.10, 0.12, 0.15, 0.20]
        best_ind = 3
        best_w = 0.12
        best_obj = -1e9
        for ic in ind_caps:
            p = _pick_industry_capped(tr, args.top_n, ic)
            m = _metrics(p)
            if m["n"] < max(60, args.top_n * 4):
                continue
            obj = float(m["hit_rate"]) + 0.2 * float(m["avg_ret20"]) - 0.03 * abs(float(m["avg_mdd20"]))
            if obj > best_obj:
                best_obj = obj
                best_ind = ic
        best_obj_w = -1e9
        for wc in weight_caps:
            p = _pick_weight_capped(tr, args.top_n, wc)
            if p.empty:
                continue
            by_d = p.groupby("date", as_index=False).agg(ret=("ret20_weighted", "sum"), mdd=("mdd20_weighted", "sum"))
            obj = float((by_d["ret"] > 0).mean()) + 0.2 * float(by_d["ret"].mean()) - 0.03 * abs(float(by_d["mdd"].mean()))
            if obj > best_obj_w:
                best_obj_w = obj
                best_w = wc

        b = _pick_baseline(te, args.top_n)
        i = _pick_industry_capped(te, args.top_n, best_ind)
        w = _pick_weight_capped(te, args.top_n, best_w)
        mb = _metrics(b)
        mi = _metrics(i)
        if w.empty:
            mw = {"n": 0, "win_day_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
        else:
            by_d = w.groupby("date", as_index=False).agg(ret=("ret20_weighted", "sum"), mdd=("mdd20_weighted", "sum"))
            mw = {
                "n": float(len(w)),
                "win_day_rate": float((by_d["ret"] > 0).mean()),
                "avg_ret20": float(by_d["ret"].mean()),
                "avg_mdd20": float(by_d["mdd"].mean()),
            }

        rows.append(
            {
                "test_month": fd["test_month"],
                "industry_cap_selected": best_ind,
                "weight_cap_selected": best_w,
                "baseline_n": int(mb["n"]),
                "baseline_hit_rate": mb["hit_rate"],
                "baseline_avg_ret20": mb["avg_ret20"],
                "indcap_n": int(mi["n"]),
                "indcap_hit_rate": mi["hit_rate"],
                "indcap_avg_ret20": mi["avg_ret20"],
                "indcap_coverage": float(mi["n"] / mb["n"]) if mb["n"] > 0 else np.nan,
                "weightcap_n": int(mw["n"]),
                "weightcap_win_day_rate": mw["win_day_rate"],
                "weightcap_avg_ret20": mw["avg_ret20"],
                "weightcap_avg_mdd20": mw["avg_mdd20"],
            }
        )

    out = pd.DataFrame(rows)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "p20_concentration_controls_monthly_oos.csv"
    out.to_csv(out_csv, index=False)

    b_ok = out[out["baseline_n"] > 0]
    i_ok = out[out["indcap_n"] > 0]
    summary = {
        "source": "FireAnt",
        "method": "baseline execution with concentration controls",
        "date_range": {"start": args.start, "end": args.end},
        "top_n": args.top_n,
        "folds": int(len(out)),
        "overall": {
            "baseline_hit_rate": float(np.average(b_ok["baseline_hit_rate"], weights=b_ok["baseline_n"])) if not b_ok.empty else np.nan,
            "baseline_avg_ret20": float(np.average(b_ok["baseline_avg_ret20"], weights=b_ok["baseline_n"])) if not b_ok.empty else np.nan,
            "indcap_hit_rate": float(np.average(i_ok["indcap_hit_rate"], weights=i_ok["indcap_n"])) if not i_ok.empty else np.nan,
            "indcap_avg_ret20": float(np.average(i_ok["indcap_avg_ret20"], weights=i_ok["indcap_n"])) if not i_ok.empty else np.nan,
            "indcap_coverage_mean": float(out["indcap_coverage"].mean()) if not out.empty else np.nan,
            "weightcap_win_day_rate_mean": float(out["weightcap_win_day_rate"].mean()) if not out.empty else np.nan,
            "weightcap_avg_ret20_mean": float(out["weightcap_avg_ret20"].mean()) if not out.empty else np.nan,
        },
        "output_csv": str(out_csv),
    }
    out_json = out_dir / "p20_concentration_controls_summary.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

