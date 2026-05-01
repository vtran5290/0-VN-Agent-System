#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.bds_leader_scan import _compute_features, fetch_symbols_universe  # noqa: E402
from scripts.research.daily_top20_stock_p20_range import _analog_p_hist_numpy, _current_lead_score_row  # noqa: E402
from src.data.fireant_client import get_client  # noqa: E402

STOCK_FEATURES = [
    "close_vs_ma20",
    "close_vs_ma50",
    "dist_to_52w_high",
    "rs20",
    "rs60",
    "vol_thrust20",
    "accum20",
]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _wave_label_and_ret(close: np.ndarray, i: int, horizon: int = 20) -> tuple[float | None, float | None, float | None]:
    if i + horizon >= len(close):
        return None, None, None
    c0 = float(close[i])
    c1 = float(close[i + horizon])
    ret = c1 / c0 - 1.0
    mdd = float(np.min(close[i + 1 : i + horizon + 1]) / c0 - 1.0)
    y = 1.0 if (ret > 0.08 and mdd > -0.08) else 0.0
    return y, ret, mdd


def _zscore_by_date(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby("date")[col]
    mu = g.transform("mean")
    sd = g.transform("std").replace(0, np.nan)
    z = (df[col] - mu) / sd
    return z.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_panel(args: argparse.Namespace) -> pd.DataFrame:
    client = get_client(timeout=45)
    vni = client.get_ohlcv("VNINDEX", start=args.history_start, end=args.end)
    if vni.empty:
        raise RuntimeError("VNINDEX empty")
    vni["date"] = pd.to_datetime(vni["date"], errors="coerce")
    vni = vni.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    uni = fetch_symbols_universe(client, limit=args.page_size)
    uni = uni[(uni["type"].str.lower() == "stock") & (uni["isListing"])].copy()
    uni = uni.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    meta = {
        str(r["symbol"]).upper(): {
            "name": r.get("name"),
            "exchange": r.get("exchange"),
            "industryCode": str(r.get("industryCode") or ""),
        }
        for _, r in uni.iterrows()
    }
    symbols = sorted(meta.keys())

    d0 = pd.Timestamp(args.start)
    d1 = pd.Timestamp(args.end)

    def _one(sym: str) -> list[dict[str, Any]]:
        df = client.get_ohlcv(sym, start=args.history_start, end=args.end)
        if df.empty or len(df) < max(args.min_rows_analog, 260):
            return []
        x = df.copy()
        x["date"] = pd.to_datetime(x["date"], errors="coerce")
        for c in ["open", "high", "low", "close", "volume"]:
            x[c] = pd.to_numeric(x[c], errors="coerce")
        x = x.dropna(subset=["date", "close", "high", "low", "volume"]).sort_values("date").reset_index(drop=True)
        if len(x) < max(args.min_rows_analog, 260):
            return []

        vni_sub = vni[vni["date"] <= x["date"].max()].copy()
        feat = _compute_features(x, vni=vni_sub)
        if feat.empty:
            return []
        feat = feat.sort_values("date").reset_index(drop=True)

        dates = feat["date"].to_numpy(dtype="datetime64[ns]")
        close = feat["close"].to_numpy(dtype=float)
        volume = feat["volume"].to_numpy(dtype=float)
        value = close * 1000.0 * volume  # FireAnt close in thousand VND
        adv50 = pd.Series(value).rolling(50, min_periods=50).mean().to_numpy(dtype=float)

        X = feat[STOCK_FEATURES].to_numpy(dtype=float)
        lab = feat["label_lead20"].to_numpy(dtype=float)

        out: list[dict[str, Any]] = []
        m = meta[sym]
        for i in range(args.min_rows_analog - 1, len(feat)):
            dt = pd.Timestamp(dates[i])
            if dt < d0 or dt > d1:
                continue
            y, fwd_ret20, fwd_mdd20 = _wave_label_and_ret(close, i, args.horizon)
            if y is None:
                continue
            sub_x = X[: i + 1]
            sub_lab = lab[: i + 1]
            p_hist = _analog_p_hist_numpy(sub_x, sub_lab, args.analog_top_k, args.min_rows_analog)
            p_now = float(_sigmoid(_current_lead_score_row(sub_x[-1]) / 3.0))
            p20 = float(np.nanmean([p_now, p_hist])) if np.isfinite(p_hist) else p_now
            if not np.isfinite(p20):
                continue
            adv = float(adv50[i]) if np.isfinite(adv50[i]) else np.nan
            if not np.isfinite(adv) or adv < args.adv_min_vnd:
                continue

            out.append(
                {
                    "date": dt.normalize(),
                    "symbol": sym,
                    "name": m["name"],
                    "exchange": m["exchange"],
                    "industryCode": m["industryCode"],
                    "p20": p20,
                    "p_now": p_now,
                    "p_hist": float(p_hist) if np.isfinite(p_hist) else np.nan,
                    "traded_value_vnd": float(value[i]),
                    "adv50_vnd": adv,
                    "label_wave20": float(y),
                    "fwd_ret20": float(fwd_ret20),
                    "fwd_mdd20": float(fwd_mdd20),
                }
            )
        return out

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_one, s): s for s in symbols}
        for fut in as_completed(futs):
            part = fut.result()
            if part:
                rows.extend(part)
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise RuntimeError("Empty panel after ADV filter.")
    return panel.sort_values(["date", "symbol"]).reset_index(drop=True)


def add_super_features(panel: pd.DataFrame, lookback: int, crowd_topk: int) -> pd.DataFrame:
    x = panel.sort_values(["symbol", "date"]).copy()
    g = x.groupby("symbol", group_keys=False)
    x["sum_p20"] = g["p20"].rolling(lookback, min_periods=5).sum().reset_index(level=0, drop=True)
    x["recent_accel"] = x["p20"] - g["p20"].rolling(5, min_periods=3).mean().shift(1).reset_index(level=0, drop=True)
    num = g.apply(
        lambda d: (d["p20"] * d["traded_value_vnd"]).rolling(lookback, min_periods=5).sum()
        / d["traded_value_vnd"].rolling(lookback, min_periods=5).sum()
    )
    x["value_weighted_p20"] = num.reset_index(level=0, drop=True)

    x["p20_rank"] = x.groupby("date")["p20"].rank(method="min", ascending=False)
    x["topk_flag"] = (x["p20_rank"] <= crowd_topk).astype(float)
    x["overcrowded_count"] = g["topk_flag"].rolling(lookback, min_periods=5).sum().reset_index(level=0, drop=True)

    x["z_sum_p20"] = _zscore_by_date(x, "sum_p20")
    x["z_recent_accel"] = _zscore_by_date(x, "recent_accel")
    x["z_value_weighted_p20"] = _zscore_by_date(x, "value_weighted_p20")
    x["z_overcrowded"] = _zscore_by_date(x, "overcrowded_count")
    return x


def evaluate_strategy(df: pd.DataFrame, score_col: str, top_n: int) -> dict[str, Any]:
    picks = (
        df.sort_values(["date", score_col], ascending=[True, False])
        .groupby("date", as_index=False)
        .head(top_n)
        .copy()
    )
    if picks.empty:
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
    return {
        "n": int(len(picks)),
        "hit_rate": float(picks["label_wave20"].mean()),
        "avg_ret20": float(picks["fwd_ret20"].mean()),
        "avg_mdd20": float(picks["fwd_mdd20"].mean()),
    }


def walkforward_optimize(df: pd.DataFrame, args: argparse.Namespace) -> tuple[dict[str, float], pd.DataFrame]:
    rng = random.Random(args.seed)
    dates = sorted(pd.to_datetime(df["date"]).unique().tolist())
    months = sorted(pd.to_datetime(pd.Series(dates)).dt.to_period("M").unique().tolist())
    if len(months) < args.train_months + 2:
        raise RuntimeError("Not enough months for walk-forward.")

    candidates: list[dict[str, float]] = []
    for _ in range(args.weight_trials):
        w1 = rng.uniform(0.5, 2.0)
        w2 = rng.uniform(0.2, 1.5)
        w3 = rng.uniform(0.5, 2.0)
        w4 = rng.uniform(0.2, 1.5)
        candidates.append({"w_sum": w1, "w_accel": w2, "w_vw": w3, "w_crowd": w4})

    wf_rows: list[dict[str, Any]] = []
    for i in range(args.train_months, len(months) - 1):
        tr_months = set(months[i - args.train_months : i])
        te_month = months[i]
        tr = df[pd.to_datetime(df["date"]).dt.to_period("M").isin(tr_months)].copy()
        te = df[pd.to_datetime(df["date"]).dt.to_period("M") == te_month].copy()
        if tr.empty or te.empty:
            continue

        best_cfg: dict[str, float] | None = None
        best_score = -1e9
        for cfg in candidates:
            tr["score"] = (
                cfg["w_sum"] * tr["z_sum_p20"]
                + cfg["w_accel"] * tr["z_recent_accel"]
                + cfg["w_vw"] * tr["z_value_weighted_p20"]
                - cfg["w_crowd"] * tr["z_overcrowded"]
            )
            met = evaluate_strategy(tr, "score", args.top_n)
            if met["n"] <= 0 or not np.isfinite(met["hit_rate"]):
                continue
            score = met["hit_rate"] + 0.25 * met["avg_ret20"]
            if score > best_score:
                best_score = score
                best_cfg = cfg
        if best_cfg is None:
            continue

        te["super_score"] = (
            best_cfg["w_sum"] * te["z_sum_p20"]
            + best_cfg["w_accel"] * te["z_recent_accel"]
            + best_cfg["w_vw"] * te["z_value_weighted_p20"]
            - best_cfg["w_crowd"] * te["z_overcrowded"]
        )
        te_super = evaluate_strategy(te, "super_score", args.top_n)
        te_base = evaluate_strategy(te, "p20", args.top_n)
        wf_rows.append(
            {
                "test_month": str(te_month),
                **{f"cfg_{k}": v for k, v in best_cfg.items()},
                "super_n": te_super["n"],
                "super_hit_rate": te_super["hit_rate"],
                "super_avg_ret20": te_super["avg_ret20"],
                "base_n": te_base["n"],
                "base_hit_rate": te_base["hit_rate"],
                "base_avg_ret20": te_base["avg_ret20"],
            }
        )

    wf = pd.DataFrame(wf_rows)
    if wf.empty:
        raise RuntimeError("Walk-forward produced no rows.")
    # Aggregate best average cfg
    best = {
        "w_sum": float(wf["cfg_w_sum"].mean()),
        "w_accel": float(wf["cfg_w_accel"].mean()),
        "w_vw": float(wf["cfg_w_vw"].mean()),
        "w_crowd": float(wf["cfg_w_crowd"].mean()),
    }
    return best, wf


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    p.add_argument("--history-start", default="2022-01-01")
    p.add_argument("--adv-min-vnd", type=float, default=2_000_000_000.0)
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--min-rows-analog", type=int, default=320)
    p.add_argument("--analog-top-k", type=int, default=20)
    p.add_argument("--lookback", type=int, default=20)
    p.add_argument("--crowd-topk", type=int, default=20)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--train-months", type=int, default=6)
    p.add_argument("--weight-trials", type=int, default=180)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--page-size", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = p.parse_args()

    panel = build_panel(args)
    panel = add_super_features(panel, args.lookback, args.crowd_topk)
    best_cfg, wf = walkforward_optimize(panel, args)

    panel["super_score"] = (
        best_cfg["w_sum"] * panel["z_sum_p20"]
        + best_cfg["w_accel"] * panel["z_recent_accel"]
        + best_cfg["w_vw"] * panel["z_value_weighted_p20"]
        - best_cfg["w_crowd"] * panel["z_overcrowded"]
    )

    overall_super = evaluate_strategy(panel, "super_score", args.top_n)
    overall_base = evaluate_strategy(panel, "p20", args.top_n)

    # Focus check for VIC/GEX in Mar-Jul 2025
    s0 = pd.Timestamp("2025-03-01")
    s1 = pd.Timestamp("2025-07-31")
    sub = panel[(panel["date"] >= s0) & (panel["date"] <= s1)].copy()
    picks_super = sub.sort_values(["date", "super_score"], ascending=[True, False]).groupby("date").head(args.top_n)
    picks_base = sub.sort_values(["date", "p20"], ascending=[True, False]).groupby("date").head(args.top_n)

    def _first_pick(picks: pd.DataFrame, sym: str) -> str | None:
        x = picks[picks["symbol"] == sym]
        if x.empty:
            return None
        return pd.Timestamp(x["date"].min()).strftime("%Y-%m-%d")

    focus = {
        "VIC": {
            "super_first_pick": _first_pick(picks_super, "VIC"),
            "base_first_pick": _first_pick(picks_base, "VIC"),
            "super_count": int((picks_super["symbol"] == "VIC").sum()),
            "base_count": int((picks_base["symbol"] == "VIC").sum()),
        },
        "GEX": {
            "super_first_pick": _first_pick(picks_super, "GEX"),
            "base_first_pick": _first_pick(picks_base, "GEX"),
            "super_count": int((picks_super["symbol"] == "GEX").sum()),
            "base_count": int((picks_base["symbol"] == "GEX").sum()),
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out_dir / "super_alpha_panel_from_2023.csv", index=False)
    wf.to_csv(out_dir / "super_alpha_walkforward_monthly_from_2023.csv", index=False)

    out = {
        "source": "FireAnt",
        "method": "REST API",
        "date_range": {"start": args.start, "end": args.end},
        "value_formula_vnd": "close * 1000 * volume",
        "adv_filter": args.adv_min_vnd,
        "symbols_covered": int(panel["symbol"].nunique()),
        "rows_panel": int(len(panel)),
        "best_weights_mean_walkforward": best_cfg,
        "overall_super": overall_super,
        "overall_baseline_p20": overall_base,
        "focus_mar_jul_2025": focus,
        "outputs": {
            "panel_csv": str(out_dir / "super_alpha_panel_from_2023.csv"),
            "walkforward_csv": str(out_dir / "super_alpha_walkforward_monthly_from_2023.csv"),
        },
        "limitations": [
            "Feature set based on technical OHLCV only; no fundamentals/news.",
            "Walk-forward optimizes simple linear score weights; may still overfit regime shifts.",
        ],
    }
    (out_dir / "super_alpha_walkforward_from_2023.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

