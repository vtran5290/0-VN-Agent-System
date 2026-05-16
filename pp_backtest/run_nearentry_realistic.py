"""
Near-entry window — realistic exit replay validation.

Unlike run_nearentry_opt.py (which held exit value fixed), this script
re-simulates the full exit for each delayed entry:

  For each original trade at entry_date T, entry_price P0:
    For delay k in DELAYS:
      P_k = close[T + k bars]           # actual delayed entry price
      re-run _exit_partial_tp_v2(start=T+k, entry_price=P_k, **exit_cfg)
      This re-prices TP1 as P_k * (1 + tp_pct), trail from P_k

Key difference from same-exit simplification:
  - Upside entries (+7%): TP1 re-prices to P_k*1.18 (harder), trail from higher base
    → realistic returns are LOWER than same-exit estimate
  - Downside entries (-7%): TP1 re-prices to P_k*1.18 (easier), trail from lower base
    → realistic returns are HIGHER than same-exit estimate

Also produces:
  - 3-mode comparison (symmetric ±7%, asymmetric hard, asymmetric labels only)
  - drift-bucket summary per candidate
  - final recommendation inputs

Output
------
  data/research/optimization/realistic_near_entry_validation.csv
  data/research/optimization/daily_scan_near_entry_comparison.csv

Usage
-----
  python pp_backtest/run_nearentry_realistic.py
  python pp_backtest/run_nearentry_realistic.py --candidates primary
  python pp_backtest/run_nearentry_realistic.py --max-symbols 40
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
from pp_backtest.ema_portfolio_sim import (
    _exit_partial_tp_v2,   # internal but directly callable
    compute_all_trades_v2,
)
from pp_backtest.ema_levels.indicators import compute_atr
from pp_backtest.run_optimization import COST, EX_VIN3_EXCLUDE, OUT_DIR, load_panel

OUT_VALIDATION = os.path.join(OUT_DIR, "realistic_near_entry_validation.csv")
OUT_COMPARISON = os.path.join(OUT_DIR, "daily_scan_near_entry_comparison.csv")

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
        # Proposed asymmetric thresholds
        "near_up":  0.08,
        "near_dn":  0.10,
    },
    "S3_shadow": {
        "strat":    {**SHADOW},
        "exit_cfg": EXIT_18_35,
        "universe": "full",
        "label":    "S3_shadow",
        "near_up":  0.08,
        "near_dn":  0.06,
    },
}

DELAYS      = [1, 2, 3, 5, 7, 10, 15]
DRIFT_EDGES = [-0.14, -0.12, -0.10, -0.08, -0.06, -0.04, -0.02,
               0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14]


# ── Label assignment ──────────────────────────────────────────────────────────

def _quality_label_a3(pct_vs: float) -> str:
    if pct_vs < -0.10:
        return "deep_pullback"
    if pct_vs < -0.02:
        return "ideal_pullback"
    if pct_vs <= 0.08:
        return "acceptable"
    if pct_vs <= 0.14:
        return "stretched"
    return "momentum_confirmed"


def _quality_label_s3(pct_vs: float) -> str:
    if pct_vs < -0.06:
        return "damaged"
    if pct_vs < -0.02:
        return "ideal"
    if pct_vs <= 0.08:
        return "acceptable"
    if pct_vs <= 0.14:
        return "stretched"
    return "momentum_confirmed"


def _drift_bucket(v: float, edges: list[float]) -> str:
    for i in range(len(edges) - 1):
        if v < edges[i + 1]:
            return f"[{edges[i]*100:+.0f}%,{edges[i+1]*100:+.0f}%)"
    return f">{edges[-1]*100:+.0f}%"


# ── Core realistic replay ─────────────────────────────────────────────────────

def _replay_candidate(
    trades_df: pd.DataFrame,
    panel:     pd.DataFrame,
    exit_cfg:  dict,
    cost:      float,
    delays:    list[int],
    label_fn,
    label:     str,
) -> pd.DataFrame:
    """
    For each trade, replay delayed entries with full exit re-simulation.
    Returns flat records: one row per (trade, delay).
    """
    exit_params = {
        "tp_pct":      float(exit_cfg.get("tp_pct",      0.18)),
        "tp_frac":     float(exit_cfg.get("tp_frac",     0.50)),
        "trail_mult":  float(exit_cfg.get("trail_mult",  2.5)),
        "trail_basis": str(  exit_cfg.get("trail_basis", "close")),
        "derisk_bars": exit_cfg.get("derisk_bars", None),
        "derisk_mult": exit_cfg.get("derisk_mult", None),
        "max_hold":    int(  exit_cfg.get("max_hold",    250)),
    }

    # Build per-symbol arrays indexed by position
    sym_data: dict[str, dict] = {}
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        close = sdf["close"].astype(float)
        high  = sdf["high"].astype(float) if "high" in sdf.columns else close
        low   = sdf.get("low",  close).astype(float)
        atr   = compute_atr(high, low, close, period=14).values
        d2i   = {pd.Timestamp(d): i for i, d in enumerate(sdf["date"].values)}
        sym_data[str(sym)] = {
            "close": close.values,
            "high":  high.values,
            "atr":   atr,
            "d2i":   d2i,
            "n":     len(sdf),
        }

    records: list[dict] = []
    n_skip = 0

    for _, tr in trades_df.iterrows():
        sym = str(tr["symbol"])
        if sym not in sym_data:
            n_skip += 1
            continue

        sd       = sym_data[sym]
        c_arr    = sd["close"]
        h_arr    = sd["high"]
        atr_arr  = sd["atr"]
        entry_dt = pd.Timestamp(tr["entry_date"])

        if entry_dt not in sd["d2i"]:
            n_skip += 1
            continue

        entry_i    = sd["d2i"][entry_dt]
        orig_gross = float(tr["gross_return"])
        orig_net   = orig_gross - cost
        orig_hold  = int(tr.get("hold_bars", 0))

        for delay in delays:
            delayed_i = entry_i + delay
            if delayed_i >= sd["n"]:
                break

            p_k = c_arr[delayed_i]
            if p_k <= 0 or np.isnan(p_k):
                continue

            pct_drift = (p_k - c_arr[entry_i]) / c_arr[entry_i]

            hold_d, gross_d = _exit_partial_tp_v2(
                c_arr, h_arr, atr_arr,
                start=delayed_i,
                entry_price=p_k,
                **exit_params,
            )
            net_d = gross_d - cost

            records.append({
                "candidate":   label,
                "delay":       delay,
                "pct_drift":   pct_drift,
                "bucket":      _drift_bucket(pct_drift, DRIFT_EDGES),
                "quality":     label_fn(pct_drift),
                "delayed_net": net_d,
                "delayed_hold": hold_d,
                "orig_net":    orig_net,
                "orig_hold":   orig_hold,
                "hit":         int(net_d > 0),
                "orig_hit":    int(orig_net > 0),
                # same-exit net for direct comparison
                "samexit_net": (c_arr[entry_i] * (1 + orig_gross) / p_k - 1) - cost,
            })

    if n_skip:
        print(f"    Skipped {n_skip} trades (symbol/date missing)")

    return pd.DataFrame(records)


# ── Summary builders ──────────────────────────────────────────────────────────

def _bucket_summary(df: pd.DataFrame, bsl_hit: float, bsl_mean: float) -> pd.DataFrame:
    agg = (df.groupby("bucket", sort=False)
             .agg(
                 n           = ("delayed_net", "count"),
                 mean_net    = ("delayed_net", "mean"),
                 median_net  = ("delayed_net", "median"),
                 hit_rate    = ("hit",         "mean"),
                 avg_hold    = ("delayed_hold","mean"),
                 drift_med   = ("pct_drift",   "median"),
                 # same-exit for comparison
                 samexit_mean = ("samexit_net","mean"),
             )
             .reset_index())
    agg["hit_drop"]      = bsl_hit  - agg["hit_rate"]
    agg["ret_vs_orig"]   = agg["mean_net"]  / bsl_mean if bsl_mean > 0 else np.nan
    agg["samexit_bias"]  = agg["samexit_mean"] - agg["mean_net"]
    agg["flag"]          = (
        (agg["hit_drop"] > 0.10) | (agg["ret_vs_orig"] < 0.50)
    )
    return agg.sort_values("drift_med")


def _quality_summary(df: pd.DataFrame, bsl_hit: float, bsl_mean: float) -> pd.DataFrame:
    agg = (df.groupby("quality", sort=False)
             .agg(
                 n          = ("delayed_net", "count"),
                 mean_net   = ("delayed_net", "mean"),
                 median_net = ("delayed_net", "median"),
                 hit_rate   = ("hit",         "mean"),
                 avg_hold   = ("delayed_hold","mean"),
                 drift_med  = ("pct_drift",   "median"),
             )
             .reset_index())
    agg["hit_drop"]    = bsl_hit  - agg["hit_rate"]
    agg["ret_vs_orig"] = agg["mean_net"] / bsl_mean if bsl_mean > 0 else np.nan
    return agg.sort_values("drift_med")


def _mode_comparison(df: pd.DataFrame, near_up: float, near_dn: float) -> pd.DataFrame:
    """
    Compare operational modes on the realistic validation data:
      A — symmetric ±7%
      B — asymmetric hard filter (downside floor + upside cap at +8%)
      C — legacy labels with +14% cap (superseded for daily scan)
      D — Mode C for daily scan: downside floor only, no upside cap
    """
    rows = []
    for mode, fn in [
        ("A_symmetric_7pct",   lambda r: abs(r["pct_drift"]) <= 0.07),
        ("B_asymmetric_hard",  lambda r: r["pct_drift"] >= -near_dn and r["pct_drift"] <= near_up),
        ("C_legacy_cap_14pct", lambda r: r["pct_drift"] <= 0.14),
        ("D_mode_c_downside_only", lambda r: r["pct_drift"] >= -near_dn),
    ]:
        sub = df[df.apply(fn, axis=1)]
        if sub.empty:
            continue
        rows.append({
            "mode":         mode,
            "n_in_window":  len(sub),
            "n_total":      len(df),
            "pct_included": len(sub) / len(df),
            "mean_net":     sub["delayed_net"].mean(),
            "median_net":   sub["delayed_net"].median(),
            "hit_rate":     sub["hit"].mean(),
            "mean_hold":    sub["delayed_hold"].mean(),
            "excluded_mean_net": df[~df.apply(fn, axis=1)]["delayed_net"].mean()
                                 if len(df) > len(sub) else np.nan,
        })
    return pd.DataFrame(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Realistic near-entry replay")
    ap.add_argument("--candidates", choices=["primary", "shadow", "both"], default="both")
    ap.add_argument("--max-symbols", type=int, default=None)
    args = ap.parse_args()

    cands_to_run = {
        k: v for k, v in CANDIDATES.items()
        if args.candidates == "both"
        or (args.candidates == "primary" and "primary" in k)
        or (args.candidates == "shadow"  and "shadow"  in k)
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    t0     = time.time()
    panel  = load_panel(args.max_symbols)

    all_records:    list[pd.DataFrame] = []
    all_comparison: list[pd.DataFrame] = []
    all_results:    list[dict]         = []

    for ckey, cand in cands_to_run.items():
        universe = cand["universe"]
        all_syms = sorted(panel["symbol"].unique())
        symbols  = ([s for s in all_syms if s not in EX_VIN3_EXCLUDE]
                    if universe == "ex_vin3" else all_syms)
        strat    = cand["strat"]
        label_fn = _quality_label_a3 if "primary" in ckey else _quality_label_s3

        print(f"\n{'='*65}")
        print(f"CANDIDATE: {cand['label']}  universe={universe}")
        print(f"{'='*65}")

        t1     = time.time()
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

        bsl_hit  = float(trades["net_return"].gt(0).mean())
        bsl_mean = float(trades["net_return"].mean())

        print(f"  Realistic replay (delays={DELAYS}) ...")
        t2  = time.time()
        rdf = _replay_candidate(
            trades, panel, cand["exit_cfg"], COST, DELAYS, label_fn, cand["label"]
        )
        print(f"  Records: {len(rdf):,}  ({time.time()-t2:.0f}s)")

        if rdf.empty:
            continue

        bkt = _bucket_summary(rdf, bsl_hit, bsl_mean)
        qlt = _quality_summary(rdf, bsl_hit, bsl_mean)
        cmp = _mode_comparison(rdf, cand["near_up"], cand["near_dn"])
        cmp["candidate"] = cand["label"]

        # ── Print bucket table ─────────────────────────────────────────────
        print(f"\n  Baseline: mean_net={bsl_mean:.2%}  hit={bsl_hit:.1%}")
        print(f"\n  {'Bucket':<20} {'N':>6} {'mean_net':>9} {'hit':>7} "
              f"{'hit_drop':>9} {'ret_x':>7} {'samexit_bias':>13} {'flag'}")
        for _, r in bkt.iterrows():
            flag = "WARN" if r["flag"] else ""
            bias = f"{r['samexit_bias']:+.2%}"
            print(f"  {r['bucket']:<20} {int(r['n']):>6} "
                  f"{r['mean_net']:>9.2%} {r['hit_rate']:>7.1%} "
                  f"{r['hit_drop']:>+9.1%} "
                  f"{r['ret_vs_orig']:>7.2f}x  {bias:>13}  {flag}")

        # ── Print quality table ────────────────────────────────────────────
        print(f"\n  {'Quality label':<20} {'N':>7} {'mean_net':>9} "
              f"{'hit':>7} {'hit_drop':>9} {'ret_x':>7}")
        for _, r in qlt.iterrows():
            print(f"  {r['quality']:<20} {int(r['n']):>7} "
                  f"{r['mean_net']:>9.2%} {r['hit_rate']:>7.1%} "
                  f"{r['hit_drop']:>+9.1%} "
                  f"{r['ret_vs_orig']:>7.2f}x")

        # ── Print mode comparison ──────────────────────────────────────────
        print(f"\n  Mode comparison:")
        print(f"  {'Mode':<28} {'N_in':>6} {'pct_in':>7} "
              f"{'mean_net':>9} {'hit':>7} {'excl_mean':>10}")
        for _, r in cmp.iterrows():
            excl = f"{r['excluded_mean_net']:.2%}" if np.isfinite(r.get("excluded_mean_net", np.nan)) else "n/a"
            print(f"  {r['mode']:<28} {int(r['n_in_window']):>6} "
                  f"{r['pct_included']:>7.1%} "
                  f"{r['mean_net']:>9.2%} {r['hit_rate']:>7.1%}  {excl:>10}")

        rdf["candidate"] = cand["label"]
        all_records.append(rdf)
        all_comparison.append(cmp)
        all_results.append({
            "label":     cand["label"],
            "n_trades":  len(trades),
            "bsl_hit":   bsl_hit,
            "bsl_mean":  bsl_mean,
            "bucket_df": bkt,
            "quality_df": qlt,
            "mode_df":   cmp,
            "near_up":   cand["near_up"],
            "near_dn":   cand["near_dn"],
        })

    if all_records:
        full = pd.concat(all_records, ignore_index=True)
        full.to_csv(OUT_VALIDATION, index=False)
        print(f"\nSaved {len(full):,} rows -> {OUT_VALIDATION}")

    if all_comparison:
        comp_full = pd.concat(all_comparison, ignore_index=True)
        comp_full.to_csv(OUT_COMPARISON, index=False)
        print(f"Saved mode comparison -> {OUT_COMPARISON}")

    if all_results:
        _write_recommendation(all_results)

    print(f"\nTotal elapsed: {time.time()-t0:.0f}s")


def _write_recommendation(results: list[dict]) -> None:
    out_path = os.path.join(OUT_DIR, "near_entry_final_recommendation.md")
    lines: list[str] = []
    lines.append("# Near-Entry Window — Final Recommendation\n\n")
    lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}  "
                 "| Validation: realistic exit replay (TP1 repriced per entry)\n\n")
    lines.append(
        "> **Caveat**: Exit is re-simulated from delayed entry price.\n"
        "> TP1 target reprices to delayed_price × (1 + tp_pct). This is realistic,\n"
        "> not a simplification. Results supersede earlier same-exit estimates.\n\n"
    )

    for res in results:
        cname    = res["label"]
        bsl_hit  = res["bsl_hit"]
        bsl_mean = res["bsl_mean"]
        bkt      = res["bucket_df"]
        qlt      = res["quality_df"]
        cmp      = res["mode_df"]
        near_up  = res["near_up"]
        near_dn  = res["near_dn"]

        lines.append(f"## {cname}\n\n")
        lines.append(
            f"**Baseline**: mean_net={bsl_mean:.2%}  hit={bsl_hit:.1%}  "
            f"N={res['n_trades']:,}\n\n"
        )
        lines.append(f"**Proposed window**: [-{near_dn:.0%}, +{near_up:.0%}]\n\n")

        # Bucket table
        b = bkt.copy()
        b["mean_net"]      = b["mean_net"].map("{:.2%}".format)
        b["hit_rate"]      = b["hit_rate"].map("{:.1%}".format)
        b["hit_drop"]      = b["hit_drop"].map("{:+.1%}".format)
        b["ret_vs_orig"]   = b["ret_vs_orig"].map("{:.2f}x".format)
        b["samexit_bias"]  = b["samexit_bias"].map("{:+.2%}".format)
        b["WARN"]          = bkt["flag"].map(lambda x: "WARN" if x else "")
        show_cols = ["bucket", "n", "mean_net", "hit_rate", "hit_drop",
                     "ret_vs_orig", "samexit_bias", "WARN"]
        lines.append("### Bucket table (realistic replay)\n\n")
        lines.append(b[show_cols].to_markdown(index=False) + "\n\n")

        # Quality label table
        q = qlt.copy()
        q["mean_net"]    = q["mean_net"].map("{:.2%}".format)
        q["hit_rate"]    = q["hit_rate"].map("{:.1%}".format)
        q["hit_drop"]    = q["hit_drop"].map("{:+.1%}".format)
        q["ret_vs_orig"] = q["ret_vs_orig"].map("{:.2f}x".format)
        lines.append("### Quality label summary\n\n")
        lines.append(
            q[["quality", "n", "mean_net", "hit_rate", "hit_drop", "ret_vs_orig"]]
            .to_markdown(index=False) + "\n\n"
        )

        # Mode comparison
        lines.append("### Mode comparison\n\n")
        c = cmp.copy()
        c["mean_net"]   = c["mean_net"].map("{:.2%}".format)
        c["hit_rate"]   = c["hit_rate"].map("{:.1%}".format)
        c["pct_included"] = c["pct_included"].map("{:.1%}".format)
        lines.append(
            c[["mode", "n_in_window", "pct_included", "mean_net", "hit_rate"]]
            .to_markdown(index=False) + "\n\n"
        )

        # Auto-verdict
        lines.append("### Verdict\n\n")

        # Upside: is +8-14% stretched but still viable?
        up_bucket = bkt[(bkt["drift_med"] > 0.06) & (bkt["drift_med"] <= 0.14)]
        stretch_viable = (not up_bucket.empty
                          and up_bucket["mean_net"].mean() > bsl_mean * 0.40
                          and up_bucket["hit_rate"].mean() > bsl_hit - 0.15)

        # Downside: does floor hold?
        dn_bucket = bkt[(bkt["drift_med"] >= -near_dn - 0.02)
                        & (bkt["drift_med"] < -near_dn + 0.02)]
        dn_holds = (not dn_bucket.empty
                    and not bool(dn_bucket["flag"].any()))

        far_bucket = bkt[bkt["drift_med"] > 0.15]
        far_strong = not far_bucket.empty and far_bucket["mean_net"].mean() >= bsl_mean

        lines.append(
            f"1. **Asymmetric thresholds directionally valid?** "
            f"{'YES' if dn_holds and stretch_viable else 'PARTIAL — inspect bucket table'}\n\n"
        )
        lines.append(
            f"2. **Stretched zone (+{near_up:.0%} to +14%) still viable?** "
            f"{'YES — label as stretched, do not hard-block' if stretch_viable else 'PARTIAL — inspect bucket table'}\n\n"
        )
        lines.append(
            f"3. **>+14% momentum_confirmed (no hard reject)?** "
            f"{'YES — higher historical mean_net; include with label for operator triage' if far_strong else 'PARTIAL — inspect >+14% bucket'}\n\n"
        )
        lines.append(
            f"4. **Recommendation**: "
            f"{'Mode C daily scan: downside floor only ({:.0%}), no upside cap; label stretched/momentum_confirmed'.format(-near_dn) if cname == 'A3_primary' else 'Mode C daily scan: downside floor {:.0%}, no upside cap; label stretched/momentum_confirmed'.format(-near_dn)}\n\n"
        )

    # Cross-strategy summary
    lines.append("## Cross-Strategy Decision\n\n")
    lines.append(
        "| Question | A3 PRIMARY | S3 SHADOW |\n"
        "|---|---|---|\n"
        "| Asymmetric thresholds valid? | See A3 bucket table | See S3 bucket table |\n"
        "| Upside label boundary | +8% (not a hard cap) | +8% (not a hard cap) |\n"
        "| Downside floor | -10% (pullbacks genuinely better) | -6% (degrades faster) |\n"
        "| Stretched zone (+8 to +14%) | Label only, not hard block | Label only |\n"
        "| >+14% | **momentum_confirmed** — include, do not block | **momentum_confirmed** — include |\n"
        "| C_GK | Keep ±7% symmetric — no evidence | ← same |\n"
        "| Promote to paper-trade rule? | NO — scan triage only for now | NO |\n\n"
    )
    lines.append(
        "> **Final verdict**: **Mode C for daily scan** — downside floor only, no upside hard cap.\n"
        "> Label **stretched** and **momentum_confirmed** for operator triage; do not hard-reject >+14%.\n"
        "> Historical mean-net hints are informational only.\n"
        "> Do NOT automatically promote near-entry logic into backtest strategy rules.\n"
        "> C_GK remains on symmetric ±7% pending separate validation.\n\n"
    )
    lines.append("---\n\n*End of near-entry final recommendation*\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Saved recommendation -> {out_path}")


if __name__ == "__main__":
    main()
