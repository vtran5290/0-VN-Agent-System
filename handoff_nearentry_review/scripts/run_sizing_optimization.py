"""
Step 3 — Position sizing / portfolio overlays.

Sweeps max_positions x sizing_mode x gross_exposure on the two OOS-validated
configs advancing from the OOS gate:

  PRIMARY (A3): B_cloud20_100 | rank=ema_dist | tp=18%/trail=2.5 | ex_vin3
  SHADOW  (S3): B_cloud21_55  | rank=mom20    | tp=18%/trail=3.5 | full universe

Output: data/research/optimization/sizing_optimization.csv
        data/research/optimization/sizing_summary.md

Usage
-----
    python pp_backtest/run_sizing_optimization.py
    python pp_backtest/run_sizing_optimization.py --candidates primary
    python pp_backtest/run_sizing_optimization.py --max-symbols 40
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
    compute_all_trades_v2,
    build_portfolio_v2,
    portfolio_metrics,
)
from pp_backtest.run_optimization import (
    COST,
    EX_VIN3_EXCLUDE,
    OUT_DIR,
    TEST_START,
    load_panel,
)

OUT_CSV = os.path.join(OUT_DIR, "sizing_optimization.csv")
OUT_MD  = os.path.join(OUT_DIR, "sizing_summary.md")

# ── OOS-validated exit configs ────────────────────────────────────────────────

EXIT_18_25 = {
    "tp_pct": 0.18,
    "tp_frac": 0.50,
    "trail_mult": 2.5,
    "trail_basis": "close",
    "derisk_bars": None,
    "derisk_mult": None,
    "max_hold": 250,
}

EXIT_18_35 = {
    **EXIT_18_25,
    "trail_mult": 3.5,
}

# ── Candidate definitions post-OOS-gate ──────────────────────────────────────

CANDIDATES: dict[str, dict] = {
    "primary_A3": {
        "strat":     {**PRIMARY},
        "rank_mode": "ema_dist",
        "exit_cfg":  EXIT_18_25,
        "universe":  "ex_vin3",
        "label":     "A3_primary",
    },
    "shadow_S3": {
        "strat":     {**SHADOW},
        "rank_mode": "mom20",
        "exit_cfg":  EXIT_18_35,
        "universe":  "full",
        "label":     "S3_shadow",
    },
}

# ── Sizing sweep grid ─────────────────────────────────────────────────────────

MAX_POSITIONS_GRID  = [10, 12, 16, 20, 24]
SIZING_MODES        = ["equal", "inv_atr", "conv_mom60", "inv_atr_conv_mom60"]
GROSS_EXPOSURE_GRID = [0.70, 0.85, 1.00]


def _write_summary(df: pd.DataFrame) -> None:
    lines: list[str] = []
    lines.append("# Sizing Optimization Summary\n")
    lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}\n\n")
    lines.append("> Step 3 — sizing/exposure sweep on OOS-validated configs.\n")
    lines.append("> PRIMARY: A3 (ema_dist + 18%/2.5 + ex_vin3) | "
                 "SHADOW: S3 (mom20 + 18%/3.5 + full)\n\n")

    show_cols = ["candidate", "max_positions", "sizing_mode", "gross_exposure",
                 "cagr", "sharpe", "max_dd", "mar", "fill_util"]

    for cname in df["candidate"].unique():
        sub = df[df["candidate"] == cname].copy()
        lines.append(f"## {cname}\n\n")

        base = sub[(sub["sizing_mode"] == "equal") & (sub["gross_exposure"] == 1.00)]
        lines.append("### Equal-weight / Full-exposure baseline\n\n")
        lines.append(base[show_cols].to_markdown(index=False, floatfmt=".4f") + "\n\n")

        top_sh = sub.sort_values("sharpe", ascending=False).head(10)
        lines.append("### Top 10 by Sharpe\n\n")
        lines.append(top_sh[show_cols].to_markdown(index=False, floatfmt=".4f") + "\n\n")

        top_mar = sub.sort_values("mar", ascending=False).head(8)
        lines.append("### Top 8 by MAR\n\n")
        lines.append(top_mar[show_cols].to_markdown(index=False, floatfmt=".4f") + "\n\n")

        lines.append("### Verdict\n\n")
        best_sh = top_sh.iloc[0]
        # Anchor = OOS-gate config: equal / max_positions=20 / gross=1.00
        anchor = sub[
            (sub["sizing_mode"] == "equal")
            & (sub["max_positions"] == 20)
            & (sub["gross_exposure"] == 1.00)
        ]
        base_row = anchor.iloc[0] if not anchor.empty else (
            base[base["max_positions"] == base["max_positions"].max()].iloc[0]
            if not base.empty else best_sh
        )
        sh_delta = best_sh["sharpe"] - base_row["sharpe"]
        # dd_delta > 0 means DD improved (less severe); < 0 means DD worsened
        dd_delta = best_sh["max_dd"] - base_row["max_dd"]
        lines.append(
            f"Anchor (equal/max_pos=20/gross=1.00): "
            f"Sharpe={base_row['sharpe']:.3f}  maxDD={base_row['max_dd']:.1%}\n\n"
        )
        lines.append(
            f"Best by Sharpe: `sizing_mode={best_sh['sizing_mode']}` "
            f"`max_positions={int(best_sh['max_positions'])}` "
            f"`gross_exposure={best_sh['gross_exposure']:.2f}`  "
            f"Sharpe={best_sh['sharpe']:.3f} ({sh_delta:+.3f} vs anchor)  "
            f"maxDD={best_sh['max_dd']:.1%} ({dd_delta:+.1%} vs anchor)\n\n"
        )
        if sh_delta < 0.05:
            lines.append("> **NEUTRAL** — sizing gain < 0.05 Sharpe vs anchor; equal-weight/20 remains preferred.\n\n")
        elif dd_delta < -0.03:
            lines.append("> **PASS_DD_WARN** — Sharpe improves but DD worsens >3pp. Monitor live.\n\n")
        else:
            lines.append("> **PASS** — sizing upgrade survives: Sharpe improves without DD regression.\n\n")

    lines.append("---\n\n*End of Sizing Summary*\n")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Saved summary -> {OUT_MD}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Step 3 sizing sweep")
    ap.add_argument(
        "--candidates",
        choices=["primary", "shadow", "both"],
        default="both",
        help="Which candidate set to run (default: both)",
    )
    ap.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Limit to N most-liquid symbols (quick validation)",
    )
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

    rows: list[dict] = []
    total = (len(cands_to_run) * len(MAX_POSITIONS_GRID)
             * len(SIZING_MODES) * len(GROSS_EXPOSURE_GRID))
    i = 0

    for ckey, cand in cands_to_run.items():
        universe    = cand["universe"]
        all_symbols = sorted(panel["symbol"].unique())
        symbols     = ([s for s in all_symbols if s not in EX_VIN3_EXCLUDE]
                       if universe == "ex_vin3" else all_symbols)
        strat       = cand["strat"]

        print(f"\n{'='*70}")
        print(f"CANDIDATE: {cand['label']}  rank={cand['rank_mode']}  "
              f"universe={universe}  tp={cand['exit_cfg']['tp_pct']:.0%}/"
              f"{cand['exit_cfg']['trail_mult']}")
        print(f"{'='*70}")

        t_cand = time.time()
        trades = compute_all_trades_v2(
            panel, symbols,
            entry_type=strat["entry_type"],
            ema_fast=strat["ema_fast"],
            ema_slow=strat["ema_slow"],
            exit_cfg=cand["exit_cfg"],
            cost=COST,
        )
        print(f"  Trades computed: {len(trades):,}  ({time.time()-t_cand:.0f}s)")

        if trades.empty:
            print("  No trades - skipping candidate.")
            continue

        n_total = len(trades)

        for max_pos in MAX_POSITIONS_GRID:
            for sm in SIZING_MODES:
                for ge in GROSS_EXPOSURE_GRID:
                    i += 1
                    print(f"  [{i}/{total}] {cand['label']} | "
                          f"max_pos={max_pos} sizing={sm} gross={ge:.2f}",
                          end="  ", flush=True)

                    equity, n_filled = build_portfolio_v2(
                        trades,
                        max_positions=max_pos,
                        rank_mode=cand["rank_mode"],
                        anti_ext_threshold=None,
                        sizing_mode=sm,
                        gross_exposure=ge,
                    )
                    m    = portfolio_metrics(equity, trades, test_start=TEST_START)
                    fill = n_filled / n_total if n_total else 0.0

                    cg = f"{m.get('cagr', float('nan')):.1%}" if np.isfinite(m.get("cagr", np.nan)) else "n/a"
                    sh = f"{m.get('sharpe', float('nan')):.3f}" if np.isfinite(m.get("sharpe", np.nan)) else "n/a"
                    dd = f"{m.get('max_dd', float('nan')):.1%}" if np.isfinite(m.get("max_dd", np.nan)) else "n/a"
                    print(f"CAGR={cg}  Sh={sh}  DD={dd}  fill={fill:.0%}")

                    rows.append({
                        "candidate":       cand["label"],
                        "strategy":        strat["label"],
                        "universe":        universe,
                        "rank_mode":       cand["rank_mode"],
                        "tp_pct":          cand["exit_cfg"]["tp_pct"],
                        "trail_mult":      cand["exit_cfg"]["trail_mult"],
                        "max_positions":   max_pos,
                        "sizing_mode":     sm,
                        "gross_exposure":  ge,
                        "cagr":            m.get("cagr", np.nan),
                        "sharpe":          m.get("sharpe", np.nan),
                        "max_dd":          m.get("max_dd", np.nan),
                        "mar":             m.get("mar", np.nan),
                        "n_trades":        m.get("n_trades", 0),
                        "n_total_signals": n_total,
                        "hit_rate":        m.get("hit_rate", np.nan),
                        "fill_util":       fill,
                        "skipped_signals": n_total - n_filled,
                        "oos_avg_ret":     m.get("oos_avg_ret", np.nan),
                        "oos_hit_rate":    m.get("oos_hit_rate", np.nan),
                    })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {len(df)} rows -> {OUT_CSV}")

    if not df.empty:
        _write_summary(df)

        show = ["candidate", "max_positions", "sizing_mode", "gross_exposure",
                "cagr", "sharpe", "max_dd", "mar", "fill_util"]
        top = df.sort_values("sharpe", ascending=False).head(12)
        print("\nTop 12 by Sharpe:")
        print(top[show].to_string(index=False, float_format="{:.4f}".format))

    print(f"\nTotal elapsed: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
