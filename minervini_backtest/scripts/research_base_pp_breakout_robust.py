"""
Robust event-study: base_id segmentation, PP rungs within base, breakout volume families,
walk-forward tags, OOS robustness summaries. Research evidence only — not live alpha.

Preserves: curated load, regime trim, next-open entries, forward close/open labels.
New default output dir does not overwrite legacy edge research CSVs.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from run import load_curated_data

import importlib.util

_rp = Path(__file__).resolve().parent / "run_prebreakout_research.py"
_spec = importlib.util.spec_from_file_location("run_prebreakout_research", _rp)
_rb = importlib.util.module_from_spec(_spec)
sys.modules["run_prebreakout_research"] = _rb
assert _spec.loader is not None
_spec.loader.exec_module(_rb)
_add_core_features = _rb._add_core_features

_scan = Path(__file__).resolve().parent / "scan_accumulation_bases.py"
_s2 = importlib.util.spec_from_file_location("scan_accumulation_bases", _scan)
_sm = importlib.util.module_from_spec(_s2)
sys.modules["scan_accumulation_bases"] = _sm
assert _s2.loader is not None
_s2.loader.exec_module(_sm)
_pick_analysis_regime = _sm._pick_analysis_regime
_trend_series = _sm._trend_series
_discover = _sm._discover_symbols_all_raw

from research.base_segmentation import EventConfig, collect_pp_and_breakout_events
from research.event_study_features import (
    breakout_day_features,
    compute_candidate_mask,
    compute_forward_labels,
    enrich_event_study_columns,
    feature_row_at,
    pp_day_features,
    rolling_base_arrays,
)
from research.event_study_scores import base_quality_score, entry_quality_score_breakout, entry_quality_score_pp
from research.walkforward import default_splits, iter_event_split_rows

# Columns only — wide event frames (scores, features) must not enter groupby (memory).
_SUMMARY_GROUP_COLS = ["param_set_id", "event_kind", "wf_split_id", "wf_fold"]
_SUMMARY_RET_COLS = ["ret_5d", "ret_10d", "ret_15d", "ret_20d"]


def _slim_for_summary(pp_df: pd.DataFrame, br_df: pd.DataFrame) -> pd.DataFrame:
    """Narrow copy for aggregation; downcast returns to float32 to reduce groupby RAM."""
    cols = _SUMMARY_GROUP_COLS + _SUMMARY_RET_COLS
    parts: list[pd.DataFrame] = []
    if not pp_df.empty:
        p = pp_df.assign(event_kind="pp")
        parts.append(p[[c for c in cols if c in p.columns]])
    if not br_df.empty:
        b = br_df.assign(event_kind="breakout")
        parts.append(b[[c for c in cols if c in b.columns]])
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    for c in _SUMMARY_RET_COLS:
        if c in out.columns:
            out[c] = out[c].astype("float32")
    return out


def _param_digest(d: dict[str, Any]) -> str:
    payload = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:14]


def _param_human_key(row: dict[str, Any], trend: str, min_adv20: float) -> str:
    """Short stable label for reports (not a unique hash)."""
    return (
        f"bd{row['base_days']}_d{row['min_base_depth']}-{row['max_base_depth']}"
        f"_p{row['min_base_pos']}_dp{row['max_dist_pivot']}"
        f"_ad{row['anti_drift_mode']}_{row['pp_bucket']}"
        f"_eb{row['entry_buffer']}_{row['breakout_vol_family']}_m{row['breakout_vol_mult']}"
        f"_t{trend}_adv{min_adv20:.0f}"
    )


def iter_grid(profile: str) -> Iterator[dict[str, Any]]:
    """Yield parameter dicts. phase1 = reduced Cartesian per spec; full = full Cartesian; smoke = 2 samples."""
    base_days_list = (70, 80, 90)
    min_depths = (0.10, 0.12)
    max_depths = (0.28, 0.32)
    min_poss = (0.50, 0.55)
    max_dists = (0.08, 0.12)
    antis = (1, 2, 3)
    pp_buckets = ("rung2", "rung3", "ge2")
    entry_bufs = (0.0015, 0.003)
    fams = ("sma20", "sma50")
    mults = (1.25, 1.35, 1.50)

    def full_product() -> Iterator[dict[str, Any]]:
        for tup in itertools.product(
            base_days_list,
            min_depths,
            max_depths,
            min_poss,
            max_dists,
            antis,
            pp_buckets,
            entry_bufs,
            fams,
            mults,
        ):
            bd, mind, maxd, minp, maxdist, anti, ppb, eb, fam, mult = tup
            yield {
                "base_days": bd,
                "min_base_depth": mind,
                "max_base_depth": maxd,
                "min_base_pos": minp,
                "max_dist_pivot": maxdist,
                "anti_drift_mode": anti,
                "pp_bucket": ppb,
                "entry_buffer": eb,
                "breakout_vol_family": fam,
                "breakout_vol_mult": mult,
            }

    def phase1_reduced() -> Iterator[dict[str, Any]]:
        for bd in base_days_list:
            for anti in antis:
                for ppb in pp_buckets:
                    for eb in entry_bufs:
                        for fam in fams:
                            for mult in mults:
                                yield {
                                    "base_days": bd,
                                    "min_base_depth": 0.12,
                                    "max_base_depth": 0.32,
                                    "min_base_pos": 0.55,
                                    "max_dist_pivot": 0.12,
                                    "anti_drift_mode": anti,
                                    "pp_bucket": ppb,
                                    "entry_buffer": eb,
                                    "breakout_vol_family": fam,
                                    "breakout_vol_mult": mult,
                                }

    if profile == "smoke":
        for i, row in enumerate(phase1_reduced()):
            if i >= 2:
                break
            yield row
        return
    if profile == "phase1":
        yield from phase1_reduced()
        return
    if profile == "full":
        yield from full_product()
        return
    if profile == "full_plus_pct":
        yield from full_product()
        # Additional pct50-only volume grid (mult = min prior-50 volume rank threshold).
        for tup in itertools.product(
            base_days_list,
            min_depths,
            max_depths,
            min_poss,
            max_dists,
            antis,
            pp_buckets,
            entry_bufs,
            ("pct50",),
            (0.75, 0.80),
        ):
            bd, mind, maxd, minp, maxdist, anti, ppb, eb, fam, mult = tup
            yield {
                "base_days": bd,
                "min_base_depth": mind,
                "max_base_depth": maxd,
                "min_base_pos": minp,
                "max_dist_pivot": maxdist,
                "anti_drift_mode": anti,
                "pp_bucket": ppb,
                "entry_buffer": eb,
                "breakout_vol_family": fam,
                "breakout_vol_mult": mult,
            }
        return
    raise ValueError(f"Unknown grid profile: {profile}")


def _load_grid_from_file(path: str) -> list[dict[str, Any]]:
    """Load explicit grid rows from JSON file (list[dict])."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"grid file not found: {path}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError("grid file must be a JSON list of parameter dicts")
    need = {
        "base_days",
        "min_base_depth",
        "max_base_depth",
        "min_base_pos",
        "max_dist_pivot",
        "anti_drift_mode",
        "pp_bucket",
        "entry_buffer",
        "breakout_vol_family",
        "breakout_vol_mult",
    }
    out: list[dict[str, Any]] = []
    for i, row in enumerate(obj):
        if not isinstance(row, dict):
            raise ValueError(f"grid row {i} is not a dict")
        missing = sorted(need - set(row.keys()))
        if missing:
            raise ValueError(f"grid row {i} missing required keys: {missing}")
        out.append(
            {
                "base_days": int(row["base_days"]),
                "min_base_depth": float(row["min_base_depth"]),
                "max_base_depth": float(row["max_base_depth"]),
                "min_base_pos": float(row["min_base_pos"]),
                "max_dist_pivot": float(row["max_dist_pivot"]),
                "anti_drift_mode": int(row["anti_drift_mode"]),
                "pp_bucket": str(row["pp_bucket"]),
                "entry_buffer": float(row["entry_buffer"]),
                "breakout_vol_family": str(row["breakout_vol_family"]),
                "breakout_vol_mult": float(row["breakout_vol_mult"]),
            }
        )
    return out


def _expectancy(ret: pd.Series) -> float:
    r = ret.dropna()
    if r.empty:
        return float("nan")
    wins = r[r > 0]
    losses = r[r <= 0]
    w = float((r > 0).mean())
    aw = float(wins.mean()) if len(wins) else 0.0
    al = float(losses.mean()) if len(losses) else 0.0
    return w * aw + (1.0 - w) * al


def _summarize_block(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby(group_cols, dropna=False)
    rows = []
    for key, sub in g:
        r10 = sub["ret_10d"]
        r15 = sub["ret_15d"] if "ret_15d" in sub.columns else pd.Series(dtype=float)
        r20 = sub["ret_20d"]
        wins = r10[r10 > 0]
        losses = r10[r10 <= 0]
        aw = float(wins.mean()) if len(wins) else float("nan")
        al = float(losses.mean()) if len(losses) else float("nan")
        row_out: dict[str, Any] = {
            **dict(zip(group_cols, key if isinstance(key, tuple) else (key,))),
            "n": len(sub),
            "win5": float((sub["ret_5d"] > 0).mean()) if "ret_5d" in sub.columns else np.nan,
            "win10": float((r10 > 0).mean()),
            "win15": float((r15 > 0).mean()) if len(r15) else np.nan,
            "win20": float((r20 > 0).mean()) if "ret_20d" in sub.columns else np.nan,
            "median_ret10": float(r10.median()),
            "mean_ret10": float(r10.mean()),
            "p10_ret10": float(r10.quantile(0.10)),
            "p20_ret10": float(r10.quantile(0.20)),
            "avg_win_10": aw,
            "avg_loss_10": al,
            "expectancy_10": _expectancy(r10),
            "median_ret15": float(r15.median()) if len(r15) else np.nan,
            "mean_ret15": float(r15.mean()) if len(r15) else np.nan,
            "expectancy_15": _expectancy(r15) if len(r15) else np.nan,
            "median_ret20": float(r20.median()) if len(r20) else np.nan,
            "mean_ret20": float(r20.mean()) if len(r20) else np.nan,
            "p10_ret20": float(r20.quantile(0.10)) if len(r20) else np.nan,
            "p20_ret20": float(r20.quantile(0.20)) if len(r20) else np.nan,
            "expectancy_20": _expectancy(r20),
        }
        rows.append(row_out)
    return pd.DataFrame(rows)


def _expand_walkforward_rows(event: dict[str, Any], splits: list) -> list[dict[str, Any]]:
    out = []
    d = pd.Timestamp(event["signal_date"])
    for split_id, fold in iter_event_split_rows(splits, d):
        row = {**event, "wf_split_id": split_id, "wf_fold": fold}
        out.append(row)
    return out


def _finalize_rows(
    raw_events: list[dict[str, Any]],
    ed: pd.DataFrame,
    cfg: dict[str, Any],
    splits: list,
    kind: str,
) -> list[dict[str, Any]]:
    close = ed["close"].to_numpy(dtype=float)
    open_ = ed["open"].to_numpy(dtype=float)
    bd = int(cfg["base_days"])
    out: list[dict[str, Any]] = []
    for ev in raw_events:
        ent = int(ev["entry_i"])
        if ent + 20 >= len(close):
            continue
        labels = compute_forward_labels(close, open_, ent)
        i_sig = int(ev["signal_i"])
        base_start = int(ev["base_start_i"])
        bh = float(ev["base_high_roll"])
        bl = float(ev["base_low_roll"])
        piv = float(ev["pivot"])
        base_feats = feature_row_at(ed, i_sig, bd, base_start, bh, bl, piv)
        if not base_feats:
            continue
        if kind == "pp":
            pf = pp_day_features(ed, i_sig)
            merged = {**base_feats, **pf, **labels}
            merged["base_quality_score"] = base_quality_score(merged)
            merged["entry_quality_score"] = entry_quality_score_pp(merged, int(ev["pp_rung_in_base"]))
        else:
            bf = breakout_day_features(ed, i_sig, piv, float(cfg["entry_buffer"]))
            merged = {**base_feats, **bf, **labels}
            merged["base_quality_score"] = base_quality_score(merged)
            merged["entry_quality_score"] = entry_quality_score_breakout(merged)
        merged["combined_research_score"] = 0.55 * float(merged["base_quality_score"]) + 0.45 * float(
            merged["entry_quality_score"]
        )
        ev2 = {
            **ev,
            **{k: merged[k] for k in merged if k not in ev},
            "trend": cfg.get("trend", "relaxed"),
            "min_adv20": cfg.get("min_adv20", np.nan),
            "base_days": bd,
            "min_base_depth": cfg["min_base_depth"],
            "max_base_depth": cfg["max_base_depth"],
            "min_base_pos": cfg["min_base_pos"],
            "max_dist_pivot": cfg["max_dist_pivot"],
            "anti_drift_mode": cfg["anti_drift_mode"],
            "pp_bucket": cfg["pp_bucket"],
            "entry_buffer": cfg["entry_buffer"],
            "breakout_vol_family": cfg["breakout_vol_family"],
            "breakout_vol_mult": cfg["breakout_vol_mult"],
            "param_human_key": cfg.get("param_human_key", ""),
        }
        out.extend(_expand_walkforward_rows(ev2, splits))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=2018)
    ap.add_argument("--max-symbols", type=int, default=0, help="0 = all raw symbols.")
    ap.add_argument("--min-adv20", type=float, default=2e9)
    ap.add_argument("--trend", choices=["medium", "relaxed", "none"], default="relaxed")
    ap.add_argument(
        "--grid-profile",
        choices=["smoke", "phase1", "full", "full_plus_pct"],
        default="smoke",
        help="full_plus_pct appends pct50 rank-threshold grid (see README).",
    )
    ap.add_argument("--max-configs", type=int, default=0, help="0 = no cap; else stop after N configs (deterministic order).")
    ap.add_argument(
        "--grid-file",
        default="",
        help="Optional JSON file containing explicit list of grid rows. Overrides --grid-profile.",
    )
    ap.add_argument(
        "--out-dir",
        default="minervini_backtest/outputs/accumulation_scan/base_pp_breakout_robust_v1",
    )
    ap.add_argument("--grace-bars", type=int, default=3)
    ap.add_argument("--invalidation-buffer", type=float, default=0.025)
    args = ap.parse_args()

    splits = default_splits()
    syms = _discover()
    if args.max_symbols and args.max_symbols > 0:
        syms = syms[: args.max_symbols]
    data = load_curated_data(syms + ["VNINDEX", "VN30"])
    bench = "VNINDEX" if "VNINDEX" in data else "VN30"
    if bench not in data:
        print("[ERROR] benchmark missing")
        return 1
    bench_df = _pick_analysis_regime(data[bench].sort_values("date"))
    bench_ret = bench_df.set_index("date")["close"].pct_change(63)
    start = pd.Timestamp(f"{args.start_year}-01-01")

    grid = _load_grid_from_file(args.grid_file) if args.grid_file else list(iter_grid(args.grid_profile))
    if args.max_configs and args.max_configs > 0:
        grid = grid[: args.max_configs]

    all_pp: list[dict[str, Any]] = []
    all_br: list[dict[str, Any]] = []

    grid_manifest: list[dict[str, Any]] = []
    for row in grid:
        _dig = _param_digest(dict(row) | {"trend": args.trend, "min_adv20": float(args.min_adv20)})
        grid_manifest.append(
            {
                "param_set_id": _dig,
                "param_human_key": _param_human_key(row, args.trend, float(args.min_adv20)),
                "params": dict(row),
            }
        )

    # Per-symbol cache: (bd, min_d, max_d, min_p, max_dp) -> (bh, bl, piv, cand bool array)
    geom_cache: dict[tuple[Any, ...], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}

    for row in grid:
        cfg = {
            **row,
            "trend": args.trend,
            "min_adv20": float(args.min_adv20),
        }
        pid = _param_digest(
            {k: cfg[k] for k in row}
            | {"trend": args.trend, "min_adv20": float(args.min_adv20)}
        )
        cfg["param_set_id"] = pid
        cfg["param_human_key"] = _param_human_key(row, args.trend, float(args.min_adv20))
        ec = EventConfig(
            base_days=int(cfg["base_days"]),
            min_base_depth=float(cfg["min_base_depth"]),
            max_base_depth=float(cfg["max_base_depth"]),
            min_base_pos=float(cfg["min_base_pos"]),
            max_dist_pivot=float(cfg["max_dist_pivot"]),
            anti_drift_mode=int(cfg["anti_drift_mode"]),
            pp_bucket=str(cfg["pp_bucket"]),
            entry_buffer=float(cfg["entry_buffer"]),
            breakout_vol_family=str(cfg["breakout_vol_family"]),
            breakout_vol_mult=float(cfg["breakout_vol_mult"]),
            grace_bars=int(args.grace_bars),
            invalidation_buffer=float(args.invalidation_buffer),
        )

        for sym in syms:
            if sym not in data:
                continue
            d0 = data[sym].sort_values("date")
            d0 = d0[d0["date"] >= start]
            d0 = _pick_analysis_regime(d0)
            if len(d0) < 400:
                continue
            ed0 = _add_core_features(d0, bench_ret)
            ed = enrich_event_study_columns(ed0).reset_index(drop=True)
            n = len(ed)
            close = ed["close"].to_numpy(dtype=float)
            high = ed["high"].to_numpy(dtype=float)
            low = ed["low"].to_numpy(dtype=float)
            open_ = ed["open"].to_numpy(dtype=float)
            vol = ed["volume"].to_numpy(dtype=float)
            vol_sma20 = ed["vol_sma20"].to_numpy(dtype=float)
            vol_sma50 = ed["vol_sma50"].to_numpy(dtype=float)
            vpr = ed["vol_pct_rank_50_prior"].to_numpy(dtype=float)
            pp = ed["pocket_pivot"].to_numpy()
            ma20 = ed["ma20"].to_numpy(dtype=float)
            ma50 = ed["ma50"].to_numpy(dtype=float)
            adv20 = ed["adv20"].to_numpy(dtype=float)
            dates = ed["date"].to_numpy()
            trend_ok = _trend_series(args.trend, ed).to_numpy()

            bd = ec.base_days
            gkey = (sym, bd, ec.min_base_depth, ec.max_base_depth, ec.min_base_pos, ec.max_dist_pivot)
            if gkey not in geom_cache:
                bh, bl, piv = rolling_base_arrays(high, low, close, bd)
                cand = compute_candidate_mask(
                    close,
                    bh,
                    bl,
                    piv,
                    ec.min_base_depth,
                    ec.max_base_depth,
                    ec.min_base_pos,
                    ec.max_dist_pivot,
                )
                geom_cache[gkey] = (bh, bl, piv, cand)
            bh, bl, piv, cand = geom_cache[gkey]
            start_i = bd + 5
            end_i = n - 25

            raw_pp, raw_br = collect_pp_and_breakout_events(
                close=close,
                high=high,
                low=low,
                open_=open_,
                vol=vol,
                vol_sma20=vol_sma20,
                vol_sma50=vol_sma50,
                vol_pct_rank=vpr,
                pp=pp,
                candidate=cand,
                base_high=bh,
                base_low=bl,
                pivot=piv,
                ma20=ma20,
                ma50=ma50,
                adv20=adv20,
                min_adv20=float(args.min_adv20),
                trend_ok=trend_ok,
                cfg=ec,
                dates=dates,
                symbol=sym,
                start_i=start_i,
                end_i=end_i,
                param_set_id=pid,
            )
            all_pp.extend(_finalize_rows(raw_pp, ed, cfg, splits, "pp"))
            all_br.extend(_finalize_rows(raw_br, ed, cfg, splits, "breakout"))

    out_root = REPO / args.out_dir
    out_root.mkdir(parents=True, exist_ok=True)

    pp_df = pd.DataFrame(all_pp)
    br_df = pd.DataFrame(all_br)
    n_pp_rows, n_br_rows = len(pp_df), len(br_df)
    pp_df.to_csv(out_root / "events_pp.csv", index=False)
    br_df.to_csv(out_root / "events_breakout.csv", index=False)

    combined_slim = _slim_for_summary(pp_df, br_df)
    del all_pp, all_br, pp_df, br_df
    gc.collect()

    if not combined_slim.empty:
        summ = _summarize_block(combined_slim, _SUMMARY_GROUP_COLS)
        summ.to_csv(out_root / "summary_by_bucket.csv", index=False)

        oos = combined_slim[combined_slim["wf_fold"] == "oos"].copy()
        del combined_slim
        gc.collect()
        rob_rows = []
        for pid, sub in oos.groupby("param_set_id"):
            exp_by_split = sub.groupby("wf_split_id")["ret_10d"].apply(_expectancy)
            vals = exp_by_split.dropna().tolist()
            pos = int((exp_by_split > 0).sum()) if len(exp_by_split) else 0
            med = float(np.nanmedian(vals)) if vals else float("nan")
            worst = float(np.nanmin(vals)) if vals else float("nan")
            score = (pos / max(1, len(exp_by_split))) * 40.0 + max(-30.0, min(30.0, med * 400.0))
            rob_rows.append(
                {
                    "param_set_id": pid,
                    "n_oos": len(sub),
                    "n_splits_with_oos": int(exp_by_split.notna().sum()),
                    "positive_splits_count": pos,
                    "median_expectancy_10_oos": med,
                    "worst_split_expectancy_10": worst,
                    "robustness_score": score,
                }
            )
        rob_df = pd.DataFrame(rob_rows)
        if not rob_df.empty:
            rob_df = rob_df.sort_values("robustness_score", ascending=False)
        rob_df.to_csv(out_root / "summary_oos_robustness.csv", index=False)

        top_md = ["# Top configs (OOS robustness heuristic)", "", "Not investment advice; research ranking only.", ""]
        man_by_id = {m["param_set_id"]: m for m in grid_manifest}
        if not rob_df.empty:
            for _, r in rob_df.head(20).iterrows():
                pid = str(r["param_set_id"])
                hk = man_by_id.get(pid, {}).get("param_human_key", "?")
                top_md.append(
                    f"- `{pid}` `{hk}` — n_oos={int(r['n_oos'])} pos_splits={int(r['positive_splits_count'])} "
                    f"med_exp10={r['median_expectancy_10_oos']:.4f} worst={r['worst_split_expectancy_10']:.4f} "
                    f"score={r['robustness_score']:.2f}"
                )
        (out_root / "top_configs.md").write_text("\n".join(top_md) + "\n", encoding="utf-8")
    else:
        pd.DataFrame().to_csv(out_root / "summary_by_bucket.csv", index=False)
        pd.DataFrame().to_csv(out_root / "summary_oos_robustness.csv", index=False)
        (out_root / "top_configs.md").write_text("# No events\n", encoding="utf-8")

    meta = {
        "cli": vars(args),
        "grid_profile": args.grid_profile,
        "grid_size": len(grid),
        "grace_bars": args.grace_bars,
        "invalidation_buffer": args.invalidation_buffer,
        "param_set_ids": [m["param_set_id"] for m in grid_manifest],
        "grid_manifest": grid_manifest,
        "walkforward_splits": [s.split_id for s in splits],
    }
    (out_root / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    readme = "\n".join(
        [
            "# Base / PP / breakout robust event study (v1)",
            "",
            "## What this is",
            "- Descriptive event study on local OHLCV; **not** a claim of profitability or alpha.",
            "- **OOS** = validation window of an expanding walk-forward split; **train** = prior train window for that split.",
            "- Each event is duplicated once per split where its `signal_date` falls in that split's train **or** val window.",
            "",
            "## Entry semantics",
            "- Fill at **next open** after signal close (`entry_i = signal_i + 1`).",
            "",
            "## base_id and PP rung",
            "- `base_id` increments when rolling geometry `candidate` turns on after being off.",
            "- `pp_rung_in_base` counts pocket-pivot **days** inside the same base segment (1st PP = 1, …).",
            "- Segment ends on: invalidation (close vs rolling base low), confirmed breakout, or candidate off > grace bars.",
            "",
            "## Anti-drift modes",
            "- 0 off; 1 close>close20d; 2 adds ma20 rising 10d; 3 adds close>ma20 and ma20>ma50.",
            "",
            "## Scores",
            "- `base_quality_score` (0–100): depth/pos/dist + contraction + dry-up + tightness + repair proxy.",
            "- `entry_quality_score` (0–100): PP or breakout specific sub-scores (see `event_study_scores.py`).",
            "- `combined_research_score`: explicit secondary blend 0.55*base + 0.45*entry (sorting only).",
            "",
            "## Grids",
            "- `smoke`: 2 configs from reduced phase1 slice.",
            "- `phase1`: reduced Cartesian = **162** configs (3 base_days × 3 anti × 3 pp × 2 entry × 2 vol family × 3 mult; geometry mid slice fixed).",
            "- `full`: full Cartesian of listed parameter values (can be large).",
            "- `full_plus_pct`: same geometry/PP/anti grid as `full` but only `pct50` vol family; `breakout_vol_mult` is **min prior-50 volume rank** in [0.75, 0.80] (see `breakout_volume_ok`).",
            "- `--grid-file path.json`: run an explicit list of rows (used by closed-loop phase-2).",
            "",
            "## Assumptions / limitations",
            "- Survivorship, regime splits in CSVs, and liquidity filters apply.",
            "- `robustness_score` is an **ad hoc** OOS blend for ranking — not a statistical test.",
            "- Use `full_plus_pct` to append pct50 rank-threshold configs to the full SMA grid.",
            "- Summaries use a **slim** copy (group keys + return columns only) so large grids do not OOM during `groupby`.",
        ]
    )
    (out_root / "README.md").write_text(readme + "\n", encoding="utf-8")

    print(f"Wrote outputs under: {out_root.resolve()}")
    print(f"events_pp rows={n_pp_rows} events_breakout rows={n_br_rows} configs={len(grid)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
