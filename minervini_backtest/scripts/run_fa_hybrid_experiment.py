from __future__ import annotations

"""
run_fa_hybrid_experiment.py
===========================

Minimal hybrid experiment to compare:
  - FA_only: FA cohort entries held for fixed horizons
  - Hybrid: FA cohort + simple 20-day breakout timing

Scope is intentionally narrow: compute only
  - median_yearly_alpha
  - sharpe (alpha-based)
  - trade_count
per strategy and horizon.
"""

import argparse
import itertools
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # .../minervini_backtest
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fa_cohort.fa_filters import FaFilterConfig  # type: ignore
from fa_cohort.cohort_backtest import (  # type: ignore
    load_fa_csv,
    _cohort_for_quarter,
    _load_price_data,
    _next_trading_day_close,
    _horizon_exit,
)


def _build_fa_cohort(fa_csv: Path) -> pd.DataFrame:
    fa_df = load_fa_csv(fa_csv)
    cfg = FaFilterConfig(
        eps_yoy_min=20.0,
        sales_yoy_min=15.0,
        roe_min=15.0,
        debt_to_equity_max=1.5,
        margin_yoy_min=0.0,
        require_eps_accel=False,
        earnings_yoy_min=20.0,
        require_earnings_accel=True,
    )
    cohort_df = _cohort_for_quarter(fa_df, cfg)
    if cohort_df.empty:
        raise ValueError("No symbols pass FA filter for hybrid experiment.")
    return cohort_df


def _compute_returns_fa_only(
    cohort_df: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    bench_df: pd.DataFrame,
    horizons: List[int],
) -> pd.DataFrame:
    records: List[dict] = []
    for _, row in cohort_df.iterrows():
        sym = row["symbol"]
        px = price_data.get(sym)
        if px is None or px.empty:
            continue
        rep_dt = row["report_date"]
        ent = _next_trading_day_close(px, rep_dt)
        if ent is None:
            continue
        entry_dt, entry_px = ent
        bench_ent = _next_trading_day_close(bench_df, entry_dt)
        if bench_ent is None:
            continue
        bench_entry_dt, bench_entry_px = bench_ent

        for weeks in horizons:
            exit_pair = _horizon_exit(px, entry_dt, weeks)
            bench_exit_pair = _horizon_exit(bench_df, bench_entry_dt, weeks)
            if exit_pair is None or bench_exit_pair is None:
                continue
            exit_dt, exit_px = exit_pair
            _, bench_exit_px = bench_exit_pair
            ret = (exit_px / entry_px) - 1.0
            bench_ret = (bench_exit_px / bench_entry_px) - 1.0
            records.append(
                {
                    "strategy": "FA_only",
                    "variant": "FA_only",
                    "symbol": sym,
                    "report_date": rep_dt,
                    "horizon_weeks": weeks,
                    "entry_date": entry_dt,
                    "exit_date": exit_dt,
                    "entry_price": float(entry_px),
                    "exit_price": float(exit_px),
                    "year": entry_dt.year,
                    "ret": ret,
                    "bench_ret": bench_ret,
                    "alpha": ret - bench_ret,
                }
            )
    return pd.DataFrame(records)


def _ma_combo_variants(windows: List[int]) -> List[str]:
    """Non-empty subsets of windows => C > MA(w) for each w. With [5,10,20] => 7 variants."""
    out: List[str] = []
    for r in range(1, len(windows) + 1):
        for subset in itertools.combinations(sorted(windows), r):
            if len(subset) == 1:
                out.append(f"c_gt_ma{subset[0]}")
            elif len(subset) == 3:
                out.append("c_gt_all")
            else:
                out.append("c_gt_ma" + "_and_ma".join(str(w) for w in subset))

    return out


def _ma_perm_variants(windows: List[int]) -> List[str]:
    """All permutations of windows => MA(a)>MA(b)>MA(c). With [5,10,20] => 6 variants."""
    return [f"ma{w[0]}_gt_ma{w[1]}_gt_ma{w[2]}" for w in itertools.permutations(sorted(windows))]


def get_ma_variants(ma_gen: str, ma_windows: List[int]) -> List[str]:
    """Return variant names for sweep. ma_gen: all|combo|perm|none."""
    if ma_gen == "none":
        return list(MA_VARIANTS)
    if ma_gen == "combo":
        return _ma_combo_variants(ma_windows)
    if ma_gen == "perm":
        return _ma_perm_variants(ma_windows)
    if ma_gen == "all":
        return _ma_combo_variants(ma_windows) + _ma_perm_variants(ma_windows)
    return list(MA_VARIANTS)


def _ma_signal_mask(d: pd.DataFrame, variant: str, windows: Tuple[int, ...] = (5, 10, 20)) -> pd.Series:
    """Boolean series: True where variant condition holds. Supports combo + perm names for 5,10,20."""
    c = d["close"].astype(float)
    mas = {w: c.rolling(w, min_periods=w).mean() for w in windows}
    # Combo: C > MA(w) for each in subset
    if variant.startswith("c_gt_ma"):
        if variant == "c_gt_all":
            return (c > mas[5]) & (c > mas[10]) & (c > mas[20])
        parts = variant.replace("c_gt_ma", "").split("_and_ma")
        if not parts:
            return pd.Series(False, index=d.index)
        cond = (c > mas[int(parts[0])]) if parts[0].isdigit() else pd.Series(False, index=d.index)
        for p in parts[1:]:
            if p.isdigit():
                cond = cond & (c > mas[int(p)])
        return cond
    # Perm: MA(a) > MA(b) > MA(c), e.g. ma5_gt_ma10_gt_ma20
    if "_gt_ma" in variant and variant.startswith("ma"):
        parts = variant.split("_gt_ma")
        if len(parts) != 3:
            return pd.Series(False, index=d.index)
        try:
            a, b, c = int(parts[0].replace("ma", "")), int(parts[1].replace("ma", "")), int(parts[2].replace("ma", ""))
        except ValueError:
            return pd.Series(False, index=d.index)
        if a not in mas or b not in mas or c not in mas:
            return pd.Series(False, index=d.index)
        return (mas[a] > mas[b]) & (mas[b] > mas[c])
    return pd.Series(False, index=d.index)


def _compute_returns_hybrid(
    cohort_df: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    bench_df: pd.DataFrame,
    horizons: List[int],
    window_days: int = 30,
    entry_mode: str = "breakout_20d",
    ma_variant: str = "c_gt_ma20",
) -> pd.DataFrame:
    records: List[dict] = []
    for _, row in cohort_df.iterrows():
        sym = row["symbol"]
        px = price_data.get(sym)
        if px is None or px.empty:
            continue
        rep_dt = row["report_date"]

        # Starting point: first trading day on or after report_date
        ent0 = _next_trading_day_close(px, rep_dt)
        if ent0 is None:
            continue
        start_dt, _ = ent0

        d = px.copy()
        d = d.sort_values("date").reset_index(drop=True)
        d["close"] = d["close"].astype(float)

        if entry_mode == "ma":
            d["signal"] = _ma_signal_mask(d, ma_variant)
            window = d[d["date"] >= start_dt].head(window_days)
            win_signals = window[window["signal"]]
            if win_signals.empty:
                continue
            br = win_signals.iloc[0]
        elif entry_mode == "pp_proxy_v1":
            # Volume thrust + close near high (breakout-like). Prior 20 days = shift(1).
            d["close_roll_max_20"] = d["close"].rolling(20, min_periods=20).max().shift(1)
            vol = d["volume"].astype(float)
            d["vol_med20"] = vol.rolling(20, min_periods=20).median().shift(1)
            rng = d["high"].astype(float) - d["low"].astype(float)
            d["close_pos"] = (d["close"].astype(float) - d["low"].astype(float)) / np.maximum(rng, 1e-9)
            breakout = d["close"] > d["close_roll_max_20"]
            vol_thrust = vol >= 1.5 * d["vol_med20"]
            close_near_high = d["close_pos"] >= 0.75
            d["signal"] = breakout & vol_thrust & close_near_high
            window = d[d["date"] >= start_dt].head(window_days)
            win_signals = window[window["signal"]]
            if win_signals.empty:
                continue
            br = win_signals.iloc[0]
        else:
            # breakout_20d
            d["roll_high_20"] = d["close"].rolling(20, min_periods=20).max().shift(1)
            d["breakout"] = d["close"] > d["roll_high_20"]
            window = d[d["date"] >= start_dt].head(window_days)
            win_breakouts = window[window["breakout"]]
            if win_breakouts.empty:
                continue
            br = win_breakouts.iloc[0]

        entry_dt = br["date"]
        entry_px = float(br["close"])

        bench_ent = _next_trading_day_close(bench_df, entry_dt)
        if bench_ent is None:
            continue
        bench_entry_dt, bench_entry_px = bench_ent

        hybrid_variant = "pp_proxy_v1" if entry_mode == "pp_proxy_v1" else ("breakout_20d" if entry_mode == "breakout_20d" else ma_variant)
        for weeks in horizons:
            exit_pair = _horizon_exit(px, entry_dt, weeks)
            bench_exit_pair = _horizon_exit(bench_df, bench_entry_dt, weeks)
            if exit_pair is None or bench_exit_pair is None:
                continue
            exit_dt, exit_px = exit_pair
            _, bench_exit_px = bench_exit_pair
            ret = (exit_px / entry_px) - 1.0
            bench_ret = (bench_exit_px / bench_entry_px) - 1.0
            records.append(
                {
                    "strategy": "Hybrid",
                    "variant": hybrid_variant,
                    "symbol": sym,
                    "report_date": rep_dt,
                    "horizon_weeks": weeks,
                    "entry_date": entry_dt,
                    "exit_date": exit_dt,
                    "entry_price": float(entry_px),
                    "exit_price": float(exit_px),
                    "year": entry_dt.year,
                    "ret": ret,
                    "bench_ret": bench_ret,
                    "alpha": ret - bench_ret,
                }
            )
    return pd.DataFrame(records)


def _decision_metrics(trades: pd.DataFrame, include_variant: bool = True) -> pd.DataFrame:
    rows: List[dict] = []
    if trades.empty:
        cols = ["strategy", "horizon", "median_yearly_alpha", "sharpe", "trade_count"]
        if include_variant:
            cols.insert(1, "variant")
        return pd.DataFrame(columns=cols)

    group_cols = ["strategy", "variant", "horizon_weeks"] if "variant" in trades.columns and include_variant else ["strategy", "horizon_weeks"]
    for key, grp in trades.groupby(group_cols):
        key_tup = key if isinstance(key, tuple) else (key,)
        if len(key_tup) == 3:
            strategy, variant, horizon = key_tup
        else:
            strategy, horizon = key_tup[0], key_tup[1]
            variant = None
        if grp.empty:
            continue
        yearly = grp.groupby("year")["alpha"].median()
        median_yearly_alpha = float(yearly.median()) if not yearly.empty else float("nan")
        alpha = grp["alpha"].to_numpy()
        mu = float(np.nanmean(alpha))
        sigma = float(np.nanstd(alpha))
        sharpe = mu / sigma if sigma > 0 else float("nan")
        row = {
            "strategy": strategy,
            "horizon": int(horizon),
            "median_yearly_alpha": median_yearly_alpha,
            "sharpe": sharpe,
            "trade_count": int(len(grp)),
        }
        if variant is not None and include_variant:
            row["variant"] = variant
        rows.append(row)
    return pd.DataFrame(rows)


MA_VARIANTS = [
    "c_gt_ma5",
    "c_gt_ma10",
    "c_gt_ma20",
    "c_gt_ma5_and_ma10",
    "c_gt_ma10_and_ma20",
    "ma5_gt_ma10_gt_ma20",
    "c_gt_ma10_and_ma10_gt_ma20",
    "c_gt_all",
]


def main() -> int:
    p = argparse.ArgumentParser(description="Minimal FA-only vs Hybrid FA+breakout experiment")
    p.add_argument(
        "--strategies",
        nargs="+",
        choices=["FA_only", "Hybrid"],
        required=True,
        help="Which strategies to run (subset of: FA_only, Hybrid)",
    )
    p.add_argument("--fa-csv", default="data/fa_minervini.csv")
    p.add_argument("--horizons", nargs="+", type=int, default=[8, 10, 13])
    p.add_argument("--bench", default="VNINDEX")
    p.add_argument(
        "--signal-window",
        type=int,
        default=30,
        help="Trading days after report_date to look for Hybrid entry (default 30)",
    )
    p.add_argument(
        "--entry-mode",
        choices=["breakout_20d", "ma", "pp_proxy_v1"],
        default="breakout_20d",
        help="Hybrid entry trigger: breakout_20d, ma, or pp_proxy_v1 (default breakout_20d)",
    )
    p.add_argument(
        "--ma-variant",
        default="c_gt_ma20",
        help="MA condition when entry-mode=ma (e.g. c_gt_ma20, c_gt_ma5_and_ma10)",
    )
    p.add_argument(
        "--sweep-ma",
        action="store_true",
        help="Run Hybrid for each MA variant and write ma_sweep/decision_metrics.csv",
    )
    p.add_argument(
        "--ma-windows",
        nargs="+",
        type=int,
        default=[5, 10, 20],
        help="MA windows for generated variants (default: 5 10 20)",
    )
    p.add_argument(
        "--ma-gen",
        choices=["all", "combo", "perm", "none"],
        default="none",
        help="When --sweep-ma: all=13 variants, combo=7, perm=6, none=hardcoded list (default: none)",
    )
    p.add_argument(
        "--out-dir",
        default="minervini_backtest/outputs/fa_hybrid_experiment",
        help="Output directory for decision_metrics.csv",
    )
    args = p.parse_args()

    fa_path = Path(args.fa_csv)
    if not fa_path.exists():
        raise FileNotFoundError(f"FA CSV not found: {fa_path}")

    horizons = sorted(set(args.horizons))
    cohort_df = _build_fa_cohort(fa_path)

    price_data = _load_price_data()
    if not price_data:
        raise RuntimeError("No curated price data available.")
    bench_symbol = args.bench.upper()
    bench_df = price_data.get(bench_symbol)
    if bench_df is None or bench_df.empty:
        raise ValueError(f"Benchmark symbol {bench_symbol} not found in curated data.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.sweep_ma:
        variants_to_run = get_ma_variants(args.ma_gen, args.ma_windows)
        all_trades: List[pd.DataFrame] = []
        fa_trades = _compute_returns_fa_only(cohort_df, price_data, bench_df, horizons)
        all_trades.append(fa_trades)
        for mv in variants_to_run:
            hyb = _compute_returns_hybrid(
                cohort_df,
                price_data,
                bench_df,
                horizons,
                window_days=args.signal_window,
                entry_mode="ma",
                ma_variant=mv,
            )
            all_trades.append(hyb)
        trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
        metrics = _decision_metrics(trades_df, include_variant=True)
        # Fill missing (variant, horizon) with 0 trade_count so output has exactly FA_only*3 + len(variants_to_run)*3 rows
        for v in variants_to_run:
            for h in horizons:
                if metrics.empty or ((metrics["variant"] == v) & (metrics["horizon"] == h)).sum() == 0:
                    metrics = pd.concat(
                        [
                            metrics,
                            pd.DataFrame(
                                [
                                    {
                                        "strategy": "Hybrid",
                                        "variant": v,
                                        "horizon": h,
                                        "median_yearly_alpha": float("nan"),
                                        "sharpe": float("nan"),
                                        "trade_count": 0,
                                    }
                                ]
                            ),
                        ],
                        ignore_index=True,
                    )
        sweep_dir = out_dir / "ma_sweep"
        sweep_dir.mkdir(parents=True, exist_ok=True)
        out_path = sweep_dir / "decision_metrics.csv"
        col_order = [c for c in ["strategy", "variant", "horizon", "median_yearly_alpha", "sharpe", "trade_count"] if c in metrics.columns]
        metrics = metrics[col_order] if col_order else metrics
        metrics.to_csv(out_path, index=False)
        print(f"Wrote MA sweep decision metrics to {out_path}")
        # Top 3 per horizon (primary median_yearly_alpha desc, secondary sharpe desc)
        for h in horizons:
            sub = metrics[metrics["horizon"] == h].copy()
            sub = sub.sort_values(
                ["median_yearly_alpha", "sharpe"],
                ascending=[False, False],
                na_position="last",
            )
            top3 = sub.head(3)
            print(f"Horizon {h}w top 3 (median_yearly_alpha, sharpe):")
            for _, r in top3.iterrows():
                print(f"  {r.get('variant', r['strategy'])}: alpha={r['median_yearly_alpha']:.4f} sharpe={r['sharpe']:.4f} n={r['trade_count']}")
        # Overall pick: average rank across horizons (lower better), tie-break avg sharpe
        hybrid_metrics = metrics[metrics["strategy"] == "Hybrid"].copy()
        if not hybrid_metrics.empty and len(horizons) >= 1:
            rank_per_h: Dict[str, List[int]] = {}
            for h in horizons:
                sub = metrics[metrics["horizon"] == h].copy()
                sub = sub.sort_values(["median_yearly_alpha", "sharpe"], ascending=[False, False], na_position="last")
                sub["rank"] = range(1, len(sub) + 1)
                for v in sub["variant"].unique():
                    if v not in rank_per_h:
                        rank_per_h[v] = []
                    r = sub[sub["variant"] == v]["rank"].iloc[0]
                    rank_per_h[v].append(r)
            avg_rank = {v: np.mean(ranks) for v, ranks in rank_per_h.items() if len(ranks) == len(horizons)}
            avg_sharpe = hybrid_metrics.groupby("variant")["sharpe"].mean().to_dict()
            candidates = [(v, avg_rank[v], avg_sharpe.get(v, 0.0)) for v in avg_rank if v != "FA_only"]
            candidates.sort(key=lambda x: (x[1], -x[2]))
            print("Top 3 overall (avg_rank across horizons, tie-break avg sharpe):")
            for v, r, s in candidates[:3]:
                print(f"  {v}: avg_rank={r:.2f} avg_sharpe={s:.4f}")
        return 0

    # Single run
    all_trades = []
    if "FA_only" in args.strategies:
        fa_trades = _compute_returns_fa_only(cohort_df, price_data, bench_df, horizons)
        all_trades.append(fa_trades)
    if "Hybrid" in args.strategies:
        hyb_trades = _compute_returns_hybrid(
            cohort_df,
            price_data,
            bench_df,
            horizons,
            window_days=args.signal_window,
            entry_mode=args.entry_mode,
            ma_variant=args.ma_variant,
        )
        all_trades.append(hyb_trades)

    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    metrics = _decision_metrics(trades_df, include_variant=True)

    subdir = f"window{args.signal_window}"
    window_dir = out_dir / subdir
    # Hybrid-only runs: write to subfolder by variant so baseline (FA_only + Hybrid) is never overwritten
    if "FA_only" not in args.strategies and "Hybrid" in args.strategies:
        variant = (
            "pp_proxy_v1"
            if args.entry_mode == "pp_proxy_v1"
            else ("breakout_20d" if args.entry_mode == "breakout_20d" else args.ma_variant)
        )
        window_dir = window_dir / f"hybrid_{variant}"
    window_dir.mkdir(parents=True, exist_ok=True)

    # Write per-trade log for this run
    trades_out = window_dir / "trades.csv"
    trades_df.to_csv(trades_out, index=False)

    out_path = window_dir / "decision_metrics.csv"
    col_order = [c for c in ["strategy", "variant", "horizon", "median_yearly_alpha", "sharpe", "trade_count"] if c in metrics.columns]
    metrics = metrics[col_order] if col_order else metrics
    metrics.to_csv(out_path, index=False)
    print(f"Wrote decision metrics to {out_path}")

    # 3-line summary: FA_only vs Hybrid_breakout_20d vs Hybrid_pp_proxy_v1 (when pp run)
    if args.entry_mode == "pp_proxy_v1":
        baseline_path = out_dir / subdir / "decision_metrics.csv"
        print("Summary (FA_only | Hybrid_breakout_20d | Hybrid_pp_proxy_v1):")
        base_df = pd.read_csv(baseline_path) if baseline_path.exists() else pd.DataFrame()
        for h in horizons:
            fa = metrics[(metrics["horizon"] == h) & (metrics["strategy"] == "FA_only")] if not metrics.empty else pd.DataFrame()
            if fa.empty and not base_df.empty:
                fa = base_df[(base_df["horizon"] == h) & (base_df["strategy"] == "FA_only")]
            br = metrics[(metrics["horizon"] == h) & (metrics["strategy"] == "Hybrid") & (metrics["variant"] == "breakout_20d")] if not metrics.empty else pd.DataFrame()
            if br.empty and not base_df.empty:
                br = base_df[(base_df["horizon"] == h) & (base_df["strategy"] == "Hybrid") & (base_df["variant"] == "breakout_20d")]
            pp = metrics[(metrics["horizon"] == h) & (metrics["strategy"] == "Hybrid") & (metrics["variant"] == "pp_proxy_v1")] if not metrics.empty else pd.DataFrame()
            fa_a, fa_s, fa_n = (fa["median_yearly_alpha"].iloc[0], fa["sharpe"].iloc[0], fa["trade_count"].iloc[0]) if not fa.empty else (float("nan"), float("nan"), 0)
            br_a, br_s, br_n = (br["median_yearly_alpha"].iloc[0], br["sharpe"].iloc[0], br["trade_count"].iloc[0]) if not br.empty else (float("nan"), float("nan"), 0)
            pp_a, pp_s, pp_n = (pp["median_yearly_alpha"].iloc[0], pp["sharpe"].iloc[0], pp["trade_count"].iloc[0]) if not pp.empty else (float("nan"), float("nan"), 0)
            print(f"  {h}w: FA_only alpha={fa_a:.4f} sharpe={fa_s:.4f} n={fa_n} | Hybrid_breakout_20d alpha={br_a:.4f} sharpe={br_s:.4f} n={br_n} | Hybrid_pp_proxy_v1 alpha={pp_a:.4f} sharpe={pp_s:.4f} n={pp_n}")

    # Window sensitivity: if this run used signal_window=15, compare to window30
    if args.signal_window == 15:
        ref_path = out_dir / "window30" / "decision_metrics.csv"
        if ref_path.exists():
            ref = pd.read_csv(ref_path)
            print("Comparison (window15 vs window30) [Hybrid only]:")
            for h in horizons:
                m15 = metrics[(metrics["horizon"] == h) & (metrics["strategy"] == "Hybrid")]
                m30 = ref[(ref["horizon"] == h) & (ref["strategy"] == "Hybrid")]
                if not m15.empty and not m30.empty:
                    a15 = m15["median_yearly_alpha"].iloc[0]
                    a30 = m30["median_yearly_alpha"].iloc[0]
                    s15 = m15["sharpe"].iloc[0]
                    s30 = m30["sharpe"].iloc[0]
                    n15 = m15["trade_count"].iloc[0]
                    n30 = m30["trade_count"].iloc[0]
                    print(f"  {h}w: delta_alpha={a15 - a30:.4f} delta_sharpe={s15 - s30:.4f} delta_trades={n15 - n30}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

