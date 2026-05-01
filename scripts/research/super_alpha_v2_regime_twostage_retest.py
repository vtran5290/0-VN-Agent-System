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


def _ensure_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    num_cols = [
        "p20",
        "traded_value_vnd",
        "adv50_vnd",
        "label_wave20",
        "fwd_ret20",
        "fwd_mdd20",
        "sum_p20",
        "recent_accel",
        "value_weighted_p20",
        "overcrowded_count",
        "z_sum_p20",
        "z_recent_accel",
        "z_value_weighted_p20",
        "z_overcrowded",
    ]
    for c in num_cols:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.dropna(subset=["date", "symbol", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    x["symbol"] = x["symbol"].astype(str).str.upper()

    # Rebuild key features if missing (defensive).
    if "sum_p20" not in x.columns or x["sum_p20"].isna().all():
        g = x.sort_values(["symbol", "date"]).groupby("symbol", group_keys=False)
        x["sum_p20"] = g["p20"].rolling(20, min_periods=5).sum().reset_index(level=0, drop=True)
    if "recent_accel" not in x.columns or x["recent_accel"].isna().all():
        g = x.sort_values(["symbol", "date"]).groupby("symbol", group_keys=False)
        x["recent_accel"] = x["p20"] - g["p20"].rolling(5, min_periods=3).mean().shift(1).reset_index(level=0, drop=True)
    if "value_weighted_p20" not in x.columns or x["value_weighted_p20"].isna().all():
        g = x.sort_values(["symbol", "date"]).groupby("symbol", group_keys=False)
        x["value_weighted_p20"] = g.apply(
            lambda d: (d["p20"] * d["traded_value_vnd"]).rolling(20, min_periods=5).sum()
            / d["traded_value_vnd"].rolling(20, min_periods=5).sum()
        ).reset_index(level=0, drop=True)
    if "overcrowded_count" not in x.columns or x["overcrowded_count"].isna().all():
        x["p20_rank"] = x.groupby("date")["p20"].rank(method="min", ascending=False)
        x["topk_flag"] = (x["p20_rank"] <= 20).astype(float)
        g = x.sort_values(["symbol", "date"]).groupby("symbol", group_keys=False)
        x["overcrowded_count"] = g["topk_flag"].rolling(20, min_periods=5).sum().reset_index(level=0, drop=True)

    def _z_by_date(col: str) -> pd.Series:
        mu = x.groupby("date")[col].transform("mean")
        sd = x.groupby("date")[col].transform("std").replace(0, np.nan)
        return ((x[col] - mu) / sd).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if "z_sum_p20" not in x.columns or x["z_sum_p20"].isna().all():
        x["z_sum_p20"] = _z_by_date("sum_p20")
    if "z_recent_accel" not in x.columns or x["z_recent_accel"].isna().all():
        x["z_recent_accel"] = _z_by_date("recent_accel")
    if "z_value_weighted_p20" not in x.columns or x["z_value_weighted_p20"].isna().all():
        x["z_value_weighted_p20"] = _z_by_date("value_weighted_p20")
    if "z_overcrowded" not in x.columns or x["z_overcrowded"].isna().all():
        x["z_overcrowded"] = _z_by_date("overcrowded_count")
    return x


def _build_regime_and_breadth(panel: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    client = get_client(timeout=45)
    vni = client.get_ohlcv("VNINDEX", start=start, end=end)
    if vni.empty:
        raise RuntimeError("VNINDEX empty")
    vni = vni.sort_values("date").reset_index(drop=True)
    vni["date"] = pd.to_datetime(vni["date"], errors="coerce")
    vni["close"] = pd.to_numeric(vni["close"], errors="coerce")
    vni = vni.dropna(subset=["date", "close"])

    vni["ma50"] = vni["close"].rolling(50, min_periods=50).mean()
    vni["ma100"] = vni["close"].rolling(100, min_periods=100).mean()
    vni["slope_ma50_10"] = vni["ma50"] / vni["ma50"].shift(10) - 1.0
    vni["slope_ma100_20"] = vni["ma100"] / vni["ma100"].shift(20) - 1.0
    prev_c = vni["close"].shift(1)
    prev_v = vni.get("volume", pd.Series(index=vni.index, dtype=float)).shift(1)
    if "volume" in vni.columns:
        vni["volume"] = pd.to_numeric(vni["volume"], errors="coerce")
    else:
        vni["volume"] = np.nan
    vni["dist_day"] = ((vni["close"] <= prev_c * (1 - 0.002)) & (vni["volume"] > prev_v)).astype(float)
    vni["dist_days_20"] = vni["dist_day"].rolling(20, min_periods=10).sum()

    b = panel.groupby("date", as_index=False).agg(
        breadth_p20_60=("p20", lambda s: float((s >= 0.60).mean())),
        breadth_top20_mean_p20=("p20", lambda s: float(s.nlargest(min(20, len(s))).mean())),
        breadth_median_p20=("p20", "median"),
    )
    out = vni[["date", "close", "ma50", "ma100", "slope_ma50_10", "slope_ma100_20", "dist_days_20"]].merge(
        b, on="date", how="left"
    )
    return out


def _score_and_pick(df: pd.DataFrame, cfg: dict[str, float], top_n: int) -> pd.DataFrame:
    z = df.copy()
    z["score"] = (
        cfg["w_sum"] * z["z_sum_p20"]
        + cfg["w_accel"] * z["z_recent_accel"]
        + cfg["w_vw"] * z["z_value_weighted_p20"]
        + cfg["w_p20"] * z["p20"]
        - cfg["w_crowd"] * z["z_overcrowded"]
    )
    picks = z.sort_values(["date", "score"], ascending=[True, False]).groupby("date", as_index=False).head(top_n)
    return picks


def _metrics(picks: pd.DataFrame) -> dict[str, float]:
    if picks.empty:
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
    return {
        "n": float(len(picks)),
        "hit_rate": float(picks["label_wave20"].mean()),
        "avg_ret20": float(picks["fwd_ret20"].mean()),
        "avg_mdd20": float(picks["fwd_mdd20"].mean()),
    }


def _apply_gate(panel: pd.DataFrame, rb: pd.DataFrame, cfg: dict[str, float]) -> pd.DataFrame:
    x = panel.merge(rb, on="date", how="left")
    gate = (
        (x["close"] > x["ma50"])
        & (x["close"] > x["ma100"])
        & (x["slope_ma50_10"] >= cfg["min_slope50"])
        & (x["slope_ma100_20"] >= cfg["min_slope100"])
        & (x["dist_days_20"] <= cfg["max_dist20"])
        & (x["breadth_p20_60"] >= cfg["min_breadth60"])
        & (x["breadth_top20_mean_p20"] >= cfg["min_breadth_top20"])
    )
    return x[gate].copy()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--panel-csv",
        default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"),
    )
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    p.add_argument("--train-months", type=int, default=6)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--trials", type=int, default=220)
    p.add_argument("--coverage-target-ratio", type=float, default=0.6)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = p.parse_args()

    panel = pd.read_csv(args.panel_csv)
    panel = _ensure_features(panel)
    panel = panel[(panel["date"] >= pd.Timestamp(args.start)) & (panel["date"] <= pd.Timestamp(args.end))].copy()
    rb = _build_regime_and_breadth(panel, args.start, args.end)

    months = sorted(pd.to_datetime(panel["date"]).dt.to_period("M").unique().tolist())
    if len(months) < args.train_months + 2:
        raise RuntimeError("Insufficient months for walk-forward.")

    rng = random.Random(args.seed)
    wf_rows: list[dict[str, Any]] = []
    best_cfgs: list[dict[str, float]] = []

    for i in range(args.train_months, len(months)):
        train_months = set(months[i - args.train_months : i])
        test_month = months[i]
        tr = panel[pd.to_datetime(panel["date"]).dt.to_period("M").isin(train_months)].copy()
        te = panel[pd.to_datetime(panel["date"]).dt.to_period("M") == test_month].copy()
        if tr.empty or te.empty:
            continue

        best_cfg = None
        best_obj = -1e9
        base_train = tr.sort_values(["date", "p20"], ascending=[True, False]).groupby("date", as_index=False).head(args.top_n)
        base_train_n = max(int(len(base_train)), 1)
        for _ in range(args.trials):
            cfg = {
                "w_sum": rng.uniform(0.5, 2.2),
                "w_accel": rng.uniform(0.2, 1.7),
                "w_vw": rng.uniform(0.4, 2.0),
                "w_p20": rng.uniform(0.2, 1.2),
                "w_crowd": rng.uniform(0.2, 1.8),
                # relaxed gate search space to avoid over-filtering
                "min_slope50": rng.uniform(-0.02, 0.02),
                "min_slope100": rng.uniform(-0.03, 0.02),
                "max_dist20": rng.uniform(3.0, 10.0),
                "min_breadth60": rng.uniform(0.03, 0.25),
                "min_breadth_top20": rng.uniform(0.40, 0.72),
            }
            tr_g = _apply_gate(tr, rb, cfg)
            tr_p = _score_and_pick(tr_g, cfg, args.top_n)
            m = _metrics(tr_p)
            if m["n"] < max(120, 5 * args.top_n):
                continue
            cov_ratio = float(m["n"]) / float(base_train_n)
            cov_penalty = max(0.0, args.coverage_target_ratio - cov_ratio)
            obj = (
                float(m["hit_rate"])
                + 0.20 * float(m["avg_ret20"])
                - 0.03 * abs(float(m["avg_mdd20"]))
                - 0.25 * cov_penalty
            )
            if obj > best_obj:
                best_obj = obj
                best_cfg = cfg
        if best_cfg is None:
            continue
        best_cfgs.append(best_cfg)

        te_base = te.sort_values(["date", "p20"], ascending=[True, False]).groupby("date", as_index=False).head(args.top_n)
        te_g = _apply_gate(te, rb, best_cfg)
        te_v2 = _score_and_pick(te_g, best_cfg, args.top_n)
        mb = _metrics(te_base)
        mv = _metrics(te_v2)
        wf_rows.append(
            {
                "test_month": str(test_month),
                "base_n": int(mb["n"]),
                "base_hit_rate": mb["hit_rate"],
                "base_avg_ret20": mb["avg_ret20"],
                "base_avg_mdd20": mb["avg_mdd20"],
                "v2_n": int(mv["n"]),
                "v2_hit_rate": mv["hit_rate"],
                "v2_avg_ret20": mv["avg_ret20"],
                "v2_avg_mdd20": mv["avg_mdd20"],
                **{f"cfg_{k}": v for k, v in best_cfg.items()},
            }
        )

    wf = pd.DataFrame(wf_rows)
    if wf.empty:
        raise RuntimeError("No walk-forward rows produced.")

    # overall comparison: aggregate all month picks under their month-specific cfg
    base_ok = wf[(wf["base_n"] > 0) & wf["base_hit_rate"].notna() & wf["base_avg_ret20"].notna()].copy()
    v2_ok = wf[(wf["v2_n"] > 0) & wf["v2_hit_rate"].notna() & wf["v2_avg_ret20"].notna()].copy()

    overall = {
        "base": {
            "n": int(wf["base_n"].sum()),
            "months_with_picks": int((wf["base_n"] > 0).sum()),
            "hit_rate_weighted": float(np.average(base_ok["base_hit_rate"], weights=base_ok["base_n"]))
            if not base_ok.empty
            else np.nan,
            "avg_ret20_weighted": float(np.average(base_ok["base_avg_ret20"], weights=base_ok["base_n"]))
            if not base_ok.empty
            else np.nan,
        },
        "v2": {
            "n": int(wf["v2_n"].sum()),
            "months_with_picks": int((wf["v2_n"] > 0).sum()),
            "hit_rate_weighted": float(np.average(v2_ok["v2_hit_rate"], weights=v2_ok["v2_n"]))
            if not v2_ok.empty
            else np.nan,
            "avg_ret20_weighted": float(np.average(v2_ok["v2_avg_ret20"], weights=v2_ok["v2_n"]))
            if not v2_ok.empty
            else np.nan,
        },
    }

    mean_cfg = pd.DataFrame(best_cfgs).mean().to_dict() if best_cfgs else {}
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_monthly = out_dir / "super_alpha_v2_monthly_compare_from_2023.csv"
    wf.to_csv(out_monthly, index=False)

    out = {
        "source": "FireAnt",
        "method": "REST API",
        "date_range": {"start": args.start, "end": args.end},
        "values_native_or_proxy": "native stock OHLCV + native VNINDEX OHLCV",
        "regime_gate": "VNINDEX MA/slope + distribution days + breadth from stock universe",
        "two_stage_selection": "stage1 gate, stage2 weighted super score",
        "overall_compare": overall,
        "best_cfg_mean": mean_cfg,
        "monthly_compare_csv": str(out_monthly),
        "limitations": [
            "Breadth is derived from internal universe panel, not full market breadth feed.",
            "Random-search optimization may still overfit specific regimes.",
        ],
    }
    out_json = out_dir / "super_alpha_v2_retest_from_2023.json"
    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

