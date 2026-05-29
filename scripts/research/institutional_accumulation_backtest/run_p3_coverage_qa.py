"""Runner: P3.1 Coverage / Price-Path QA.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.p3_coverage_qa import (
    LIQUID_THRESHOLD_20B,
    run_p3_coverage_qa,
)
from scripts.research.institutional_accumulation_backtest.build_review_pack import (
    _write_source_inventory,
    _write_diff_patch,
    _write_source_snapshots,
)

OUTCOMES_DEFAULT = "data/research/institutional_accumulation/forward_outcomes_panel.parquet"
OUT_DIR = Path("data/research/institutional_accumulation")
HTML_OUT = Path("reports/research/institutional_accumulation/p3_coverage_qa.html")
REVIEW_DIR = Path("outputs/review_packages")


def main() -> None:
    ap = argparse.ArgumentParser(description="P3.1 Coverage/Price-Path QA")
    ap.add_argument("--outcomes", default=OUTCOMES_DEFAULT)
    ap.add_argument("--liquid-threshold", type=float, default=LIQUID_THRESHOLD_20B)
    ap.add_argument("--variant-key", default="V4_NO_DISTRIBUTION_RISK")
    ap.add_argument("--top-n", type=int, default=30)
    ap.add_argument("--skip-review-pack", action="store_true")
    args = ap.parse_args()

    run_date = str(date.today())
    print(f"[P3.1] Loading outcomes from {args.outcomes} …")
    outcomes = pd.read_parquet(args.outcomes)
    print(f"[P3.1] Rows: {len(outcomes):,}  Columns: {len(outcomes.columns)}")

    result = run_p3_coverage_qa(
        outcomes=outcomes,
        out_dir=OUT_DIR,
        html_path=HTML_OUT,
        run_date=run_date,
        liquid_threshold=args.liquid_threshold,
        variant_key=args.variant_key,
        top_n=args.top_n,
    )

    print(f"[P3.1] QA Label: {result.qa_label}")
    print(f"[P3.1] Note    : {result.qa_note}")
    print(f"[P3.1] HTML    : {HTML_OUT}")

    if not args.skip_review_pack:
        _build_review_pack(run_date, result)


def _build_review_pack(run_date: str, result) -> None:
    import zipfile, io

    tag = f"institutional_accumulation_p3_coverage_qa_review_pack_{run_date.replace('-','')}"
    zip_path = REVIEW_DIR / f"{tag}.zip"
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    data_files = [
        OUT_DIR / "p3_coverage_audit_by_scan.csv",
        OUT_DIR / "p3_coverage_audit_summary.csv",
        OUT_DIR / "p3_price_path_audit.csv",
        OUT_DIR / "p3_candidate_density_by_week.csv",
        OUT_DIR / "p3_candidate_density_by_year.csv",
        OUT_DIR / "p3_missing_price_reasons.csv",
        OUT_DIR / "p3_holding_period_qa.csv",
        HTML_OUT,
    ]

    root = Path.cwd()
    snap_dir = REVIEW_DIR / f"{tag}_staging" / "source_snapshots"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in data_files:
            if p.is_file():
                arc = str(p).replace("\\", "/")
                zf.write(p, arc)
                print(f"  added {arc}")

        # implementation report
        report_lines = [
            "# P3.1 Coverage QA Implementation Report",
            "",
            f"Run date: {run_date}",
            f"QA Label: {result.qa_label}",
            f"Note: {result.qa_note}",
            "",
            "## Coverage summary",
            result.coverage_audit_summary.to_csv(index=False) if not result.coverage_audit_summary.empty else "(empty)",
            "",
            "## Holding-period QA aggregated",
        ]
        if not result.holding_period_qa.empty:
            agg = (
                result.holding_period_qa.groupby("holding_weeks")
                .agg(
                    n_scans=("scan_date", "nunique"),
                    mean_holdings=("n_held", "mean"),
                    mean_return=("mean_return", "mean"),
                    hit_rate=("hit_rate", "mean"),
                )
                .reset_index()
            )
            report_lines.append(agg.to_csv(index=False))
        report_lines += [
            "",
            "## Research-only declaration",
            "RESEARCH_ONLY_NOT_PRODUCTION — no A3/S3/OMS/final_action/DNSE/live orders/sizing changed.",
        ]
        zf.writestr("implementation_report.md", "\n".join(report_lines))

        # source snapshots
        qa_source_files = [
            root / "src" / "research" / "institutional_accumulation_backtest" / "p3_coverage_qa.py",
            root / "scripts" / "research" / "institutional_accumulation_backtest" / "run_p3_coverage_qa.py",
            root / "tests" / "test_institutional_accumulation_p3_coverage_qa.py",
        ]
        for p in qa_source_files:
            if p.is_file():
                arc = f"source_snapshots/{p.relative_to(root)}".replace("\\", "/")
                zf.write(p, arc)

    print(f"[P3.1] Review pack: {zip_path}")


if __name__ == "__main__":
    main()
