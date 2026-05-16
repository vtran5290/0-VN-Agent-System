"""
Near-entry window optimisation.

For each OOS-validated config (A3 PRIMARY, S3 SHADOW), simulates "delayed
entry" at T+k bars after the signal bar. Measures how return and hit-rate
degrade as price drifts away from the original signal close.

Method
------
For every trade (signal at T, entry_price P0, gross_return G):
  approximate_exit_value = P0 * (1 + G + COST)   # same exit, different entry
  for delay k in DELAYS:
    P_k = close[T + k business days for this symbol]
    pct_drift   = (P_k - P0) / P0
    delayed_net = (exit_val / P_k - 1) - COST

Then bucket by pct_drift and by delay to find:
  - At what drift does hit-rate drop >= 10pp below baseline?
  - At what drift does mean net return drop below 50 % of baseline?
  - Recommended asymmetric window: [down_floor, up_cap]

Output
------
  data/research/optimization/nearentry_opt.csv
  data/research/optimization/nearentry_summary.md

Usage
-----
  python pp_backtest/run_nearentry_opt.py
  python pp_backtest/run_nearentry_opt.py --candidates primary
  python pp_backtest/run_nearentry_opt.py --max-symbols 40
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pp_backtest.candidate_strategy_manifest import PRIMARY, SHADOW
from pp_backtest.ema_portfolio_sim import compute_all_trades_v2
from pp_backtest.run_optimization import COST, EX_VIN3_EXCLUDE, OUT_DIR, load_panel

OUT_CSV = os.path.join(OUT_DIR, "nearentry_opt.csv")
OUT_MD  = os.path.join(OUT_DIR, "nearentry_summary.md")

EXIT_18_25 = {
    "tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5,
    "trail_basis": "close", "derisk_bars": None, "derisk_mult": None, "max_hold": 250,
}
EXIT_18_35 = {**EXIT_18_25, "trail_mult": 3.5}

CANDIDATES = {
    "A3_primary": {
        "strat":    {**PRIMARY},
        "exit_cfg": EXIT_18_25,
        "universe": "ex_vin3",
        "label":    "A3_primary",
    },
    "S3_shadow": {
        "strat":    {**SHADOW},
        "exit_cfg": EXIT_18_35,
        "universe": "full",
        "label":    "S3_shadow",
    },
}

# Delays to test (in trading bars after signal bar)
DELAYS = [1, 2, 3, 5, 7, 10, 15]

# Drift buckets for binning: edges in percentage points
# e.g. bucket (-inf, -12], (-12,-10], ..., (10,12], (12, +inf)
DRIFT_EDGES_PCT = [-14, -12, -10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 14]


def _bucket_label(lo: float | None, hi: float | None) -> str:
    if lo is None:
        return f"<{hi:+.0f}%"
    if hi is None:
        return f">{lo:+.0f}%"
    return f"[{lo:+.0f}%,{hi:+.0f}%)"


def _drift_buckets(edges_pct: list[float]) -> list[tuple[float | None, float | None, str]]:
    edges = [e / 100 for e in edges_pct]
    buckets: list[tuple] = [(None, edges[0], _bucket_label(None, edges_pct[0]))]
    for i in range(len(edges) - 1):
        buckets.append((edges[i], edges[i + 1], _bucket_label(edges_pct[i], edges_pct[i + 1])))
    buckets.append((edges[-1], None, _bucket_label(edges_pct[-1], None)))
    return buckets


def _assign_bucket(v: float, buckets: list[tuple]) -> str:
    for lo, hi, lbl in buckets:
        if (lo is None or v >= lo) and (hi is None or v < hi):
            return lbl
    return "other"


def _analyse_candidate(
    trades_df: pd.DataFrame,
    panel: pd.DataFrame,
    cost: float,
    delays: list[int],
    buckets: list[tuple],
) -> pd.DataFrame:
    """
    For each trade simulate delayed entry at T+k and return a flat record per
    (trade, delay) with pct_drift and delayed_net.
    """
    # Build per-symbol date-indexed close series
    sym_close: dict[str, pd.Series] = {}
    for sym, sdf in panel.groupby("symbol", sort=False):
        s = (sdf.sort_values("date")
               .set_index("date")["close"]
               .astype(float))
        sym_close[sym] = s

    records: list[dict] = []
    n_skip = 0

    for _, tr in trades_df.iterrows():
        sym         = str(tr["symbol"])
        entry_price = float(tr["entry_price"])
        gross       = float(tr["gross_return"])
        entry_date  = pd.Timestamp(tr["entry_date"])

        if sym not in sym_close or entry_price <= 0:
            n_skip += 1
            continue

        cs = sym_close[sym]
        # approximate exit value under same-exit assumption
        exit_val = entry_price * (1.0 + gross + cost)
        orig_net = gross - cost

        future_dates = cs.index[cs.index > entry_date]
        max_k = len(future_dates)

        for delay in delays:
            if delay > max_k:
                break
            delayed_date  = future_dates[delay - 1]
            delayed_close = float(cs.loc[delayed_date])
            if delayed_close <= 0:
                continue

            pct_drift   = (delayed_close - entry_price) / entry_price
            delayed_net = (exit_val / delayed_close - 1.0) - cost

            records.append({
                "delay":       delay,
                "pct_drift":   pct_drift,
                "bucket":      _assign_bucket(pct_drift, buckets),
                "delayed_net": delayed_net,
                "orig_net":    orig_net,
                "hit":         int(delayed_net > 0),
                "orig_hit":    int(orig_net > 0),
            })

    if n_skip:
        print(f"    Skipped {n_skip} trades (symbol not in panel or zero entry price)")
    return pd.DataFrame(records)


def _summarise_by_drift(df: pd.DataFrame, orig_hit: float, orig_mean: float,
                        hit_drop_thresh: float = 0.10,
                        return_drop_frac: float = 0.50) -> pd.DataFrame:
    """Aggregate by bucket; flag where hit-rate or return degrades materially."""
    agg = (df.groupby("bucket", sort=False)
             .agg(n=("delayed_net", "count"),
                  mean_net=("delayed_net", "mean"),
                  hit_rate=("hit", "mean"),
                  pct_drift_mean=("pct_drift", "mean"),
                  pct_drift_median=("pct_drift", "median"))
             .reset_index())
    agg["hit_drop"]    = orig_hit  - agg["hit_rate"]
    agg["ret_vs_orig"] = agg["mean_net"] / orig_mean if orig_mean > 0 else np.nan
    agg["flag_hit"]    = agg["hit_drop"]    > hit_drop_thresh
    agg["flag_ret"]    = agg["ret_vs_orig"] < return_drop_frac
    return agg


def _summarise_by_delay(df: pd.DataFrame) -> pd.DataFrame:
    agg = (df.groupby("delay", sort=True)
             .agg(n=("delayed_net", "count"),
                  mean_net=("delayed_net", "mean"),
                  hit_rate=("hit", "mean"),
                  pct_drift_mean=("pct_drift", "mean"))
             .reset_index())
    return agg


def _recommend_window(drift_df: pd.DataFrame,
                      orig_hit: float,
                      orig_mean: float) -> tuple[float, float, str]:
    """
    Return (down_floor_pct, up_cap_pct, rationale) as % values.
    Rule: find tightest symmetric bound where both hit-rate and return are
    still >= 80% of baseline. If asymmetric, report both sides separately.
    """
    HIT_MIN  = orig_hit   * 0.90
    RET_MIN  = orig_mean  * 0.50 if orig_mean > 0 else -np.inf

    # Sort buckets by drift_mean
    df = drift_df.copy()
    df = df[df["n"] >= 10]  # ignore thin buckets
    df = df.sort_values("pct_drift_mean")

    # Upside: max drift where hit >= HIT_MIN and mean_net >= RET_MIN
    up_ok = df[(df["pct_drift_mean"] > 0)
               & (df["hit_rate"] >= HIT_MIN)
               & (df["mean_net"]  >= RET_MIN)]
    up_cap = float(up_ok["pct_drift_mean"].max()) if not up_ok.empty else 0.0

    # Downside: min drift (most negative) where conditions still hold
    dn_ok = df[(df["pct_drift_mean"] < 0)
               & (df["hit_rate"] >= HIT_MIN)
               & (df["mean_net"]  >= RET_MIN)]
    dn_floor = float(dn_ok["pct_drift_mean"].min()) if not dn_ok.empty else 0.0

    up_cap_pct  = round(up_cap  * 100, 1)
    dn_floor_pct = round(dn_floor * 100, 1)

    rationale = (
        f"hit_rate threshold >= {HIT_MIN:.1%}  "
        f"| mean_net threshold >= {RET_MIN:.2%}  "
        f"| upside cap {up_cap_pct:+.1f}%  "
        f"| downside floor {dn_floor_pct:+.1f}%"
    )
    return dn_floor_pct, up_cap_pct, rationale


def _write_summary(all_results: list[dict]) -> None:
    lines: list[str] = []
    lines.append("# Near-Entry Window Optimisation\n\n")
    lines.append(
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}  "
        f"| Current default: +/-7%\n\n"
    )
    lines.append(
        "> **Method**: For each historical trade, simulate delayed entry at T+k bars\n"
        "> at the actual close price. Exit is approximated as the original trade's\n"
        "> exit value (same-exit simplification). Reports return and hit-rate by\n"
        "> price-drift bucket and by delay.\n\n"
    )

    for res in all_results:
        cname   = res["label"]
        bsl_hit = res["baseline_hit"]
        bsl_net = res["baseline_mean"]
        drift   = res["drift_df"]
        delay_  = res["delay_df"]
        dn, up, rat = res["recommendation"]

        lines.append(f"## {cname}\n\n")
        lines.append(
            f"**Baseline** (original entry):  "
            f"mean net={bsl_net:.2%}  hit-rate={bsl_hit:.1%}  "
            f"N={res['n_trades']:,}\n\n"
        )
        lines.append(f"**Recommendation**: down_floor={dn:+.1f}%  up_cap={up:+.1f}%\n")
        lines.append(f"*{rat}*\n\n")

        # Current default assessment
        cur_up_bucket = drift[drift["pct_drift_mean"].between(0.04, 0.09)]
        if not cur_up_bucket.empty:
            cur_hit = cur_up_bucket["hit_rate"].mean()
            cur_ret = cur_up_bucket["mean_net"].mean()
            lines.append(
                f"**Current +7% cap assessment**: "
                f"buckets [+4%,+8%) avg hit={cur_hit:.1%}  avg net={cur_ret:.2%}  "
                f"(baseline hit={bsl_hit:.1%}  net={bsl_net:.2%})\n\n"
            )

        # Drift table
        drift_show = drift.copy()
        drift_show["mean_net"]  = drift_show["mean_net"].map(lambda x: f"{x:.2%}")
        drift_show["hit_rate"]  = drift_show["hit_rate"].map(lambda x: f"{x:.1%}")
        drift_show["hit_drop"]  = drift_show["hit_drop"].map(lambda x: f"{x:+.1%}")
        drift_show["ret_vs_orig"] = drift_show["ret_vs_orig"].map(
            lambda x: f"{x:.2f}x" if np.isfinite(x) else "n/a"
        )
        drift_show["flag"] = drift_show.apply(
            lambda r: "WARN" if (res["drift_df"].loc[r.name, "flag_hit"]
                                  or res["drift_df"].loc[r.name, "flag_ret"]) else "", axis=1
        )
        cols = ["bucket", "n", "pct_drift_median", "mean_net", "hit_rate",
                "hit_drop", "ret_vs_orig", "flag"]
        lines.append("### Return by drift bucket (all delays pooled)\n\n")
        lines.append(drift_show[cols].to_markdown(index=False, floatfmt=".4f") + "\n\n")

        # Delay table
        delay_show = delay_.copy()
        delay_show["mean_net"] = delay_show["mean_net"].map(lambda x: f"{x:.2%}")
        delay_show["hit_rate"] = delay_show["hit_rate"].map(lambda x: f"{x:.1%}")
        delay_show["pct_drift_mean"] = delay_show["pct_drift_mean"].map(
            lambda x: f"{x:+.1%}"
        )
        lines.append("### Return by delay (bars after signal)\n\n")
        lines.append(delay_show.to_markdown(index=False) + "\n\n")

    lines.append("---\n\n*End of Near-Entry Window Optimisation*\n")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Saved summary -> {OUT_MD}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Near-entry window optimisation")
    ap.add_argument(
        "--candidates", choices=["primary", "shadow", "both"], default="both"
    )
    ap.add_argument("--max-symbols", type=int, default=None)
    args = ap.parse_args()

    cands_to_run = {
        k: v for k, v in CANDIDATES.items()
        if args.candidates == "both"
        or (args.candidates == "primary" and "primary" in k)
        or (args.candidates == "shadow"  and "shadow"  in k)
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    panel = load_panel(args.max_symbols)

    buckets = _drift_buckets(DRIFT_EDGES_PCT)

    all_records: list[dict] = []
    all_results: list[dict] = []

    for ckey, cand in cands_to_run.items():
        universe    = cand["universe"]
        all_syms    = sorted(panel["symbol"].unique())
        symbols     = ([s for s in all_syms if s not in EX_VIN3_EXCLUDE]
                       if universe == "ex_vin3" else all_syms)
        strat       = cand["strat"]

        print(f"\n{'='*65}")
        print(f"CANDIDATE: {cand['label']}  universe={universe}")
        print(f"{'='*65}")

        t1 = time.time()
        trades = compute_all_trades_v2(
            panel, symbols,
            entry_type=strat["entry_type"],
            ema_fast=strat["ema_fast"],
            ema_slow=strat["ema_slow"],
            exit_cfg=cand["exit_cfg"],
            cost=COST,
        )
        print(f"  Trades: {len(trades):,}  ({time.time()-t1:.0f}s)")

        if trades.empty:
            print("  No trades - skipping.")
            continue

        print(f"  Analysing delayed entries (delays={DELAYS}) ...")
        t2 = time.time()
        df = _analyse_candidate(trades, panel, COST, DELAYS, buckets)
        print(f"  Records: {len(df):,}  ({time.time()-t2:.0f}s)")

        if df.empty:
            continue

        bsl_hit  = float(trades["net_return"].gt(0).mean())
        bsl_mean = float(trades["net_return"].mean())

        drift_df = _summarise_by_drift(df, bsl_hit, bsl_mean)
        delay_df = _summarise_by_delay(df)
        dn, up, rat = _recommend_window(drift_df, bsl_hit, bsl_mean)

        # Print quick table
        print(f"\n  Baseline: mean_net={bsl_mean:.2%}  hit={bsl_hit:.1%}")
        print(f"  Recommendation: down_floor={dn:+.1f}%  up_cap={up:+.1f}%")
        print()
        print(f"  {'Bucket':<18} {'N':>6} {'mean_net':>9} {'hit_rate':>9} "
              f"{'hit_drop':>9} {'ret_x':>7} {'flag'}")
        for _, r in drift_df.sort_values("pct_drift_mean").iterrows():
            flag = "WARN" if (r["flag_hit"] or r["flag_ret"]) else ""
            print(f"  {r['bucket']:<18} {int(r['n']):>6} "
                  f"{r['mean_net']:>9.2%} {r['hit_rate']:>9.1%} "
                  f"{r['hit_drop']:>+9.1%} "
                  f"{r['ret_vs_orig']:>7.2f}x  {flag}")

        print()
        print(f"  {'Delay':>6} {'N':>7} {'mean_net':>9} {'hit_rate':>9} "
              f"{'avg_drift':>10}")
        for _, r in delay_df.iterrows():
            print(f"  {int(r['delay']):>6} {int(r['n']):>7} "
                  f"{r['mean_net']:>9.2%} {r['hit_rate']:>9.1%} "
                  f"{r['pct_drift_mean']:>+10.1%}")

        df["candidate"] = cand["label"]
        all_records.append(df)
        all_results.append({
            "label":         cand["label"],
            "n_trades":      len(trades),
            "baseline_hit":  bsl_hit,
            "baseline_mean": bsl_mean,
            "drift_df":      drift_df,
            "delay_df":      delay_df,
            "recommendation": (dn, up, rat),
        })

    if all_records:
        full_df = pd.concat(all_records, ignore_index=True)
        full_df.to_csv(OUT_CSV, index=False)
        print(f"\nSaved {len(full_df):,} rows -> {OUT_CSV}")
        _write_summary(all_results)

    print(f"\nTotal elapsed: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
