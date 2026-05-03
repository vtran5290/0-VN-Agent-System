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

from src.data.fireant_client import get_client  # noqa: E402


def pct_rank_to_pm1(s: pd.Series) -> pd.Series:
    r = s.rank(method="average", pct=True)
    return 2.0 * r - 1.0


def eval_rows(x: pd.DataFrame) -> dict[str, Any]:
    if x.empty:
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan, "payoff_ratio": np.nan}
    ret = pd.to_numeric(x["fwd_ret20"], errors="coerce")
    mdd = pd.to_numeric(x["fwd_mdd20"], errors="coerce")
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    payoff = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else np.nan
    return {
        "n": int(len(x)),
        "hit_rate": float(pd.to_numeric(x["label_wave20"], errors="coerce").mean()),
        "avg_ret20": float(ret.mean()),
        "avg_mdd20": float(mdd.mean()),
        "payoff_ratio": payoff,
    }


def build_episode_picks(df: pd.DataFrame, score_col: str, candidate_n: int, top_n: int, cooldown_days: int) -> pd.DataFrame:
    x = df.dropna(subset=[score_col]).copy()
    x = x.sort_values(["date", score_col], ascending=[True, False])
    x["rank"] = x.groupby("date")[score_col].rank(method="first", ascending=False).astype(int)
    cand = x.groupby("date", as_index=False).head(candidate_n).copy()
    if cand.empty:
        return cand
    dlist = sorted(pd.to_datetime(cand["date"]).unique().tolist())
    d2i = {d: i for i, d in enumerate(dlist)}
    next_allowed: dict[str, int] = {}
    rows = []
    for dt, g in cand.groupby("date"):
        di = d2i[pd.Timestamp(dt)]
        chosen = 0
        for _, r in g.sort_values("rank").iterrows():
            sym = str(r["symbol"])
            if di < next_allowed.get(sym, -10**9):
                continue
            rows.append(r.to_dict())
            next_allowed[sym] = di + cooldown_days
            chosen += 1
            if chosen >= top_n:
                break
    return pd.DataFrame(rows)


def make_folds(df: pd.DataFrame, train_months: int, val_months: int, embargo_days: int) -> list[dict[str, Any]]:
    months = sorted(df["date"].dt.to_period("M").unique().tolist())
    folds = []
    for i in range(train_months + val_months, len(months)):
        tr_m = set(months[i - train_months - val_months : i - val_months])
        va_m = set(months[i - val_months : i])
        te_m = months[i]
        tr = df[df["date"].dt.to_period("M").isin(tr_m)].copy()
        va = df[df["date"].dt.to_period("M").isin(va_m)].copy()
        te = df[df["date"].dt.to_period("M") == te_m].copy()
        if tr.empty or va.empty or te.empty:
            continue
        te = te[te["date"] > va["date"].max() + pd.Timedelta(days=embargo_days)]
        if te.empty:
            continue
        folds.append({"test_month": str(te_m), "train": tr, "val": va, "test": te})
    return folds


def enrich_close(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if "close" in df.columns and df["close"].notna().any():
        return df
    c = get_client(timeout=45)
    syms = sorted(df["symbol"].astype(str).str.upper().unique().tolist())
    rows: list[dict[str, Any]] = []

    def _one(sym: str) -> list[dict[str, Any]]:
        h = c.get_ohlcv(sym, start=start, end=end)
        if h.empty:
            return []
        x = h[["date", "close"]].copy()
        x["date"] = pd.to_datetime(x["date"], errors="coerce")
        x["close"] = pd.to_numeric(x["close"], errors="coerce")
        x["symbol"] = sym
        return x.dropna().to_dict(orient="records")

    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(_one, s): s for s in syms}
        for fut in as_completed(futs):
            part = fut.result()
            if part:
                rows.extend(part)
    hdf = pd.DataFrame(rows)
    out = df.copy()
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out = out.merge(hdf, on=["date", "symbol"], how="left", suffixes=("", "_new"))
    if "close_new" in out.columns and "close" in out.columns:
        out["close"] = out["close"].fillna(out["close_new"])
        out = out.drop(columns=["close_new"])
    elif "close" not in out.columns and "close_new" in out.columns:
        out = out.rename(columns={"close_new": "close"})
    return out


def add_features(panel: pd.DataFrame, idx: pd.DataFrame) -> pd.DataFrame:
    x = panel.sort_values(["symbol", "date"]).copy()
    x["close"] = pd.to_numeric(x["close"], errors="coerce")
    x = x.merge(idx, on="date", how="left")
    g = x.groupby("symbol", group_keys=False)

    # RS pullback core
    x["stk_ret_10"] = g["close"].pct_change(10)
    x["idx_ret_10"] = x["idx_close"] / x["idx_close"].shift(10) - 1.0
    x["rel_ret_10"] = x["stk_ret_10"] - x["idx_ret_10"]
    stk_recent_low = g["close"].rolling(5, min_periods=5).min().reset_index(level=0, drop=True)
    stk_prev_low = g["close"].shift(5).rolling(5, min_periods=5).min().reset_index(level=0, drop=True)
    idx_recent_low = x["idx_close"].rolling(5, min_periods=5).min()
    idx_prev_low = x["idx_close"].shift(5).rolling(5, min_periods=5).min()
    x["higher_low_vs_index"] = ((stk_recent_low > stk_prev_low) & (idx_recent_low < idx_prev_low)).astype(float)
    x["rs_pullback"] = x["rel_ret_10"] + 0.5 * x["higher_low_vs_index"]

    # p20 slope/range
    x["p20_slope_5d"] = g["p20"].transform(lambda s: s / s.shift(5) - 1.0)
    x["neg_slope_pref"] = -x["p20_slope_5d"]
    x["p20_high"] = (x["p20"] >= 0.75).astype(float)
    x["p20_mid"] = ((x["p20"] >= 0.65) & (x["p20"] < 0.75)).astype(float)
    x["high_neg_slope_flag"] = ((x["p20"] >= 0.75) & (x["p20_slope_5d"] <= 0)).astype(float)

    by_d = x.groupby("date", group_keys=False)
    x["r_p20"] = by_d["p20"].transform(pct_rank_to_pm1)
    x["r_rs"] = by_d["rs_pullback"].transform(pct_rank_to_pm1)
    x["r_neg_slope"] = by_d["neg_slope_pref"].transform(pct_rank_to_pm1)
    x["r_high_flag"] = by_d["high_neg_slope_flag"].transform(pct_rank_to_pm1)
    x["r_mid_flag"] = by_d["p20_mid"].transform(pct_rank_to_pm1)
    return x


def monthly_compare(base: pd.DataFrame, var: pd.DataFrame, test_month: str, name: str) -> dict[str, Any]:
    mb = eval_rows(base)
    mv = eval_rows(var)
    beat = bool((mv["avg_ret20"] >= mb["avg_ret20"]) and (mv["avg_mdd20"] >= mb["avg_mdd20"] - 0.005) and (mv["hit_rate"] >= mb["hit_rate"] - 0.005)) if np.isfinite(mv["avg_ret20"]) and np.isfinite(mb["avg_ret20"]) and np.isfinite(mv["avg_mdd20"]) and np.isfinite(mb["avg_mdd20"]) and np.isfinite(mv["hit_rate"]) and np.isfinite(mb["hit_rate"]) else False
    return {
        "test_month": test_month,
        "score_name": name,
        "baseline_n": int(mb["n"]),
        "variant_n": int(mv["n"]),
        "coverage_ratio": float(mv["n"] / mb["n"]) if mb["n"] > 0 else np.nan,
        "baseline_hit_rate": mb["hit_rate"],
        "variant_hit_rate": mv["hit_rate"],
        "hit_rate_uplift": mv["hit_rate"] - mb["hit_rate"] if np.isfinite(mv["hit_rate"]) and np.isfinite(mb["hit_rate"]) else np.nan,
        "baseline_avg_ret20": mb["avg_ret20"],
        "variant_avg_ret20": mv["avg_ret20"],
        "avg_ret20_uplift": mv["avg_ret20"] - mb["avg_ret20"] if np.isfinite(mv["avg_ret20"]) and np.isfinite(mb["avg_ret20"]) else np.nan,
        "baseline_avg_mdd20": mb["avg_mdd20"],
        "variant_avg_mdd20": mv["avg_mdd20"],
        "avg_mdd20_uplift": mv["avg_mdd20"] - mb["avg_mdd20"] if np.isfinite(mv["avg_mdd20"]) and np.isfinite(mb["avg_mdd20"]) else np.nan,
        "variant_beats_baseline_flag": beat,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--candidate-pool-n", type=int, default=100)
    ap.add_argument("--episode-cooldown-days", type=int, default=20)
    ap.add_argument("--train-months", type=int, default=12)
    ap.add_argument("--validation-months", type=int, default=3)
    ap.add_argument("--embargo-days", type=int, default=20)
    ap.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(args.panel_csv)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel = panel[(panel["date"] >= pd.Timestamp(args.start)) & (panel["date"] <= pd.Timestamp(args.end))].copy()
    panel = panel.dropna(subset=["date", "symbol", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    panel["symbol"] = panel["symbol"].astype(str).str.upper()
    for c in ["p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]:
        panel[c] = pd.to_numeric(panel[c], errors="coerce")
    panel = enrich_close(panel, args.start, args.end)

    c = get_client(timeout=45)
    idx = c.get_ohlcv("VNINDEX", start=args.start, end=args.end)
    idx["date"] = pd.to_datetime(idx["date"], errors="coerce")
    idx["idx_close"] = pd.to_numeric(idx["close"], errors="coerce")
    idx = idx[["date", "idx_close"]].dropna().sort_values("date")

    feat = add_features(panel, idx)
    feat["B0_baseline_p20"] = feat["p20"]
    # fixed variants combining RS + range + slope preference
    feat["V1_rs_slope"] = 0.70 * feat["r_p20"] + 0.20 * feat["r_rs"] + 0.10 * feat["r_neg_slope"]
    feat["V2_rs_range_slope"] = 0.60 * feat["r_p20"] + 0.20 * feat["r_rs"] + 0.10 * feat["r_neg_slope"] + 0.10 * feat["r_high_flag"]
    feat["V3_rs_midrange_slope"] = 0.58 * feat["r_p20"] + 0.18 * feat["r_rs"] + 0.12 * feat["r_neg_slope"] + 0.12 * feat["r_mid_flag"]
    feat["V4_balanced"] = 0.55 * feat["r_p20"] + 0.20 * feat["r_rs"] + 0.15 * feat["r_neg_slope"] + 0.10 * feat["r_high_flag"]
    score_cols = ["B0_baseline_p20", "V1_rs_slope", "V2_rs_range_slope", "V3_rs_midrange_slope", "V4_balanced"]

    folds = make_folds(feat, args.train_months, args.validation_months, args.embargo_days)
    if not folds:
        raise RuntimeError("No folds.")

    monthly_rows = []
    all_ep: dict[str, list[pd.DataFrame]] = {k: [] for k in score_cols}
    for fd in folds:
        te = fd["test"]
        base = build_episode_picks(te, "B0_baseline_p20", args.candidate_pool_n, args.top_n, args.episode_cooldown_days)
        all_ep["B0_baseline_p20"].append(base)
        for sc in score_cols:
            ep = build_episode_picks(te, sc, args.candidate_pool_n, args.top_n, args.episode_cooldown_days)
            all_ep[sc].append(ep)
            monthly_rows.append(monthly_compare(base, ep, fd["test_month"], sc))

    monthly = pd.DataFrame(monthly_rows).sort_values(["test_month", "score_name"])
    base_all = pd.concat(all_ep["B0_baseline_p20"], ignore_index=True) if all_ep["B0_baseline_p20"] else pd.DataFrame()
    base_m = eval_rows(base_all)
    summary_rows = []
    for sc in score_cols:
        ep = pd.concat(all_ep[sc], ignore_index=True) if all_ep[sc] else pd.DataFrame()
        vm = eval_rows(ep)
        sub = monthly[monthly["score_name"] == sc]
        cov = float(sub["coverage_ratio"].mean()) if len(sub) else np.nan
        win = float(sub["variant_beats_baseline_flag"].mean()) if len(sub) else np.nan
        hit_pp = 100.0 * (vm["hit_rate"] - base_m["hit_rate"]) if np.isfinite(vm["hit_rate"]) and np.isfinite(base_m["hit_rate"]) else np.nan
        ret_pp = 100.0 * (vm["avg_ret20"] - base_m["avg_ret20"]) if np.isfinite(vm["avg_ret20"]) and np.isfinite(base_m["avg_ret20"]) else np.nan
        mdd_pp = 100.0 * (vm["avg_mdd20"] - base_m["avg_mdd20"]) if np.isfinite(vm["avg_mdd20"]) and np.isfinite(base_m["avg_mdd20"]) else np.nan
        pass_flag = np.isfinite(hit_pp) and hit_pp >= 1.5 and np.isfinite(ret_pp) and ret_pp >= -0.20 and np.isfinite(mdd_pp) and mdd_pp >= -0.50 and np.isfinite(cov) and cov >= 0.90 and np.isfinite(win) and win >= 0.55
        verdict = "PASS" if pass_flag else ("WATCH" if np.isfinite(hit_pp) and hit_pp > 0 else "FAIL")
        summary_rows.append(
            {
                "score_name": sc,
                "n": vm["n"],
                "hit_rate": vm["hit_rate"],
                "avg_ret20": vm["avg_ret20"],
                "avg_mdd20": vm["avg_mdd20"],
                "payoff_ratio": vm["payoff_ratio"],
                "hit_rate_uplift_pp": hit_pp,
                "avg_ret20_uplift_pp": ret_pp,
                "avg_mdd20_uplift_pp": mdd_pp,
                "coverage_ratio": cov,
                "monthly_win_rate": win,
                "verdict": verdict,
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values("score_name")

    monthly_path = out_dir / "p20_rs_range_slope_monthly_episode_oos.csv"
    summary_path = out_dir / "p20_rs_range_slope_summary.csv"
    json_path = out_dir / "p20_rs_range_slope_summary.json"
    monthly.to_csv(monthly_path, index=False)
    summary.to_csv(summary_path, index=False)
    out = {
        "source": "FireAnt",
        "method": "REST API + enriched close merge",
        "date_range": {"start": args.start, "end": args.end},
        "features": "RS pullback + p20 range + p20 slope variants",
        "outputs": {"monthly_episode_oos": str(monthly_path), "summary_csv": str(summary_path)},
        "summary_table": summary.to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

