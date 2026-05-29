"""Run real repo-wide evidence search.

Writes: data/research/cloud_daily_report_validation/evidence_search_hits.csv

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from src.research.cloud_daily_report_validation.evidence_search import run_evidence_search_full

if __name__ == "__main__":
    print("RESEARCH_ONLY_NOT_PRODUCTION")
    df = run_evidence_search_full()
    print(f"Evidence search complete: {len(df)} hits")
    if not df.empty:
        print("\nTop 10 queries by hit count:")
        print(df.groupby("query").size().sort_values(ascending=False).head(10).to_string())
