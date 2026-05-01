#!/usr/bin/env python3
from __future__ import annotations

"""
Baseline+ OOS evaluator with two modes:
1) diagnostic   : failure analysis only (NOT final OOS proof)
2) nested_oos   : strict nested walk-forward recalibration and untouched test evaluation

This script enforces:
- No test-month tuning
- PASS/FAIL verdicts based on EPISODE-LEVEL OOS metrics only
"""

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


FIXED_SCORES = [
    "B0_baseline_p20",
    "B1_p_now_only",
    "B2_p_hist_only",
    "E1_p20_persistence",
    "E2_p20_accel",
    "E3_p20_extension_penalty",
    "F1_baseline_plus_fixed",
]


def pct_rank_to_pm1(s: pd.Series) -> pd.Series:
    r = s.rank(method="average", pct=True)
    return 2.0 * r - 1.0


def eval_rows(x: pd.DataFrame, top_n: int) -> dict[str, Any]:
    if x.empty:
        return {
            "n": 0,
            "hit_rate": np.nan,
            "avg_ret20": np.nan,
            "median_ret20": np.nan,
            "avg_mdd20": np.nan,
            "median_mdd20": np.nan,
            "payoff_ratio": np.nan,
            "avg_picks_per_trading_day": np.nan,
            "turnover_proxy": np.nan,
        }
    ret = x["fwd_ret20"].astype(float)
    mdd = x["fwd_mdd20"].astype(float)
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    payoff = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else np.nan

    turn = []
    prev: set[str] = set()
    for _, g in x.groupby("date"):
        cur = set(g["symbol"].astype(str).tolist())
        if prev:
            turn.append(1.0 - len(cur & prev) / max(top_n, 1))
        prev = cur
    return {
        "n": int(len(x)),
        "hit_rate": float(x["label_wave20"].mean()),
        "avg_ret20": float(ret.mean()),
        "median_ret20": float(ret.median()),
        "avg_mdd20": float(mdd.mean()),
        "median_mdd20": float(mdd.median()),
        "payoff_ratio": payoff,
        "avg_picks_per_trading_day": float(x.groupby("date")["symbol"].size().mean()),
        "turnover_proxy": float(np.mean(turn)) if turn else np.nan,
    }


def enrich_close_volume_if_missing(df: pd.DataFrame, start: str, end: str, workers: int = 10) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = df.copy()
    qa = {"close_volume_enriched": False, "enrich_symbols": 0, "enrich_rows": 0}
    if "close" in out.columns and "volume" in out.columns and out["close"].notna().any() and out["volume"].notna().any():
        return out, qa

    c = get_client(timeout=45)
    symbols = sorted(out["symbol"].astype(str).str.upper().unique().tolist())
    rows: list[dict[str, Any]] = []

    def _one(sym: str) -> list[dict[str, Any]]:
        h = c.get_ohlcv(sym, start=start, end=end)
        if h.empty:
            return []
        x = h[["date", "close", "volume"]].copy()
        x["date"] = pd.to_datetime(x["date"], errors="coerce")
        x["close"] = pd.to_numeric(x["close"], errors="coerce")
        x["volume"] = pd.to_numeric(x["volume"], errors="coerce")
        x["symbol"] = sym
        return x.dropna(subset=["date", "close", "volume"]).to_dict(orient="records")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(_one, s): s for s in symbols}
        for fut in as_completed(futs):
            part = fut.result()
            if part:
                rows.extend(part)
    if not rows:
        return out, qa

    hdf = pd.DataFrame(rows)
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out = out.merge(hdf, on=["date", "symbol"], how="left", suffixes=("", "_new"))
    if "close_new" in out.columns:
        out["close"] = out["close"].fillna(out["close_new"]) if "close" in out.columns else out["close_new"]
        out = out.drop(columns=["close_new"])
    if "volume_new" in out.columns:
        out["volume"] = out["volume"].fillna(out["volume_new"]) if "volume" in out.columns else out["volume_new"]
        out = out.drop(columns=["volume_new"])
    qa = {"close_volume_enriched": True, "enrich_symbols": len(symbols), "enrich_rows": int(len(hdf))}
    return out, qa


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.sort_values(["symbol", "date"]).copy()
    g = x.groupby("symbol", group_keys=False)
    x["p20_5d_mean"] = g["p20"].rolling(5, min_periods=2).mean().reset_index(level=0, drop=True)
    prev3 = g["p20"].rolling(3, min_periods=2).mean().shift(1).reset_index(level=0, drop=True)
    x["p20_3d_accel"] = x["p20"] - prev3
    if "close" in x.columns and x["close"].notna().any():
        x["ma20"] = g["close"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
        x["ma50"] = g["close"].rolling(50, min_periods=50).mean().reset_index(level=0, drop=True)
        x["extension"] = np.maximum(0.0, x["close"] / x["ma20"] - 1.0) + 0.5 * np.maximum(0.0, x["close"] / x["ma50"] - 1.0)
    else:
        x["extension"] = 0.0

    by_d = x.groupby("date", group_keys=False)
    x["r_p20"] = by_d["p20"].transform(pct_rank_to_pm1)
    x["r_p_now"] = by_d["p_now"].transform(pct_rank_to_pm1)
    x["r_p_hist"] = by_d["p_hist"].transform(pct_rank_to_pm1)
    x["r_p20_5d_mean"] = by_d["p20_5d_mean"].transform(pct_rank_to_pm1)
    x["r_p20_3d_accel"] = by_d["p20_3d_accel"].transform(pct_rank_to_pm1)
    x["r_extension"] = by_d["extension"].transform(pct_rank_to_pm1)

    x["B0_baseline_p20"] = x["p20"]
    x["B1_p_now_only"] = x["p_now"]
    x["B2_p_hist_only"] = x["p_hist"]  # missing stays NaN, dropped when ranking
    x["E1_p20_persistence"] = 0.85 * x["r_p20"] + 0.15 * x["r_p20_5d_mean"]
    x["E2_p20_accel"] = 0.85 * x["r_p20"] + 0.15 * x["r_p20_3d_accel"]
    x["E3_p20_extension_penalty"] = x["r_p20"] - 0.10 * x["r_extension"]
    x["F1_baseline_plus_fixed"] = 0.75 * x["r_p20"] + 0.15 * x["r_p20_5d_mean"] + 0.10 * x["r_p20_3d_accel"] - 0.10 * x["r_extension"]
    return x


def compute_score_by_family(df: pd.DataFrame, family: str, params: dict[str, Any]) -> pd.Series:
    if family == "A_blend_now_hist":
        w = float(params["w_now"])
        p_hist = df["p_hist"].copy()
        use_hist = p_hist.notna()
        out = w * df["p_now"] + (1.0 - w) * p_hist
        out.loc[~use_hist] = df.loc[~use_hist, "p_now"]
        return out
    if family == "B_persistence":
        a = float(params["a"])
        b = float(params["b"])
        return a * df["r_p20"] + b * df["r_p20_5d_mean"]
    if family == "C_extension":
        pw = float(params["penalty_weight"])
        return df["r_p20"] - pw * df["r_extension"]
    if family == "D_final_blend":
        return (
            float(params["w_p20"]) * df["r_p20"]
            + float(params["w_persist"]) * df["r_p20_5d_mean"]
            + float(params["w_accel"]) * df["r_p20_3d_accel"]
            - float(params["w_ext"]) * df["r_extension"]
        )
    raise ValueError(f"Unknown family: {family}")


def build_daily_picks(df: pd.DataFrame, score_col: str, top_n: int) -> pd.DataFrame:
    x = df.dropna(subset=[score_col]).copy()
    x = x.sort_values(["date", score_col], ascending=[True, False]).copy()
    x["rank_on_start_date"] = x.groupby("date")[score_col].rank(method="first", ascending=False).astype(int)
    out = x.groupby("date", as_index=False).head(top_n).copy()
    return out


def build_episode_picks_from_candidates(
    df: pd.DataFrame,
    score_col: str,
    candidate_n: int,
    top_n: int,
    cooldown_days: int,
) -> pd.DataFrame:
    """
    Canonical episode builder for OOS:
    - Build daily candidate pool (top candidate_n by score)
    - Chronologically apply symbol cooldown over trading-day index
    - Fill up to top_n valid picks per date from candidate pool
    """
    x = df.dropna(subset=[score_col]).copy()
    x = x.sort_values(["date", score_col], ascending=[True, False]).copy()
    x["rank_on_start_date"] = x.groupby("date")[score_col].rank(method="first", ascending=False).astype(int)
    cand = x.groupby("date", as_index=False).head(candidate_n).copy()
    if cand.empty:
        return cand
    dates = sorted(pd.to_datetime(cand["date"]).unique().tolist())
    d2i = {d: i for i, d in enumerate(dates)}
    next_allowed: dict[str, int] = {}
    rows = []
    for dt, g in cand.groupby("date"):
        di = d2i[pd.Timestamp(dt)]
        chosen = 0
        for _, r in g.sort_values("rank_on_start_date").iterrows():
            sym = str(r["symbol"])
            if di < next_allowed.get(sym, -10**9):
                continue
            rows.append(r.to_dict())
            next_allowed[sym] = di + cooldown_days
            chosen += 1
            if chosen >= top_n:
                break
    return pd.DataFrame(rows)


def make_nested_folds(df: pd.DataFrame, train_months: int, validation_months: int, embargo_days: int) -> list[dict[str, Any]]:
    months = sorted(df["date"].dt.to_period("M").unique().tolist())
    folds = []
    for i in range(train_months + validation_months, len(months)):
        tr_m = set(months[i - train_months - validation_months : i - validation_months])
        va_m = set(months[i - validation_months : i])
        te_m = months[i]
        tr = df[df["date"].dt.to_period("M").isin(tr_m)].copy()
        va = df[df["date"].dt.to_period("M").isin(va_m)].copy()
        te = df[df["date"].dt.to_period("M") == te_m].copy()
        if tr.empty or va.empty or te.empty:
            continue
        # embargo after validation end before test
        va_end = va["date"].max()
        te = te[te["date"] > va_end + pd.Timedelta(days=embargo_days)].copy()
        if te.empty:
            continue
        folds.append({"test_month": str(te_m), "train": tr, "val": va, "test": te})
    return folds


def validation_utility(m: dict[str, Any]) -> float:
    pr = min(float(m["payoff_ratio"]), 3.0) if np.isfinite(m["payoff_ratio"]) else 0.0
    return float(m["hit_rate"]) + 0.30 * float(m["avg_ret20"]) - 0.20 * abs(float(m["avg_mdd20"])) + 0.10 * pr


def run_diagnostic(scored: pd.DataFrame, args: argparse.Namespace) -> dict[str, Any]:
    rows = []
    for sc in FIXED_SCORES:
        daily = build_daily_picks(scored, sc, args.top_n)
        if daily.empty:
            continue
        daily["year"] = daily["date"].dt.year
        daily["month"] = daily["date"].dt.to_period("M").astype(str)
        daily["p20_decile"] = pd.qcut(daily["p20"], q=10, labels=False, duplicates="drop")
        # Optional regime split if present.
        if "regime" not in daily.columns:
            daily["regime"] = "unknown"

        groups = [
            ("year", "year"),
            ("month", "month"),
            ("p20_decile", "p20_decile"),
            ("industryCode", "industryCode"),
            ("regime", "regime"),
        ]
        for grp_name, col in groups:
            for key, g in daily.groupby(col):
                m = eval_rows(g, args.top_n)
                rows.append(
                    {
                        "score_name": sc,
                        "slice_type": grp_name,
                        "slice_key": str(key),
                        "n": m["n"],
                        "hit_rate": m["hit_rate"],
                        "avg_ret20": m["avg_ret20"],
                        "avg_mdd20": m["avg_mdd20"],
                        "payoff_ratio": m["payoff_ratio"],
                    }
                )

    out = pd.DataFrame(rows)
    out_csv = Path(args.out_dir) / "p20_diagnostic_backtest_results.csv"
    out.to_csv(out_csv, index=False)

    md = []
    md.append("# Diagnostic Failure Analysis")
    md.append("")
    md.append("Diagnostic results are not final OOS proof. They are used only to form candidate recalibration rules.")
    md.append("")
    md.append("## Notes")
    md.append("- Slices include year/month/p20 decile/regime(if available)/industryCode.")
    md.append("- Any improvement here must be re-validated in nested_oos mode.")
    md_path = Path(args.out_dir) / "p20_diagnostic_failure_analysis.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"diagnostic_csv": str(out_csv), "diagnostic_md": str(md_path)}


def run_nested_oos(scored: pd.DataFrame, qa: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out_dir)
    folds = make_nested_folds(scored, args.train_months, args.validation_months, args.embargo_days)

    # ---------- Fixed variants OOS (for baseline+ files, with EPISODE monthly canonical table) ----------
    monthly_daily_rows = []
    monthly_episode_rows = []
    oos_episode_concat: dict[str, list[pd.DataFrame]] = {s: [] for s in FIXED_SCORES}

    for fd in folds:
        te = fd["test"]
        # Daily metrics table
        b_daily = build_daily_picks(te, "B0_baseline_p20", args.top_n)
        bm_d = eval_rows(b_daily, args.top_n)
        for sc in FIXED_SCORES:
            v_daily = build_daily_picks(te, sc, args.top_n)
            vm_d = eval_rows(v_daily, args.top_n)
            monthly_daily_rows.append(
                {
                    "test_month": fd["test_month"],
                    "score_name": sc,
                    "baseline_n": int(bm_d["n"]),
                    "variant_n": int(vm_d["n"]),
                    "coverage_ratio": float(vm_d["n"] / bm_d["n"]) if bm_d["n"] > 0 else np.nan,
                    "baseline_hit_rate": bm_d["hit_rate"],
                    "variant_hit_rate": vm_d["hit_rate"],
                    "hit_rate_uplift": vm_d["hit_rate"] - bm_d["hit_rate"] if np.isfinite(vm_d["hit_rate"]) and np.isfinite(bm_d["hit_rate"]) else np.nan,
                    "baseline_avg_ret20": bm_d["avg_ret20"],
                    "variant_avg_ret20": vm_d["avg_ret20"],
                    "avg_ret20_uplift": vm_d["avg_ret20"] - bm_d["avg_ret20"] if np.isfinite(vm_d["avg_ret20"]) and np.isfinite(bm_d["avg_ret20"]) else np.nan,
                    "baseline_avg_mdd20": bm_d["avg_mdd20"],
                    "variant_avg_mdd20": vm_d["avg_mdd20"],
                    "avg_mdd20_uplift": vm_d["avg_mdd20"] - bm_d["avg_mdd20"] if np.isfinite(vm_d["avg_mdd20"]) and np.isfinite(bm_d["avg_mdd20"]) else np.nan,
                    "variant_beats_baseline_flag": bool(vm_d["hit_rate"] > bm_d["hit_rate"]) if np.isfinite(vm_d["hit_rate"]) and np.isfinite(bm_d["hit_rate"]) else False,
                }
            )

        # Episode monthly canonical table using candidate pool top100.
        b_ep = build_episode_picks_from_candidates(te, "B0_baseline_p20", 100, args.top_n, args.episode_cooldown_days)
        b_ep["score_name"] = "B0_baseline_p20"
        bm_e = eval_rows(b_ep, args.top_n)
        oos_episode_concat["B0_baseline_p20"].append(b_ep)

        for sc in FIXED_SCORES:
            v_ep = build_episode_picks_from_candidates(te, sc, 100, args.top_n, args.episode_cooldown_days)
            v_ep["score_name"] = sc
            vm_e = eval_rows(v_ep, args.top_n)
            oos_episode_concat[sc].append(v_ep)

            hit_u = vm_e["hit_rate"] - bm_e["hit_rate"] if np.isfinite(vm_e["hit_rate"]) and np.isfinite(bm_e["hit_rate"]) else np.nan
            ret_u = vm_e["avg_ret20"] - bm_e["avg_ret20"] if np.isfinite(vm_e["avg_ret20"]) and np.isfinite(bm_e["avg_ret20"]) else np.nan
            mdd_u = vm_e["avg_mdd20"] - bm_e["avg_mdd20"] if np.isfinite(vm_e["avg_mdd20"]) and np.isfinite(bm_e["avg_mdd20"]) else np.nan
            beat = bool((vm_e["hit_rate"] > bm_e["hit_rate"]) and (vm_e["avg_ret20"] >= bm_e["avg_ret20"] - 0.002)) if np.isfinite(vm_e["hit_rate"]) and np.isfinite(bm_e["hit_rate"]) and np.isfinite(vm_e["avg_ret20"]) and np.isfinite(bm_e["avg_ret20"]) else False
            monthly_episode_rows.append(
                {
                    "test_month": fd["test_month"],
                    "score_name": sc,
                    "baseline_episode_n": int(bm_e["n"]),
                    "variant_episode_n": int(vm_e["n"]),
                    "episode_coverage_ratio": float(vm_e["n"] / bm_e["n"]) if bm_e["n"] > 0 else np.nan,
                    "baseline_hit_rate": bm_e["hit_rate"],
                    "variant_hit_rate": vm_e["hit_rate"],
                    "hit_rate_uplift": hit_u,
                    "baseline_avg_ret20": bm_e["avg_ret20"],
                    "variant_avg_ret20": vm_e["avg_ret20"],
                    "avg_ret20_uplift": ret_u,
                    "baseline_avg_mdd20": bm_e["avg_mdd20"],
                    "variant_avg_mdd20": vm_e["avg_mdd20"],
                    "avg_mdd20_uplift": mdd_u,
                    "variant_beats_baseline_flag": beat,
                }
            )

    monthly_daily_df = pd.DataFrame(monthly_daily_rows).sort_values(["test_month", "score_name"])
    monthly_episode_df = pd.DataFrame(monthly_episode_rows).sort_values(["test_month", "score_name"])

    # Full-period daily and episode tables
    daily_rows = []
    episode_rows = []
    all_episode_rows = []
    for sc in FIXED_SCORES:
        d = build_daily_picks(scored, sc, args.top_n)
        m_d = eval_rows(d, args.top_n)
        m_d["score_name"] = sc
        daily_rows.append(m_d)

        ep_full = build_episode_picks_from_candidates(scored, sc, 100, args.top_n, args.episode_cooldown_days)
        ep_full["score_name"] = sc
        ep_full["episode_start_date"] = pd.to_datetime(ep_full["date"]).dt.strftime("%Y-%m-%d")
        keep = [
            "episode_start_date",
            "symbol",
            "score_name",
            "rank_on_start_date",
            "p20",
            "fwd_ret20",
            "fwd_mdd20",
            "label_wave20",
            "industryCode",
            "traded_value_vnd",
            "adv50_vnd",
        ]
        for c in keep:
            if c not in ep_full.columns:
                ep_full[c] = np.nan
        all_episode_rows.append(ep_full[keep].copy())
        m_e = eval_rows(ep_full, args.top_n)
        m_e["score_name"] = sc
        episode_rows.append(m_e)

    daily_df = pd.DataFrame(daily_rows).sort_values("score_name")
    episode_df = pd.DataFrame(episode_rows).sort_values("score_name")
    episode_rows_df = pd.concat(all_episode_rows, axis=0, ignore_index=True).sort_values(
        ["score_name", "episode_start_date", "rank_on_start_date"]
    )

    # Canonical verdict from OOS episode-only source of truth.
    oos_episode_metrics = {}
    for sc in FIXED_SCORES:
        chunk = pd.concat(oos_episode_concat[sc], axis=0, ignore_index=True) if oos_episode_concat[sc] else pd.DataFrame()
        oos_episode_metrics[sc] = eval_rows(chunk, args.top_n)

    base = oos_episode_metrics["B0_baseline_p20"]
    verdicts: dict[str, Any] = {"B0_baseline_p20": {"verdict": "BENCHMARK", "reason": "production benchmark"}}
    for sc in FIXED_SCORES:
        if sc == "B0_baseline_p20":
            continue
        sub = monthly_episode_df[monthly_episode_df["score_name"] == sc]
        wins = float(sub["variant_beats_baseline_flag"].mean()) if len(sub) else np.nan
        cov = float(sub["episode_coverage_ratio"].mean()) if len(sub) else np.nan
        v = oos_episode_metrics[sc]
        hit_pp = 100.0 * (v["hit_rate"] - base["hit_rate"]) if np.isfinite(v["hit_rate"]) and np.isfinite(base["hit_rate"]) else np.nan
        ret_pp = 100.0 * (v["avg_ret20"] - base["avg_ret20"]) if np.isfinite(v["avg_ret20"]) and np.isfinite(base["avg_ret20"]) else np.nan
        mdd_pp = 100.0 * (v["avg_mdd20"] - base["avg_mdd20"]) if np.isfinite(v["avg_mdd20"]) and np.isfinite(base["avg_mdd20"]) else np.nan
        pass_flag = (
            np.isfinite(hit_pp)
            and hit_pp >= 1.5
            and np.isfinite(ret_pp)
            and ret_pp >= -0.20
            and np.isfinite(mdd_pp)
            and mdd_pp >= -0.50
            and np.isfinite(cov)
            and cov >= 0.90
            and np.isfinite(wins)
            and wins >= 0.55
        )
        verdict = "PASS" if pass_flag else ("WATCH" if np.isfinite(hit_pp) and hit_pp > 0 else "FAIL")
        verdicts[sc] = {
            "verdict": verdict,
            "episode_hit_rate_uplift_pp": hit_pp,
            "episode_avg_ret20_uplift_pp": ret_pp,
            "episode_avg_mdd20_uplift_pp": mdd_pp,
            "episode_coverage_ratio": cov,
            "monthly_episode_win_rate": wins,
        }

    # add monthly comparison columns to tables
    cov_map = monthly_episode_df.groupby("score_name")["episode_coverage_ratio"].mean().to_dict() if not monthly_episode_df.empty else {}
    win_map = monthly_episode_df.groupby("score_name")["variant_beats_baseline_flag"].mean().to_dict() if not monthly_episode_df.empty else {}
    for tdf in [daily_df, episode_df]:
        tdf["coverage_vs_baseline"] = tdf["score_name"].map(cov_map)
        tdf["monthly_win_rate_vs_baseline"] = tdf["score_name"].map(win_map)

    # ---------- Nested recalibration families ----------
    families = {
        "A_blend_now_hist": [{"w_now": w} for w in [0.25, 0.40, 0.50, 0.60, 0.75]],
        "B_persistence": [{"a": a, "b": b} for a, b in [(0.90, 0.10), (0.85, 0.15), (0.80, 0.20), (0.75, 0.25)]],
        "C_extension": [{"penalty_weight": x} for x in [0.00, 0.03, 0.05, 0.07, 0.10]],
        "D_final_blend": [
            {"w_p20": wp, "w_persist": ws, "w_accel": wa, "w_ext": we}
            for wp in [0.70, 0.80, 0.90]
            for ws in [0.05, 0.10, 0.15, 0.20]
            for wa in [0.00, 0.05, 0.10]
            for we in [0.00, 0.03, 0.05, 0.07]
        ],
    }
    nested_rows = []
    selected_params_rows = []

    for fd in folds:
        tr = fd["train"]
        va = fd["val"]
        te = fd["test"]
        base_va = build_episode_picks_from_candidates(va, "B0_baseline_p20", 100, args.top_n, args.episode_cooldown_days)
        base_va_m = eval_rows(base_va, args.top_n)
        base_te = build_episode_picks_from_candidates(te, "B0_baseline_p20", 100, args.top_n, args.episode_cooldown_days)
        base_te_m = eval_rows(base_te, args.top_n)

        for fam, grid in families.items():
            best_params = None
            best_val_m = None
            best_u = -1e9

            for prm in grid:
                # only train/validation used to select params; test untouched
                va = va.copy()
                va["tmp_score"] = compute_score_by_family(va, fam, prm)
                va_ep = build_episode_picks_from_candidates(va, "tmp_score", 100, args.top_n, args.episode_cooldown_days)
                vm = eval_rows(va_ep, args.top_n)
                cov = float(vm["n"] / base_va_m["n"]) if base_va_m["n"] > 0 else np.nan
                c1 = np.isfinite(cov) and cov >= 0.90
                c2 = np.isfinite(vm["avg_ret20"]) and np.isfinite(base_va_m["avg_ret20"]) and vm["avg_ret20"] >= base_va_m["avg_ret20"] - 0.002
                c3 = np.isfinite(vm["avg_mdd20"]) and np.isfinite(base_va_m["avg_mdd20"]) and vm["avg_mdd20"] >= base_va_m["avg_mdd20"] - 0.005
                if not (c1 and c2 and c3):
                    continue
                u = validation_utility(vm)
                if u > best_u:
                    best_u = u
                    best_params = prm
                    best_val_m = vm

            fallback = False
            if best_params is None:
                fallback = True
                te_var = base_te.copy()
                te_var_m = base_te_m
                sel_json = json.dumps({"fallback_to_baseline": True}, ensure_ascii=False)
                val_n = 0
                val_hr = np.nan
                val_ret = np.nan
                val_mdd = np.nan
                val_u = np.nan
            else:
                te = te.copy()
                te["tmp_score"] = compute_score_by_family(te, fam, best_params)
                te_var = build_episode_picks_from_candidates(te, "tmp_score", 100, args.top_n, args.episode_cooldown_days)
                te_var_m = eval_rows(te_var, args.top_n)
                sel_json = json.dumps(best_params, ensure_ascii=False)
                val_n = int(best_val_m["n"])
                val_hr = best_val_m["hit_rate"]
                val_ret = best_val_m["avg_ret20"]
                val_mdd = best_val_m["avg_mdd20"]
                val_u = best_u

            cov_test = float(te_var_m["n"] / base_te_m["n"]) if base_te_m["n"] > 0 else np.nan
            hr_u = te_var_m["hit_rate"] - base_te_m["hit_rate"] if np.isfinite(te_var_m["hit_rate"]) and np.isfinite(base_te_m["hit_rate"]) else np.nan
            ret_u = te_var_m["avg_ret20"] - base_te_m["avg_ret20"] if np.isfinite(te_var_m["avg_ret20"]) and np.isfinite(base_te_m["avg_ret20"]) else np.nan
            mdd_u = te_var_m["avg_mdd20"] - base_te_m["avg_mdd20"] if np.isfinite(te_var_m["avg_mdd20"]) and np.isfinite(base_te_m["avg_mdd20"]) else np.nan
            beat = bool((te_var_m["hit_rate"] > base_te_m["hit_rate"]) and (te_var_m["avg_ret20"] >= base_te_m["avg_ret20"] - 0.002)) if np.isfinite(te_var_m["hit_rate"]) and np.isfinite(base_te_m["hit_rate"]) and np.isfinite(te_var_m["avg_ret20"]) and np.isfinite(base_te_m["avg_ret20"]) else False
            nested_rows.append(
                {
                    "test_month": fd["test_month"],
                    "strategy_family": fam,
                    "selected_params_json": sel_json,
                    "validation_n": val_n,
                    "validation_hit_rate": val_hr,
                    "validation_avg_ret20": val_ret,
                    "validation_avg_mdd20": val_mdd,
                    "validation_utility": val_u,
                    "test_baseline_n": int(base_te_m["n"]),
                    "test_variant_n": int(te_var_m["n"]),
                    "test_coverage": cov_test,
                    "test_baseline_hit_rate": base_te_m["hit_rate"],
                    "test_variant_hit_rate": te_var_m["hit_rate"],
                    "test_hit_rate_uplift": hr_u,
                    "test_baseline_avg_ret20": base_te_m["avg_ret20"],
                    "test_variant_avg_ret20": te_var_m["avg_ret20"],
                    "test_avg_ret20_uplift": ret_u,
                    "test_baseline_avg_mdd20": base_te_m["avg_mdd20"],
                    "test_variant_avg_mdd20": te_var_m["avg_mdd20"],
                    "test_avg_mdd20_uplift": mdd_u,
                    "variant_beats_baseline_flag": beat,
                }
            )
            selected_params_rows.append({"test_month": fd["test_month"], "strategy_family": fam, "selected_params_json": sel_json, "fallback": fallback})

    nested_df = pd.DataFrame(nested_rows)
    if nested_df.empty:
        raise RuntimeError("nested_oos produced no folds.")

    # nested summary by family
    fam_rows = []
    for fam, g in nested_df.groupby("strategy_family"):
        b = g[g["test_baseline_n"] > 0]
        v = g[g["test_variant_n"] > 0]
        base_hr = float(np.average(b["test_baseline_hit_rate"], weights=b["test_baseline_n"])) if not b.empty else np.nan
        var_hr = float(np.average(v["test_variant_hit_rate"], weights=v["test_variant_n"])) if not v.empty else np.nan
        base_ret = float(np.average(b["test_baseline_avg_ret20"], weights=b["test_baseline_n"])) if not b.empty else np.nan
        var_ret = float(np.average(v["test_variant_avg_ret20"], weights=v["test_variant_n"])) if not v.empty else np.nan
        base_mdd = float(np.average(b["test_baseline_avg_mdd20"], weights=b["test_baseline_n"])) if not b.empty else np.nan
        var_mdd = float(np.average(v["test_variant_avg_mdd20"], weights=v["test_variant_n"])) if not v.empty else np.nan
        cov = float(np.average(v["test_coverage"], weights=np.maximum(v["test_variant_n"], 1))) if not v.empty else np.nan
        win = float(g["variant_beats_baseline_flag"].mean()) if len(g) else np.nan
        hr_u_pp = 100.0 * (var_hr - base_hr) if np.isfinite(var_hr) and np.isfinite(base_hr) else np.nan
        ret_u_pp = 100.0 * (var_ret - base_ret) if np.isfinite(var_ret) and np.isfinite(base_ret) else np.nan
        mdd_u_pp = 100.0 * (var_mdd - base_mdd) if np.isfinite(var_mdd) and np.isfinite(base_mdd) else np.nan
        pass_flag = (
            np.isfinite(hr_u_pp)
            and hr_u_pp >= 1.5
            and np.isfinite(ret_u_pp)
            and ret_u_pp >= -0.20
            and np.isfinite(mdd_u_pp)
            and mdd_u_pp >= -0.50
            and np.isfinite(cov)
            and cov >= 0.90
            and np.isfinite(win)
            and win >= 0.55
        )
        verdict = "PASS" if pass_flag else ("WATCH" if np.isfinite(hr_u_pp) and hr_u_pp > 0 else "FAIL")
        fam_rows.append(
            {
                "strategy_family": fam,
                "total_test_episode_n": int(v["test_variant_n"].sum()) if not v.empty else 0,
                "coverage_ratio": cov,
                "hit_rate": var_hr,
                "hit_rate_uplift_vs_baseline": hr_u_pp,
                "avg_ret20": var_ret,
                "avg_ret20_uplift_vs_baseline": ret_u_pp,
                "avg_mdd20": var_mdd,
                "avg_mdd20_uplift_vs_baseline": mdd_u_pp,
                "monthly_win_rate": win,
                "pass_fail_verdict": verdict,
            }
        )
    nested_summary_df = pd.DataFrame(fam_rows).sort_values("strategy_family")

    # selected parameter stability table
    sel = pd.DataFrame(selected_params_rows)
    stab_rows = []
    for fam, g in sel.groupby("strategy_family"):
        total = len(g)
        param_counts = g["selected_params_json"].value_counts()
        for param_json, cnt in param_counts.items():
            gg = nested_df[(nested_df["strategy_family"] == fam) & (nested_df["selected_params_json"] == param_json)]
            stab_rows.append(
                {
                    "strategy_family": fam,
                    "param_name": "params_json",
                    "param_value": param_json,
                    "fold_count": int(cnt),
                    "fold_share": float(cnt / total) if total else np.nan,
                    "avg_test_hit_rate": float(gg["test_variant_hit_rate"].mean()) if len(gg) else np.nan,
                    "avg_test_ret20": float(gg["test_variant_avg_ret20"].mean()) if len(gg) else np.nan,
                }
            )
    stab_df = pd.DataFrame(stab_rows).sort_values(["strategy_family", "fold_count"], ascending=[True, False])

    # write required files
    daily_path = out_dir / "p20_baseline_plus_ablation_daily.csv"
    ep_path = out_dir / "p20_baseline_plus_ablation_episode.csv"
    ep_rows_path = out_dir / "p20_baseline_plus_episode_rows.csv"
    monthly_path = out_dir / "p20_baseline_plus_monthly_oos.csv"
    monthly_ep_path = out_dir / "p20_baseline_plus_monthly_episode_oos.csv"
    nested_folds_path = out_dir / "p20_nested_oos_recalibration_folds.csv"
    nested_sum_path = out_dir / "p20_nested_oos_recalibration_summary.csv"
    nested_sel_path = out_dir / "p20_nested_oos_selected_params.csv"
    nested_md_path = out_dir / "p20_nested_oos_recalibration_summary.md"
    summary_json_path = out_dir / "p20_baseline_plus_summary.json"
    summary_md_path = out_dir / "p20_baseline_plus_summary.md"

    daily_df.to_csv(daily_path, index=False)
    episode_df.to_csv(ep_path, index=False)
    episode_rows_df.to_csv(ep_rows_path, index=False)
    monthly_daily_df.to_csv(monthly_path, index=False)
    monthly_episode_df.to_csv(monthly_ep_path, index=False)
    nested_df.to_csv(nested_folds_path, index=False)
    nested_summary_df.to_csv(nested_sum_path, index=False)
    stab_df.to_csv(nested_sel_path, index=False)

    # baseline summary files (must reflect canonical OOS episode verdicts)
    summary = {
        "source": "FireAnt",
        "date_range": {"start": args.start, "end": args.end},
        "top_n": args.top_n,
        "episode_cooldown_days": args.episode_cooldown_days,
        "validation_protocol": {
            "mode": "nested_oos",
            "train_months": args.train_months,
            "validation_months": args.validation_months,
            "embargo_days": args.embargo_days,
            "candidate_pool_for_episode": 100,
            "no_leakage_note": "parameter selection uses train/validation only; test month untouched",
        },
        "score_definitions": {
            "B0_baseline_p20": "score=p20",
            "B1_p_now_only": "score=p_now",
            "B2_p_hist_only": "score=p_hist, missing uses NaN and row is dropped for this score",
            "E1_p20_persistence": "0.85*rank(p20)+0.15*rank(p20_5d_mean)",
            "E2_p20_accel": "0.85*rank(p20)+0.15*rank(p20_3d_accel)",
            "E3_p20_extension_penalty": "rank(p20)-0.10*rank(extension)",
            "F1_baseline_plus_fixed": "0.75*rank(p20)+0.15*rank(p20_5d_mean)+0.10*rank(p20_3d_accel)-0.10*rank(extension)",
        },
        "overall_daily_metrics": daily_df.to_dict(orient="records"),
        "overall_episode_metrics": episode_df.to_dict(orient="records"),
        "monthly_oos_summary": monthly_daily_df.to_dict(orient="records"),
        "monthly_episode_oos_summary": monthly_episode_df.to_dict(orient="records"),
        "oos_episode_metrics": oos_episode_metrics,
        "pass_fail_verdicts": verdicts,
        "qa_checks": qa,
        "key_findings": [],
        "limitations": [
            "PASS/FAIL is computed from episode-level OOS only (canonical source of truth).",
            "Diagnostic insights are not considered final OOS proof.",
            "v2/v2.2/v2.3 remain research references only.",
        ],
    }
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# p20 Baseline+ Summary")
    md.append("")
    md.append("## Executive conclusion")
    pass_list = [k for k, v in verdicts.items() if isinstance(v, dict) and v.get("verdict") == "PASS"]
    md.append(f"- PASS variants: {pass_list if pass_list else 'None'}")
    md.append("- No variant passes unless the exact PASS criteria are met.")
    md.append("- If B1 has higher hit rate but worse avg_ret20/mdd, it must be WATCH or FAIL, not PASS.")
    md.append("- B0_baseline_p20 remains production benchmark unless a variant passes OOS episode-level criteria.")
    md.append("")
    md.append("## Daily-pick vs episode-level")
    md.append("- Episode-level OOS with cooldown is canonical for verdict.")
    md.append("")
    md.append("## Research references")
    md.append("- v2/v2.2/v2.3 scripts are retained as references only.")
    summary_md_path.write_text("\n".join(md), encoding="utf-8")

    nested_md = []
    nested_md.append("# Nested OOS Recalibration Summary")
    nested_md.append("")
    nested_md.append("## 1) Diagnostic backtest observations")
    nested_md.append("- Separate mode (`--mode diagnostic`) and not final OOS proof.")
    nested_md.append("")
    nested_md.append("## 2) Validation-selected parameters")
    nested_md.append("- Parameters selected on validation with hard constraints and utility objective.")
    nested_md.append("")
    nested_md.append("## 3) Final untouched nested-OOS test results")
    nested_md.append("- Test month is untouched for selection.")
    nested_md.append("")
    nested_md.append("## 4) Production recommendation")
    if (nested_summary_df["pass_fail_verdict"] == "PASS").any():
        nested_md.append("The recalibrated strategy passes nested-OOS acceptance rules and may be promoted to paper-trading, not live production yet.")
    else:
        nested_md.append("Recalibration did not produce a production-grade improvement. Baseline p20 remains the benchmark.")
    nested_md_path.write_text("\n".join(nested_md), encoding="utf-8")

    return {
        "files": {
            "daily": str(daily_path),
            "episode": str(ep_path),
            "episode_rows": str(ep_rows_path),
            "monthly_oos": str(monthly_path),
            "monthly_episode_oos": str(monthly_ep_path),
            "summary_json": str(summary_json_path),
            "summary_md": str(summary_md_path),
            "nested_folds": str(nested_folds_path),
            "nested_summary": str(nested_sum_path),
            "nested_selected_params": str(nested_sel_path),
            "nested_summary_md": str(nested_md_path),
        }
    }


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.panel_csv)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[(df["date"] >= pd.Timestamp(args.start)) & (df["date"] <= pd.Timestamp(args.end))].copy()

    required = ["date", "symbol", "p20", "p_now", "p_hist", "label_wave20", "fwd_ret20", "fwd_mdd20"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise ValueError(f"Missing required columns: {miss}")

    qa: dict[str, Any] = {
        "missing_required_columns": miss,
        "n_rows_raw": int(len(df)),
        "n_symbols_raw": int(df["symbol"].nunique()),
        "n_dates_raw": int(df["date"].nunique()),
    }
    dup = df.duplicated(subset=["date", "symbol"], keep=False)
    qa["duplicate_symbol_date_rows"] = int(dup.sum())
    if dup.any():
        df = df[~df.duplicated(subset=["date", "symbol"], keep="first")].copy()
    qa["nonfinite_p20_rows"] = int((~np.isfinite(pd.to_numeric(df["p20"], errors="coerce"))).sum())

    df, q2 = enrich_close_volume_if_missing(df, args.start, args.end, workers=10)
    qa.update(q2)
    if "close" in df.columns and df["close"].notna().any():
        med_close = float(pd.to_numeric(df["close"], errors="coerce").median())
        qa["median_close"] = med_close
        qa["close_likely_thousand_vnd"] = bool(1.0 <= med_close <= 500.0)
    else:
        qa["median_close"] = None
        qa["close_likely_thousand_vnd"] = None

    qa["adv_formula_consistency_corr"] = None
    if {"close", "volume", "adv50_vnd", "symbol", "date"}.issubset(df.columns):
        x = df.sort_values(["symbol", "date"]).copy()
        x["tv"] = pd.to_numeric(x["close"], errors="coerce") * 1000.0 * pd.to_numeric(x["volume"], errors="coerce")
        x["adv50_check"] = x.groupby("symbol")["tv"].rolling(50, min_periods=20).mean().reset_index(level=0, drop=True)
        z = x[["adv50_vnd", "adv50_check"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(z) > 50:
            qa["adv_formula_consistency_corr"] = float(z["adv50_vnd"].corr(z["adv50_check"]))

    tail = df[df["date"] >= pd.Timestamp(args.end) - pd.Timedelta(days=40)]
    qa["tail_rows_last_40d"] = int(len(tail))
    qa["tail_missing_label_rows"] = int(tail["label_wave20"].isna().sum())

    before = len(df)
    df = df.dropna(subset=["date", "symbol", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    qa["rows_dropped_for_core_eval"] = int(before - len(df))
    df["symbol"] = df["symbol"].astype(str).str.upper()
    for c in ["p20", "p_now", "p_hist", "label_wave20", "fwd_ret20", "fwd_mdd20"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan)

    scored = add_features(df)
    if args.mode == "diagnostic":
        return run_diagnostic(scored, args)
    if args.mode == "nested_oos":
        return run_nested_oos(scored, qa, args)
    raise ValueError(f"Unsupported mode: {args.mode}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["diagnostic", "nested_oos"], default="nested_oos")
    ap.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--episode-cooldown-days", type=int, default=20)
    ap.add_argument("--train-months", type=int, default=12)
    ap.add_argument("--validation-months", type=int, default=3)
    ap.add_argument("--embargo-days", type=int, default=20)
    ap.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    return ap.parse_args()


if __name__ == "__main__":
    a = parse_args()
    result = run_pipeline(a)
    print(json.dumps(result, ensure_ascii=False, indent=2))

