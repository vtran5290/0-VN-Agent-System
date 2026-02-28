from __future__ import annotations

"""
run_fa_cohort_end_to_end.py
===========================

Convenience runner for FA Cohort Study (Phase 2).

Pipeline:
  1) (Optional) Fetch quarterly fundamentals from FireAnt into `data/fundamentals_raw.csv`
     using `fetch_fundamentals_raw.py`.
  2) Build `data/fa_minervini.csv` via `build_fa_minervini_csv.py`.
  3) Run FA Cohort backtest (`run_fa_cohort.py`) for:
       - Run 0 (base): no acceleration requirement
       - Run 1 EPS accel (optional): require_eps_accel = True, only if
         --require-eps-accel is passed AND eps_yoy coverage >= 70%.
       - Run 1 earnings accel (optional): require_earnings_accel = True
         when --require-earnings-accel is passed (uses earnings_yoy /
         earnings_qoq_accel_flag derived from net_profit).

Outputs:
  - minervini_backtest/outputs/fa_cohort/run0_base/...
  - minervini_backtest/outputs/fa_cohort/run1_eps_accel/...        (optional, EPS accel)
  - minervini_backtest/outputs/fa_cohort/run1_earnings_accel/...   (optional, earnings accel)

Typical usage (from repo root):

  .\.venv\Scripts\python.exe minervini_backtest/scripts/run_fa_cohort_end_to_end.py ^
      --fetch ^
      --symbols-file minervini_backtest/config/watchlist_80.txt ^
      --start 2014-01-01 --end 2024-12-31 ^
      --raw-out data/fundamentals_raw.csv ^
      --fa-out data/fa_minervini.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # .../minervini_backtest
REPO_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fa_cohort.fa_filters import FaFilterConfig  # type: ignore
from fa_cohort.cohort_backtest import run_cohort_backtest  # type: ignore
from scripts.fetch_fundamentals_raw import build_fundamentals_csv  # type: ignore
from scripts.build_fa_minervini_csv import build_fa_csv  # type: ignore


def _eps_coverage(fa_csv: Path) -> float:
    """
    Compute non-NaN coverage ratio for eps_yoy column in FA CSV.
    Returns value in [0, 1]. If column missing/empty -> 0.0.
    """
    if not fa_csv.exists():
        return 0.0
    df = pd.read_csv(fa_csv)
    if "eps_yoy" not in df.columns or df.empty:
        return 0.0
    return float(df["eps_yoy"].notna().mean())


def main() -> int:
    p = argparse.ArgumentParser(description="End-to-end FA Cohort Study runner")

    # Fetch fundamentals_raw.csv
    p.add_argument(
        "--fetch",
        action="store_true",
        help="If set, fetch fundamentals_raw.csv from FireAnt before building FA CSV",
    )
    p.add_argument(
        "--symbols-file",
        default=str(Path("minervini_backtest") / "config" / "watchlist_80.txt"),
        help="Path to symbols file (one symbol per line)",
    )
    p.add_argument(
        "--start",
        default="2014-01-01",
        help="Start date for fundamentals fetch (YYYY-MM-DD)",
    )
    p.add_argument(
        "--end",
        default="2024-12-31",
        help="End date for fundamentals fetch (YYYY-MM-DD)",
    )
    p.add_argument(
        "--raw-out",
        default="data/fundamentals_raw.csv",
        help="Output path for fundamentals_raw.csv",
    )

    # Build fa_minervini.csv
    p.add_argument(
        "--fa-out",
        default="data/fa_minervini.csv",
        help="Output path for fa_minervini.csv",
    )

    # Cohort backtest params
    p.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=[8, 10, 13],
        help="Hold horizons in weeks",
    )
    p.add_argument(
        "--bench",
        default="VNINDEX",
        help="Benchmark symbol (default VNINDEX)",
    )
    p.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs" / "fa_cohort"),
        help="Base output directory for FA cohort runs",
    )
    p.add_argument(
        "--start-report",
        default=None,
        help="Min report_date (YYYY-MM-DD) for cohort window",
    )
    p.add_argument(
        "--end-report",
        default=None,
        help="Max report_date (YYYY-MM-DD) for cohort window",
    )

    # FA filter thresholds (mirrors run_fa_cohort.py)
    p.add_argument("--eps-yoy-min", type=float, default=20.0)
    p.add_argument("--sales-yoy-min", type=float, default=15.0)
    p.add_argument("--roe-min", type=float, default=15.0)
    p.add_argument("--margin-yoy-min", type=float, default=0.0)
    p.add_argument("--debt-to-equity-max", type=float, default=None)
    p.add_argument(
        "--require-eps-accel",
        action="store_true",
        help="If set, also run a cohort with require_eps_accel=True when eps_yoy coverage >= 70%%",
    )
    p.add_argument(
        "--earnings-yoy-min",
        type=float,
        default=None,
        help="Minimum earnings YoY (from net_profit) to pass filter; None to disable",
    )
    p.add_argument(
        "--require-earnings-accel",
        action="store_true",
        help="If set, also run a cohort with require_earnings_accel=True (earnings accel based on net_profit)",
    )

    args = p.parse_args()

    raw_path = Path(args.raw_out)
    fa_path = Path(args.fa_out)
    out_root = Path(args.out_dir)

    # 1) Fetch fundamentals_raw.csv (optional)
    if args.fetch:
        try:
            build_fundamentals_csv(
                symbols_file=Path(args.symbols_file),
                start_str=args.start,
                end_str=args.end,
                out_path=raw_path,
            )
        except Exception as e:
            print(f"[fa_cohort_e2e] fundamentals_raw fetch failed: {e}", file=sys.stderr)
            return 1

    # 2) Build fa_minervini.csv (always)
    try:
        build_fa_csv(in_path=raw_path, out_path=fa_path)
    except Exception as e:
        print(f"[fa_cohort_e2e] build_fa_minervini_csv failed: {e}", file=sys.stderr)
        return 1

    # 3) Run FA cohort(s)
    coverage = _eps_coverage(fa_path)
    print(f"[fa_cohort_e2e] eps_yoy coverage in {fa_path}: {coverage:.3%}")

    # Base filter config (Run 0)
    base_cfg = FaFilterConfig(
        eps_yoy_min=args.eps_yoy_min,
        sales_yoy_min=args.sales_yoy_min,
        roe_min=args.roe_min,
        margin_yoy_min=args.margin_yoy_min,
        debt_to_equity_max=args.debt_to_equity_max,
        require_eps_accel=False,
        earnings_yoy_min=args.earnings_yoy_min,
        require_earnings_accel=False,
    )

    # Run 0: no EPS accel requirement
    out_run0 = out_root / "run0_base"
    run_cohort_backtest(
        fa_csv=str(fa_path),
        horizons=args.horizons,
        bench_symbol=args.bench,
        start=args.start_report,
        end=args.end_report,
        cfg=base_cfg,
        out_dir=str(out_run0),
    )
    print(f"[fa_cohort_e2e] Run 0 (base) written to {out_run0}")

    # Run 1: require_eps_accel (only if requested AND coverage ok)
    if args.require_eps_accel:
        if coverage >= 0.70:
            accel_cfg = FaFilterConfig(
                eps_yoy_min=args.eps_yoy_min,
                sales_yoy_min=args.sales_yoy_min,
                roe_min=args.roe_min,
                margin_yoy_min=args.margin_yoy_min,
                debt_to_equity_max=args.debt_to_equity_max,
                require_eps_accel=True,
                earnings_yoy_min=args.earnings_yoy_min,
                require_earnings_accel=False,
            )
            out_run1 = out_root / "run1_eps_accel"
            run_cohort_backtest(
                fa_csv=str(fa_path),
                horizons=args.horizons,
                bench_symbol=args.bench,
                start=args.start_report,
                end=args.end_report,
                cfg=accel_cfg,
                out_dir=str(out_run1),
            )
            print(f"[fa_cohort_e2e] Run 1 (require_eps_accel) written to {out_run1}")
        else:
            print(
                f"[fa_cohort_e2e] Skip Run 1: eps_yoy coverage {coverage:.3%} < 70% "
                "(use --require-eps-accel only when EPS data sufficiently populated)."
            )

    # Run 1 (earnings accel): no coverage gating; relies on net_profit coverage
    if args.require_earnings_accel:
        earnings_accel_cfg = FaFilterConfig(
            eps_yoy_min=args.eps_yoy_min,
            sales_yoy_min=args.sales_yoy_min,
            roe_min=args.roe_min,
            margin_yoy_min=args.margin_yoy_min,
            debt_to_equity_max=args.debt_to_equity_max,
            require_eps_accel=False,
            earnings_yoy_min=args.earnings_yoy_min,
            require_earnings_accel=True,
        )
        out_run1_earnings = out_root / "run1_earnings_accel"
        run_cohort_backtest(
            fa_csv=str(fa_path),
            horizons=args.horizons,
            bench_symbol=args.bench,
            start=args.start_report,
            end=args.end_report,
            cfg=earnings_accel_cfg,
            out_dir=str(out_run1_earnings),
        )
        print(f"[fa_cohort_e2e] Run 1 (earnings accel) written to {out_run1_earnings}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

