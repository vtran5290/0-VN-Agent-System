"""Orchestrate Distribution Risk Lens research outputs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.buckets import build_probability_table
from src.market.distribution_risk_lens.events import run_event_study
from src.market.distribution_risk_lens.features import build_features
from src.market.distribution_risk_lens.index_views import load_index_views
from src.market.distribution_risk_lens.outcomes import attach_forward_outcomes
from src.market.distribution_risk_lens.warnings import (
    snapshot_probabilities,
    vin_distortion_flag,
    warning_disagreement,
    warning_state_row,
)

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "data" / "research" / "market_risk"
METHOD_VERSION = "distribution_risk_lens_v1.2"


def _json_safe(obj: Any) -> Any:
    """Convert numpy scalars to native Python types for json.dumps."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def _ret_n(close: pd.Series, n: int) -> Optional[float]:
    if len(close) <= n:
        return None
    a = float(close.iloc[-1])
    b = float(close.iloc[-1 - n])
    if b == 0 or np.isnan(a) or np.isnan(b):
        return None
    return a / b - 1.0


def _align_closes_by_date(raw_df: pd.DataFrame, ex_df: pd.DataFrame) -> pd.DataFrame:
    """Align VNINDEX raw and ex-VIN close on calendar date (not RangeIndex)."""
    raw = raw_df.set_index(pd.to_datetime(raw_df["date"]))["close"].astype(float)
    ex = ex_df.set_index(pd.to_datetime(ex_df["date"]))["close"].astype(float)
    return pd.DataFrame({"raw": raw, "ex": ex}).dropna().sort_index()


def _return_spread(joined: pd.DataFrame, n: int) -> Optional[float]:
    raw_r = _ret_n(joined["raw"], n)
    ex_r = _ret_n(joined["ex"], n)
    if raw_r is None or ex_r is None:
        return None
    return raw_r - ex_r


def run_distribution_risk_lens(
    *,
    start: str = "2012-01-01",
    as_of: str | None = None,
    offline: bool = True,
) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    views, view_meta, load_warnings = load_index_views(start=start)
    if not views:
        raise RuntimeError("No index views loaded")

    feature_frames = []
    full_frames = []
    for vid, ohlcv in views.items():
        meta_v = view_meta.get(vid)
        dist_vol_ok = meta_v.distribution_volume_available if meta_v else True
        feat = build_features(
            ohlcv,
            index_view=vid,
            variant="base",
            distribution_volume_available=dist_vol_ok,
        )
        full = attach_forward_outcomes(feat)
        feature_frames.append(feat)
        full_frames.append(full)

    features_all = pd.concat(feature_frames, ignore_index=True)
    forward_all = pd.concat(full_frames, ignore_index=True)

    prob_parts = []
    event_parts = []
    warning_bt = []
    yearly = []
    for vid, full in zip(views.keys(), full_frames, strict=True):
        prob_parts.append(build_probability_table(full, index_view=vid))
        event_parts.append(run_event_study(full, index_view=vid, skip_days=25))
        full["warning_state"] = full.apply(warning_state_row, axis=1)
        warning_bt.append(full[["date", "index_view", "warning_state", "dist_count_25d"]].copy())
        full["year"] = pd.to_datetime(full["date"]).dt.year
        for yr, grp in full.groupby("year"):
            risky = grp["warning_state"].isin(
                ["CORRECTION_RISK", "DOWNTREND_WARNING", "DISTRIBUTION_CLUSTER"]
            ).mean()
            r25 = grp["fwd_ret_25d"].dropna()
            yearly.append(
                {
                    "year": int(yr),
                    "index_view": vid,
                    "warning_days_pct": float(risky),
                    "p_ret_neg_25d": float((r25 < 0).mean()) if len(r25) else np.nan,
                    "median_fwd_ret_25d": float(r25.median()) if len(r25) else np.nan,
                    "n": len(grp),
                }
            )

    prob_table = pd.concat(prob_parts, ignore_index=True)
    events = pd.concat(event_parts, ignore_index=True)
    warning_backtest = pd.concat(warning_bt, ignore_index=True)
    yearly_df = pd.DataFrame(yearly)

    features_all.to_csv(OUT_DIR / "distribution_days_features.csv", index=False)
    forward_all.to_csv(OUT_DIR / "distribution_days_forward_returns.csv", index=False)
    prob_table.to_csv(OUT_DIR / "distribution_days_probability_table.csv", index=False)
    events.to_csv(OUT_DIR / "distribution_days_event_study.csv", index=False)
    warning_backtest.to_csv(OUT_DIR / "distribution_days_warning_backtest.csv", index=False)
    yearly_df.to_csv(OUT_DIR / "distribution_days_yearly_validation.csv", index=False)

    as_of_ts = pd.Timestamp(as_of) if as_of else pd.Timestamp(views["vnindex_raw"]["date"].max())
    latest = _build_latest_json(
        views=views,
        view_meta=view_meta,
        prob_table=prob_table,
        as_of=as_of_ts,
        load_warnings=load_warnings,
    )
    (OUT_DIR / "distribution_risk_latest.json").write_text(
        json.dumps(_json_safe(latest), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    from src.trading.reports.distribution_risk_card import write_distribution_risk_latest_artifacts

    artifacts = write_distribution_risk_latest_artifacts(latest)
    return {
        "outputs_dir": str(OUT_DIR),
        "latest_json": latest,
        "n_features": len(features_all),
        "warnings": load_warnings,
        "artifacts": artifacts,
    }


def _view_last_data_date(ohlcv: pd.DataFrame) -> Optional[str]:
    if ohlcv is None or ohlcv.empty or "date" not in ohlcv.columns:
        return None
    return pd.Timestamp(ohlcv["date"].max()).strftime("%Y-%m-%d")


def _build_latest_json(
    *,
    views: dict[str, pd.DataFrame],
    view_meta: dict,
    prob_table: pd.DataFrame,
    as_of: pd.Timestamp,
    load_warnings: list[str],
) -> dict[str, Any]:
    primary = "ex_vin_proxy" if "ex_vin_proxy" in views else "vnindex_raw"
    available = list(views.keys())
    requested_as_of = as_of.strftime("%Y-%m-%d")
    payload: dict[str, Any] = {
        "as_of_date": requested_as_of,
        "requested_as_of_date": requested_as_of,
        "data_start": "2012-01-01",
        "data_end": requested_as_of,
        "method_version": METHOD_VERSION,
        "index_views_available": available,
        "primary_view": primary,
        "load_warnings": list(load_warnings),
        "safety_note": "Distribution Risk Lens is market context only and does not change final_action.",
    }

    view_snapshots = {}
    ex_vin_method_note = (
        "ex-VIN proxy drawdown/correction probabilities are close-based; "
        "high/low are synthetic from close when native OHLC is unavailable."
    )
    for vid, ohlcv in views.items():
        meta = view_meta.get(vid)
        dist_vol_ok = meta.distribution_volume_available if meta else True
        feat = attach_forward_outcomes(
            build_features(
                ohlcv,
                index_view=vid,
                distribution_volume_available=dist_vol_ok,
            )
        )
        row = feat[feat["date"] <= as_of].iloc[-1] if not feat.empty else None
        if row is None:
            continue
        d10 = row["dist_count_10d"]
        d25 = row["dist_count_25d"]
        d50 = row["dist_count_50d"]
        dist_unavail = not dist_vol_ok or pd.isna(d25)
        b25 = _bucket_label_25(float(d25)) if not dist_unavail else "unknown"
        probs = snapshot_probabilities(prob_table, index_view=vid, bucket=b25) if not dist_unavail else {}
        snap: dict[str, Any] = {
            "dist_count_10d": None if dist_unavail else int(d10),
            "dist_count_25d": None if dist_unavail else int(d25),
            "dist_count_50d": None if dist_unavail else int(d50),
            "warning_state": warning_state_row(row),
            "probabilities": probs,
            "base_rates": probs.get("base_rates", {}),
            "lift_vs_base": probs.get("lift_vs_base", {}),
            "sample_size": probs.get("sample_size", 0),
            "confidence": probs.get("confidence", "LOW"),
            "is_proxy": meta.is_proxy if meta else False,
            "label": meta.label if meta else vid,
            "distribution_volume_available": bool(dist_vol_ok),
        }
        if meta and meta.notes:
            snap["note"] = meta.notes
        if meta and meta.ohlc_synthetic_from_close:
            snap["methodology_note"] = ex_vin_method_note
        last_date = _view_last_data_date(ohlcv)
        snap["last_data_date"] = last_date
        snap["requested_as_of_date"] = requested_as_of
        snap["is_stale_for_as_of"] = bool(
            last_date is not None and last_date < requested_as_of
        )
        view_snapshots[vid] = snap

    freshness_rows = []
    for vid in ("vnindex_raw", "ex_vin_proxy", "vin_group"):
        snap = view_snapshots.get(vid, {})
        freshness_rows.append(
            {
                "index_view": vid,
                "last_data_date": snap.get("last_data_date"),
                "requested_as_of_date": requested_as_of,
                "is_stale_for_as_of": snap.get("is_stale_for_as_of", False),
            }
        )
    payload["view_freshness"] = freshness_rows
    primary_snap = view_snapshots.get(primary, {})
    if primary_snap.get("is_stale_for_as_of"):
        payload["load_warnings"].append(
            f"PRIMARY_VIEW_STALE: {primary} last_data_date={primary_snap.get('last_data_date')} "
            f"< requested_as_of_date={requested_as_of}"
        )
        payload["report_status"] = "NEEDS_REVIEW"
    else:
        payload["report_status"] = "OK"

    payload["vnindex_raw"] = view_snapshots.get("vnindex_raw", {})
    payload["ex_vin_proxy"] = view_snapshots.get("ex_vin_proxy", {})
    vin = view_snapshots.get("vin_group", {})
    raw_df = views.get("vnindex_raw")
    ex_df = views.get("ex_vin_proxy")
    joined = (
        _align_closes_by_date(raw_df, ex_df)
        if raw_df is not None and ex_df is not None
        else pd.DataFrame()
    )
    distortion = False
    if not joined.empty:
        distortion = vin_distortion_flag(
            _ret_n(joined["raw"], 10),
            _ret_n(joined["ex"], 10),
            _ret_n(joined["raw"], 25),
            _ret_n(joined["ex"], 25),
        )
    vin_last = _view_last_data_date(views.get("vin_group", pd.DataFrame()))
    payload["vin_group"] = {
        "available": "vin_group" in views,
        "distortion_flag": bool(distortion),
        "note": "VIC,VHM,VRE equal-weight basket; VPL excluded if <252 bars",
        "last_data_date": vin_last,
        "requested_as_of_date": requested_as_of,
        "is_stale_for_as_of": bool(vin_last is not None and vin_last < requested_as_of),
        **vin,
    }
    for row in freshness_rows:
        if row["index_view"] == "vin_group":
            row["last_data_date"] = vin_last
            row["is_stale_for_as_of"] = payload["vin_group"]["is_stale_for_as_of"]
    raw_ws = view_snapshots.get("vnindex_raw", {}).get("warning_state", "UNKNOWN")
    ex_ws = view_snapshots.get("ex_vin_proxy", {}).get("warning_state", "UNKNOWN")
    spread_10 = _return_spread(joined, 10) if not joined.empty else None
    spread_25 = _return_spread(joined, 25) if not joined.empty else None
    payload["comparison"] = {
        "raw_vs_ex_vin_warning_disagreement": warning_disagreement(raw_ws, ex_ws),
        "raw_vs_ex_vin_return_spread_10d": spread_10,
        "raw_vs_ex_vin_return_spread_25d": spread_25,
        "interpretation": (
            "VNINDEX raw may be VIN-skewed when distortion_flag is true; prefer ex_vin_proxy for broad market context."
            if distortion
            else "Raw and ex-VIN proxy broadly aligned on distribution warning."
        ),
    }
    if distortion and raw_ws != ex_ws:
        payload["comparison"]["vin_distortion_warning"] = True
    return payload


def _bucket_label_25(v: float) -> str:
    if pd.isna(v):
        return "unknown"
    if v <= 0:
        return "0"
    if v == 1:
        return "1"
    if v == 2:
        return "2"
    if v == 3:
        return "3"
    if v == 4:
        return "4"
    return ">=5"
