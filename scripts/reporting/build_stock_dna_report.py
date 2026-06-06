"""
Stock DNA Report Builder — CLI runner
Reads CSV/JSON outputs from discovery and overlay backtest,
builds executive HTML report and implementation report markdown.

Usage:
  python scripts/reporting/build_stock_dna_report.py \
    --input-dir data/research/stock_dna \
    --output data/research/stock_dna/stock_dna_research_report.html

RESEARCH ONLY.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.reporting import (
    build_html_report,
    save_implementation_report,
)
from src.trading.research.stock_dna.schema import DNA_DIR, RESEARCH_ONLY_LABEL, assert_output_path_safe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("stock_dna.report_builder")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock DNA Report Builder")
    parser.add_argument("--input-dir", default=str(DNA_DIR))
    parser.add_argument("--output",    default=str(DNA_DIR / "stock_dna_research_report.html"))
    args = parser.parse_args()

    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output).parent

    assert_output_path_safe(output_dir)

    logger.info("Building Stock DNA report from: %s", input_dir)

    # Load profiles
    profiles_path = input_dir / "stock_dna_symbol_profiles.csv"
    profiles = pd.read_csv(profiles_path) if profiles_path.exists() else pd.DataFrame()

    # Load line scores
    line_scores_path = input_dir / "stock_dna_line_scores.csv"
    line_scores = pd.read_csv(line_scores_path) if line_scores_path.exists() else pd.DataFrame()

    # Load overlay metrics
    overlay_path = input_dir / "stock_dna_a3_overlay_metrics.csv"
    if overlay_path.exists():
        overlay_df = pd.read_csv(overlay_path)
        overlay_metrics = overlay_df.iloc[0].to_dict() if not overlay_df.empty else {}
    else:
        overlay_metrics = {}

    # Load null benchmark
    null_path = input_dir / "stock_dna_null_benchmark.json"
    if null_path.exists():
        with open(null_path, "r", encoding="utf-8") as f:
            null_benchmark = json.load(f)
    else:
        null_benchmark = {}

    # Load by-year overlay CSV for annual breakdown table
    by_year_path = input_dir / "stock_dna_a3_overlay_by_year.csv"
    by_year_df = pd.read_csv(by_year_path) if by_year_path.exists() else pd.DataFrame()

    # Build HTML
    html_path = build_html_report(
        profiles=profiles,
        line_scores=line_scores,
        overlay_metrics=overlay_metrics,
        null_benchmark=null_benchmark,
        output_dir=output_dir,
        by_year_df=by_year_df,
    )
    logger.info("HTML report: %s", html_path)

    # Count output files
    output_files = sorted(str(p) for p in input_dir.glob("*") if p.is_file())

    # Determine verdict
    n_med_plus = len(profiles[profiles["confidence"].isin(["MEDIUM", "HIGH"])]) if not profiles.empty else 0
    null_ok    = null_benchmark.get("passes_null_test", False)
    oos_lift   = overlay_metrics.get("v1_t2_gate_lift", 0.0) or 0.0

    if n_med_plus < 5 or not null_ok:
        verdict = "WATCHLIST_ONLY"
    elif isinstance(oos_lift, float) and oos_lift > 0.05:
        verdict = "RESEARCH_ANNOTATION_ONLY"
    else:
        verdict = "RESEARCH_ANNOTATION_ONLY"

    summary = {
        "n_symbols": len(profiles) if not profiles.empty else 0,
        "n_touch_events": "see stock_dna_line_scores.csv",
        "n_medium_plus_profiles": n_med_plus,
        "null_benchmark_passes": null_ok,
        "oos_lift": f"{float(oos_lift):.1%}" if isinstance(oos_lift, float) and not np.isnan(oos_lift) else "N/A",
        "v1_t2_gate_lift": overlay_metrics.get("v1_t2_gate_lift", "N/A"),
        "best_variant": "V1 A3-like T2 proxy (NOT proven A3 improvement — a3_true_ledger_used=False)",
        "verdict": verdict,
        "output_files": output_files,
    }

    impl_path = save_implementation_report(summary, output_dir)
    logger.info("Implementation report: %s", impl_path)

    logger.info("Report build complete. Verdict: %s", verdict)


if __name__ == "__main__":
    main()
