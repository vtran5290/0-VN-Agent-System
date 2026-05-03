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
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
    return {
        "n": int(len(x)),
        "hit_rate": float(pd.to_numeric(x["label_wave20"], errors="coerce").mean()),
        "avg_ret20": float(pd.to_numeric(x["fwd_ret20"], errors="coerce").mean()),
        "avg_mdd20": float(pd.to_numeric(x["fwd_mdd20"], errors="coerce").mean()),
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

    x["stk_ret_10"] = g["close"].pct_change(10)
    x["idx_ret_10"] = x["idx_close"] / x["idx_close"].shift(10) - 1.0
    x["rel_ret_10"] = x["stk_ret_10"] - x["idx_ret_10"]
    stk_recent_low = g["close"].rolling(5, min_periods=5).min().reset_index(level=0, drop=True)
    stk_prev_low = g["close"].shift(5).rolling(5, min_periods=5).min().reset_index(level=0, drop=True)
    idx_recent_low = x["idx_close"].rolling(5, min_periods=5).min()
    idx_prev_low = x["idx_close"].shift(5).rolling(5, min_periods=5).min()
    x["higher_low_vs_index"] = ((stk_recent_low > stk_prev_low) & (idx_recent_low < idx_prev_low)).astype(float)
    x["rs_pullback"] = x["rel_ret_10"] + 0.5 * x["higher_low_vs_index"]

    # Pullback event mask on index: drawdown from 10d high and short MA slope down.
    x["idx_10d_high"] = x["idx_close"].rolling(10, min_periods=5).max()
    x["idx_dd10"] = x["idx_close"] / x["idx_10d_high"] - 1.0
    x["idx_ma5"] = x["idx_close"].rolling(5, min_periods=5).mean()
    x["idx_ma5_slope3"] = x["idx_ma5"] / x["idx_ma5"].shift(3) - 1.0

    by_d = x.groupby("date", group_keys=False)
    x["r_p20"] = by_d["p20"].transform(pct_rank_to_pm1)
    x["r_rs_pullback"] = by_d["rs_pullback"].transform(pct_rank_to_pm1)
    return x


def score_with_event_gate(df: pd.DataFrame, rs_weight: float, dd_thr: float, slope_thr: float) -> pd.Series:
    pullback_on = ((df["idx_dd10"] <= dd_thr) & (df["idx_ma5_slope3"] <= slope_thr)).astype(float)
    return (1.0 - rs_weight * pullback_on) * df["r_p20"] + (rs_weight * pullback_on) * df["r_rs_pullback"]


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
    folds = make_folds(feat, args.train_months, args.validation_months, args.embargo_days)
    if not folds:
        raise RuntimeError("No folds.")

    grid = []
    for w in [0.15, 0.25, 0.35, 0.50]:
        for dd in [-0.02, -0.03, -0.04, -0.05]:
            for sl in [-0.002, -0.004, -0.006]:
                grid.append({"rs_weight": w, "dd_thr": dd, "slope_thr": sl})

    monthly_rows = []
    all_base: list[pd.DataFrame] = []
    all_var: list[pd.DataFrame] = []
    sel_rows = []
    for fd in folds:
        tr = fd["train"]
        va = fd["val"]
        te = fd["test"]
        base_va = build_episode_picks(va, "B0_baseline_p20", args.candidate_pool_n, args.top_n, args.episode_cooldown_days)
        mb_va = eval_rows(base_va)
        best_cfg = None
        best_u = -1e9
        for cfg in grid:
            va2 = va.copy()
            va2["S_event_rs"] = score_with_event_gate(va2, cfg["rs_weight"], cfg["dd_thr"], cfg["slope_thr"])
            ep = build_episode_picks(va2, "S_event_rs", args.candidate_pool_n, args.top_n, args.episode_cooldown_days)
            vm = eval_rows(ep)
            cov = float(vm["n"] / mb_va["n"]) if mb_va["n"] > 0 else np.nan
            if not (np.isfinite(cov) and cov >= 0.90):
                continue
            if not (np.isfinite(vm["avg_ret20"]) and np.isfinite(mb_va["avg_ret20"]) and vm["avg_ret20"] >= mb_va["avg_ret20"] - 0.002):
                continue
            if not (np.isfinite(vm["avg_mdd20"]) and np.isfinite(mb_va["avg_mdd20"]) and vm["avg_mdd20"] >= mb_va["avg_mdd20"] - 0.005):
                continue
            u = float(vm["hit_rate"]) + 0.30 * float(vm["avg_ret20"]) - 0.20 * abs(float(vm["avg_mdd20"]))
            if u > best_u:
                best_u = u
                best_cfg = cfg

        base_te = build_episode_picks(te, "B0_baseline_p20", args.candidate_pool_n, args.top_n, args.episode_cooldown_days)
        mb = eval_rows(base_te)
        all_base.append(base_te)
        te2 = te.copy()
        fallback = False
        if best_cfg is None:
            fallback = True
            var_te = base_te.copy()
            vm = mb
            sel = {"fallback": True}
        else:
            te2["S_event_rs"] = score_with_event_gate(te2, best_cfg["rs_weight"], best_cfg["dd_thr"], best_cfg["slope_thr"])
            var_te = build_episode_picks(te2, "S_event_rs", args.candidate_pool_n, args.top_n, args.episode_cooldown_days)
            vm = eval_rows(var_te)
            sel = best_cfg
        all_var.append(var_te)
        hit_u = vm["hit_rate"] - mb["hit_rate"] if np.isfinite(vm["hit_rate"]) and np.isfinite(mb["hit_rate"]) else np.nan
        ret_u = vm["avg_ret20"] - mb["avg_ret20"] if np.isfinite(vm["avg_ret20"]) and np.isfinite(mb["avg_ret20"]) else np.nan
        mdd_u = vm["avg_mdd20"] - mb["avg_mdd20"] if np.isfinite(vm["avg_mdd20"]) and np.isfinite(mb["avg_mdd20"]) else np.nan
        beat = bool((vm["avg_ret20"] >= mb["avg_ret20"]) and (vm["avg_mdd20"] >= mb["avg_mdd20"] - 0.005) and (vm["hit_rate"] >= mb["hit_rate"] - 0.005)) if np.isfinite(vm["avg_ret20"]) and np.isfinite(mb["avg_ret20"]) and np.isfinite(vm["avg_mdd20"]) and np.isfinite(mb["avg_mdd20"]) and np.isfinite(vm["hit_rate"]) and np.isfinite(mb["hit_rate"]) else False
        monthly_rows.append(
            {
                "test_month": fd["test_month"],
                "selected_params_json": json.dumps(sel, ensure_ascii=False),
                "fallback_to_baseline": fallback,
                "baseline_n": int(mb["n"]),
                "variant_n": int(vm["n"]),
                "coverage_ratio": float(vm["n"] / mb["n"]) if mb["n"] > 0 else np.nan,
                "baseline_hit_rate": mb["hit_rate"],
                "variant_hit_rate": vm["hit_rate"],
                "hit_rate_uplift": hit_u,
                "baseline_avg_ret20": mb["avg_ret20"],
                "variant_avg_ret20": vm["avg_ret20"],
                "avg_ret20_uplift": ret_u,
                "baseline_avg_mdd20": mb["avg_mdd20"],
                "variant_avg_mdd20": vm["avg_mdd20"],
                "avg_mdd20_uplift": mdd_u,
                "variant_beats_baseline_flag": beat,
            }
        )
        sel_rows.append({"test_month": fd["test_month"], **sel})

    monthly = pd.DataFrame(monthly_rows).sort_values("test_month")
    base_all = pd.concat(all_base, ignore_index=True) if all_base else pd.DataFrame()
    var_all = pd.concat(all_var, ignore_index=True) if all_var else pd.DataFrame()
    mb_all = eval_rows(base_all)
    vm_all = eval_rows(var_all)
    hit_pp = 100.0 * (vm_all["hit_rate"] - mb_all["hit_rate"]) if np.isfinite(vm_all["hit_rate"]) and np.isfinite(mb_all["hit_rate"]) else np.nan
    ret_pp = 100.0 * (vm_all["avg_ret20"] - mb_all["avg_ret20"]) if np.isfinite(vm_all["avg_ret20"]) and np.isfinite(mb_all["avg_ret20"]) else np.nan
    mdd_pp = 100.0 * (vm_all["avg_mdd20"] - mb_all["avg_mdd20"]) if np.isfinite(vm_all["avg_mdd20"]) and np.isfinite(mb_all["avg_mdd20"]) else np.nan
    cov = float(monthly["coverage_ratio"].mean()) if len(monthly) else np.nan
    win = float(monthly["variant_beats_baseline_flag"].mean()) if len(monthly) else np.nan
    pass_flag = np.isfinite(hit_pp) and hit_pp >= 1.5 and np.isfinite(ret_pp) and ret_pp >= -0.20 and np.isfinite(mdd_pp) and mdd_pp >= -0.50 and np.isfinite(cov) and cov >= 0.90 and np.isfinite(win) and win >= 0.55
    verdict = "PASS" if pass_flag else ("WATCH" if np.isfinite(hit_pp) and hit_pp > 0 else "FAIL")

    monthly_path = out_dir / "p20_rs_pullback_event_monthly_episode_oos.csv"
    summary_path = out_dir / "p20_rs_pullback_event_summary.json"
    sel_path = out_dir / "p20_rs_pullback_event_selected_params.csv"
    monthly.to_csv(monthly_path, index=False)
    pd.DataFrame(sel_rows).to_csv(sel_path, index=False)
    out = {
        "source": "FireAnt",
        "method": "REST API + enriched close",
        "date_range": {"start": args.start, "end": args.end},
        "feature": "event-based RS pullback (enabled only during index pullback events)",
        "overall_baseline": mb_all,
        "overall_variant": vm_all,
        "uplift_pp": {"hit_rate_pp": hit_pp, "avg_ret20_pp": ret_pp, "avg_mdd20_pp": mdd_pp},
        "coverage_ratio": cov,
        "monthly_win_rate": win,
        "verdict": verdict,
        "outputs": {
            "monthly_episode_oos": str(monthly_path),
            "selected_params": str(sel_path),
        },
        "limitations": [
            "higher-low is close-based proxy",
            "no intraday low structure for precise swing-point detection",
        ],
    }
    summary_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

