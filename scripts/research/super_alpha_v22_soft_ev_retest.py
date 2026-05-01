#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402


def _metrics(picks: pd.DataFrame) -> dict[str, float]:
    if picks.empty:
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
    return {
        "n": float(len(picks)),
        "hit_rate": float(picks["label_wave20"].mean()),
        "avg_ret20": float(picks["fwd_ret20"].mean()),
        "avg_mdd20": float(picks["fwd_mdd20"].mean()),
    }


def _build_regime(panel: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    c = get_client(timeout=45)
    vni = c.get_ohlcv("VNINDEX", start=start, end=end)
    vni["date"] = pd.to_datetime(vni["date"], errors="coerce")
    vni["close"] = pd.to_numeric(vni["close"], errors="coerce")
    vni["volume"] = pd.to_numeric(vni.get("volume"), errors="coerce")
    vni = vni.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    vni["ma50"] = vni["close"].rolling(50, min_periods=50).mean()
    vni["ma100"] = vni["close"].rolling(100, min_periods=100).mean()
    vni["slope50"] = vni["ma50"] / vni["ma50"].shift(10) - 1.0
    vni["slope100"] = vni["ma100"] / vni["ma100"].shift(20) - 1.0
    vni["dist"] = ((vni["close"] <= vni["close"].shift(1) * (1 - 0.002)) & (vni["volume"] > vni["volume"].shift(1))).astype(float)
    vni["dist20"] = vni["dist"].rolling(20, min_periods=10).sum()

    b = panel.groupby("date", as_index=False).agg(
        breadth60=("p20", lambda s: float((s >= 0.60).mean())),
        breadth_top20=("p20", lambda s: float(s.nlargest(min(20, len(s))).mean())),
    )
    return vni[["date", "close", "ma50", "ma100", "slope50", "slope100", "dist20"]].merge(b, on="date", how="left")


def _fit_monthly_calibration(train: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    z = train.dropna(subset=["p20", "label_wave20"]).copy()
    if z.empty:
        return pd.DataFrame(columns=["p", "p_cal", "exp_ret"])
    z["bucket"] = pd.qcut(z["p20"], q=min(n_bins, max(2, z["p20"].nunique())), duplicates="drop")
    m = z.groupby("bucket", observed=True).agg(p=("p20", "mean"), p_cal=("label_wave20", "mean"), exp_ret=("fwd_ret20", "mean"))
    return m.reset_index(drop=True)


def _apply_interp(x: pd.Series, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
    if len(xp) == 0:
        return np.full(len(x), np.nan)
    if len(xp) == 1:
        return np.full(len(x), float(fp[0]))
    xx = x.astype(float).clip(float(np.min(xp)), float(np.max(xp))).values
    return np.interp(xx, xp, fp)


def _score(df: pd.DataFrame, cfg: dict[str, float]) -> pd.Series:
    # Soft regime penalty (continuous, no hard gate)
    weak_ma = np.maximum(0.0, (df["ma50"] - df["close"]) / df["ma50"].replace(0, np.nan))
    weak_slope = np.maximum(0.0, -df["slope50"]) + 0.6 * np.maximum(0.0, -df["slope100"])
    weak_breadth = np.maximum(0.0, cfg["min_breadth60"] - df["breadth60"]) + 0.6 * np.maximum(
        0.0, cfg["min_breadth_top20"] - df["breadth_top20"]
    )
    high_dist = np.maximum(0.0, df["dist20"] - cfg["dist_soft_cap"]) / 10.0
    penalty = (
        cfg["w_pen_ma"] * weak_ma.fillna(0.0)
        + cfg["w_pen_slope"] * weak_slope.fillna(0.0)
        + cfg["w_pen_breadth"] * weak_breadth.fillna(0.0)
        + cfg["w_pen_dist"] * high_dist.fillna(0.0)
    )
    alpha_part = (
        cfg["w_sum"] * df["z_sum_p20"].fillna(0.0)
        + cfg["w_accel"] * df["z_recent_accel"].fillna(0.0)
        + cfg["w_vw"] * df["z_value_weighted_p20"].fillna(0.0)
        - cfg["w_crowd"] * df["z_overcrowded"].fillna(0.0)
    )
    # EV ranking core requested by user
    ev = df["p20_cal"].fillna(df["p20"]) * df["exp_ret20_hat"].fillna(0.0)
    return ev + 0.15 * alpha_part - penalty


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--end", default="2026-04-30")
    p.add_argument("--train-months", type=int, default=6)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--trials", type=int, default=240)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = p.parse_args()

    panel = pd.read_csv(args.panel_csv)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel = panel.dropna(subset=["date", "symbol", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    panel = panel[(panel["date"] >= pd.Timestamp(args.start)) & (panel["date"] <= pd.Timestamp(args.end))].copy()
    rb = _build_regime(panel, args.start, args.end)
    panel = panel.merge(rb, on="date", how="left")

    months = sorted(panel["date"].dt.to_period("M").unique().tolist())
    rng = random.Random(args.seed)
    wf_rows: list[dict[str, Any]] = []
    best_cfgs: list[dict[str, float]] = []

    for i in range(args.train_months, len(months)):
        tr_m = set(months[i - args.train_months : i])
        te_m = months[i]
        tr = panel[panel["date"].dt.to_period("M").isin(tr_m)].copy()
        te = panel[panel["date"].dt.to_period("M") == te_m].copy()
        if tr.empty or te.empty:
            continue

        # Monthly calibration map from train to reduce regime bias
        cal = _fit_monthly_calibration(tr, n_bins=10)
        xp = cal["p"].to_numpy(dtype=float) if not cal.empty else np.array([])
        pcal = cal["p_cal"].to_numpy(dtype=float) if not cal.empty else np.array([])
        eret = cal["exp_ret"].to_numpy(dtype=float) if not cal.empty else np.array([])
        tr["p20_cal"] = _apply_interp(tr["p20"], xp, pcal) if len(xp) else tr["p20"].values
        te["p20_cal"] = _apply_interp(te["p20"], xp, pcal) if len(xp) else te["p20"].values
        tr["exp_ret20_hat"] = _apply_interp(tr["p20"], xp, eret) if len(xp) else tr["fwd_ret20"].mean()
        te["exp_ret20_hat"] = _apply_interp(te["p20"], xp, eret) if len(xp) else tr["fwd_ret20"].mean()

        best_cfg = None
        best_obj = -1e9
        for _ in range(args.trials):
            cfg = {
                "w_sum": rng.uniform(0.5, 2.0),
                "w_accel": rng.uniform(0.2, 1.5),
                "w_vw": rng.uniform(0.4, 1.8),
                "w_crowd": rng.uniform(0.1, 1.5),
                "w_pen_ma": rng.uniform(0.3, 2.0),
                "w_pen_slope": rng.uniform(0.3, 2.0),
                "w_pen_breadth": rng.uniform(0.3, 2.0),
                "w_pen_dist": rng.uniform(0.1, 1.2),
                "min_breadth60": rng.uniform(0.03, 0.25),
                "min_breadth_top20": rng.uniform(0.42, 0.72),
                "dist_soft_cap": rng.uniform(3.0, 8.0),
            }
            tr["score"] = _score(tr, cfg)
            tr_pick = tr.sort_values(["date", "score"], ascending=[True, False]).groupby("date", as_index=False).head(args.top_n)
            m = _metrics(tr_pick)
            if m["n"] < max(120, args.top_n * 5):
                continue
            obj = float(m["hit_rate"]) + 0.25 * float(m["avg_ret20"]) - 0.04 * abs(float(m["avg_mdd20"]))
            if obj > best_obj:
                best_obj = obj
                best_cfg = cfg
        if best_cfg is None:
            continue
        best_cfgs.append(best_cfg)

        te["score"] = _score(te, best_cfg)
        te_v22 = te.sort_values(["date", "score"], ascending=[True, False]).groupby("date", as_index=False).head(args.top_n)
        te_base = te.sort_values(["date", "p20"], ascending=[True, False]).groupby("date", as_index=False).head(args.top_n)
        mv = _metrics(te_v22)
        mb = _metrics(te_base)
        wf_rows.append(
            {
                "test_month": str(te_m),
                "base_n": int(mb["n"]),
                "base_hit_rate": mb["hit_rate"],
                "base_avg_ret20": mb["avg_ret20"],
                "v22_n": int(mv["n"]),
                "v22_hit_rate": mv["hit_rate"],
                "v22_avg_ret20": mv["avg_ret20"],
                **{f"cfg_{k}": v for k, v in best_cfg.items()},
            }
        )

    wf = pd.DataFrame(wf_rows)
    if wf.empty:
        raise RuntimeError("No walk-forward rows for v2.2.")

    base_ok = wf[(wf["base_n"] > 0) & wf["base_hit_rate"].notna() & wf["base_avg_ret20"].notna()]
    v_ok = wf[(wf["v22_n"] > 0) & wf["v22_hit_rate"].notna() & wf["v22_avg_ret20"].notna()]
    overall = {
        "base": {
            "n": int(wf["base_n"].sum()),
            "months_with_picks": int((wf["base_n"] > 0).sum()),
            "hit_rate_weighted": float(np.average(base_ok["base_hit_rate"], weights=base_ok["base_n"])) if not base_ok.empty else np.nan,
            "avg_ret20_weighted": float(np.average(base_ok["base_avg_ret20"], weights=base_ok["base_n"])) if not base_ok.empty else np.nan,
        },
        "v22": {
            "n": int(wf["v22_n"].sum()),
            "months_with_picks": int((wf["v22_n"] > 0).sum()),
            "hit_rate_weighted": float(np.average(v_ok["v22_hit_rate"], weights=v_ok["v22_n"])) if not v_ok.empty else np.nan,
            "avg_ret20_weighted": float(np.average(v_ok["v22_avg_ret20"], weights=v_ok["v22_n"])) if not v_ok.empty else np.nan,
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "super_alpha_v22_monthly_compare_from_2023.csv"
    wf.to_csv(out_csv, index=False)
    mean_cfg = pd.DataFrame(best_cfgs).mean().to_dict() if best_cfgs else {}
    out = {
        "source": "FireAnt",
        "method": "REST API",
        "date_range": {"start": args.start, "end": args.end},
        "values_native_or_proxy": "native stock OHLCV + native VNINDEX OHLCV",
        "v22_design": {
            "gate_type": "soft penalty regime (no hard gate)",
            "ranking": "expected value = calibrated_p20 * expected_ret20_hat",
            "calibration": "monthly train-window calibration by p20 buckets",
        },
        "overall_compare": overall,
        "best_cfg_mean": mean_cfg,
        "monthly_compare_csv": str(out_csv),
        "limitations": [
            "expected_ret20_hat derived from train bucket averages; may lag abrupt regime shifts",
            "calibration granularity uses bucket interpolation, not full probabilistic model",
        ],
    }
    (out_dir / "super_alpha_v22_retest_from_2023.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

