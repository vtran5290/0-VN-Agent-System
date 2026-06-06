"""
Stock DNA Review Packager — CLI runner
Zips all research outputs into a review pack for ChatGPT review.
Zip goes to review_outputs/ ONLY — never to production directories.

Usage:
  python scripts/research/package_stock_dna_review.py \
    --input-dir data/research/stock_dna \
    --output review_outputs/stock_dna_research_YYYYMMDD.zip

RESEARCH ONLY.
"""
import argparse
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.schema import DNA_DIR, RESEARCH_ONLY_LABEL, REVIEW_DIR, assert_output_path_safe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("stock_dna.packager")

TODAY = date.today().strftime("%Y%m%d")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock DNA Review Packager")
    parser.add_argument("--input-dir", default=str(DNA_DIR))
    parser.add_argument("--output",    default=str(REVIEW_DIR / f"stock_dna_research_{TODAY}.zip"))
    args = parser.parse_args()

    input_dir  = Path(args.input_dir)
    output_zip = Path(args.output)

    # Safety check
    assert_output_path_safe(output_zip.parent)

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Packaging Stock DNA review: %s -> %s", input_dir, output_zip)

    # Collect files — exclude large parquet files
    included = []
    excluded = []
    for p in sorted(input_dir.rglob("*")):
        if not p.is_file():
            continue
        size_mb = p.stat().st_size / 1e6
        if p.suffix in {".parquet", ".pkl"} or size_mb > 20:
            excluded.append(str(p))
            continue
        included.append(p)

    if not included:
        logger.error("No files found to package in %s", input_dir)
        sys.exit(1)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in included:
            arcname = p.relative_to(input_dir.parent)
            zf.write(p, arcname=arcname)
            logger.info("  + %s", arcname)

        # Write manifest
        manifest_lines = [
            f"# Stock DNA Review Pack — {TODAY}",
            f"# {RESEARCH_ONLY_LABEL}",
            "",
            "## Included files",
        ] + [f"  {p.relative_to(input_dir.parent)}" for p in included] + [
            "",
            "## Excluded (large or binary)",
        ] + [f"  {e}" for e in excluded] + [
            "",
            "## Instructions for ChatGPT reviewer",
            "1. Read stock_dna_implementation_report.md for summary and verdict.",
            "2. Check stock_dna_null_benchmark.json — universe_z_score >= 2 = real edge.",
            "3. Review stock_dna_symbol_profiles.csv — check sample_confidence + edge_confidence split.",
            "4. Review stock_dna_a3_overlay_metrics.csv for V1 lift.",
            "5. Review stock_dna_a3_overlay_by_year.csv for year-by-year aligned vs off-support.",
            "6. Review stock_dna_trade_level_overlay_full.csv for trade-level audit.",
            "7. Read stock_dna_open_questions.md for unresolved issues.",
            "8. OOS lift [●] insufficient OOS events is expected — verdict rests on null z-score.",
            "9. Approve/reject RESEARCH_ANNOTATION_ONLY vs WATCHLIST_ONLY per symbol.",
        ]
        zf.writestr("MANIFEST.md", "\n".join(manifest_lines))

    size_kb = output_zip.stat().st_size / 1024
    logger.info("Review pack created: %s (%.1f KB)", output_zip, size_kb)
    logger.info("Pass to ChatGPT for final review before any operator-facing integration.")


if __name__ == "__main__":
    main()
