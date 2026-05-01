from __future__ import annotations

"""
Utility: list symbols in Q1 2026 that pass the A_balanced_improver short-term FA preset.

This is a thin wrapper around fa_filters.FaFilterConfig + fa_pass on data/fa_minervini.csv.
"""

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # .../minervini_backtest
REPO = ROOT.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fa_cohort.fa_filters import FaFilterConfig, fa_pass  # type: ignore  # noqa: E402


def main() -> int:
    fa_path = REPO / "data" / "fa_minervini.csv"
    df = pd.read_csv(fa_path)
    df["report_date"] = pd.to_datetime(df["report_date"])

    start = pd.Timestamp("2026-01-01")
    end = pd.Timestamp("2026-03-31")
    q1 = df[(df["report_date"] >= start) & (df["report_date"] <= end)].copy()

    cfg = FaFilterConfig(
        debt_to_equity_max=0.90,
        gross_margin_min=0.18,
        roe_min=14,
        sales_yoy_min=10,
        earnings_yoy_min=5,
        eps_yoy_min=None,
        margin_yoy_min=0,
        require_earnings_accel=True,
        require_eps_accel=False,
    )

    passes: list[tuple[str, str]] = []
    for _, row in q1.iterrows():
        if fa_pass(row, cfg):
            passes.append((str(row["symbol"]), row["report_date"].strftime("%Y-%m-%d")))

    symbols = sorted({s for s, _ in passes})
    print(f"Q1 2026 symbols passing A_balanced_improver (count={len(symbols)}):")
    print(", ".join(symbols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

