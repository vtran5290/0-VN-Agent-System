#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.data.fireant_client import RESTV2_BASE, get_client  # noqa: E402


FEATURE_COLS = [
    "close_vs_ma20",
    "close_vs_ma50",
    "close_vs_ma200",
    "ma20_slope_5d",
    "ma50_slope_10d",
    "dist_to_20d_high",
    "dist_to_50d_high",
    "near_high_20_ratio_5d",
    "volume_thrust_20",
    "rs_20d",
    "rs_60d",
    "dist_days_10",
    "dist_days_20",
    "atrp_14",
    "volatility_20",
]

PROBABILITY_COLS = ["p_wave_10d_raw", "p_wave_20d_raw", "p_wave_10d", "p_wave_20d"]


@dataclass
class BinModel:
    edges: Dict[str, np.ndarray]
    stats: Dict[str, Dict[int, tuple[float, float]]]
    base_p: float


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _safe_logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _safe_pct_change(series: pd.Series, periods: int) -> pd.Series:
    prev = series.shift(periods)
    out = (series / prev) - 1.0
    out[(prev <= 0) | (~np.isfinite(prev))] = np.nan
    return out


def _drawdown_forward(close: pd.Series, horizon: int) -> pd.Series:
    future_min = close.shift(-1).rolling(horizon, min_periods=horizon).min().shift(-(horizon - 1))
    dd = (future_min / close) - 1.0
    return dd


def _parse_industry_master(raw: Sequence[Dict[str, Any]], level: int) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    if df.empty:
        return pd.DataFrame(columns=["industryCode", "name", "level"])
    for col in ["industryCode", "name", "level"]:
        if col not in df.columns:
            df[col] = np.nan
    df["industryCode"] = df["industryCode"].astype(str)
    if "level" in df.columns:
        df["level"] = pd.to_numeric(df["level"], errors="coerce")
        df = df[df["level"] == level]
    return df[["industryCode", "name", "level"]].dropna(subset=["industryCode"])


def _infer_level1_parent(code: str) -> str:
    """Infer level-1 parent code from ICB-style code string."""
    c = str(code).zfill(4)
    if c in {"0001", "1000", "2000", "3000", "4000", "5000", "6000", "7000", "8000", "9000"}:
        return c
    if c.startswith("0"):
        return "0001"
    return f"{(int(c) // 1000) * 1000:04d}"


def _fetch_industry_history(client: Any, code: str, start: str, end: str) -> pd.DataFrame:
    data = client._get(  # type: ignore[attr-defined]
        f"{RESTV2_BASE}/industries/{code}/historical-stats",
        params={"startDate": start, "endDate": end},
    )
    rows: List[Dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            rows.append(
                {
                    "industryCode": code,
                    "date": str(item.get("date", ""))[:10],
                    "open": item.get("indexOpen"),
                    "high": item.get("indexHigh"),
                    "low": item.get("indexLow"),
                    "close": item.get("indexClose"),
                    "volume": item.get("totalVolume"),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["industryCode", "date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    return df


def _fetch_vnindex(client: Any, start: str, end: str) -> pd.DataFrame:
    from src.data.fireant_client import get_client as _get_fireant_client

    idx = _get_fireant_client().get_ohlcv("VNINDEX", start, end)
    if idx.empty:
        return pd.DataFrame(columns=["date", "vnindex_close"])
    out = idx[["date", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.rename(columns={"close": "vnindex_close"})
    return out


def _feature_engineering(df: pd.DataFrame, vnindex: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.merge(vnindex, on="date", how="left")

    out["ma20"] = out["close"].rolling(20).mean()
    out["ma50"] = out["close"].rolling(50).mean()
    out["ma200"] = out["close"].rolling(200).mean()

    out["close_vs_ma20"] = (out["close"] / out["ma20"]) - 1.0
    out["close_vs_ma50"] = (out["close"] / out["ma50"]) - 1.0
    out["close_vs_ma200"] = (out["close"] / out["ma200"]) - 1.0
    out["ma20_slope_5d"] = (out["ma20"] / out["ma20"].shift(5)) - 1.0
    out["ma50_slope_10d"] = (out["ma50"] / out["ma50"].shift(10)) - 1.0

    out["dist_to_20d_high"] = (out["close"] / out["high"].rolling(20).max()) - 1.0
    out["dist_to_50d_high"] = (out["close"] / out["high"].rolling(50).max()) - 1.0
    out["near_high_20"] = (out["dist_to_20d_high"] >= -0.02).astype(float)
    out["near_high_20_ratio_5d"] = out["near_high_20"].rolling(5).mean()

    out["volume_thrust_20"] = out["volume"] / out["volume"].rolling(20).median()

    out["ret_20"] = _safe_pct_change(out["close"], 20)
    out["ret_60"] = _safe_pct_change(out["close"], 60)
    out["vni_ret_20"] = _safe_pct_change(out["vnindex_close"], 20)
    out["vni_ret_60"] = _safe_pct_change(out["vnindex_close"], 60)
    out["rs_20d"] = out["ret_20"] - out["vni_ret_20"]
    out["rs_60d"] = out["ret_60"] - out["vni_ret_60"]

    prev_close = out["close"].shift(1)
    prev_volume = out["volume"].shift(1)
    out["distribution_day"] = ((out["close"] < prev_close) & (out["volume"] > prev_volume)).astype(float)
    out["dist_days_10"] = out["distribution_day"].rolling(10).sum()
    out["dist_days_20"] = out["distribution_day"].rolling(20).sum()

    tr1 = out["high"] - out["low"]
    tr2 = (out["high"] - out["close"].shift(1)).abs()
    tr3 = (out["low"] - out["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["atr_14"] = tr.rolling(14).mean()
    out["atrp_14"] = out["atr_14"] / out["close"]

    out["daily_ret"] = out["close"].pct_change()
    out["volatility_20"] = out["daily_ret"].rolling(20).std()

    out["fwd_ret_10"] = out["close"].shift(-10) / out["close"] - 1.0
    out["fwd_ret_20"] = out["close"].shift(-20) / out["close"] - 1.0
    out["fwd_mdd_20"] = _drawdown_forward(out["close"], 20)
    out["label_wave_10d"] = (out["fwd_ret_10"] > 0.05).astype(float)
    out["label_wave_20d"] = ((out["fwd_ret_20"] > 0.08) & (out["fwd_mdd_20"] > -0.05)).astype(float)

    return out


def _quantile_edges(values: pd.Series, n_bins: int) -> np.ndarray:
    clean = values.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return np.array([-np.inf, np.inf])
    qs = np.linspace(0, 1, n_bins + 1)
    cuts = np.unique(np.nanquantile(clean.values, qs))
    if len(cuts) < 2:
        return np.array([-np.inf, np.inf])
    cuts[0] = -np.inf
    cuts[-1] = np.inf
    return cuts


def _fit_bin_model(train_df: pd.DataFrame, target_col: str, features: Sequence[str], n_bins: int) -> BinModel:
    y = train_df[target_col].astype(float)
    base_p = float(y.mean()) if len(y) else 0.5
    edges: Dict[str, np.ndarray] = {}
    stats: Dict[str, Dict[int, tuple[float, float]]] = {}

    for feat in features:
        e = _quantile_edges(train_df[feat], n_bins=n_bins)
        edges[feat] = e
        bins = pd.cut(train_df[feat], bins=e, labels=False, include_lowest=True)

        feat_stats: Dict[int, tuple[float, float]] = {}
        for b in sorted(pd.Series(bins).dropna().astype(int).unique().tolist()):
            m = bins == b
            yb = y[m]
            if len(yb) == 0:
                continue
            pos = float(yb.sum())
            neg = float(len(yb) - pos)
            p1 = (pos + 1.0) / (len(yb) + 2.0)
            p0 = (neg + 1.0) / (len(yb) + 2.0)
            feat_stats[b] = (p1, p0)
        stats[feat] = feat_stats

    return BinModel(edges=edges, stats=stats, base_p=base_p)


def _predict_bin_model(model: BinModel, frame: pd.DataFrame, features: Sequence[str]) -> pd.Series:
    base_logit = _safe_logit(model.base_p)
    out = np.full(len(frame), base_logit, dtype=float)
    base_ratio = model.base_p / max(1.0 - model.base_p, 1e-4)

    for feat in features:
        edges = model.edges.get(feat, np.array([-np.inf, np.inf]))
        bins = pd.cut(frame[feat], bins=edges, labels=False, include_lowest=True)
        stat = model.stats.get(feat, {})
        for i, b in enumerate(bins):
            if pd.isna(b):
                continue
            pair = stat.get(int(b))
            if pair is None:
                continue
            p1, p0 = pair
            ratio = p1 / max(p0, 1e-4)
            out[i] += math.log(max(ratio, 1e-4) / max(base_ratio, 1e-4))

    probs = pd.Series([_sigmoid(float(v)) for v in out], index=frame.index)
    return probs.clip(0.001, 0.999)


def _build_calibration_map(oos_prob: pd.Series, oos_y: pd.Series, n_bins: int = 10) -> pd.DataFrame:
    raw = pd.DataFrame({"p": oos_prob, "y": oos_y}).dropna()
    if raw.empty:
        return pd.DataFrame(columns=["p_mean", "y_mean"])
    raw["bucket"] = pd.qcut(raw["p"], q=min(n_bins, max(2, raw["p"].nunique())), duplicates="drop")
    g = raw.groupby("bucket", observed=True).agg(p_mean=("p", "mean"), y_mean=("y", "mean")).reset_index(drop=True)
    return g


def _apply_calibration(prob: pd.Series, cal_map: pd.DataFrame) -> pd.Series:
    if cal_map.empty:
        return prob
    xp = cal_map["p_mean"].values
    fp = cal_map["y_mean"].values
    if len(xp) == 1:
        return pd.Series(np.full(len(prob), fp[0]), index=prob.index)
    clipped = prob.clip(min(xp), max(xp))
    out = np.interp(clipped.values, xp, fp)
    return pd.Series(out, index=prob.index)


def _fit_isotonic_pava(p: pd.Series, y: pd.Series) -> pd.DataFrame:
    z = pd.DataFrame({"p": p, "y": y}).dropna().sort_values("p")
    if z.empty:
        return pd.DataFrame(columns=["p_left", "p_right", "yhat"])
    xs = z["p"].to_numpy(dtype=float)
    ys = z["y"].to_numpy(dtype=float)
    blocks = [{"sum_w": 1.0, "sum_y": float(yy), "left": float(xx), "right": float(xx)} for xx, yy in zip(xs, ys)]
    i = 0
    while i < len(blocks) - 1:
        m1 = blocks[i]["sum_y"] / blocks[i]["sum_w"]
        m2 = blocks[i + 1]["sum_y"] / blocks[i + 1]["sum_w"]
        if m1 <= m2:
            i += 1
            continue
        blocks[i]["sum_w"] += blocks[i + 1]["sum_w"]
        blocks[i]["sum_y"] += blocks[i + 1]["sum_y"]
        blocks[i]["right"] = blocks[i + 1]["right"]
        del blocks[i + 1]
        if i > 0:
            i -= 1
    out = []
    for b in blocks:
        out.append(
            {
                "p_left": float(b["left"]),
                "p_right": float(b["right"]),
                "yhat": float(b["sum_y"] / b["sum_w"]),
            }
        )
    return pd.DataFrame(out)


def _apply_isotonic(prob: pd.Series, iso_map: pd.DataFrame) -> pd.Series:
    if iso_map.empty:
        return prob
    p = prob.to_numpy(dtype=float)
    out = np.full_like(p, np.nan, dtype=float)
    for _, row in iso_map.iterrows():
        mask = (p >= float(row["p_left"])) & (p <= float(row["p_right"]))
        out[mask] = float(row["yhat"])
    y0 = float(iso_map.iloc[0]["yhat"])
    y1 = float(iso_map.iloc[-1]["yhat"])
    out[np.isnan(out) & (p < float(iso_map.iloc[0]["p_left"]))] = y0
    out[np.isnan(out) & (p > float(iso_map.iloc[-1]["p_right"]))] = y1
    out = np.where(np.isnan(out), np.nanmean(iso_map["yhat"].to_numpy(dtype=float)), out)
    return pd.Series(np.clip(out, 0.001, 0.999), index=prob.index)


def _split_oos_by_date(oos_df: pd.DataFrame, train_frac: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = oos_df.dropna(subset=["prob_raw", "y", "date"]).copy()
    if d.empty:
        return d, d
    dates = sorted(pd.to_datetime(d["date"]).dropna().unique().tolist())
    if len(dates) < 4:
        return d, d.iloc[0:0].copy()
    cut_idx = int(len(dates) * train_frac)
    cut_idx = min(max(cut_idx, 1), len(dates) - 1)
    cut_date = dates[cut_idx]
    tr = d[pd.to_datetime(d["date"]) < cut_date].copy()
    va = d[pd.to_datetime(d["date"]) >= cut_date].copy()
    return tr, va


def _optimize_calibration(oos_df: pd.DataFrame) -> Dict[str, Any]:
    oos_df = oos_df.dropna(subset=["prob_raw", "y"]).copy()
    if oos_df.empty:
        return {"name": "identity", "details": {}, "brier_valid": None}
    tr, va = _split_oos_by_date(oos_df, train_frac=0.7)
    if tr.empty or va.empty:
        b_raw = _brier_score(oos_df["y"], oos_df["prob_raw"])
        return {"name": "identity", "details": {}, "brier_valid": b_raw}

    candidates: List[Dict[str, Any]] = []

    p_id = va["prob_raw"].copy()
    candidates.append({"name": "identity", "details": {}, "brier_valid": _brier_score(va["y"], p_id)})

    hmap = _build_calibration_map(tr["prob_raw"], tr["y"], n_bins=15)
    p_hist = _apply_calibration(va["prob_raw"], hmap)
    candidates.append(
        {
            "name": "histogram",
            "details": {"n_bins": 15},
            "brier_valid": _brier_score(va["y"], p_hist),
            "cal_map": hmap,
        }
    )

    iso = _fit_isotonic_pava(tr["prob_raw"], tr["y"])
    p_iso = _apply_isotonic(va["prob_raw"], iso)
    candidates.append(
        {
            "name": "isotonic_pava",
            "details": {},
            "brier_valid": _brier_score(va["y"], p_iso),
            "iso_map": iso,
        }
    )

    base = float(tr["y"].mean())
    for alpha in [0.25, 0.4, 0.55, 0.7, 0.85]:
        p_sh = alpha * va["prob_raw"] + (1 - alpha) * base
        candidates.append(
            {
                "name": "shrink",
                "details": {"alpha": alpha, "base_rate": base},
                "brier_valid": _brier_score(va["y"], p_sh),
            }
        )

    best = min(candidates, key=lambda x: x["brier_valid"] if x["brier_valid"] is not None else 9e9)
    best["brier_raw_valid"] = _brier_score(va["y"], va["prob_raw"])
    return best


def _apply_selected_calibration(prob: pd.Series, selected: Dict[str, Any], oos_df: pd.DataFrame) -> pd.Series:
    name = selected.get("name", "identity")
    if name == "identity":
        return prob.copy()
    if name == "histogram":
        cmap = selected.get("cal_map")
        if cmap is None or not isinstance(cmap, pd.DataFrame):
            cmap = _build_calibration_map(oos_df["prob_raw"], oos_df["y"], n_bins=15)
        return _apply_calibration(prob, cmap)
    if name == "isotonic_pava":
        iso = selected.get("iso_map")
        if iso is None or not isinstance(iso, pd.DataFrame):
            iso = _fit_isotonic_pava(oos_df["prob_raw"], oos_df["y"])
        return _apply_isotonic(prob, iso)
    if name == "shrink":
        alpha = float(selected.get("details", {}).get("alpha", 0.7))
        base = float(selected.get("details", {}).get("base_rate", oos_df["y"].mean()))
        return (alpha * prob + (1 - alpha) * base).clip(0.001, 0.999)
    return prob.copy()


def _oos_walkforward_predictions(df_all: pd.DataFrame, target_col: str, min_train_rows: int, n_bins: int) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    dates = sorted(df_all["date"].dropna().unique().tolist())
    for dt in dates:
        train = df_all[df_all["date"] < dt].copy()
        test = df_all[df_all["date"] == dt].copy()
        train = train.dropna(subset=list(FEATURE_COLS) + [target_col])
        test = test.dropna(subset=list(FEATURE_COLS) + [target_col])
        if len(train) < min_train_rows or test.empty:
            continue
        model = _fit_bin_model(train, target_col=target_col, features=FEATURE_COLS, n_bins=n_bins)
        p = _predict_bin_model(model, test, features=FEATURE_COLS)
        for idx, val in p.items():
            rows.append(
                {
                    "date": test.at[idx, "date"],
                    "industryCode": test.at[idx, "industryCode"],
                    "prob_raw": float(val),
                    "y": float(test.at[idx, target_col]),
                }
            )
    return pd.DataFrame(rows)


def _brier_score(y: pd.Series, p: pd.Series) -> float:
    x = pd.DataFrame({"y": y, "p": p}).dropna()
    if x.empty:
        return float("nan")
    return float(((x["y"] - x["p"]) ** 2).mean())


def _probability_bucket_report(oos_df: pd.DataFrame, n_bins: int = 5) -> List[Dict[str, Any]]:
    if oos_df.empty:
        return []
    x = oos_df.dropna(subset=["prob_raw", "y"]).copy()
    if x.empty:
        return []
    x["bucket"] = pd.qcut(
        x["prob_raw"],
        q=min(n_bins, max(2, x["prob_raw"].nunique())),
        duplicates="drop",
    )
    rep = (
        x.groupby("bucket", observed=True)
        .agg(
            n=("y", "size"),
            mean_pred=("prob_raw", "mean"),
            realized=("y", "mean"),
        )
        .reset_index(drop=True)
    )
    rep["lift_vs_base"] = rep["realized"] / max(float(x["y"].mean()), 1e-6)
    return rep.to_dict(orient="records")


def _confidence_from_brier(y: pd.Series, p: pd.Series) -> float:
    brier = _brier_score(y, p)
    if not np.isfinite(brier):
        return float("nan")
    # Use 0.25 as the worst-case Brier upper bound for binary probs.
    score = 1.0 - (brier / 0.25)
    return float(np.clip(score, 0.0, 1.0))


def _prepare_dataset(
    master_df: pd.DataFrame,
    master_all_df: pd.DataFrame,
    histories: Dict[str, pd.DataFrame],
    vnindex_df: pd.DataFrame,
) -> pd.DataFrame:
    level1_name_map = {
        str(r["industryCode"]): str(r.get("name", ""))
        for _, r in master_all_df[master_all_df["level"] == 1].iterrows()
    }
    parts: List[pd.DataFrame] = []
    for _, row in master_df.iterrows():
        code = str(row["industryCode"])
        hist = histories.get(code)
        if hist is None or hist.empty:
            continue
        feat = _feature_engineering(hist, vnindex=vnindex_df)
        feat["industryCode"] = code
        feat["industryName"] = row.get("name")
        feat["industryLevel"] = row.get("level")
        feat["parentLevel1Code"] = _infer_level1_parent(code)
        feat["parentLevel1Name"] = feat["parentLevel1Code"].map(level1_name_map)
        parts.append(feat)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["date", "industryCode"]).reset_index(drop=True)


def run(args: argparse.Namespace) -> Dict[str, Any]:
    client = get_client(timeout=args.timeout)
    raw_master = client._get(f"{RESTV2_BASE}/industries", params=None)  # type: ignore[attr-defined]
    raw_master_list = raw_master if isinstance(raw_master, list) else []
    master_all_df = pd.DataFrame(raw_master_list)
    if master_all_df.empty:
        return {"errors": ["industries_master_empty"], "warnings": [], "ranking": []}
    master_all_df["industryCode"] = master_all_df["industryCode"].astype(str)
    master_all_df["level"] = pd.to_numeric(master_all_df["level"], errors="coerce")

    master_df = _parse_industry_master(raw_master_list, level=args.level)
    if args.focus_parent_level1:
        parent_code = str(args.focus_parent_level1).zfill(4)
        master_df = master_df[
            master_df["industryCode"].astype(str).map(_infer_level1_parent) == parent_code
        ].copy()

    histories: Dict[str, pd.DataFrame] = {}
    warnings: List[str] = []
    for code in master_df["industryCode"].astype(str).tolist():
        try:
            histories[code] = _fetch_industry_history(client, code=code, start=args.start, end=args.end)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"industry_fetch_failed:{code}:{exc}")
            histories[code] = pd.DataFrame()

    vnindex_df = _fetch_vnindex(client, start=args.start, end=args.end)
    if vnindex_df.empty:
        warnings.append("vnindex_history_empty")

    dataset = _prepare_dataset(
        master_df,
        master_all_df=master_all_df,
        histories=histories,
        vnindex_df=vnindex_df,
    )
    if dataset.empty:
        return {
            "errors": ["no_data_after_feature_engineering"],
            "warnings": warnings,
            "ranking": [],
        }

    clean_train = dataset.dropna(subset=list(FEATURE_COLS) + ["label_wave_10d", "label_wave_20d"]).copy()
    if clean_train.empty:
        return {
            "errors": ["no_valid_training_rows"],
            "warnings": warnings,
            "ranking": [],
        }

    oos10 = _oos_walkforward_predictions(
        clean_train,
        target_col="label_wave_10d",
        min_train_rows=args.min_train_rows,
        n_bins=args.n_bins,
    )
    oos20 = _oos_walkforward_predictions(
        clean_train,
        target_col="label_wave_20d",
        min_train_rows=args.min_train_rows,
        n_bins=args.n_bins,
    )

    model10 = _fit_bin_model(clean_train, target_col="label_wave_10d", features=FEATURE_COLS, n_bins=args.n_bins)
    model20 = _fit_bin_model(clean_train, target_col="label_wave_20d", features=FEATURE_COLS, n_bins=args.n_bins)

    latest_date = dataset["date"].max()
    latest = dataset[dataset["date"] == latest_date].copy()
    latest = latest.dropna(subset=list(FEATURE_COLS))
    latest["p_wave_10d_raw"] = _predict_bin_model(model10, latest, features=FEATURE_COLS)
    latest["p_wave_20d_raw"] = _predict_bin_model(model20, latest, features=FEATURE_COLS)

    selected10 = _optimize_calibration(oos10)
    selected20 = _optimize_calibration(oos20)
    latest["p_wave_10d"] = _apply_selected_calibration(latest["p_wave_10d_raw"], selected10, oos10)
    latest["p_wave_20d"] = _apply_selected_calibration(latest["p_wave_20d_raw"], selected20, oos20)
    oos10["prob_cal"] = _apply_selected_calibration(oos10["prob_raw"], selected10, oos10)
    oos20["prob_cal"] = _apply_selected_calibration(oos20["prob_raw"], selected20, oos20)

    latest["expected_return_10d"] = latest["p_wave_10d"] * 0.05
    latest["expected_return_20d"] = latest["p_wave_20d"] * 0.08
    mdd_hist = clean_train["fwd_mdd_20"].dropna()
    upside_dd = float(mdd_hist.median()) if not mdd_hist.empty else -0.04
    downside_dd = float(mdd_hist.quantile(0.25)) if not mdd_hist.empty else -0.08
    latest["expected_drawdown_20d"] = (
        latest["p_wave_20d"] * upside_dd + (1 - latest["p_wave_20d"]) * downside_dd
    )

    confidence_10d = _confidence_from_brier(oos10.get("y", pd.Series(dtype=float)), oos10.get("prob_cal", pd.Series(dtype=float)))
    confidence_20d = _confidence_from_brier(oos20.get("y", pd.Series(dtype=float)), oos20.get("prob_cal", pd.Series(dtype=float)))
    latest["confidence_10d"] = confidence_10d
    latest["confidence_20d"] = confidence_20d

    latest = latest.sort_values(["p_wave_20d", "p_wave_10d"], ascending=False).reset_index(drop=True)

    out_cols = [
        "date",
        "industryCode",
        "industryName",
        "industryLevel",
        "parentLevel1Code",
        "parentLevel1Name",
        *PROBABILITY_COLS,
        "expected_return_10d",
        "expected_return_20d",
        "expected_drawdown_20d",
        "confidence_10d",
        "confidence_20d",
        "rs_20d",
        "rs_60d",
        "dist_days_10",
        "dist_days_20",
        "volume_thrust_20",
        "close_vs_ma20",
        "close_vs_ma50",
        "dist_to_20d_high",
    ]
    for c in out_cols:
        if c not in latest.columns:
            latest[c] = np.nan

    report = latest[out_cols].copy()
    report["date"] = pd.to_datetime(report["date"]).dt.strftime("%Y-%m-%d")
    report_path_csv = Path(args.out_csv)
    report_path_csv.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(report_path_csv, index=False)

    meta = {
        "source": "FireAnt",
        "method": "REST API",
        "endpoints": [
            "/industries",
            "/industries/{industryCode}/historical-stats",
            "/symbols/VNINDEX/historical-quotes",
        ],
        "date_range": {"start": args.start, "end": args.end, "asof": str(report["date"].iloc[0]) if not report.empty else None},
        "industry_level": args.level,
        "focus_parent_level1": str(args.focus_parent_level1).zfill(4) if args.focus_parent_level1 else None,
        "symbols_or_logical_names": {
            "benchmark": "VNINDEX",
            "industry_codes": master_df["industryCode"].astype(str).tolist(),
        },
        "proxy_usage": {
            "benchmark": "native",
            "industries": "native /industries historical-stats",
        },
        "model": {
            "type": "walk-forward naive-bayes bin model + calibration-selection loop",
            "n_features": len(FEATURE_COLS),
            "n_bins": args.n_bins,
            "min_train_rows": args.min_train_rows,
            "oos_rows_10d": int(len(oos10)),
            "oos_rows_20d": int(len(oos20)),
            "oos_brier_raw_10d": _brier_score(oos10.get("y", pd.Series(dtype=float)), oos10.get("prob_raw", pd.Series(dtype=float))),
            "oos_brier_raw_20d": _brier_score(oos20.get("y", pd.Series(dtype=float)), oos20.get("prob_raw", pd.Series(dtype=float))),
            "oos_brier_cal_10d": _brier_score(oos10.get("y", pd.Series(dtype=float)), oos10.get("prob_cal", pd.Series(dtype=float))),
            "oos_brier_cal_20d": _brier_score(oos20.get("y", pd.Series(dtype=float)), oos20.get("prob_cal", pd.Series(dtype=float))),
            "selected_calibrator_10d": {
                "name": selected10.get("name"),
                "details": selected10.get("details", {}),
                "brier_valid": selected10.get("brier_valid"),
                "brier_raw_valid": selected10.get("brier_raw_valid"),
            },
            "selected_calibrator_20d": {
                "name": selected20.get("name"),
                "details": selected20.get("details", {}),
                "brier_valid": selected20.get("brier_valid"),
                "brier_raw_valid": selected20.get("brier_raw_valid"),
            },
            "oos_mean_pred_10d": float(oos10["prob_cal"].mean()) if not oos10.empty else None,
            "oos_mean_pred_20d": float(oos20["prob_cal"].mean()) if not oos20.empty else None,
            "oos_realized_rate_10d": float(oos10["y"].mean()) if not oos10.empty else None,
            "oos_realized_rate_20d": float(oos20["y"].mean()) if not oos20.empty else None,
            "confidence_10d": confidence_10d,
            "confidence_20d": confidence_20d,
            "oos_bucket_report_10d": _probability_bucket_report(
                pd.DataFrame({"prob_raw": oos10.get("prob_cal"), "y": oos10.get("y")}),
                n_bins=5,
            ),
            "oos_bucket_report_20d": _probability_bucket_report(
                pd.DataFrame({"prob_raw": oos20.get("prob_cal"), "y": oos20.get("y")}),
                n_bins=5,
            ),
        },
        "integrity_flags": {
            "missing_bars": bool(dataset.groupby("industryCode")["date"].diff().dropna().gt(pd.Timedelta(days=7)).any()),
            "high_zero_volume": bool((dataset["volume"] == 0).mean() > 0.10),
            "warnings": warnings,
            "errors": [],
        },
        "limitations": [
            "No constituent-level breadth feature in v1 (industry index only).",
            "Expected drawdown is model-based estimate, not guaranteed forward realization.",
            "Probabilities are conditional on historical FireAnt coverage and regime mix.",
        ],
        "outputs": {
            "ranking_csv": str(report_path_csv),
        },
    }

    json_path = Path(args.out_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {
                "meta": meta,
                "ranking": report.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return {"meta": meta, "ranking_len": len(report), "csv": str(report_path_csv), "json": str(json_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute industry wave probabilities from FireAnt industry history.",
    )
    parser.add_argument("--start", default="2016-01-01", help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", default=date.today().isoformat(), help="End date YYYY-MM-DD.")
    parser.add_argument("--level", type=int, default=1, help="Industry level from /industries.")
    parser.add_argument(
        "--focus-parent-level1",
        default=None,
        help="Optional level-1 parent code filter (e.g. 8000 for Finance).",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout seconds.")
    parser.add_argument("--min-train-rows", type=int, default=600, help="Minimum rows before walk-forward prediction.")
    parser.add_argument("--n-bins", type=int, default=5, help="Quantile bins per feature.")
    parser.add_argument(
        "--out-csv",
        default=str(_REPO / "data" / "research" / "industry_wave_probability_latest.csv"),
        help="Output CSV ranking path.",
    )
    parser.add_argument(
        "--out-json",
        default=str(_REPO / "data" / "research" / "industry_wave_probability_latest.json"),
        help="Output JSON report path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
