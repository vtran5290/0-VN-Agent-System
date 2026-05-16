"""CLI for VNINDEX distribution v2 study."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.research.vnindex_dist_v2 import anchors as anc
from scripts.research.vnindex_dist_v2 import breadth as br
from scripts.research.vnindex_dist_v2 import decision_table as dt
from scripts.research.vnindex_dist_v2 import random_baseline as rb
from scripts.research.vnindex_dist_v2 import stats_utils as su
from scripts.research.vnindex_dist_v2 import writers as wr
from scripts.research.vnindex_dist_v2.data_io import build_source_meta, load_vnindex_tracked
from scripts.research.vnindex_dist_v2.dist_rule import add_dist_day
from scripts.research.vnindex_low_dist_ex_vin import build_ex_vin_series


def _attach_dist_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    f = add_dist_day(out[["date", "vnindex_close", "vnindex_volume"]].copy(), "vnindex_close", "vnindex_volume")
    out["dist_day_full"] = f["dist_day"].astype(float).values
    e = add_dist_day(out[["date", "close_ex_vin", "volume_ex_vin"]].copy(), "close_ex_vin", "volume_ex_vin")
    out["dist_day_ex"] = e["dist_day"].astype(float).values
    return out


def _horizon_analysis(
    closes: np.ndarray,
    dates: np.ndarray,
    sparse_x: list[int],
    L: int,
    H: int,
    min_spacing: int,
    oos_start: pd.Timestamp | None,
    mc_reps: int,
    spacing_mc_reps: int,
    year_mc_reps: int,
    boot_reps: int,
    rng: np.random.Generator,
) -> dict | None:
    used = anc.anchors_with_valid_horizon(sparse_x, closes, H)
    if not used:
        return None
    rets = anc.forward_returns_at_h(closes, used, H)
    n = int(rets.size)
    wins = int(np.sum(rets > 0))
    wr = wins / n if n else float("nan")
    wlo, whi = su.wilson_ci(wins, n)
    years = np.array([pd.Timestamp(dates[i]).year for i in used], dtype=int)
    boot = su.block_bootstrap_year_mean_median(years, rets, boot_reps, rng)
    pool = rb.eligible_pool(len(closes), L, H, closes)
    mc_iid = rb.mc_random_win_rates(wr, n, pool, closes, H, mc_reps, rng)
    mc_sp = rb.mc_spacing_matched_win_rates(wr, n, pool, closes, H, min_spacing, spacing_mc_reps, rng)
    mc_yr = rb.mc_year_histogram_matched_win_rates(wr, used, dates, pool, closes, H, year_mc_reps, rng)
    out: dict = {
        "kind": "descriptive_empirical_win_rate",
        "n": n,
        "wins": wins,
        "win_rate": wr,
        "wilson_ci95_low": wlo,
        "wilson_ci95_high": whi,
        "forward_return_mean": float(np.mean(rets)),
        "forward_return_median": float(np.median(rets)),
        "block_bootstrap_by_year": boot,
        "random_baseline_iid": mc_iid,
        "random_baseline_spacing_matched": mc_sp,
        "random_baseline_year_histogram_matched": mc_yr,
    }
    if oos_start is not None:
        used_oos = [i for i in used if pd.Timestamp(dates[i]).normalize() >= oos_start.normalize()]
        rets_oos = anc.forward_returns_at_h(closes, used_oos, H) if used_oos else np.array([])
        no = int(rets_oos.size)
        if no > 0:
            wo = int(np.sum(rets_oos > 0))
            wro = wo / no
            wl, wh = su.wilson_ci(wo, no)
            yo = np.array([pd.Timestamp(dates[i]).year for i in used_oos], dtype=int)
            boot_o = su.block_bootstrap_year_mean_median(yo, rets_oos, boot_reps, rng)
            pool_o = rb.eligible_pool(len(closes), L, H, closes)
            out["oos"] = {
                "oos_start": str(oos_start.date()),
                "n": no,
                "wins": wo,
                "win_rate": wro,
                "wilson_ci95_low": wl,
                "wilson_ci95_high": wh,
                "forward_return_mean": float(np.mean(rets_oos)),
                "forward_return_median": float(np.median(rets_oos)),
                "block_bootstrap_by_year": boot_o,
                "random_baseline_iid": rb.mc_random_win_rates(wro, no, pool_o, closes, H, mc_reps, rng),
                "random_baseline_spacing_matched": rb.mc_spacing_matched_win_rates(
                    wro, no, pool_o, closes, H, min_spacing, spacing_mc_reps, rng
                ),
                "random_baseline_year_histogram_matched": rb.mc_year_histogram_matched_win_rates(
                    wro, used_oos, dates, pool_o, closes, H, year_mc_reps, rng
                ),
            }
        else:
            out["oos"] = {"note": "no_anchors_in_oos_window", "oos_start": str(oos_start.date())}
    return out


def _verify_baseline(path: Path, n_full: int, n_ex: int, dates: list[str]) -> None:
    j = json.loads(path.read_text(encoding="utf-8"))
    exp_f = j["distribution_counts_in_window"]["vnindex_full_cap_weighted"]
    exp_e = j["distribution_counts_in_window"]["synthetic_ex_vin_VIC_VHM_VRE"]
    if n_full != exp_f or n_ex != exp_e:
        raise SystemExit(
            f"--verify-baseline mismatch: counts full={n_full} (exp {exp_f}), ex={n_ex} (exp {exp_e})"
        )
    exp_dates = set(j["distribution_counts_in_window"]["distribution_dates_common_calendar"])
    if set(dates) != exp_dates:
        raise SystemExit(f"--verify-baseline mismatch dates: got {sorted(dates)} exp {sorted(exp_dates)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="VNINDEX distribution regime v2 (reproducibility + baselines)")
    ap.add_argument("--end", required=True)
    ap.add_argument("--start-window", required=True, help="Inclusive window start YYYY-MM-DD")
    ap.add_argument("--history-start", default="2012-01-01")
    ap.add_argument("--min-anchor-spacing", type=int, default=20)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--oos-start", default=None, help="Optional OOS split: anchor_date >= this")
    ap.add_argument("--mc-reps", type=int, default=1000, help="IID random baseline reps")
    ap.add_argument("--spacing-mc-reps", type=int, default=5000, help="Spacing-matched random baseline reps")
    ap.add_argument("--year-block-mc-reps", type=int, default=5000, help="Year-histogram-matched random baseline reps")
    ap.add_argument("--bootstrap-reps", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verify-baseline", type=str, default=None, help="Path to RESULTS_BASELINE.json")
    ap.add_argument(
        "--breadth-watchlist",
        type=str,
        default=None,
        help="Symbols file for breadth (default: config/watchlist.txt)",
    )
    ap.add_argument("--skip-breadth", action="store_true", help="Do not compute watchlist breadth")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    vn_merged, vmeta = load_vnindex_tracked(args.end, args.offline)
    source_meta = build_source_meta(args.end, args.offline, vmeta)

    ex_raw = build_ex_vin_series(
        args.end,
        offline=args.offline,
        preloaded_vnindex=vn_merged,
    )
    hist = pd.Timestamp(args.history_start)
    df = ex_raw[ex_raw["date"] >= hist].reset_index(drop=True)
    df = _attach_dist_columns(df)
    n = len(df)
    last_i = n - 1
    dates_np = df["date"].values
    master_dates = pd.DatetimeIndex(df["date"])
    closes_full = df["vnindex_close"].astype(float).values
    closes_ex = df["close_ex_vin"].astype(float).values
    dist_full = df["dist_day_full"].astype(float).values
    dist_ex = df["dist_day_ex"].astype(float).values

    win_start = pd.Timestamp(args.start_window)
    win_end = pd.Timestamp(args.end)
    win = df[(df["date"] >= win_start) & (df["date"] <= win_end)].reset_index(drop=True)
    actual_L = int(len(win))
    obs_full = int(win["dist_day_full"].fillna(0).sum())
    obs_ex = int(win["dist_day_ex"].fillna(0).sum())
    dist_rows_full = win.loc[win["dist_day_full"] == 1, "date"].dt.strftime("%Y-%m-%d").tolist()
    dist_rows_ex = win.loc[win["dist_day_ex"] == 1, "date"].dt.strftime("%Y-%m-%d").tolist()

    if args.verify_baseline:
        if set(dist_rows_full) != set(dist_rows_ex):
            raise SystemExit("--verify-baseline: full vs ex dist dates differ; investigate data.")
        _verify_baseline(Path(args.verify_baseline), obs_full, obs_ex, dist_rows_full)

    oos_ts = pd.Timestamp(args.oos_start) if args.oos_start else None

    forks = [
        ("strict_le1_full_dist", dist_full, 1, "full_dist"),
        ("matched_density_full_dist_hypothesis_fork", dist_full, obs_full, "full_dist"),
        ("strict_le1_ex_vin_dist", dist_ex, 1, "ex_vin_dist"),
        ("matched_density_ex_vin_dist_hypothesis_fork", dist_ex, obs_ex, "ex_vin_dist"),
    ]

    summary: dict = {
        "meta": {
            **source_meta,
            "actual_last_bar_date": str(pd.Timestamp(df["date"].max()).date()),
            "window_start": args.start_window,
            "window_end": args.end,
            "actual_L_trading_days": actual_L,
            "history_start": args.history_start,
            "min_anchor_spacing": args.min_anchor_spacing,
            "mc_reps_iid": args.mc_reps,
            "spacing_mc_reps": args.spacing_mc_reps,
            "year_block_mc_reps": args.year_block_mc_reps,
            "bootstrap_reps": args.bootstrap_reps,
            "seed": args.seed,
            "horizons": list(anc.HORIZONS_V2),
            "ex_vin_non_tradable_synthetic": True,
            "vin_basket_symbols": ["VIC", "VHM", "VRE"],
            "vpl_excluded": True,
            "disclosure": (
                "ex-VIN is a derived non-tradable synthetic level; see docs/research/VIN_EMA_CLOUD_BASELINE.md "
                "for dual reporting and VNINDEX cap-weight caveats 2025–2026."
            ),
        },
        "distribution_window": {
            "distribution_day_rule": "close <= prior_close * (1 - 0.002) AND volume > prior_volume",
            "distribution_days_full_vnindex": obs_full,
            "distribution_days_ex_vin": obs_ex,
            "distribution_dates_full": dist_rows_full,
            "distribution_dates_ex_vin": dist_rows_ex,
        },
        "regime_forks": {},
        "decision_table": [],
        "breadth": {"available": False, "note": "skipped_or_missing"},
    }

    anchor_rows: list[dict] = []
    decision_rows: list[dict] = []
    sparse_matched_full: list[int] = []

    for fork_name, dist_arr, thresh, sel_label in forks:
        cand = anc.regime_candidates(dist_arr, n, actual_L, thresh)
        sparse = anc.sparse_anchors(cand, args.min_anchor_spacing)
        sparse_x = anc.exclude_last_index(sparse, last_i)
        if fork_name == "matched_density_full_dist_hypothesis_fork":
            sparse_matched_full = list(sparse_x)
        fork_payload: dict = {
            "hypothesis_fork": "matched_density" in fork_name,
            "selection_dist_series": sel_label,
            "max_dist_in_trailing_L": thresh,
            "n_candidates": len(cand),
            "n_sparse_excl_last_bar": len(sparse_x),
            "horizons": {},
        }
        for H in anc.HORIZONS_V2:
            hp: dict = {}
            for tgt_name, closes in (("vnindex_full_forward", closes_full), ("synthetic_ex_vin_forward", closes_ex)):
                block = _horizon_analysis(
                    closes,
                    dates_np,
                    sparse_x,
                    actual_L,
                    H,
                    args.min_anchor_spacing,
                    oos_ts,
                    args.mc_reps,
                    args.spacing_mc_reps,
                    args.year_block_mc_reps,
                    args.bootstrap_reps,
                    rng,
                )
                if block:
                    hp[tgt_name] = block
                    dr = dt.row_from_block(fork_name, tgt_name, H, block)
                    if dr:
                        decision_rows.append(dr)
            if hp:
                fork_payload["horizons"][f"{H}d"] = hp
        summary["regime_forks"][fork_name] = fork_payload

        for i in sparse_x:
            row: dict = {
                "anchor_date": str(pd.Timestamp(dates_np[i]).date()),
                "regime_fork": fork_name,
                "selected_using": sel_label,
                "dist_sum_in_window": anc.dist_sum_window(dist_arr, i, actual_L),
                "prior_dist_count_percentile_same_series": anc.prior_dist_count_percentile(
                    dist_arr, n, actual_L, i
                ),
                "oos_flag": bool(oos_ts is not None and pd.Timestamp(dates_np[i]).normalize() >= oos_ts.normalize()),
            }
            for H in anc.HORIZONS_V2:
                j = i + H
                for col, closes in (
                    (f"fwd_full_{H}d", closes_full),
                    (f"fwd_ex_vin_{H}d", closes_ex),
                ):
                    if j < n and np.isfinite(closes[i]) and closes[i] > 0 and np.isfinite(closes[j]):
                        row[col] = float(closes[j] / closes[i] - 1.0)
                    else:
                        row[col] = None
            anchor_rows.append(row)

    summary["decision_table"] = decision_rows

    wl_path = Path(args.breadth_watchlist) if args.breadth_watchlist else _REPO / "config" / "watchlist.txt"
    if not args.skip_breadth and wl_path.exists() and sparse_matched_full:
        b = br.compute_breadth_for_anchors(
            _REPO,
            master_dates,
            sparse_matched_full,
            args.end,
            args.offline,
            wl_path,
        )
        summary["breadth"] = b
        if b.get("available") and b.get("full_universe", {}).get("by_anchor"):
            summary["breadth"]["full_universe"]["summary_across_anchors"] = br.summarize_breadth_list(
                b["full_universe"]["by_anchor"]
            )
        if b.get("available") and b.get("ex_vin_universe", {}).get("by_anchor"):
            summary["breadth"]["ex_vin_universe"]["summary_across_anchors"] = br.summarize_breadth_list(
                b["ex_vin_universe"]["by_anchor"]
            )
    elif args.skip_breadth:
        summary["breadth"] = {"available": False, "note": "skipped_by_flag"}
    elif not wl_path.exists():
        summary["breadth"] = {"available": False, "note": f"watchlist_missing:{wl_path}"}

    wr.write_json(summary)
    wr.write_csv(pd.DataFrame(anchor_rows))
    if decision_rows:
        wr.write_decision_csv(pd.DataFrame(decision_rows))
    wr.write_methods_md(_methods_note())
    extra = f"\n{wr.OUT_DECISION_CSV}" if decision_rows else ""
    print(f"Wrote {wr.OUT_JSON}\n{wr.OUT_CSV}{extra}\n{wr.OUT_MD}")


def _methods_note() -> str:
    return """# VNINDEX distribution v2 — methods note

## Purpose

Descriptive event-study statistics for VNINDEX and a **non-tradable synthetic ex-VIN** level (VIC, VHM, VRE; VPL excluded per `docs/research/VIN_EMA_CLOUD_BASELINE.md`). **Not** a calibrated predictive model.

## Distribution day (fixed)

`close <= prior_close * (1 - 0.002)` AND `volume > prior_volume`; valid only when volumes strictly positive.

## Regime forks

- **strict_le1_***: trailing `L` trading days with at most **1** distribution day (same `L` as the current window).
- **matched_density_*** (**hypothesis fork**): trailing `L` with at most the **observed** count of distribution days in the current window (separate threshold for full vs ex-VIN series). This matches today’s density by construction and is **not** the original low-distribution hypothesis.

## Data / reproducibility

- `source_used`: `csv_only` or `csv+fireant` (heuristic: VNINDEX extended past CSV, or any Vin CSV ended before `--end` implying fetch path in `build_ex_vin_series`).
- `--offline` fails fast if CSVs do not reach `--end`.
- Outputs record `actual_last_bar_date` and `actual_L_trading_days`.

## Random baselines

1. **IID** (`random_baseline_iid`): `mc_reps` draws of `n` eligible indices with replacement.
2. **Spacing-matched** (`random_baseline_spacing_matched`): `spacing_mc_reps` draws; each draw is a random **sparse** set of `n` indices from the eligible pool with the same **min_anchor_spacing** in trading-day index space as regime anchors; same horizon survival as the pool definition.
3. **Year-histogram-matched** (`random_baseline_year_histogram_matched`): `year_block_mc_reps` draws; each draw samples the same count of anchors per **calendar year** as the conditional anchor set, uniformly from pool dates in that year (without replacement within the year).

## Decision table (`vnindex_dist_v2_decision_table.csv`)

Heuristic `conclusion` enum (uses **spacing-matched** median and p-value): `strong_short_term_edge` (horizons 25–50d only), `weak_or_inconclusive`, `no_edge_vs_baseline`. Not investment advice.

## Breadth (optional)

If `config/watchlist.txt` (or `--breadth-watchlist`) exists and `--skip-breadth` is not set: for **matched_density_full_dist** anchors, report % above EMA50, median 20d forward return across loaded names, and 1d advance fraction — for full watchlist and ex-VIN subset (drop VIC/VHM/VRE).

## OOS

If `--oos-start` is set, `oos` blocks restrict to anchors on/after that date; regime labels still use only past prices by construction (trailing window).

## Run

`python scripts/research/run_vnindex_dist_v2.py --end YYYY-MM-DD --start-window YYYY-MM-DD [--offline] [--oos-start ...] [--spacing-mc-reps 5000] [--year-block-mc-reps 5000] [--skip-breadth]`

"""


if __name__ == "__main__":
    main()
