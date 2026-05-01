#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _metrics(picks: pd.DataFrame) -> dict[str, float]:
    if picks.empty:
        return {"n": 0, "hit_rate": np.nan, "avg_ret20": np.nan, "avg_mdd20": np.nan}
    return {
        "n": float(len(picks)),
        "hit_rate": float(picks["label_wave20"].mean()),
        "avg_ret20": float(picks["fwd_ret20"].mean()),
        "avg_mdd20": float(picks["fwd_mdd20"].mean()),
    }


def _fit_monthly_calibration(train: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    z = train.dropna(subset=["p20", "label_wave20"]).copy()
    if z.empty:
        return pd.DataFrame(columns=["p", "p_cal"])
    z["bucket"] = pd.qcut(z["p20"], q=min(n_bins, max(2, z["p20"].nunique())), duplicates="drop")
    m = z.groupby("bucket", observed=True).agg(p=("p20", "mean"), p_cal=("label_wave20", "mean")).reset_index(drop=True)
    return m


def _apply_interp(x: pd.Series, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
    if len(xp) == 0:
        return np.full(len(x), np.nan)
    if len(xp) == 1:
        return np.full(len(x), float(fp[0]))
    xx = x.astype(float).clip(float(np.min(xp)), float(np.max(xp))).values
    return np.interp(xx, xp, fp)


def _ridge_fit_predict(
    tr: pd.DataFrame,
    te: pd.DataFrame,
    feats: list[str],
    target: str,
    l2: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    xtr = tr[feats].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    ytr = tr[target].astype(float).to_numpy()
    xte = te[feats].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    mu = xtr.mean(axis=0)
    sd = xtr.std(axis=0)
    sd = np.where(sd > 1e-9, sd, 1.0)
    xtrn = (xtr - mu) / sd
    xten = (xte - mu) / sd
    x1 = np.column_stack([np.ones(len(xtrn)), xtrn])
    x2 = np.column_stack([np.ones(len(xten)), xten])
    eye = np.eye(x1.shape[1])
    eye[0, 0] = 0.0
    beta = np.linalg.pinv(x1.T @ x1 + l2 * eye) @ (x1.T @ ytr)
    return x1 @ beta, x2 @ beta


def _neutralize_by_date(df: pd.DataFrame, y_col: str) -> pd.Series:
    out = pd.Series(index=df.index, dtype=float)
    for dt, g in df.groupby("date"):
        gg = g.copy()
        y = gg[y_col].astype(float).to_numpy()
        beta = gg["beta_proxy"].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
        dummies = pd.get_dummies(gg["industryCode"].astype(str), prefix="ind", drop_first=True)
        X = np.column_stack([np.ones(len(gg)), beta, dummies.to_numpy(dtype=float)])
        b = np.linalg.pinv(X.T @ X) @ (X.T @ y)
        yhat = X @ b
        resid = y - yhat
        out.loc[gg.index] = resid
    return out


def _build_beta_proxy(panel: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    x = panel.sort_values(["symbol", "date"]).copy()
    mkt = x.groupby("date")["p20"].median().rename("mkt_p20")
    x = x.merge(mkt, on="date", how="left")

    def _roll_beta(g: pd.DataFrame) -> pd.Series:
        a = g["p20"].astype(float)
        b = g["mkt_p20"].astype(float)
        cov = a.rolling(window, min_periods=20).cov(b)
        var = b.rolling(window, min_periods=20).var()
        beta = cov / var.replace(0, np.nan)
        return beta.replace([np.inf, -np.inf], np.nan)

    x["beta_proxy"] = x.groupby("symbol", group_keys=False).apply(_roll_beta).reset_index(level=0, drop=True)
    x["beta_proxy"] = x["beta_proxy"].fillna(1.0)
    return x


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--end", default="2026-04-30")
    p.add_argument("--train-months", type=int, default=6)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--ridge-l2", type=float, default=1.0)
    p.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = p.parse_args()

    panel = pd.read_csv(args.panel_csv)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel = panel.dropna(subset=["date", "symbol", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    panel = panel[(panel["date"] >= pd.Timestamp(args.start)) & (panel["date"] <= pd.Timestamp(args.end))].copy()
    panel["symbol"] = panel["symbol"].astype(str).str.upper()
    panel["industryCode"] = panel["industryCode"].astype(str)
    panel = _build_beta_proxy(panel, window=60)

    feats = [
        "p20",
        "p_now",
        "p_hist",
        "sum_p20",
        "recent_accel",
        "value_weighted_p20",
        "overcrowded_count",
        "z_sum_p20",
        "z_recent_accel",
        "z_value_weighted_p20",
        "z_overcrowded",
        "beta_proxy",
    ]
    feats = [f for f in feats if f in panel.columns]
    months = sorted(panel["date"].dt.to_period("M").unique().tolist())

    wf_rows: list[dict[str, Any]] = []
    for i in range(args.train_months, len(months)):
        tr_m = set(months[i - args.train_months : i])
        te_m = months[i]
        tr = panel[panel["date"].dt.to_period("M").isin(tr_m)].copy()
        te = panel[panel["date"].dt.to_period("M") == te_m].copy()
        if tr.empty or te.empty:
            continue

        # Monthly probability calibration
        cal = _fit_monthly_calibration(tr, n_bins=10)
        xp = cal["p"].to_numpy(dtype=float) if not cal.empty else np.array([])
        fp = cal["p_cal"].to_numpy(dtype=float) if not cal.empty else np.array([])
        tr["p20_cal"] = _apply_interp(tr["p20"], xp, fp) if len(xp) else tr["p20"].values
        te["p20_cal"] = _apply_interp(te["p20"], xp, fp) if len(xp) else te["p20"].values

        # Cross-sectional return model
        _, pred_te = _ridge_fit_predict(tr, te, feats, "fwd_ret20", l2=args.ridge_l2)
        te["pred_ret20_raw"] = pred_te
        te["pred_ret20_neut"] = _neutralize_by_date(te, "pred_ret20_raw")

        # EV with calibrated p20 and neutralized return forecast
        te["score_v23"] = te["p20_cal"].fillna(te["p20"]) * te["pred_ret20_neut"]

        te_v23 = te.sort_values(["date", "score_v23"], ascending=[True, False]).groupby("date", as_index=False).head(args.top_n)
        te_base = te.sort_values(["date", "p20"], ascending=[True, False]).groupby("date", as_index=False).head(args.top_n)
        mv = _metrics(te_v23)
        mb = _metrics(te_base)
        wf_rows.append(
            {
                "test_month": str(te_m),
                "base_n": int(mb["n"]),
                "base_hit_rate": mb["hit_rate"],
                "base_avg_ret20": mb["avg_ret20"],
                "v23_n": int(mv["n"]),
                "v23_hit_rate": mv["hit_rate"],
                "v23_avg_ret20": mv["avg_ret20"],
            }
        )

    wf = pd.DataFrame(wf_rows)
    if wf.empty:
        raise RuntimeError("No walk-forward rows for v2.3.")

    base_ok = wf[(wf["base_n"] > 0) & wf["base_hit_rate"].notna() & wf["base_avg_ret20"].notna()]
    v_ok = wf[(wf["v23_n"] > 0) & wf["v23_hit_rate"].notna() & wf["v23_avg_ret20"].notna()]
    overall = {
        "base": {
            "n": int(wf["base_n"].sum()),
            "months_with_picks": int((wf["base_n"] > 0).sum()),
            "hit_rate_weighted": float(np.average(base_ok["base_hit_rate"], weights=base_ok["base_n"])) if not base_ok.empty else np.nan,
            "avg_ret20_weighted": float(np.average(base_ok["base_avg_ret20"], weights=base_ok["base_n"])) if not base_ok.empty else np.nan,
        },
        "v23": {
            "n": int(wf["v23_n"].sum()),
            "months_with_picks": int((wf["v23_n"] > 0).sum()),
            "hit_rate_weighted": float(np.average(v_ok["v23_hit_rate"], weights=v_ok["v23_n"])) if not v_ok.empty else np.nan,
            "avg_ret20_weighted": float(np.average(v_ok["v23_avg_ret20"], weights=v_ok["v23_n"])) if not v_ok.empty else np.nan,
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "super_alpha_v23_monthly_compare_from_2023.csv"
    wf.to_csv(out_csv, index=False)
    out = {
        "source": "FireAnt",
        "method": "REST API",
        "date_range": {"start": args.start, "end": args.end},
        "values_native_or_proxy": "native stock OHLCV; beta_proxy is derived from panel p20 vs market-median p20",
        "v23_design": {
            "return_model": "cross-sectional ridge regression (re-fitted walk-forward each month)",
            "neutralization": "daily residualization by industry dummies + beta_proxy",
            "ranking": "EV = calibrated_p20 * neutralized_pred_ret20",
            "calibration": "monthly p20 bucket calibration",
        },
        "overall_compare": overall,
        "monthly_compare_csv": str(out_csv),
        "limitations": [
            "beta is proxy-derived from p20 co-movement, not native return beta",
            "linear ridge may miss nonlinear effects",
        ],
    }
    (out_dir / "super_alpha_v23_retest_from_2023.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

