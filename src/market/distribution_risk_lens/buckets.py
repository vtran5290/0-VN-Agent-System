"""Bucket probability tables with base rates and lift."""

from __future__ import annotations



import numpy as np

import pandas as pd



HORIZONS = (5, 10, 25, 75, 100)

DD_THRESHOLDS_PCT = (3, 5, 10, 15)





def confidence_label(n: int) -> str:

    if n < 30:

        return "LOW"

    if n < 100:

        return "MEDIUM"

    return "HIGH"





def _bucket_dist_10(v: float) -> str:

    if v <= 0:

        return "0"

    if v == 1:

        return "1"

    if v == 2:

        return "2"

    return ">=3"





def _bucket_dist_25(v: float) -> str:

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





def _bucket_dist_50(v: float) -> str:

    if v <= 2:

        return "0-2"

    if v <= 5:

        return "3-5"

    if v <= 8:

        return "6-8"

    return ">=9"





def _dd_probs(mdd: pd.Series) -> dict[str, float]:

    out: dict[str, float] = {}

    if mdd.empty:

        for pct in DD_THRESHOLDS_PCT:

            out[f"p_max_dd_le_neg{pct}pct"] = np.nan

        return out

    for pct in DD_THRESHOLDS_PCT:

        out[f"p_max_dd_le_neg{pct}pct"] = float((mdd <= -(pct / 100.0)).mean())

    return out





def build_probability_table(df: pd.DataFrame, *, index_view: str) -> pd.DataFrame:

    rows = []

    specs = [

        ("dist_count_10d", _bucket_dist_10),

        ("dist_count_25d", _bucket_dist_25),

        ("dist_count_50d", _bucket_dist_50),

    ]

    for metric, bucketer in specs:

        sub = df.copy()

        sub["bucket"] = sub[metric].apply(bucketer)

        for h in HORIZONS:

            ret_col = f"fwd_ret_{h}d"

            dd_col = f"max_dd_{h}d"

            if ret_col not in sub.columns:

                continue

            base = sub[ret_col].dropna()

            base_neg = float((base < 0).mean()) if len(base) else np.nan

            base_mdd = sub[dd_col].dropna() if dd_col in sub.columns else pd.Series(dtype=float)

            base_dd = _dd_probs(base_mdd)

            for bucket, grp in sub.groupby("bucket", sort=False):

                if bucket == "unknown":

                    continue

                r = grp[ret_col].dropna()

                n = len(r)

                if n == 0:

                    continue

                p_neg = float((r < 0).mean())

                mdd = grp[dd_col].dropna() if dd_col in grp.columns else pd.Series(dtype=float)

                dd_row = _dd_probs(mdd)

                rec = {

                    "index_view": index_view,

                    "metric": metric,

                    "bucket": bucket,

                    "horizon_d": h,

                    "n": n,

                    "median_fwd_ret": float(r.median()),

                    "mean_fwd_ret": float(r.mean()),

                    "p10_fwd_ret": float(r.quantile(0.10)),

                    "p25_fwd_ret": float(r.quantile(0.25)),

                    "p75_fwd_ret": float(r.quantile(0.75)),

                    "p_ret_neg": p_neg,

                    "base_rate_p_ret_neg": base_neg,

                    "lift_p_ret_neg": p_neg - base_neg if pd.notna(base_neg) else np.nan,

                    "confidence": confidence_label(n),

                }

                rec.update(dd_row)

                for pct in DD_THRESHOLDS_PCT:

                    key = f"base_rate_p_max_dd_le_neg{pct}pct"

                    rec[key] = base_dd.get(f"p_max_dd_le_neg{pct}pct", np.nan)

                rows.append(rec)

    return pd.DataFrame(rows)

