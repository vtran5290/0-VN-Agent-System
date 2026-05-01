"""
One-command runner: scarcity diagnosis, Path B baseline, Path A vs Path B comparison.

1. Run Path A trade scarcity diagnosis -> artifacts/trade_scarcity_diagnosis.{md,csv}
2. Run Path B daily PP baseline for each period -> artifacts/path_b_daily_baseline.{md,csv}
3. Run Path A weekly for same periods, then compare -> artifacts/path_a_vs_path_b_comparison.{md,csv}
4. Ensure artifacts/PARALLEL_PATHS_PLAN.md exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))


def _sanitize(v):
    if isinstance(v, (np.integer, np.int64)):
        return int(v)
    if isinstance(v, (np.floating, np.float64)):
        if np.isnan(v) or np.isinf(v):
            return None
        return float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def main() -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Always (re)write PARALLEL_PATHS_PLAN early
    plan_path = artifacts_dir / "PARALLEL_PATHS_PLAN.md"
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write("# Parallel Paths Plan\n\n")
        f.write("## Path A (current)\n")
        f.write("- Weekly pivot / accumulation: weekly_pp on weekly bars, weekly EMA21/MA50/MA10.\n")
        f.write("- Signal -> next week open execution.\n")
        f.write("- Same risk framework: VND, fees, regime, liquidity cap, PIT eligibility.\n\n")
        f.write("## Path B\n")
        f.write("- True daily Pocket Pivot (signals.pocket_pivot on daily OHLCV).\n")
        f.write("- Trend: EMA21_daily > MA50_daily. Exit: close < EMA21 or < MA50 or EMA21 cross below MA50.\n")
        f.write("- Entry/exit at next day open. Same risk framework as Path A.\n")
    print(f"[parallel] Wrote {plan_path}", flush=True)

    periods = [
        ("2018-01-01", "2021-12-31", "2018-2021"),
        ("2022-01-01", "2024-12-31", "2022-2024"),
        ("2025-01-01", "2026-02-21", "2025-2026Q1"),
        ("2012-01-01", "2026-02-21", "full_sample"),
    ]

    # --- 1) Scarcity diagnosis (Path A) ---
    csv_scarcity = artifacts_dir / "trade_scarcity_diagnosis.csv"
    md_scarcity = artifacts_dir / "trade_scarcity_diagnosis.md"
    if csv_scarcity.exists() and md_scarcity.exists():
        print("[parallel] Using existing trade_scarcity_diagnosis artifacts.", flush=True)
    else:
        print("[parallel] Running trade scarcity diagnosis (Path A)...", flush=True)
        try:
            from pp_backtest.run_trade_scarcity_diagnosis import main as diagnosis_main
            diagnosis_main()
        except Exception as e:
            print(f"[parallel] Scarcity diagnosis failed: {e}", flush=True)

    # --- 2) Path B baseline ---
    print("[parallel] Running Path B daily baseline...", flush=True)
    from pp_backtest.run_daily_pp_portfolio import run_period as run_path_b_period

    pb_csv = artifacts_dir / "path_b_daily_baseline.csv"
    existing_pb = pd.read_csv(pb_csv) if pb_csv.exists() else pd.DataFrame()

    path_b_rows = [] if existing_pb.empty else existing_pb.to_dict(orient="records")
    have_labels = {r["period"] for r in path_b_rows} if path_b_rows else set()
    for start, end, label in periods:
        if label in have_labels:
            print(f"  Path B period={label} (reuse)", flush=True)
            continue
        print(f"  Path B period={label}", flush=True)
        try:
            _, stats = run_path_b_period(start, end)
            if stats:
                row = {"period": label, "path": "B", "start": start, "end": end}
                for k, v in stats.items():
                    row[k] = _sanitize(v)
                path_b_rows.append(row)
        except Exception as e:
            print(f"    Error: {e}", flush=True)

    if path_b_rows:
        pb_df = pd.DataFrame(path_b_rows)
        pb_df.to_csv(pb_csv, index=False)
        pb_md = artifacts_dir / "path_b_daily_baseline.md"
        with open(pb_md, "w", encoding="utf-8") as f:
            f.write("# Path B – Daily Pocket Pivot Baseline\n\n")
            f.write("True daily PP signal, daily EMA21>MA50, next-day open execution.\n\n")
            cols = ["period", "cagr", "mdd", "mar", "n_trades", "trades_per_month", "final_equity", "avg_heat", "avg_gross_exposure"]
            cols = [c for c in cols if c in pb_df.columns]
            f.write(pb_df[cols].to_string(index=False))
        print(f"[parallel] Wrote {pb_csv} and {pb_md}")

    # --- 3) Path A per-period (for comparison) ---
    print("[parallel] Running Path A weekly per period...", flush=True)
    from pp_backtest.run_weekly_ema21_portfolio import run_weekly_period

    path_a_rows = []
    for start, end, label in periods:
        print(f"  Path A period={label}", flush=True)
        try:
            _, stats = run_weekly_period(start, end)
            if stats:
                row = {"period": label, "path": "A", "start": start, "end": end}
                for k, v in stats.items():
                    row[k] = _sanitize(v)
                path_a_rows.append(row)
        except Exception as e:
            print(f"    Error: {e}", flush=True)

    # --- 4) Comparison ---
    comparison_rows = []
    for start, end, label in periods:
        pa = next((r for r in path_a_rows if r["period"] == label), None)
        pb = next((r for r in path_b_rows if r["period"] == label), None)
        if pa and pb:
            comparison_rows.append({
                "period": label,
                "cagr_a": pa.get("cagr"),
                "cagr_b": pb.get("cagr"),
                "mdd_a": pa.get("mdd"),
                "mdd_b": pb.get("mdd"),
                "mar_a": pa.get("mar"),
                "mar_b": pb.get("mar"),
                "n_trades_a": pa.get("n_trades"),
                "n_trades_b": pb.get("n_trades"),
                "trades_per_month_a": pa.get("trades_per_month"),
                "trades_per_month_b": pb.get("trades_per_month"),
                "final_equity_a": pa.get("final_equity"),
                "final_equity_b": pb.get("final_equity"),
                "avg_heat_a": pa.get("avg_heat"),
                "avg_heat_b": pb.get("avg_heat"),
                "avg_gross_exposure_a": pa.get("avg_gross_exposure"),
                "avg_gross_exposure_b": pb.get("avg_gross_exposure"),
            })

    if comparison_rows:
        cmp_df = pd.DataFrame(comparison_rows)
        cmp_csv = artifacts_dir / "path_a_vs_path_b_comparison.csv"
        cmp_df.to_csv(cmp_csv, index=False)
        cmp_md = artifacts_dir / "path_a_vs_path_b_comparison.md"
        with open(cmp_md, "w", encoding="utf-8") as f:
            f.write("# Path A vs Path B Comparison\n\n")
            f.write("## Strategy identity\n\n")
            f.write("- **Path A:** Weekly pivot / accumulation system (weekly_pp on weekly bars, weekly EMA21/MA50, next week open).\n")
            f.write("- **Path B:** True daily Pocket Pivot (daily PP, daily EMA21>MA50, next day open).\n\n")
            f.write("## Performance by period\n\n")
            f.write(cmp_df.to_string(index=False))
            f.write("\n\n## Conclusion\n\n")
            f.write("Compare CAGR, MDD, MAR and trades_per_month by period to decide which path to prioritize.\n")
        print(f"[parallel] Wrote {cmp_csv} and {cmp_md}")

    print("\n[parallel] Artifact paths:")
    for name in [
        "PARALLEL_PATHS_PLAN.md",
        "trade_scarcity_diagnosis.md",
        "path_b_daily_baseline.md",
        "path_a_vs_path_b_comparison.md",
    ]:
        p = artifacts_dir / name
        print(f"  {p}" if p.exists() else f"  (missing) {name}")


if __name__ == "__main__":
    main()
