"""Runner: P3.2 Modern-Liquidity Portfolio Simulation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.p3_2_modern_portfolio import run_p3_2_modern
from src.research.institutional_accumulation_backtest.p3_2_reporting import write_p3_2_html

OUTCOMES_DEFAULT = "data/research/institutional_accumulation/forward_outcomes_panel.parquet"
OUT_DIR = Path("data/research/institutional_accumulation")
HTML_OUT = Path("reports/research/institutional_accumulation/p3_2_modern_liquidity_portfolio.html")
REVIEW_DIR = Path("outputs/review_packages")


def main() -> None:
    ap = argparse.ArgumentParser(description="P3.2 Modern-Liquidity Portfolio")
    ap.add_argument("--outcomes", default=OUTCOMES_DEFAULT)
    ap.add_argument("--skip-review-pack", action="store_true")
    args = ap.parse_args()

    run_date = str(date.today())
    print(f"[P3.2] Loading {args.outcomes} …")
    outcomes = pd.read_parquet(args.outcomes)
    print(f"[P3.2] rows={len(outcomes):,}  tickers={outcomes['ticker'].nunique()}")

    result = run_p3_2_modern(outcomes, OUT_DIR)

    write_p3_2_html(
        HTML_OUT,
        portfolio_metrics=result.portfolio_metrics,
        diagnostic_summary=result.diagnostic_summary,
        equity_curves=result.equity_curves,
        turnover_capacity=result.turnover_capacity,
        yearly_returns=result.yearly_returns,
        sensitivity=result.sensitivity,
        run_date=run_date,
    )
    print(f"[P3.2] HTML: {HTML_OUT}")

    if not args.skip_review_pack:
        _build_review_pack(run_date, result)
    else:
        print("[P3.2] Skipped review pack.")


def _build_review_pack(run_date: str, result) -> None:
    tag = f"institutional_accumulation_p3_2_modern_liquidity_review_pack_{run_date.replace('-', '')}"
    zip_path = REVIEW_DIR / f"{tag}.zip"
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    data_files = [
        OUT_DIR / "p3_2_modern_portfolio_metrics.csv",
        OUT_DIR / "p3_2_modern_equity_curves.csv",
        OUT_DIR / "p3_2_modern_turnover_capacity.csv",
        OUT_DIR / "p3_2_modern_yearly_returns.csv",
        OUT_DIR / "p3_2_modern_sensitivity.csv",
        OUT_DIR / "p3_2_diagnostic_summary.csv",
        HTML_OUT,
    ]

    root = Path.cwd()
    source_files = [
        root / "src" / "research" / "institutional_accumulation_backtest" / "p3_2_modern_portfolio.py",
        root / "src" / "research" / "institutional_accumulation_backtest" / "p3_2_reporting.py",
        root / "scripts" / "research" / "institutional_accumulation_backtest" / "run_p3_2_modern_portfolio.py",
        root / "tests" / "test_institutional_accumulation_p3_2_modern_portfolio.py",
    ]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in data_files:
            if p.is_file():
                arc = str(p).replace("\\", "/")
                zf.write(p, arc)
                print(f"  added {arc}")
        for p in source_files:
            if p.is_file():
                arc = f"source_snapshots/{p.relative_to(root)}".replace("\\", "/")
                zf.write(p, arc)

        _write_impl_report(zf, run_date, result)

    print(f"[P3.2] Review pack: {zip_path}")


def _write_impl_report(zf: zipfile.ZipFile, run_date: str, result) -> None:
    diag = result.diagnostic_summary
    promising = diag[diag["label"] == "PORTFOLIO_PROMISING"]

    lines = [
        "# P3.2 Modern-Liquidity Portfolio — Implementation Report",
        f"\nRun date: {run_date}",
        "\nResearch-only. No A3/S3/OMS/final_action/DNSE/live trading changed.",
        "\n## Diagnostic summary (modern_20b)\n",
        diag[diag["liq_threshold_label"] == "20b"].to_csv(index=False),
        "\n## Promising portfolios\n",
        promising.to_csv(index=False) if not promising.empty else "(none)",
        "\n## Liquidity sensitivity (top_n=20)\n",
        result.sensitivity.to_csv(index=False) if not result.sensitivity.empty else "(empty)",
    ]
    zf.writestr("implementation_report.md", "\n".join(lines))


if __name__ == "__main__":
    main()
