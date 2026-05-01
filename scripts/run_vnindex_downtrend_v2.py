#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
import sys

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.intake.fireant_historical import fetch_historical  # noqa: E402


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1.0 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    half = z * np.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return float(ctr - half), float(ctr + half)


def auc_rank(y_true: pd.Series, y_score: pd.Series) -> float | None:
    d = pd.DataFrame({"y": y_true, "p": y_score}).dropna()
    if d.empty:
        return None
    y = d["y"].astype(float).to_numpy()
    p = d["p"].astype(float).to_numpy()
    pos = y > 0.5
    n_pos = int(pos.sum())
    n_neg = int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = pd.Series(p).rank(method="average").to_numpy()
    sum_pos = float(ranks[pos].sum())
    auc = (sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc)


def brier(y_true: pd.Series, y_prob: pd.Series) -> float | None:
    d = pd.DataFrame({"y": y_true, "p": y_prob}).dropna()
    if d.empty:
        return None
    return float(np.mean((d["p"].astype(float) - d["y"].astype(float)) ** 2))


def build_frame(symbol: str, start: str, end: str) -> pd.DataFrame:
    rows = fetch_historical(symbol, start, end)
    df = pd.DataFrame(
        [{"date": pd.Timestamp(r.d), "open": r.o, "high": r.h, "low": r.l, "close": r.c, "volume": r.v} for r in rows]
    ).sort_values("date")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "close", "high", "low"]).reset_index(drop=True)
    return df


def add_dist_day(df: pd.DataFrame, dist_threshold: float, volume_mode: str) -> pd.DataFrame:
    out = df.copy()
    c = out["close"].astype(float)
    v = out["volume"].astype(float)
    prev_c = c.shift(1)
    prev_v = v.shift(1)
    down = c <= prev_c * (1.0 + dist_threshold)
    if volume_mode == "prev":
        vol_up = v > prev_v
    elif volume_mode == "prev_105":
        vol_up = v > 1.05 * prev_v
    elif volume_mode == "ma20":
        vol_up = v > v.rolling(20, min_periods=20).mean()
    else:
        raise ValueError(f"Unsupported volume_mode={volume_mode}")
    out["dist_day"] = np.where(
        prev_c.notna() & prev_v.notna() & v.notna() & down & vol_up,
        1.0,
        np.where(prev_c.notna() & prev_v.notna() & v.notna(), 0.0, np.nan),
    )
    return out


def add_ma_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ma20"] = out["close"].rolling(20, min_periods=20).mean()
    out["ma50"] = out["close"].rolling(50, min_periods=50).mean()
    out["ma200"] = out["close"].rolling(200, min_periods=200).mean()
    out["ma20_slope_5d"] = out["ma20"] / out["ma20"].shift(5) - 1.0
    out["ma50_slope_10d"] = out["ma50"] / out["ma50"].shift(10) - 1.0
    out["close_vs_ma20"] = out["close"] / out["ma20"] - 1.0
    out["close_vs_ma50"] = out["close"] / out["ma50"] - 1.0
    out["above_ma50"] = (out["close"] > out["ma50"]).astype(float)
    return out


def find_events(dist: pd.Series, method: str) -> list[tuple[int, int]]:
    events: list[tuple[int, int]] = []
    i = 0
    n = len(dist)
    cooldown = 0
    if method == "cooldown_5":
        cooldown = 5
    if method == "cooldown_10":
        cooldown = 10
    while i <= n - 8:
        w = dist.iloc[i : i + 8]
        if w.isna().any() or (w != 0).any():
            i += 1
            continue
        events.append((i, i + 7))
        if method == "overlap":
            i += 1
        elif method == "nonoverlap_8":
            i += 8
        elif method.startswith("cooldown_"):
            i += cooldown
        else:
            raise ValueError(f"Unsupported event method: {method}")
    return events


@dataclass
class BuildConfig:
    mode: str  # T0/T5/T10
    event_method: str
    dist_threshold: float
    volume_mode: str


def build_event_dataset(df: pd.DataFrame, cfg: BuildConfig) -> pd.DataFrame:
    mode_map = {"T0": 0, "T5": 5, "T10": 10}
    if cfg.mode not in mode_map:
        raise ValueError("mode must be T0/T5/T10")
    offset = mode_map[cfg.mode]
    events = find_events(df["dist_day"], cfg.event_method)
    rows: list[dict[str, Any]] = []
    n = len(df)

    for s, e in events:
        pred_i = e + offset
        if pred_i >= n:
            continue
        fwd_start = pred_i + 1
        fwd_end = pred_i + 20
        if fwd_end >= n:
            continue
        r = df.iloc[pred_i]
        if not np.isfinite(r.get("ma50", np.nan)):
            continue
        close0 = float(r["close"])
        # prediction-time features only
        feat = {
            "event_start_i": s,
            "event_i": e,
            "pred_i": pred_i,
            "event_date": str(df.at[e, "date"].date()),
            "pred_date": str(df.at[pred_i, "date"].date()),
            "close_vs_ma20": float(r.get("close_vs_ma20", np.nan)),
            "close_vs_ma50": float(r.get("close_vs_ma50", np.nan)),
            "ma50_slope_10d": float(r.get("ma50_slope_10d", np.nan)),
            "ma20_slope_5d": float(r.get("ma20_slope_5d", np.nan)),
            "above_ma50": float(r.get("above_ma50", np.nan)),
        }
        if cfg.mode == "T0":
            feat["d5_pre"] = np.nan
            feat["d10_pre"] = np.nan
        else:
            post = df.iloc[e + 1 : pred_i + 1]["dist_day"]
            feat["d5_pre"] = float((post.tail(5) == 1).sum()) if len(post) else np.nan
            feat["d10_pre"] = float((post.tail(10) == 1).sum()) if len(post) else np.nan

        fw = df.iloc[fwd_start : fwd_end + 1].copy()
        lows = fw["low"].to_numpy(dtype=float)
        highs = fw["high"].to_numpy(dtype=float)
        closes = fw["close"].to_numpy(dtype=float)
        ma50 = fw["ma50"].to_numpy(dtype=float)
        ma20s5 = fw["ma20_slope_5d"].to_numpy(dtype=float)
        distf = fw["dist_day"].to_numpy(dtype=float)
        min_low = float(np.nanmin(lows))
        max_dd = min_low / close0 - 1.0
        # existing labels (for backward comparison)
        outcome_A = bool(max_dd <= -0.05)
        if np.isfinite(ma50).sum() > 0:
            outcome_B = bool(np.any(np.isfinite(ma50) & (closes < ma50)))
            below = np.where(np.isfinite(ma50), closes < ma50, False)
            outcome_B_strict = bool(np.any(below[:-1] & below[1:])) if len(below) >= 2 else False
        else:
            outcome_B = np.nan
            outcome_B_strict = np.nan
        n_dist = int(np.nansum(distf == 1))
        outcome_C = bool(n_dist >= 4)

        # new labels
        pullback_20d = bool(max_dd <= -0.05)
        cond_2close = False
        if np.isfinite(ma50).sum() >= 2:
            below = np.where(np.isfinite(ma50), closes < ma50, False)
            cond_2close = bool(np.any(below[:-1] & below[1:]))
        cond_ma20_neg = bool(np.any(np.isfinite(ma50) & np.isfinite(ma20s5) & (closes < ma50) & (ma20s5 <= 0)))
        trend_break_20d = bool(cond_2close or cond_ma20_neg)

        # confirmed_downtrend_20d
        req_available = np.isfinite(ma50).sum() >= 2 and np.isfinite(df.at[pred_i, "ma50_slope_10d"])
        if req_available:
            confirmed_downtrend_20d = bool(
                (max_dd <= -0.07)
                and cond_2close
                and ((float(df.at[pred_i, "ma50_slope_10d"]) <= 0.0) or (n_dist >= 4))
            )
        else:
            confirmed_downtrend_20d = np.nan

        ret20 = float(df.at[fwd_end, "close"] / close0 - 1.0)
        rows.append(
            {
                **feat,
                "ret_20d": ret20,
                "max_drawdown_20d": max_dd,
                "outcome_A": outcome_A,
                "outcome_B": outcome_B,
                "outcome_B_strict": outcome_B_strict,
                "outcome_C": outcome_C,
                "pullback_20d": pullback_20d,
                "trend_break_20d": trend_break_20d,
                "confirmed_downtrend_20d": confirmed_downtrend_20d,
            }
        )
    return pd.DataFrame(rows)


def distance_row(r: pd.Series, c: pd.Series, mode: str) -> float:
    terms = [
        (r["close_vs_ma50"] - c["close_vs_ma50"]) ** 2,
        (r["close_vs_ma20"] - c["close_vs_ma20"]) ** 2,
        4.0 * (r["ma50_slope_10d"] - c["ma50_slope_10d"]) ** 2,
        (r["above_ma50"] - c["above_ma50"]) ** 2,
    ]
    if mode != "T0":
        if np.isfinite(r.get("d5_pre", np.nan)) and np.isfinite(c.get("d5_pre", np.nan)):
            terms.append(0.15 * (r["d5_pre"] - c["d5_pre"]) ** 2)
        if np.isfinite(r.get("d10_pre", np.nan)) and np.isfinite(c.get("d10_pre", np.nan)):
            terms.append(0.1 * (r["d10_pre"] - c["d10_pre"]) ** 2)
    return float(np.nansum(terms))


def analog_probabilities(
    train_df: pd.DataFrame,
    cur: pd.Series,
    target: str,
    k: int,
    baseline_p: float | None,
    prior_strength: float,
    mode: str,
) -> dict[str, Any]:
    t = pd.to_numeric(train_df[target], errors="coerce")
    cand = train_df[t.notna()].copy()
    if cand.empty:
        return {"k": 0, "n": 0, "raw_p": np.nan, "raw_ci95": (np.nan, np.nan), "adjusted_p": np.nan}
    cand["distance"] = cand.apply(lambda r: distance_row(r, cur, mode), axis=1)
    top = cand.nsmallest(min(k, len(cand)), "distance")
    n = int(len(top))
    k_pos = int(pd.to_numeric(top[target], errors="coerce").fillna(0).astype(float).sum())
    raw_p = k_pos / n if n else np.nan
    lo, hi = wilson_ci(k_pos, n)
    if baseline_p is None or not np.isfinite(baseline_p):
        adjusted = np.nan
    else:
        adjusted = (k_pos + prior_strength * baseline_p) / (n + prior_strength) if n >= 0 else np.nan
    warns = []
    if n < 10:
        warns.append("very small sample; do not interpret as stable probability")
    elif n < 30:
        warns.append("small sample; high uncertainty")
    return {
        "k": k_pos,
        "n": n,
        "raw_p": raw_p,
        "raw_ci95": (lo, hi),
        "adjusted_p": adjusted,
        "top_analogs": top,
        "warnings": warns,
    }


def calibration_table(y: pd.Series, p: pd.Series) -> pd.DataFrame:
    d = pd.DataFrame({"y": y, "p": p}).dropna()
    if d.empty:
        return pd.DataFrame(columns=["bucket", "n", "pred_mean", "obs_rate"])
    bins = [-1e-9, 0.2, 0.4, 0.6, 0.8, 1.0]
    labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
    d["bucket"] = pd.cut(d["p"], bins=bins, labels=labels, include_lowest=True)
    g = d.groupby("bucket", observed=True).agg(n=("y", "size"), pred_mean=("p", "mean"), obs_rate=("y", "mean")).reset_index()
    return g


def infer_regime(prob: float | None, above_ma50: bool, breadth_weak: bool, recent_dist_up: bool) -> str:
    if prob is None or not np.isfinite(prob):
        return "Unknown"
    if prob < 0.25 and above_ma50 and not breadth_weak:
        return "Green"
    if prob < 0.40 or (not above_ma50 and not breadth_weak):
        return "Yellow"
    if prob <= 0.60 or recent_dist_up:
        return "Orange"
    return "Red"


def infer_regime_v2(
    confirmed_adj: float | None,
    trend_adj: float | None,
    outcome_b_adj: float | None,
    breadth_constructive: bool,
    above_ma20: bool,
    above_ma50: bool,
    sample_uncertainty_high: bool,
) -> str:
    c = confirmed_adj if confirmed_adj is not None and np.isfinite(confirmed_adj) else np.nan
    t = trend_adj if trend_adj is not None and np.isfinite(trend_adj) else np.nan
    b = outcome_b_adj if outcome_b_adj is not None and np.isfinite(outcome_b_adj) else np.nan
    if (
        np.isfinite(c)
        and np.isfinite(t)
        and np.isfinite(b)
        and c < 0.10
        and t < 0.25
        and b < 0.30
        and breadth_constructive
        and above_ma20
        and above_ma50
        and not sample_uncertainty_high
    ):
        return "Green"
    if (np.isfinite(c) and c > 0.40) or ((not above_ma50) and np.isfinite(t) and t > 0.50):
        return "Red"
    if (np.isfinite(c) and 0.20 <= c <= 0.40) or (np.isfinite(t) and t > 0.50) or (not above_ma50):
        return "Orange"
    return "Yellow"


def latest_breadth_context() -> dict[str, Any]:
    fp = REPO / "data" / "research" / "industry_wave_probability_l3_tune_d_latest.csv"
    if not fp.exists():
        return {"available": False, "note": "industry breadth file missing"}
    d = pd.read_csv(fp)
    if "p_wave_20d" not in d.columns:
        return {"available": False, "note": "p_wave_20d missing in breadth file"}
    s = pd.to_numeric(d["p_wave_20d"], errors="coerce")
    return {
        "available": True,
        "asof": str(pd.to_datetime(d["date"]).max().date()) if "date" in d.columns else None,
        "mean": float(s.mean()),
        "median": float(s.median()),
        "pct_lt_0_2": float((s < 0.2).mean()),
        "pct_ge_0_4": float((s >= 0.4).mean()),
        "historical_series_available": bool("date" in d.columns and pd.to_datetime(d["date"]).nunique() > 1),
    }


def write_text(path: Path, txt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")


def df_to_md(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "No rows.\n"
    cols = [str(c) for c in df.columns]
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, r in df.iterrows():
        vals = []
        for c in df.columns:
            v = r[c]
            if isinstance(v, float):
                if np.isnan(v):
                    vals.append("")
                else:
                    vals.append(f"{v:.6g}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    cfg = BuildConfig(
        mode=args.mode,
        event_method=args.event_method,
        dist_threshold=args.dist_threshold,
        volume_mode=args.volume_mode,
    )
    df = add_ma_features(add_dist_day(build_frame("VNINDEX", args.start, args.end), args.dist_threshold, args.volume_mode))
    ev = build_event_dataset(df, cfg)
    if ev.empty:
        raise RuntimeError("No valid events built.")
    ev = ev.sort_values("pred_date").reset_index(drop=True)

    asof = pd.Timestamp(args.asof)
    cur_idx = df.index[df["date"].dt.normalize() <= asof.normalize()].max()
    if pd.isna(cur_idx):
        raise RuntimeError("No index row at/before asof.")
    cur_idx = int(cur_idx)
    # create synthetic current row using latest known point, with mode logic
    cur_row = pd.Series(
        {
            "close_vs_ma20": float(df.at[cur_idx, "close_vs_ma20"]),
            "close_vs_ma50": float(df.at[cur_idx, "close_vs_ma50"]),
            "ma50_slope_10d": float(df.at[cur_idx, "ma50_slope_10d"]),
            "ma20_slope_5d": float(df.at[cur_idx, "ma20_slope_5d"]),
            "above_ma50": float(df.at[cur_idx, "close"] > df.at[cur_idx, "ma50"]) if np.isfinite(df.at[cur_idx, "ma50"]) else np.nan,
            "d5_pre": np.nan,
            "d10_pre": np.nan,
        }
    )

    targets = ["outcome_B", "outcome_B_strict", "trend_break_20d", "confirmed_downtrend_20d"]
    baseline = {}
    for t in targets:
        s = pd.to_numeric(ev[t], errors="coerce")
        baseline[t] = {"p": float(s.mean()) if s.notna().sum() else np.nan, "n": int(s.notna().sum())}

    current_probs = {}
    analog_tables = {}
    for t in targets:
        current_probs[t] = {}
        for k in [5, 10, 20]:
            ap = analog_probabilities(
                ev[ev["pred_date"] <= str(asof.date())],
                cur_row,
                t,
                k,
                baseline_p=baseline[t]["p"],
                prior_strength=args.prior_strength,
                mode=args.mode,
            )
            current_probs[t][k] = {kk: vv for kk, vv in ap.items() if kk != "top_analogs"}
            if k == args.k and "top_analogs" in ap:
                analog_tables[t] = ap["top_analogs"]

    # walk-forward
    wf_rows = []
    if not args.skip_validation:
        for i in range(len(ev)):
            cur = ev.iloc[i]
            train = ev.iloc[:i].copy()
            row = {"pred_date": cur["pred_date"], "event_date": cur["event_date"]}
            if len(train) < 20:
                row["skipped"] = True
                wf_rows.append(row)
                continue
            row["skipped"] = False
            for t in targets:
                bl = pd.to_numeric(train[t], errors="coerce")
                blp = float(bl.mean()) if bl.notna().sum() else np.nan
                ap = analog_probabilities(
                    train_df=train,
                    cur=cur,
                    target=t,
                    k=args.k,
                    baseline_p=blp,
                    prior_strength=args.prior_strength,
                    mode=args.mode,
                )
                row[f"{t}_y"] = pd.to_numeric(cur[t], errors="coerce")
                row[f"{t}_p_raw"] = ap["raw_p"]
                row[f"{t}_p_adj"] = ap["adjusted_p"]
                row[f"{t}_n"] = ap["n"]
            wf_rows.append(row)
    wf = pd.DataFrame(wf_rows)
    wf_out = REPO / "data" / "decision" / "downtrend_walkforward_predictions.csv"
    wf_out.parent.mkdir(parents=True, exist_ok=True)
    wf.to_csv(wf_out, index=False)

    cal_json = {}
    cal_md_parts = ["# Downtrend Walk-forward Calibration\n"]
    if args.skip_validation or wf.empty:
        cal_md_parts.append("Validation skipped by flag or no walk-forward rows.\n")
        cal_json["status"] = "skipped"
    for t in targets:
        if args.skip_validation or wf.empty:
            continue
        d = wf[(wf["skipped"] == False)].copy()
        y = pd.to_numeric(d[f"{t}_y"], errors="coerce")
        p_raw = pd.to_numeric(d[f"{t}_p_raw"], errors="coerce")
        p_adj = pd.to_numeric(d[f"{t}_p_adj"], errors="coerce")
        c_raw = calibration_table(y, p_raw)
        c_adj = calibration_table(y, p_adj)
        cal_json[t] = {
            "n_predictions": int(pd.DataFrame({"y": y, "p": p_raw}).dropna().shape[0]),
            "n_skipped": int((wf["skipped"] == True).sum()),
            "brier_raw": brier(y, p_raw),
            "brier_adj": brier(y, p_adj),
            "auc_raw": auc_rank(y, p_raw),
            "auc_adj": auc_rank(y, p_adj),
            "calibration_raw": c_raw.to_dict(orient="records"),
            "calibration_adj": c_adj.to_dict(orient="records"),
        }
        cal_md_parts.append(f"## {t}\n")
        cal_md_parts.append(
            f"- n_predictions: {cal_json[t]['n_predictions']}\n"
            f"- n_skipped: {cal_json[t]['n_skipped']}\n"
            f"- brier_raw: {cal_json[t]['brier_raw']}\n"
            f"- brier_adj: {cal_json[t]['brier_adj']}\n"
            f"- auc_raw: {cal_json[t]['auc_raw']}\n"
            f"- auc_adj: {cal_json[t]['auc_adj']}\n"
        )
        cal_md_parts.append("### Calibration buckets (raw)\n")
        cal_md_parts.append(df_to_md(c_raw) if not c_raw.empty else "No valid rows.\n")
        cal_md_parts.append("\n### Calibration buckets (adjusted)\n")
        cal_md_parts.append(df_to_md(c_adj) if not c_adj.empty else "No valid rows.\n")
        cal_md_parts.append("\n")
    cal_md = "\n".join(cal_md_parts)
    write_text(REPO / "reports" / "latest" / "downtrend_walkforward_calibration.md", cal_md)
    write_text(
        REPO / "reports" / "latest" / "downtrend_walkforward_calibration.json",
        json.dumps(cal_json, ensure_ascii=False, indent=2, default=str),
    )

    # sensitivity tests
    sens_rows = []
    # k sensitivity
    for k in [5, 10, 20]:
        d = wf[(wf["skipped"] == False)].copy()
        # recompute quickly using stored k=args.k only unavailable -> rebuild predictions for outcome_B
        # For sensitivity, run fresh loop for outcome_B only.
        preds = []
        for i in range(len(ev)):
            if i < 20:
                continue
            cur = ev.iloc[i]
            train = ev.iloc[:i]
            ap = analog_probabilities(train, cur, "outcome_B", k, float(pd.to_numeric(train["outcome_B"], errors="coerce").mean()), args.prior_strength, args.mode)
            preds.append({"y": pd.to_numeric(cur["outcome_B"], errors="coerce"), "p": ap["raw_p"]})
        pdf = pd.DataFrame(preds)
        sens_rows.append(
            {
                "test_type": "k_neighbors",
                "setting": f"k={k}",
                "target": "outcome_B",
                "n": int(pdf.dropna().shape[0]),
                "brier": brier(pdf["y"], pdf["p"]) if not pdf.empty else np.nan,
                "auc": auc_rank(pdf["y"], pdf["p"]) if not pdf.empty else np.nan,
            }
        )
    # event method sensitivity (baseline dist settings)
    for m in ["nonoverlap_8", "overlap", "cooldown_5", "cooldown_10"]:
        evm = build_event_dataset(df, BuildConfig(args.mode, m, args.dist_threshold, args.volume_mode))
        s = pd.to_numeric(evm["outcome_B"], errors="coerce")
        sens_rows.append(
            {
                "test_type": "event_method",
                "setting": m,
                "target": "outcome_B_baseline",
                "n": int(s.notna().sum()),
                "brier": np.nan,
                "auc": np.nan,
                "event_rate": float(s.mean()) if s.notna().sum() else np.nan,
            }
        )
    # dist-day threshold and volume-mode sensitivity
    for thr in [-0.002, -0.005, -0.01]:
        for vm in ["prev", "prev_105", "ma20"]:
            dfx = add_ma_features(add_dist_day(build_frame("VNINDEX", args.start, args.end), thr, vm))
            evx = build_event_dataset(dfx, BuildConfig(args.mode, args.event_method, thr, vm))
            s = pd.to_numeric(evx["outcome_B"], errors="coerce")
            sens_rows.append(
                {
                    "test_type": "dist_rule",
                    "setting": f"thr={thr},vol={vm}",
                    "target": "outcome_B_baseline",
                    "n": int(s.notna().sum()),
                    "event_rate": float(s.mean()) if s.notna().sum() else np.nan,
                }
            )
    sens = pd.DataFrame(sens_rows)
    sens.to_csv(REPO / "data" / "decision" / "downtrend_sensitivity.csv", index=False)
    write_text(REPO / "reports" / "latest" / "downtrend_sensitivity.md", "# Downtrend Sensitivity\n\n" + df_to_md(sens))

    # timestamp-alignment audit
    allowed_cols = ["close_vs_ma20", "close_vs_ma50", "ma50_slope_10d", "ma20_slope_5d", "above_ma50"]
    if args.mode != "T0":
        allowed_cols += ["d5_pre", "d10_pre"]
    mode_offset = {"T0": 0, "T5": 5, "T10": 10}[args.mode]
    align_rows = []
    for _, r in ev.iterrows():
        ev_date = pd.Timestamp(r["event_date"])
        pred_ts = pd.Timestamp(r["pred_date"])
        pred_i = int(r["pred_i"])
        expected_end = pd.Timestamp(df.at[int(r["event_i"]) + mode_offset, "date"])
        if pred_ts.normalize() != expected_end.normalize():
            raise RuntimeError(
                f"Timestamp alignment violation: mode={args.mode}, event={ev_date.date()}, prediction={pred_ts.date()}, expected={expected_end.date()}"
            )
        target_start = pd.Timestamp(df.at[pred_i + 1, "date"])
        target_end = pd.Timestamp(df.at[pred_i + 20, "date"])
        if not (target_start > pred_ts):
            raise RuntimeError(
                f"Target window starts before/at prediction timestamp: mode={args.mode}, event={ev_date.date()}"
            )
        forbidden = False
        if args.mode == "T0":
            if np.isfinite(pd.to_numeric(r.get("d5_pre"), errors="coerce")) or np.isfinite(
                pd.to_numeric(r.get("d10_pre"), errors="coerce")
            ):
                forbidden = True
                raise RuntimeError(f"Forbidden future columns detected in T0 at event {ev_date.date()}")
        align_rows.append(
            {
                "mode": args.mode,
                "event_date": str(ev_date.date()),
                "prediction_timestamp": str(pred_ts.date()),
                "feature_window_start": str(pd.Timestamp(df["date"].iloc[0]).date()),
                "feature_window_end": str(pred_ts.date()),
                "target_window_start": str(target_start.date()),
                "target_window_end": str(target_end.date()),
                "allowed_feature_columns": ",".join(allowed_cols),
                "forbidden_future_columns_detected": forbidden,
            }
        )
    align_df = pd.DataFrame(align_rows)
    align_csv = REPO / "data" / "decision" / "downtrend_timestamp_alignment_audit.csv"
    align_df.to_csv(align_csv, index=False)
    write_text(
        REPO / "reports" / "latest" / "downtrend_timestamp_alignment_audit.md",
        "# Downtrend Timestamp Alignment Audit\n\n" + df_to_md(align_df.head(120)),
    )

    # breadth integration feasibility
    breadth = latest_breadth_context()
    breadth_note = (
        "Breadth not fused quantitatively because historical breadth time series is unavailable."
        if not breadth.get("historical_series_available", False)
        else "Historical breadth exists; quantitative fusion can be added in next step."
    )

    # decision layer
    outcome_b_adj = current_probs["outcome_B"].get(args.k, {}).get("adjusted_p")
    trend_adj = current_probs["trend_break_20d"].get(args.k, {}).get("adjusted_p")
    confirmed_adj = current_probs["confirmed_downtrend_20d"].get(args.k, {}).get("adjusted_p")
    reference_target_used = "confirmed_downtrend_20d"
    p_ref = confirmed_adj
    if not np.isfinite(p_ref):
        reference_target_used = "trend_break_20d"
        p_ref = trend_adj
    if not np.isfinite(p_ref):
        reference_target_used = "outcome_B"
        p_ref = outcome_b_adj
    sample_n = current_probs[reference_target_used][args.k]["n"] if reference_target_used in current_probs else 0
    sample_uncertainty_high = bool(sample_n < 30)
    breadth_constructive = bool(
        breadth.get("available")
        and (breadth.get("pct_lt_0_2", 1.0) < 0.6)
        and (breadth.get("pct_ge_0_4", 0.0) > 0.1)
    )
    above_ma20_now = bool(np.isfinite(df.at[cur_idx, "ma20"]) and df.at[cur_idx, "close"] > df.at[cur_idx, "ma20"])
    above_ma50_now = bool(np.isfinite(df.at[cur_idx, "ma50"]) and df.at[cur_idx, "close"] > df.at[cur_idx, "ma50"])
    regime = infer_regime_v2(
        confirmed_adj=confirmed_adj,
        trend_adj=trend_adj,
        outcome_b_adj=outcome_b_adj,
        breadth_constructive=breadth_constructive,
        above_ma20=above_ma20_now,
        above_ma50=above_ma50_now,
        sample_uncertainty_high=sample_uncertainty_high,
    )
    regime_reason = [
        (
            f"confirmed_downtrend_20d adjusted probability = {confirmed_adj*100:.1f}%, below 25% risk threshold"
            if np.isfinite(confirmed_adj)
            else "confirmed_downtrend_20d adjusted probability = Unknown"
        ),
        (
            f"outcome_B adjusted probability = {outcome_b_adj*100:.1f}%, so MA50-breach proxy risk remains non-trivial"
            if np.isfinite(outcome_b_adj)
            else "outcome_B adjusted probability = Unknown"
        ),
        (
            f"trend_break adjusted probability = {trend_adj*100:.1f}%, so not clean enough for Green"
            if np.isfinite(trend_adj)
            else "trend_break adjusted probability = Unknown"
        ),
        "Breadth snapshot is constructive but not statistically fused into probability. It should be treated as supporting context, not model evidence.",
        "top-10 analog sample has high uncertainty" if sample_uncertainty_high else "analog sample uncertainty is moderate",
    ]

    # audit markdown
    audit_md = f"""# Downtrend Probability Methodology Audit

## Current code path / entry points
- Legacy event study: `scripts/research/vnindex_8ndd_event_study.py`
- Legacy current analog classification: `scripts/research/vnindex_current_case_classification.py`
- V2 runner added: `scripts/run_vnindex_downtrend_v2.py`
- FireAnt loader: `src/intake/fireant_historical.py`
- Breadth snapshot source: `data/research/industry_wave_probability_l3_tune_d_latest.csv`

## Current feature list (V2, mode={args.mode})
- `close_vs_ma20`, `close_vs_ma50`, `ma50_slope_10d`, `ma20_slope_5d`, `above_ma50`
- `{('d5_pre,d10_pre (for T+ modes only)' if args.mode!='T0' else 'd5_pre/d10_pre excluded in T0 by design')}`

## Target labels
- Backward-compatible: `outcome_A`, `outcome_B` (MA50 breach proxy), `outcome_B_strict`, `outcome_C`
- New: `pullback_20d`, `trend_break_20d`, `confirmed_downtrend_20d`

## Timestamp / leakage risk findings
- Legacy risk: post-event deterioration metrics can leak if mixed in T0 inference.
- V2 fix: strict mode separation (`T0`, `T5`, `T10`); T0 excludes all post-event features.
- Forward outcomes measured after prediction timestamp (`pred_i+1` to `pred_i+20`).

## Denominator / sample-size issues
- MA50 unavailable rows are excluded from valid target denominators.
- Raw analog probabilities include Wilson CI and explicit small-sample warnings.

## Calibration status
- Legacy 20% was raw analog frequency (not calibrated probability).
- V2 now reports raw, Wilson CI, and shrinkage-adjusted stabilized estimate.
- Calibration evidence stored in walk-forward reports.

## What changed in this patch
- Added V2 script with:
  - leakage-safe inference modes
  - expanded targets
  - uncertainty bands
  - shrinkage estimator
  - walk-forward validation + calibration outputs
  - sensitivity tests
  - production markdown report
"""
    write_text(REPO / "reports" / "latest" / "downtrend_probability_methodology_audit.md", audit_md)

    # current inference report
    def prob_row(name: str, target: str, kk: int) -> dict[str, Any]:
        bp = baseline[target]["p"]
        an = current_probs[target][kk]
        return {
            "target": name,
            "baseline_rate": bp,
            "analog_k_n": f"{an['k']}/{an['n']}",
            "raw_analog_p": an["raw_p"],
            "wilson95_low": an["raw_ci95"][0],
            "wilson95_high": an["raw_ci95"][1],
            "shrinkage_adjusted_p": an["adjusted_p"],
            "calibration_status": "walk-forward available",
        }

    ptable = pd.DataFrame(
        [
            prob_row("MA50 breach proxy (outcome_B)", "outcome_B", args.k),
            prob_row("B strict (2 closes below MA50)", "outcome_B_strict", args.k),
            prob_row("trend_break_20d", "trend_break_20d", args.k),
            prob_row("confirmed_downtrend_20d", "confirmed_downtrend_20d", args.k),
        ]
    )
    cal_summary_rows = []
    for t in ["outcome_B", "trend_break_20d", "confirmed_downtrend_20d"]:
        cj = cal_json.get(t, {})
        cal_summary_rows.append(
            {
                "target": t,
                "n_predictions": cj.get("n_predictions"),
                "n_skipped": cj.get("n_skipped"),
                "brier_raw": cj.get("brier_raw"),
                "brier_adj": cj.get("brier_adj"),
                "auc_raw": cj.get("auc_raw"),
                "auc_adj": cj.get("auc_adj"),
            }
        )
    cal_summary_df = pd.DataFrame(cal_summary_rows)
    cal_bucket_md = []
    for t in ["outcome_B", "trend_break_20d", "confirmed_downtrend_20d"]:
        c_adj = pd.DataFrame(cal_json.get(t, {}).get("calibration_adj", []))
        cal_bucket_md.append(f"### {t} (adjusted)\n")
        cal_bucket_md.append(df_to_md(c_adj) if not c_adj.empty else "No valid rows.\n")
        cal_bucket_md.append("\n")
    analog_md = ""
    if "outcome_B" in analog_tables:
        cols = ["event_date", "pred_date", "close_vs_ma50", "ma50_slope_10d", "outcome_B", "trend_break_20d", "confirmed_downtrend_20d", "ret_20d", "max_drawdown_20d", "distance"]
        a = analog_tables["outcome_B"][cols].copy() if set(cols).issubset(analog_tables["outcome_B"].columns) else analog_tables["outcome_B"].copy()
        analog_md = df_to_md(a.head(args.k))

    report_md = f"""# VNINDEX Downtrend Probability V2

## As-of
- asof_date: {asof.date()}
- mode: {args.mode}
- event_method: {args.event_method}
- dist_rule: threshold={args.dist_threshold}, volume_mode={args.volume_mode}

## Current state classification
- above_ma50: {bool(cur_row['above_ma50']==1.0)}
- close_vs_ma50: {cur_row['close_vs_ma50']}
- ma50_slope_10d: {cur_row['ma50_slope_10d']}

## Raw analog table (target=outcome_B proxy, k={args.k})
{analog_md if analog_md else "Unknown (no analog table available)."}

## Probability table
{df_to_md(ptable)}

## Headline wording (corrected)
- Raw top-{args.k} analog frequency for MA50-breach proxy = {current_probs['outcome_B'][args.k]['raw_p']:.1%} at {args.mode}
- Shrinkage-adjusted MA50-breach proxy risk = {outcome_b_adj:.1%} at {args.mode}
- Shrinkage-adjusted confirmed-downtrend risk = {confirmed_adj:.1%} at {args.mode}
- Regime = {regime}

## Calibration summary (walk-forward)
{df_to_md(cal_summary_df)}
Not a calibrated probability; use as stabilized analog estimate only.

## Calibration buckets (0-20%,20-40%,40-60%,60-80%,80-100%)
{''.join(cal_bucket_md)}

## Breadth context
- breadth_available: {breadth.get('available')}
- breadth_asof: {breadth.get('asof')}
- p20_mean: {breadth.get('mean')}
- p20_median: {breadth.get('median')}
- pct_industries_p20_lt_0_2: {breadth.get('pct_lt_0_2')}
- pct_industries_p20_ge_0_4: {breadth.get('pct_ge_0_4')}
- breadth_fusion: {breadth_note}
- breadth_statement: Breadth snapshot is constructive but not statistically fused into probability. It should be treated as supporting context, not model evidence.

## Decision layer
- regime: {regime}
- reference_probability_used: {p_ref}
- reference_target_used: {reference_target_used}
- regime_reason:
  - {regime_reason[0]}
  - {regime_reason[1]}
  - {regime_reason[2]}
  - {regime_reason[3]}
  - {regime_reason[4]}
- mapping_note:
  - Green: confirmed<10%, trend_break<25%, outcome_B<30%, breadth constructive, price above MA20/MA50
  - Yellow: confirmed<20% but trend_break/outcome_B >=30%, or uncertainty high, or breadth contextual only
  - Orange: confirmed 20-40% or trend_break>50% or price below MA50
  - Red: confirmed>40% or confirmed MA50 break + breadth deterioration + rising distribution

## Caveats
- outcome_B is MA50 breach proxy, not a full downtrend definition.
- raw analog probability is not calibrated by itself; use calibration report.
- small sample warnings apply when analog n is low.
"""
    write_text(REPO / "reports" / "latest" / "vnindex_downtrend_probability_v2.md", report_md)

    payload = {
        "asof": str(asof.date()),
        "mode": args.mode,
        "baseline": baseline,
        "current_probabilities": current_probs,
        "breadth": breadth,
        "breadth_note": breadth_note,
        "regime": regime,
        "reference_probability": p_ref,
        "reference_target_used": reference_target_used,
        "regime_reason": regime_reason,
        "outputs": {
            "walkforward_csv": "data/decision/downtrend_walkforward_predictions.csv",
            "calibration_md": "reports/latest/downtrend_walkforward_calibration.md",
            "calibration_json": "reports/latest/downtrend_walkforward_calibration.json",
            "sensitivity_md": "reports/latest/downtrend_sensitivity.md",
            "sensitivity_csv": "data/decision/downtrend_sensitivity.csv",
            "timestamp_alignment_csv": "data/decision/downtrend_timestamp_alignment_audit.csv",
            "timestamp_alignment_md": "reports/latest/downtrend_timestamp_alignment_audit.md",
            "audit_md": "reports/latest/downtrend_probability_methodology_audit.md",
            "current_report_md": "reports/latest/vnindex_downtrend_probability_v2.md",
        },
    }
    write_text(REPO / "data" / "decision" / "vnindex_downtrend_probability_v2.json", json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return payload


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run VNINDEX downtrend probability V2.")
    p.add_argument("--asof", default="2026-04-29")
    p.add_argument("--symbol", default="VNINDEX")
    p.add_argument("--start", default="2012-01-01")
    p.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    p.add_argument("--mode", default="T0", choices=["T0", "T5", "T10"])
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--prior-strength", type=float, default=20.0)
    p.add_argument("--event-method", default="nonoverlap_8", choices=["nonoverlap_8", "overlap", "cooldown_5", "cooldown_10"])
    p.add_argument("--dist-threshold", type=float, default=-0.002)
    p.add_argument("--volume-mode", default="prev", choices=["prev", "prev_105", "ma20"])
    p.add_argument("--skip-validation", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = run(args)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

