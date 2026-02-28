from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .run_e5_overlap_matrix import _read_trades
from .run_fa_hybrid_experiment import _decision_metrics


def _build_or_trades(
    breakout: pd.DataFrame,
    ma: pd.DataFrame,
    tolerance_days: int,
) -> pd.DataFrame:
    """
    Build Hybrid_OR trades as the union of breakout and MA trades.

    - Identity at idea level: (symbol, report_date, horizon_weeks)
    - If both engines fire within +/- tolerance_days for the same idea:
      pick the earlier entry_date as the OR trade (no look-ahead on alpha).
    - If only one engine fires for an idea, keep that trade as-is.
    """
    if breakout.empty and ma.empty:
        return pd.DataFrame(columns=breakout.columns)

    b = breakout.copy().reset_index(drop=True)
    m = ma.copy().reset_index(drop=True)

    # Ensure required columns exist
    required = [
        "symbol",
        "report_date",
        "horizon_weeks",
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "ret",
        "bench_ret",
        "alpha",
        "year",
    ]
    for col in required:
        if col not in b.columns or col not in m.columns:
            raise ValueError(f"Missing required column {col} in breakout/ma trades.")

    key_cols = ["symbol", "report_date", "horizon_weeks"]
    used_b = set()
    used_m = set()
    out_rows: List[Dict] = []

    # Index MA trades by (symbol, report_date, horizon_weeks)
    ma_index: Dict[Tuple, List[int]] = {}
    for mid, row in m.iterrows():
        key = tuple(row[c] for c in key_cols)
        ma_index.setdefault(key, []).append(mid)

    # First pass: breakout trades, try to pair with nearest MA trade inside tolerance
    for bid, brow in b.iterrows():
        key = tuple(brow[c] for c in key_cols)
        candidates = ma_index.get(key, [])
        best_mid = None
        best_diff = None
        for mid in candidates:
            if mid in used_m:
                continue
            mrow = m.loc[mid]
            diff_days = abs((brow["entry_date"] - mrow["entry_date"]).days)
            if diff_days <= tolerance_days:
                if best_diff is None or diff_days < best_diff:
                    best_diff = diff_days
                    best_mid = mid

        if best_mid is not None:
            # Overlapping idea: choose the earlier entry_date
            mrow = m.loc[best_mid]
            used_m.add(best_mid)
            used_b.add(bid)
            chosen = brow if brow["entry_date"] <= mrow["entry_date"] else mrow
            out_rows.append(chosen.to_dict())
        else:
            # No nearby MA trade: keep breakout trade
            used_b.add(bid)
            out_rows.append(brow.to_dict())

    # Second pass: remaining MA trades that were never used
    for mid, mrow in m.iterrows():
        if mid in used_m:
            continue
        out_rows.append(mrow.to_dict())

    or_df = pd.DataFrame(out_rows)
    if or_df.empty:
        return or_df

    # Label OR portfolio explicitly
    or_df = or_df.copy()
    # Preserve existing strategy if present, but overwrite variant with a clear OR label
    or_df["strategy"] = or_df.get("strategy", "Hybrid")
    single_variants = sorted(
        set(breakout.get("variant", pd.Series([], dtype=str)).unique()).union(
            set(ma.get("variant", pd.Series([], dtype=str)).unique())
        )
    )
    if len(single_variants) == 2:
        or_variant = f"OR_{single_variants[0]}_{single_variants[1]}"
    else:
        or_variant = "OR"
    or_df["variant"] = or_variant
    return or_df


def _evaluate_e6_rule(
    metrics: pd.DataFrame,
    single_variants: List[str],
    or_variant: str,
    max_trade_increase_pct: float,
) -> Dict:
    """
    Apply E6 decision rule on per-horizon metrics.

    Rule:
      - OR increases median_yearly_alpha vs best(single) on at least
        ceil(0.60 * n_horizons) horizons
      - Sharpe of OR is not worse than best(single) by more than 0.02 on ANY horizon
      - trade_count of OR does not exceed best(single) by more than max_trade_increase_pct on ANY horizon
    """
    if metrics.empty:
        return {
            "horizons": [],
            "per_horizon": {},
            "conditions": {
                "alpha_improved_enough": False,
                "sharpe_not_worse_0_02": False,
                "trades_not_increase_too_much": False,
            },
            "verdict": "NO_OR",
        }

    # Focus on Hybrid strategy rows only
    sub = metrics[(metrics["strategy"] == "Hybrid")].copy()
    horizons = sorted(sub["horizon"].unique())
    n_h = len(horizons)
    min_h_improve = max(1, ceil(0.60 * n_h))  # e.g. 3/5 horizons

    per_h: Dict[int, Dict[str, float]] = {}
    improve_count = 0
    sharpe_ok_all = True
    trades_ok_all = True

    for h in horizons:
        h_rows = sub[sub["horizon"] == h]
        if h_rows.empty:
            continue
        # Best single by median_yearly_alpha
        singles = h_rows[h_rows["variant"].isin(single_variants)].copy()
        or_row = h_rows[h_rows["variant"] == or_variant].copy()

        if singles.empty or or_row.empty:
            continue

        singles = singles.sort_values("median_yearly_alpha", ascending=False)
        best_single = singles.iloc[0]
        or_r = or_row.iloc[0]

        alpha_best = float(best_single["median_yearly_alpha"])
        alpha_or = float(or_r["median_yearly_alpha"])
        sharpe_best = float(best_single["sharpe"])
        sharpe_or = float(or_r["sharpe"])
        trades_best = int(best_single["trade_count"])
        trades_or = int(or_r["trade_count"])

        alpha_delta = alpha_or - alpha_best
        sharpe_delta = sharpe_or - sharpe_best
        trades_delta = trades_or - trades_best
        trades_limit = trades_best * (1.0 + max_trade_increase_pct / 100.0)

        improved_alpha = alpha_delta > 0.0
        sharpe_ok = sharpe_delta >= -0.02
        trades_ok = trades_or <= trades_limit

        if improved_alpha:
            improve_count += 1
        if not sharpe_ok:
            sharpe_ok_all = False
        if not trades_ok:
            trades_ok_all = False

        per_h[int(h)] = {
            "alpha_or": alpha_or,
            "alpha_best_single": alpha_best,
            "alpha_delta": alpha_delta,
            "sharpe_or": sharpe_or,
            "sharpe_best_single": sharpe_best,
            "sharpe_delta": sharpe_delta,
            "trades_or": trades_or,
            "trades_best_single": trades_best,
            "trades_delta": trades_delta,
            "trades_limit": float(trades_limit),
            "alpha_improved": bool(improved_alpha),
            "sharpe_ok": bool(sharpe_ok),
            "trades_ok": bool(trades_ok),
        }

    cond_alpha = improve_count >= min_h_improve
    cond_sharpe = sharpe_ok_all
    cond_trades = trades_ok_all
    promote_or = bool(cond_alpha and cond_sharpe and cond_trades)

    return {
        "horizons": [int(h) for h in horizons],
        "per_horizon": per_h,
        "conditions": {
            "alpha_improved_enough": bool(cond_alpha),
            "sharpe_not_worse_0_02": bool(cond_sharpe),
            "trades_not_increase_too_much": bool(cond_trades),
        },
        "min_horizons_with_alpha_improvement": int(min_h_improve),
        "max_trade_increase_pct": float(max_trade_increase_pct),
        "verdict": "PROMOTE_OR" if promote_or else "NO_OR",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="E6 OR performance test: Hybrid breakout_20d vs ma5>ma10>ma20 vs OR union."
    )
    ap.add_argument(
        "--breakout-dir",
        required=True,
        help="Directory for breakout_20d engine (expects trades.csv and strategy=Hybrid, variant=breakout_20d).",
    )
    ap.add_argument(
        "--ma-dir",
        required=True,
        help="Directory for ma engine (expects trades.csv and strategy=Hybrid, variant=ma5_gt_ma10_gt_ma20).",
    )
    ap.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for E6 OR performance report.",
    )
    ap.add_argument(
        "--tolerance-days",
        type=int,
        default=3,
        help="Tolerance on entry_date matching when defining overlapping ideas (default 3).",
    )
    ap.add_argument(
        "--max-trade-increase-pct",
        type=float,
        default=25.0,
        help="Maximum allowed percentage increase in OR trade_count vs best(single) per horizon (default 25%%).",
    )
    args = ap.parse_args()

    breakout_dir = Path(args.breakout_dir)
    ma_dir = Path(args.ma_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    b_trades = _read_trades(breakout_dir)
    m_trades = _read_trades(ma_dir)

    if b_trades.empty or m_trades.empty:
        raise ValueError("Both breakout and MA trades must be non-empty for E6.")

    # Identify single variants from inputs
    single_variants = sorted(
        set(b_trades.get("variant", pd.Series([], dtype=str)).unique()).union(
            set(m_trades.get("variant", pd.Series([], dtype=str)).unique())
        )
    )
    if len(single_variants) != 2:
        print(f"[WARN] Expected exactly 2 single variants, found: {single_variants}")

    print(
        f"[INFO] Loaded breakout trades: {len(b_trades)} rows; "
        f"MA trades: {len(m_trades)} rows. Variants={single_variants}"
    )

    # Build OR union trades
    or_trades = _build_or_trades(b_trades, m_trades, args.tolerance_days)
    if or_trades.empty:
        raise ValueError("OR portfolio has no trades after union logic.")

    or_variant = str(or_trades["variant"].iloc[0])
    print(
        f"[INFO] Built OR portfolio with {len(or_trades)} trades, "
        f"variant label='{or_variant}', tolerance_days={args.tolerance_days}"
    )

    # Prepare combined trades for metrics: breakout, MA, OR
    b_trades = b_trades.copy()
    m_trades = m_trades.copy()
    # Ensure strategy/variant columns exist for metrics grouping
    if "strategy" not in b_trades.columns:
        b_trades["strategy"] = "Hybrid"
    if "strategy" not in m_trades.columns:
        m_trades["strategy"] = "Hybrid"

    combined = pd.concat([b_trades, m_trades, or_trades], ignore_index=True)
    metrics = _decision_metrics(combined, include_variant=True)

    # Persist metrics
    metrics_out = out_dir / "e6_or_metrics.csv"
    col_order = [
        c
        for c in [
            "strategy",
            "variant",
            "horizon",
            "median_yearly_alpha",
            "sharpe",
            "trade_count",
        ]
        if c in metrics.columns
    ]
    metrics = metrics[col_order] if col_order else metrics
    metrics.to_csv(metrics_out, index=False)

    # Apply E6 rule
    summary = _evaluate_e6_rule(
        metrics=metrics,
        single_variants=single_variants,
        or_variant=or_variant,
        max_trade_increase_pct=args.max_trade_increase_pct,
    )

    # Write JSON summary
    json_out = out_dir / "e6_or_summary.json"
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Human-readable report
    lines: List[str] = []
    lines.append("# E6 OR Performance Report\n")
    lines.append("## Inputs\n")
    lines.append(f"- **breakout_dir**: `{breakout_dir}`")
    lines.append(f"- **ma_dir**: `{ma_dir}`")
    lines.append(f"- **out_dir**: `{out_dir}`")
    lines.append(f"- **tolerance_days**: {args.tolerance_days}")
    lines.append(
        f"- **max_trade_increase_pct**: {args.max_trade_increase_pct}\n"
    )

    lines.append("## Per-strategy metrics by horizon\n")
    if not metrics.empty:
        # Restrict to Hybrid strategy only for clarity
        sub = metrics[metrics["strategy"] == "Hybrid"].copy()
        sub = sub.sort_values(["horizon", "variant"])
        lines.append(sub.to_string(index=False))
    else:
        lines.append("No metrics available.\n")

    lines.append("\n\n## OR vs best(single) per horizon\n")
    per_h = summary.get("per_horizon", {})
    if per_h:
        for h in sorted(per_h.keys()):
            info = per_h[h]
            lines.append(f"- **Horizon {h}w**:")
            lines.append(
                f"  OR alpha={info['alpha_or']:.4f}, best_single alpha={info['alpha_best_single']:.4f}, "
                f"delta={info['alpha_delta']:.4f}"
            )
            lines.append(
                f"  OR sharpe={info['sharpe_or']:.4f}, best_single sharpe={info['sharpe_best_single']:.4f}, "
                f"delta={info['sharpe_delta']:.4f}"
            )
            lines.append(
                f"  OR trades={info['trades_or']} vs best_single trades={info['trades_best_single']}, "
                f"delta={info['trades_delta']} (limit={info['trades_limit']:.1f})"
            )
            lines.append(
                f"  flags: alpha_improved={info['alpha_improved']}, "
                f"sharpe_ok={info['sharpe_ok']}, trades_ok={info['trades_ok']}"
            )
    else:
        lines.append("No per-horizon comparison available.\n")

    conds = summary.get("conditions", {})
    lines.append("\n\n## Verdict\n")
    lines.append(f"**Verdict**: `{summary.get('verdict', 'NO_OR')}`\n")
    lines.append(
        f"- alpha_improved_enough (>= {summary.get('min_horizons_with_alpha_improvement', 0)} horizons): "
        f"{conds.get('alpha_improved_enough', False)}"
    )
    lines.append(
        f"- sharpe_not_worse_0_02 (all horizons): {conds.get('sharpe_not_worse_0_02', False)}"
    )
    lines.append(
        f"- trades_not_increase_too_much (all horizons, max_trade_increase_pct="
        f"{summary.get('max_trade_increase_pct', args.max_trade_increase_pct)}): "
        f"{conds.get('trades_not_increase_too_much', False)}"
    )

    report_out = out_dir / "e6_or_report.md"
    report_out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote E6 OR metrics/report/summary to {out_dir}")
    print(f"Final E6 verdict: {summary.get('verdict', 'NO_OR')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
