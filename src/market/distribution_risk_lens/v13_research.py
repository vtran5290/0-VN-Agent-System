"""Distribution Risk Lens v1.3 — join, buckets, walk-forward, probability surface."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.buckets import confidence_label
from src.market.distribution_risk_lens.breadth_features import build_breadth_features
from src.market.distribution_risk_lens.features import build_features
from src.market.distribution_risk_lens.index_views import load_index_views
from src.market.distribution_risk_lens.largecap_divergence import build_largecap_divergence
from src.market.distribution_risk_lens.liquid_universe import ADV50_THRESHOLD_VND, audit_panel
from src.market.distribution_risk_lens.ma_participation import build_ma_participation
from src.market.distribution_risk_lens.new_high_low import build_new_high_low_features
from src.market.distribution_risk_lens.outcomes import attach_forward_outcomes
from src.market.distribution_risk_lens.prior_rally import build_prior_rally_context
from src.market.distribution_risk_lens.value_weighted_breadth import build_value_weighted_breadth
from src.market.distribution_risk_lens.warnings import warning_state_row

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "data" / "research" / "market_risk"
PRIMARY_VIEW = "ex_vin_proxy"
V13_VERSION = "distribution_risk_lens_v1.3_research"

TARGET_SPECS = [
    ("max_dd_25d", "<=", -0.05, "hit_max_dd_neg5pct_25d"),
    ("max_dd_25d", "<=", -0.03, "hit_max_dd_neg3pct_25d"),
    ("max_dd_25d", "<=", -0.08, "hit_max_dd_neg8pct_25d"),
    ("max_dd_25d", "<=", -0.10, "hit_max_dd_neg10pct_25d"),
    ("max_dd_75d", "<=", -0.10, "hit_max_dd_neg10pct_75d"),
    ("fwd_ret_25d", "<", 0, "end_ret_neg_25d"),
    ("fwd_ret_25d", "<=", -0.05, "end_ret_le_neg5pct_25d"),
]


def write_stage0_audit(path: Path) -> PanelAuditRef:
    audit = audit_panel()
    lines = [
        "# Distribution Risk v1.3 — Stage 0 Data Audit",
        "",
        "## Source files",
        f"- OHLCV panel: `{audit.source_path}`",
        "- Index views: `minervini_backtest/data/raw/VNINDEX.csv`, `data/research/vnindex_ex_vin_daily_series.csv`",
        "",
        "## Columns available (panel)",
        ", ".join(f"`{c}`" for c in audit.columns if c in ("symbol", "ticker", "date", "open", "high", "low", "close", "volume", "value")),
        "",
        "## Date range",
        f"- Panel: **{audit.date_min}** → **{audit.date_max}**",
        "- Distribution index features from 2012 where CSV available; breadth joins from panel start",
        "",
        "## Latest liquid universe",
        f"- ADV50 threshold: **{ADV50_THRESHOLD_VND:,.0f} VND**",
        f"- Latest liquid count (as of panel max date): **{audit.latest_liquid_n}**",
        "",
        "## Panel stats",
        f"- Rows: {audit.n_rows:,}",
        f"- Tickers: {audit.n_tickers:,}",
        f"- Price unit: {audit.price_unit}",
        f"- Value traded: {audit.value_unit_note}",
        "",
        "## Assumptions",
    ]
    for a in audit.assumptions:
        lines.append(f"- {a}")
    if audit.warnings:
        lines.extend(["", "## Warnings"])
        for w in audit.warnings:
            lines.append(f"- {w}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return PanelAuditRef(audit)


class PanelAuditRef:
    def __init__(self, audit) -> None:
        self.audit = audit


def _hit_col(df: pd.DataFrame, col: str, op: str, thr: float, out: str) -> None:
    """Derive hit label; NaN driving outcome -> NaN label (not 0)."""
    s = df[col]
    valid = s.notna()
    result = pd.Series(np.nan, index=df.index, dtype=float)
    if op == "<=":
        result.loc[valid] = (s.loc[valid] <= thr).astype(float)
    elif op == "<":
        result.loc[valid] = (s.loc[valid] < thr).astype(float)
    df[out] = result


def _compute_breadth_staleness(
    dataset: pd.DataFrame,
    *,
    index_as_of: Optional[str] = None,
) -> dict[str, Any]:
    """Compare index date vs latest non-null breadth date in joined dataset."""
    dates = sorted(set(dataset["date"].astype(str).unique()))
    idx = index_as_of or str(dataset["date"].max())
    if idx not in dates:
        dates = sorted(set(dates) | {idx})
    breadth_col = "advancers_pct"
    if breadth_col in dataset.columns:
        valid_b = dataset[dataset[breadth_col].notna()]
        breadth_as_of = str(valid_b["date"].max()) if not valid_b.empty else idx
    else:
        breadth_as_of = idx
    if idx in dates and breadth_as_of in dates:
        breadth_lag_sessions = dates.index(idx) - dates.index(breadth_as_of)
    else:
        breadth_lag_sessions = 0
    breadth_status = "OK" if breadth_lag_sessions <= 2 else "STALE_BREADTH_NEEDS_REFRESH"
    return {
        "index_as_of": idx,
        "breadth_as_of": breadth_as_of,
        "breadth_lag_sessions": int(breadth_lag_sessions),
        "breadth_status": breadth_status,
    }


def refresh_v13_json_from_artifacts(
    latest_path: Path | None = None,
) -> Optional[dict[str, Any]]:
    """Re-apply v13_research to latest JSON after v1.2 overwrite (uses saved CSV artifacts)."""
    latest_path = latest_path or OUT_DIR / "distribution_risk_latest.json"
    dataset_path = OUT_DIR / "distribution_v13_research_dataset.csv"
    wf_path = OUT_DIR / "v13_walkforward_validation.csv"
    surf_path = OUT_DIR / "v13_probability_surface_25d.csv"
    if not latest_path.is_file() or not dataset_path.is_file():
        return None
    dataset = pd.read_csv(dataset_path)
    base_json = json.loads(latest_path.read_text(encoding="utf-8"))
    index_as_of = str(
        base_json.get("requested_as_of_date") or base_json.get("as_of_date") or dataset["date"].max()
    )
    staleness = _compute_breadth_staleness(dataset, index_as_of=index_as_of)
    breadth_row_df = dataset[dataset["date"] == staleness["breadth_as_of"]]
    if breadth_row_df.empty:
        breadth_row_df = dataset[dataset["advancers_pct"].notna()].iloc[[-1]]
    lr = breadth_row_df.iloc[0]
    liquid_n = int(lr.get("liquid_universe_n", 0) or 0)
    if liquid_n <= 0:
        audit = audit_panel()
        liquid_n = audit.latest_liquid_n
    br_keys = [k for k in lr.index if any(x in str(k) for x in ("adv", "decl", "net", "streak", "liquid"))]
    ma_keys = [k for k in lr.index if str(k).startswith("pct_above") or str(k).startswith("n_above")]
    wf_summary: dict[str, Any] = {}
    if wf_path.is_file():
        wf = pd.read_csv(wf_path)
        if not wf.empty and "brier_score" in wf.columns:
            mean_brier = wf.groupby("model")["brier_score"].mean().sort_values()
            wf_summary["mean_brier_by_model"] = mean_brier.to_dict()
            wf_summary["best_model"] = {"id": mean_brier.index[0], "mean_brier": float(mean_brier.iloc[0])}
    prob_surface: dict[str, float] = {}
    if surf_path.is_file():
        surf = pd.read_csv(surf_path)
        if not surf.empty and "metric" in surf.columns:
            prob_surface = surf.set_index("metric")["probability"].astype(float).to_dict()
    patch_latest_json_v13(
        latest_path,
        liquid_n=liquid_n,
        breadth_row={k: float(lr[k]) if pd.notna(lr[k]) else None for k in br_keys},
        ma_row={k: float(lr[k]) if pd.notna(lr[k]) else None for k in ma_keys},
        prob_surface=prob_surface,
        wf_summary=wf_summary,
        staleness=staleness,
    )
    from src.trading.reports.distribution_risk_card import write_distribution_risk_latest_artifacts

    merged_json = json.loads(latest_path.read_text(encoding="utf-8"))
    write_distribution_risk_latest_artifacts(merged_json)
    card = build_daily_card_draft(
        dataset,
        view=PRIMARY_VIEW,
        liquid_n=liquid_n,
        staleness=staleness,
    )
    (OUT_DIR / "v13_daily_card_draft.md").write_text(card, encoding="utf-8")
    return json.loads(latest_path.read_text(encoding="utf-8"))


def _load_dist_forward(primary: str, start: str) -> pd.DataFrame:
    views, meta, _ = load_index_views(start=start)
    if primary not in views:
        primary = "vnindex_raw"
    ohlcv = views[primary]
    dist_vol_ok = meta.get(primary)
    dv = dist_vol_ok.distribution_volume_available if dist_vol_ok else True
    feat = build_features(ohlcv, index_view=primary, distribution_volume_available=dv)
    full = attach_forward_outcomes(feat)
    full["view"] = primary
    full["warning_state"] = full.apply(warning_state_row, axis=1)
    for col, op, thr, out in TARGET_SPECS:
        if col in full.columns:
            _hit_col(full, col, op, thr, out)
    full["date"] = pd.to_datetime(full["date"]).dt.strftime("%Y-%m-%d")
    return full


def build_research_dataset(
    *,
    breadth: pd.DataFrame,
    ma: pd.DataFrame,
    value_b: pd.DataFrame,
    largecap: pd.DataFrame,
    prior: pd.DataFrame,
    new_hl: pd.DataFrame | None,
    dist: pd.DataFrame,
) -> pd.DataFrame:
    base = dist.copy()
    for extra in (breadth, ma, value_b, largecap, prior):
        if extra is not None and not extra.empty:
            base = base.merge(extra, on="date", how="left", suffixes=("", "_dup"))
            base = base[[c for c in base.columns if not c.endswith("_dup")]]
    if new_hl is not None and not new_hl.empty:
        cols = [c for c in new_hl.columns if c not in base.columns or c == "date"]
        base = base.merge(new_hl[cols], on="date", how="left")
    return base


def _bucket_row(metric: str, bucket: str, grp: pd.DataFrame, base: pd.DataFrame) -> dict:
    n = len(grp)
    rec: dict[str, Any] = {"metric": metric, "bucket": bucket, "n": n, "confidence": confidence_label(n)}
    if n == 0:
        return rec
    for _col, _op, _thr, out in TARGET_SPECS:
        if out not in grp.columns:
            continue
        g = grp[out].dropna()
        b = base[out].dropna()
        if len(g) == 0:
            continue
        p = float(g.mean())
        br = float(b.mean()) if len(b) else np.nan
        rec[f"p_{out}"] = p
        rec[f"base_rate_{out}"] = br
        rec[f"lift_{out}"] = p - br if pd.notna(br) else np.nan
    if "fwd_ret_25d" in grp.columns:
        r = grp["fwd_ret_25d"].dropna()
        rec["mean_fwd_ret_25d"] = float(r.mean()) if len(r) else np.nan
        rec["median_fwd_ret_25d"] = float(r.median()) if len(r) else np.nan
    if "max_dd_25d" in grp.columns:
        m = grp["max_dd_25d"].dropna()
        rec["mean_max_dd_25d"] = float(m.mean()) if len(m) else np.nan
        rec["median_max_dd_25d"] = float(m.median()) if len(m) else np.nan
    return rec


def build_baseline_v12_comparison(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = df.copy()
    base["dist_bucket_25"] = base["dist_count_25d"].apply(_dist_bucket_25)
    targets = [
        ("hit_max_dd_neg5pct_25d", "max_dd_25d <= -5%"),
        ("hit_max_dd_neg10pct_25d", "max_dd_25d <= -10%"),
        ("end_ret_neg_25d", "end_return_25d < 0"),
        ("end_ret_le_neg5pct_25d", "end_return_25d <= -5%"),
    ]
    br_all = {t[0]: float(base[t[0]].dropna().mean()) for t in targets if t[0] in base.columns}
    for bucket, grp in base.groupby("dist_bucket_25"):
        for out, label in targets:
            if out not in grp.columns:
                continue
            g = grp[out].dropna()
            n = len(g)
            if n == 0:
                continue
            p = float(g.mean())
            br = br_all.get(out, np.nan)
            rows.append(
                {
                    "model": "v1.2_baseline",
                    "bucket_metric": "dist_count_25d",
                    "bucket": bucket,
                    "target": label,
                    "target_col": out,
                    "n": n,
                    "conditional_prob": p,
                    "base_rate": br,
                    "lift": p - br if pd.notna(br) else np.nan,
                    "confidence": confidence_label(n),
                }
            )
    return pd.DataFrame(rows)


def _dist_bucket_25(v: float) -> str:
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


def _assign_bucket(series: pd.Series, cuts: list[tuple[str, float, float | None]]) -> pd.Series:
    out = pd.Series("unknown", index=series.index)
    for label, lo, hi in cuts:
        if hi is None:
            mask = series >= lo
        elif lo is None:
            mask = series < hi
        else:
            mask = (series >= lo) & (series < hi)
        out[mask] = label
    return out


def build_breadth_bucket_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    specs = [
        ("advancers_pct_5d_avg", [("weak", None, 0.40), ("neutral", 0.40, 0.55), ("strong", 0.55, None)]),
        ("decliners_pct_5d_avg", [("low", None, 0.35), ("medium", 0.35, 0.50), ("high", 0.50, None)]),
        ("net_adv_dec_pct_5d_avg", [("negative", None, -0.10), ("neutral", -0.10, 0.10), ("positive", 0.10, None)]),
    ]
    for metric, cuts in specs:
        if metric not in df.columns:
            continue
        sub = df.copy()
        sub["bucket"] = _assign_bucket(sub[metric].astype(float), cuts)
        for bucket, grp in sub.groupby("bucket"):
            rec = _bucket_row(metric, bucket, grp, sub)
            rec["bucket_metric"] = metric
            rows.append(rec)
    return pd.DataFrame(rows)


def build_ma_bucket_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    specs = [
        ("pct_above_ma50", [("weak", None, 0.45), ("neutral", 0.45, 0.60), ("strong", 0.60, None)]),
        ("pct_above_ma20_change_5d", [("deteriorating", None, -0.10), ("stable", -0.10, 0.10), ("improving", 0.10, None)]),
        ("pct_above_ma200", [("structural_weak", None, 0.50), ("structural_ok", 0.50, None)]),
    ]
    for metric, cuts in specs:
        if metric not in df.columns:
            continue
        sub = df.copy()
        sub["bucket"] = _assign_bucket(sub[metric].astype(float), cuts)
        for bucket, grp in sub.groupby("bucket"):
            rec = _bucket_row(metric, bucket, grp, sub)
            rec["bucket_metric"] = metric
            rows.append(rec)
    return pd.DataFrame(rows)


def build_interaction_bucket_table(df: pd.DataFrame) -> pd.DataFrame:
    interactions = [
        ("dist>=5 AND ma50<0.50", (df["dist_count_25d"] >= 5) & (df["pct_above_ma50"] < 0.50)),
        ("dist>=5 AND ma20_chg_5d<-0.10", (df["dist_count_25d"] >= 5) & (df["pct_above_ma20_change_5d"] < -0.10)),
        ("dist>=5 AND decliners_5d>0.50", (df["dist_count_25d"] >= 5) & (df["decliners_pct_5d_avg"] > 0.50)),
        ("dist>=5 AND value_net_5d<-0.10", (df["dist_count_25d"] >= 5) & (df["value_net_breadth_pct_5d_avg"] < -0.10)),
        (
            "dist>=5 AND hot AND ma20_chg<-0.10",
            (df["dist_count_25d"] >= 5)
            & (df["prior_20d_return_bucket"] == "hot")
            & (df["pct_above_ma20_change_5d"] < -0.10),
        ),
        ("dist>=5 AND below_ma50", (df["dist_count_25d"] >= 5) & (df["index_ma_zone"] == "below_ma50")),
        (
            "dist>=5 AND top30_adv>0.50 AND all_adv<0.45",
            (df["dist_count_25d"] >= 5)
            & (df["top30_adv50_advancers_pct"] > 0.50)
            & (df["all_liquid_adv50_gt_2b_advancers_pct"] < 0.45),
        ),
    ]
    rows = []
    primary_target = "hit_max_dd_neg5pct_25d"
    base_rate = float(df[primary_target].dropna().mean()) if primary_target in df.columns else np.nan
    for name, mask in interactions:
        grp = df[mask.fillna(False)]
        n = len(grp)
        if n == 0:
            continue
        if primary_target in grp.columns:
            g = grp[primary_target].dropna()
            p = float(g.mean()) if len(g) else np.nan
            false_alarm = float(1.0 - g.mean()) if len(g) else np.nan
        else:
            p, false_alarm = np.nan, np.nan
        r25 = grp["fwd_ret_25d"].dropna() if "fwd_ret_25d" in grp.columns else pd.Series(dtype=float)
        mdd = grp["max_dd_25d"].dropna() if "max_dd_25d" in grp.columns else pd.Series(dtype=float)
        rows.append(
            {
                "interaction": name,
                "n": n,
                "base_rate": base_rate,
                "conditional_prob": p,
                "lift": p - base_rate if pd.notna(base_rate) and pd.notna(p) else np.nan,
                "mean_fwd_ret_25d": float(r25.mean()) if len(r25) else np.nan,
                "median_fwd_ret_25d": float(r25.median()) if len(r25) else np.nan,
                "mean_max_dd_25d": float(mdd.mean()) if len(mdd) else np.nan,
                "median_max_dd_25d": float(mdd.median()) if len(mdd) else np.nan,
                "false_alarm_rate": false_alarm,
                "confidence": confidence_label(n),
            }
        )
    return pd.DataFrame(rows).sort_values("lift", ascending=False, na_position="last")


def _zone_labels(row: pd.Series) -> tuple[str, str, str, str]:
    ap = row.get("advancers_pct_5d_avg", np.nan)
    if pd.isna(ap):
        bz = "unknown"
    elif ap < 0.40:
        bz = "weak"
    elif ap <= 0.55:
        bz = "neutral"
    else:
        bz = "strong"
    net = row.get("net_adv_dec_pct_5d_avg", np.nan)
    if pd.isna(net):
        bt = "unknown"
    elif net < -0.10:
        bt = "negative"
    elif net <= 0.10:
        bt = "neutral"
    else:
        bt = "positive"
    ma50 = row.get("pct_above_ma50", np.nan)
    if pd.isna(ma50):
        mz = "unknown"
    elif ma50 < 0.45:
        mz = "weak"
    elif ma50 <= 0.60:
        mz = "neutral"
    else:
        mz = "strong"
    vn = row.get("value_net_breadth_pct_5d_avg", np.nan)
    if pd.isna(vn):
        vz = "unknown"
    elif vn < -0.10:
        vz = "negative"
    elif vn <= 0.10:
        vz = "neutral"
    else:
        vz = "positive"
    return bz, bt, mz, vz


def _model_key(row: pd.Series, model: str) -> str:
    d = _dist_bucket_25(float(row.get("dist_count_25d", np.nan)))
    if model == "A":
        return f"A|{d}"
    if model == "B":
        return f"B|{_bucket_adv(row)}|{_bucket_dec(row)}|{_bucket_net(row)}"
    if model == "C":
        return f"C|{d}|{_bucket_adv(row)}|{_bucket_dec(row)}|{_bucket_net(row)}"
    if model == "D":
        return (
            f"D|{d}|{_bucket_adv(row)}|{_bucket_dec(row)}|"
            f"{_bucket_ma50(row)}|{_bucket_ma20_chg(row)}|{_bucket_ma50_chg10(row)}"
        )
    bz, bt, mz, vz = _zone_labels(row)
    pr = row.get("prior_20d_return_bucket", "unknown")
    iz = row.get("index_ma_zone", "unknown")
    return f"E|{d}|{bz}|{bt}|{mz}|{pr}|{iz}|{vz}"


def _bucket_adv(row: pd.Series) -> str:
    v = row.get("advancers_pct_5d_avg", np.nan)
    if pd.isna(v):
        return "u"
    if v < 0.40:
        return "w"
    if v <= 0.55:
        return "n"
    return "s"


def _bucket_dec(row: pd.Series) -> str:
    v = row.get("decliners_pct_5d_avg", np.nan)
    if pd.isna(v):
        return "u"
    if v < 0.35:
        return "l"
    if v <= 0.50:
        return "m"
    return "h"


def _bucket_net(row: pd.Series) -> str:
    v = row.get("net_adv_dec_pct_5d_avg", np.nan)
    if pd.isna(v):
        return "u"
    if v < -0.10:
        return "neg"
    if v <= 0.10:
        return "neu"
    return "pos"


def _bucket_ma50(row: pd.Series) -> str:
    v = row.get("pct_above_ma50", np.nan)
    if pd.isna(v):
        return "u"
    return "w" if v < 0.45 else ("n" if v <= 0.60 else "s")


def _bucket_ma20_chg(row: pd.Series) -> str:
    v = row.get("pct_above_ma20_change_5d", np.nan)
    if pd.isna(v):
        return "u"
    return "d" if v < -0.10 else ("s" if v <= 0.10 else "i")


def _bucket_ma50_chg10(row: pd.Series) -> str:
    v = row.get("pct_above_ma50_change_10d", np.nan)
    if pd.isna(v):
        return "u"
    return "d" if v < -0.10 else ("s" if v <= 0.10 else "i")


def walkforward_validation(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    target = "hit_max_dd_neg5pct_25d"
    df = df.copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year
    models = ("A", "B", "C", "D", "E")
    min_train_bucket_n = 30
    rows = []
    cal_rows = []
    for test_year in range(2018, 2027):
        train = df[df["year"] < test_year]
        test = df[df["year"] == test_year]
        if train.empty or test.empty:
            continue
        base_rate = float(train[target].dropna().mean()) if target in train.columns else np.nan
        for model in models:
            train["mk"] = train.apply(lambda r: _model_key(r, model), axis=1)
            test["mk"] = test.apply(lambda r: _model_key(r, model), axis=1)
            probs_map: dict[str, float] = {}
            counts: dict[str, int] = {}
            for mk, grp in train.groupby("mk"):
                g = grp[target].dropna()
                if len(g) >= min_train_bucket_n:
                    probs_map[mk] = float(g.mean())
                    counts[mk] = len(g)
            parent = float(train[target].dropna().mean()) if target in train.columns else 0.5
            preds = []
            actuals = []
            for _, row in test.iterrows():
                mk = row["mk"]
                p = probs_map.get(mk, parent)
                if mk not in probs_map:
                    parts = mk.split("|")
                    if model == "C" and len(parts) >= 2:
                        simpler = "|".join(parts[:2])
                        p = probs_map.get(simpler, parent)
                    elif model in ("D", "E"):
                        simpler = "|".join(parts[:2]) if len(parts) >= 2 else mk
                        p = probs_map.get(simpler, parent)
                preds.append(p)
                actuals.append(row.get(target, np.nan))
            pred_s = pd.Series(preds)
            act_s = pd.Series(actuals).dropna()
            pred_s = pred_s.iloc[: len(act_s)]
            if len(act_s) == 0:
                continue
            brier = float(np.mean((pred_s - act_s) ** 2))
            try:
                from sklearn.metrics import roc_auc_score

                auc = float(roc_auc_score(act_s, pred_s)) if act_s.nunique() > 1 else np.nan
            except Exception:
                auc = np.nan
            high_risk = pred_s >= 0.55
            prec = float(act_s[high_risk].mean()) if high_risk.any() else np.nan
            rec = float(act_s[high_risk].sum() / act_s.sum()) if act_s.sum() > 0 else np.nan
            rows.append(
                {
                    "test_year": test_year,
                    "model": model,
                    "n_test": len(act_s),
                    "brier_score": brier,
                    "auc": auc,
                    "base_rate_train": base_rate,
                    "mean_predicted_prob": float(pred_s.mean()),
                    "precision_high_risk": prec,
                    "recall_high_risk": rec,
                    "lift_precision_vs_base": prec - base_rate if pd.notna(prec) and pd.notna(base_rate) else np.nan,
                    "n_high_risk_days": int(high_risk.sum()),
                }
            )
            for decile in range(10):
                lo = decile / 10.0
                hi = (decile + 1) / 10.0
                mask = (pred_s >= lo) & (pred_s < hi if decile < 9 else pred_s <= 1.0)
                if not mask.any():
                    continue
                cal_rows.append(
                    {
                        "test_year": test_year,
                        "model": model,
                        "decile": decile + 1,
                        "n": int(mask.sum()),
                        "mean_predicted": float(pred_s[mask].mean()),
                        "observed_rate": float(act_s[mask].mean()),
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(cal_rows)


def build_probability_surface(df: pd.DataFrame, *, as_of: Optional[str] = None) -> pd.DataFrame:
    sub = df.copy()
    if as_of:
        sub = sub[sub["date"] <= as_of]
    rows = []
    thresholds_end = [
        (0, "P(end_return_25d < 0)"),
        (-0.03, "P(end_return_25d <= -3%)"),
        (-0.05, "P(end_return_25d <= -5%)"),
        (-0.08, "P(end_return_25d <= -8%)"),
        (-0.10, "P(end_return_25d <= -10%)"),
    ]
    thresholds_dd = [
        (-0.03, "P(max_dd_25d <= -3%)"),
        (-0.05, "P(max_dd_25d <= -5%)"),
        (-0.08, "P(max_dd_25d <= -8%)"),
        (-0.10, "P(max_dd_25d <= -10%)"),
        (-0.10, "P(max_dd_75d <= -10%)", "max_dd_75d"),
    ]
    for dt in sub["date"].unique():
        hist = sub[sub["date"] <= dt]
        if len(hist) < 50:
            continue
        for thr, label in thresholds_end:
            r = hist["fwd_ret_25d"].dropna()
            if len(r) == 0:
                continue
            base = float((r < 0).mean()) if thr == 0 else float((r <= thr).mean())
            rows.append({"date": dt, "metric": label, "probability": base, "base_rate": base, "lift": 0.0})
        for item in thresholds_dd:
            thr, label = item[0], item[1]
            col = item[2] if len(item) > 2 else "max_dd_25d"
            m = hist[col].dropna()
            if len(m) == 0:
                continue
            base = float((m <= thr).mean())
            rows.append({"date": dt, "metric": label, "probability": base, "base_rate": base, "lift": 0.0})
    surf = pd.DataFrame(rows)
    if as_of and not surf.empty:
        surf = surf[surf["date"] == as_of]
    return surf


def _fmt_pct(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "n/a"
    return f"{float(val):.1%}"


def build_daily_card_draft(
    df: pd.DataFrame,
    *,
    view: str,
    liquid_n: int,
    staleness: dict[str, Any],
) -> str:
    index_as_of = staleness["index_as_of"]
    breadth_as_of = staleness["breadth_as_of"]
    status = staleness["breadth_status"]
    idx_row = df[df["date"] == index_as_of]
    if idx_row.empty:
        idx_row = df.iloc[[-1]]
    ir = idx_row.iloc[0]
    br_row = df[df["date"] == breadth_as_of]
    if br_row.empty:
        br_row = df[df["advancers_pct"].notna()].iloc[[-1]] if df["advancers_pct"].notna().any() else idx_row
    br = br_row.iloc[0]
    lines = [
        "## MARKET CONTEXT — Distribution Risk v1.3 Research",
        "",
        f"**Status:** {status}",
        f"**Index as-of:** {index_as_of}",
        f"**Breadth as-of:** {breadth_as_of}",
        f"**Primary view:** {view}",
        f"**Liquid universe:** {liquid_n} stocks with ADV50 > 2B VND",
        "",
        "_Index/distribution facts use index_as_of; breadth/MA facts use breadth_as_of._",
        "",
        "### Facts",
        f"- Distribution: dist 10/25/50 = {ir.get('dist_count_10d')}/{ir.get('dist_count_25d')}/{ir.get('dist_count_50d')}",
        f"- Breadth: advancers {_fmt_pct(br.get('advancers_pct'))}, decliners {_fmt_pct(br.get('decliners_pct'))}, net {_fmt_pct(br.get('net_adv_dec_pct'))}",
        f"- 5d breadth: adv {_fmt_pct(br.get('advancers_pct_5d_avg'))}, decl {_fmt_pct(br.get('decliners_pct_5d_avg'))}, net {_fmt_pct(br.get('net_adv_dec_pct_5d_avg'))}",
        f"- MA participation: >MA20 {_fmt_pct(br.get('pct_above_ma20'))}, >MA50 {_fmt_pct(br.get('pct_above_ma50'))}, >MA200 {_fmt_pct(br.get('pct_above_ma200'))}",
        f"- Value-weighted breadth: advancing {_fmt_pct(br.get('advancing_value_pct'))}, declining {_fmt_pct(br.get('declining_value_pct'))}, net {_fmt_pct(br.get('value_net_breadth_pct'))}",
    ]
    if pd.notna(br.get("top30_advancers_minus_all_advancers")):
        lines.append(
            f"- Large-cap divergence: top30−all adv {_fmt_pct(br.get('top30_advancers_minus_all_advancers'))}, "
            f"leadership_flag={int(br.get('largecap_breadth_leadership_flag', 0))}, "
            f"divergence_flag={int(br.get('largecap_breadth_divergence_flag', 0))}"
        )
    if pd.notna(ir.get("ret_20d")):
        lines.append(
            f"- Prior rally context: ret_20d {float(ir.get('ret_20d', 0)):.2%}, "
            f"bucket {ir.get('prior_20d_return_bucket')}, zone {ir.get('index_ma_zone')}"
        )
    lines.extend(
        [
            "",
            "### Interpretation",
            "- **FACTS:** Breadth and MA participation describe how broad the market move is versus the index alone.",
            "- **INTERPRETATION:** Facts-based context only. v1.3 bucket probabilities are research-only and not promoted as forecasts.",
            "",
            "### Safety",
            "Context only. Does not change final_action, OMS, A3/S3, or position sizing.",
        ]
    )
    if status == "STALE_BREADTH_NEEDS_REFRESH":
        lines.insert(
            6,
            f"**Staleness:** breadth lags index by {staleness.get('breadth_lag_sessions', 0)} trading sessions — refresh OHLCV panel before relying on breadth facts.",
        )
    return "\n".join(lines) + "\n"


def patch_latest_json_v13(
    latest_path: Path,
    *,
    liquid_n: int,
    breadth_row: dict,
    ma_row: dict,
    prob_surface: dict,
    wf_summary: dict,
    staleness: dict[str, Any],
) -> None:
    if not latest_path.is_file():
        return
    data = json.loads(latest_path.read_text(encoding="utf-8"))
    data["v13_research"] = {
        "enabled": True,
        "context_only": True,
        "changes_final_action": False,
        "method_version": V13_VERSION,
        "breadth_status": staleness.get("breadth_status", "OK"),
        "breadth_as_of": staleness.get("breadth_as_of"),
        "index_as_of": staleness.get("index_as_of"),
        "breadth_lag_sessions": staleness.get("breadth_lag_sessions", 0),
        "liquid_universe": {"adv50_threshold_vnd": ADV50_THRESHOLD_VND, "latest_n": liquid_n},
        "breadth": breadth_row,
        "ma_participation": ma_row,
        "probability_surface_25d": prob_surface,
        "best_validated_model": wf_summary.get("best_model", {}),
        "validation_summary": wf_summary,
    }
    latest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_v13_research(
    *,
    start: str = "2012-01-01",
    as_of: Optional[str] = None,
) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = OUT_DIR / "v13_stage0_data_audit.md"
    audit_ref = write_stage0_audit(audit_path)

    from src.market.distribution_risk_lens.liquid_universe import load_normalized_panel

    panel = load_normalized_panel()
    breadth = build_breadth_features(start=start, panel=panel)
    ma = build_ma_participation(start=start, panel=panel)
    value_b = build_value_weighted_breadth(start=start, panel=panel)
    largecap = build_largecap_divergence(start=start, panel=panel)
    prior = build_prior_rally_context(start=start, primary_view=PRIMARY_VIEW)
    new_hl = build_new_high_low_features(start=start, panel=panel)

    breadth.to_csv(OUT_DIR / "distribution_breadth_features.csv", index=False)
    ma.to_csv(OUT_DIR / "distribution_ma_participation.csv", index=False)
    value_b.to_csv(OUT_DIR / "distribution_value_weighted_breadth.csv", index=False)
    largecap.to_csv(OUT_DIR / "distribution_largecap_breadth_divergence.csv", index=False)
    prior.to_csv(OUT_DIR / "distribution_prior_rally_context.csv", index=False)
    new_hl.to_csv(OUT_DIR / "distribution_new_high_low_features.csv", index=False)

    dist = _load_dist_forward(PRIMARY_VIEW, start)
    dataset = build_research_dataset(
        breadth=breadth,
        ma=ma,
        value_b=value_b,
        largecap=largecap,
        prior=prior,
        new_hl=new_hl,
        dist=dist,
    )
    dataset.to_csv(OUT_DIR / "distribution_v13_research_dataset.csv", index=False)

    baseline = build_baseline_v12_comparison(dataset)
    baseline.to_csv(OUT_DIR / "v13_baseline_v12_comparison.csv", index=False)
    build_breadth_bucket_table(dataset).to_csv(OUT_DIR / "v13_breadth_bucket_probability_table.csv", index=False)
    build_ma_bucket_table(dataset).to_csv(OUT_DIR / "v13_ma_participation_probability_table.csv", index=False)
    build_interaction_bucket_table(dataset).to_csv(
        OUT_DIR / "v13_interaction_bucket_probability_table.csv", index=False
    )

    wf, cal = walkforward_validation(dataset)
    wf.to_csv(OUT_DIR / "v13_walkforward_validation.csv", index=False)
    cal.to_csv(OUT_DIR / "v13_walkforward_calibration_by_decile.csv", index=False)

    staleness = _compute_breadth_staleness(dataset)
    surf_as_of = staleness["breadth_as_of"]
    surf = build_probability_surface(dataset, as_of=surf_as_of)
    surf.to_csv(OUT_DIR / "v13_probability_surface_25d.csv", index=False)

    liquid_n = int(audit_ref.audit.latest_liquid_n)
    breadth_row_df = dataset[dataset["date"] == staleness["breadth_as_of"]]
    if breadth_row_df.empty:
        breadth_row_df = dataset[dataset["advancers_pct"].notna()].iloc[[-1]]
    lr = breadth_row_df.iloc[0]
    card = build_daily_card_draft(
        dataset,
        view=PRIMARY_VIEW,
        liquid_n=liquid_n,
        staleness=staleness,
    )
    (OUT_DIR / "v13_daily_card_draft.md").write_text(card, encoding="utf-8")

    wf_summary: dict[str, Any] = {}
    if not wf.empty:
        mean_brier = wf.groupby("model")["brier_score"].mean().sort_values()
        wf_summary["mean_brier_by_model"] = mean_brier.to_dict()
        best_model = mean_brier.index[0]
        wf_summary["best_model"] = {"id": best_model, "mean_brier": float(mean_brier.iloc[0])}

    latest_json = OUT_DIR / "distribution_risk_latest.json"
    br_keys = [k for k in lr.index if any(x in str(k) for x in ("adv", "decl", "net", "streak", "liquid"))]
    ma_keys = [k for k in lr.index if str(k).startswith("pct_above") or str(k).startswith("n_above")]
    patch_latest_json_v13(
        latest_json,
        liquid_n=liquid_n,
        breadth_row={k: float(lr[k]) if pd.notna(lr[k]) else None for k in br_keys},
        ma_row={k: float(lr[k]) if pd.notna(lr[k]) else None for k in ma_keys},
        prob_surface=surf.set_index("metric")["probability"].to_dict() if not surf.empty else {},
        wf_summary=wf_summary,
        staleness=staleness,
    )

    return {
        "outputs_dir": str(OUT_DIR),
        "as_of": staleness["index_as_of"],
        "breadth_as_of": staleness["breadth_as_of"],
        "breadth_status": staleness["breadth_status"],
        "liquid_n": liquid_n,
        "n_dataset": len(dataset),
        "wf_summary": wf_summary,
    }
