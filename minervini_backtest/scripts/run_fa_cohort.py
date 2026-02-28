# minervini_backtest/scripts/run_fa_cohort.py — Lightweight FA Cohort Study
"""
Run FA cohort backtest:

  - Load FA CSV (symbol, report_date, eps_yoy, eps_qoq_accel_flag,
    earnings_yoy, earnings_qoq_accel_flag, sales_yoy,
    roe, gross_margin_yoy, debt_to_equity).
  - Build quarterly cohorts that pass FA filters.
  - Buy next trading day close, hold fixed horizons (8/10/13 weeks).
  - Compute equal-weight cohort vs benchmark returns.

Outputs (default under minervini_backtest/outputs/fa_cohort):
  - annual_cohort_counts.csv
  - cohort_returns.csv
  - yearly_alpha.csv
  - summary.md (with PASS/FAIL verdict)

Run example:
  .\.venv\Scripts\python.exe minervini_backtest/scripts/run_fa_cohort.py --fa-csv data/fa_minervini.csv --horizons 8 10 13
"""
from __future__ import annotations
import sys
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent.parent  # .../minervini_backtest
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fa_cohort.fa_filters import FaFilterConfig
from fa_cohort.cohort_backtest import run_cohort_backtest


def main() -> int:
    p = argparse.ArgumentParser(description="FA Cohort Study runner")
    p.add_argument("--fa-csv", required=True, help="Path to FA CSV (symbol, report_date, eps_yoy, etc.)")
    p.add_argument("--horizons", nargs="+", type=int, default=[8, 10, 13], help="Hold horizons in weeks")
    p.add_argument("--bench", default="VNINDEX", help="Benchmark symbol (default VNINDEX)")
    p.add_argument("--out-dir", default=str(Path("minervini_backtest") / "outputs" / "fa_cohort"))
    p.add_argument("--start", default=None, help="Min report_date (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="Max report_date (YYYY-MM-DD)")
    # Optional FA thresholds overrides
    p.add_argument("--eps-yoy-min", type=float, default=20.0)
    p.add_argument("--sales-yoy-min", type=float, default=15.0)
    p.add_argument("--roe-min", type=float, default=15.0)
    p.add_argument("--margin-yoy-min", type=float, default=0.0)
    p.add_argument("--debt-to-equity-max", type=float, default=None)
    p.add_argument("--require-eps-accel", action="store_true")
    p.add_argument(
        "--earnings-yoy-min",
        type=float,
        default=None,
        help="Minimum earnings YoY (from net_profit) to pass filter; None to disable",
    )
    p.add_argument(
        "--require-earnings-accel",
        action="store_true",
        help="Require earnings acceleration flag (earnings_qoq_accel_flag == 1) when available",
    )

    args = p.parse_args()

    cfg = FaFilterConfig(
        eps_yoy_min=args.eps_yoy_min,
        sales_yoy_min=args.sales_yoy_min,
        roe_min=args.roe_min,
        debt_to_equity_max=args.debt_to_equity_max,
        margin_yoy_min=args.margin_yoy_min,
        require_eps_accel=args.require_eps_accel,
        earnings_yoy_min=args.earnings_yoy_min,
        require_earnings_accel=args.require_earnings_accel,
    )

    run_cohort_backtest(
        fa_csv=args.fa_csv,
        horizons=args.horizons,
        bench_symbol=args.bench,
        start=args.start,
        end=args.end,
        cfg=cfg,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

