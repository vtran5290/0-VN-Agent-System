#!/usr/bin/env python3
"""
Convert FireAnt financials CSV → Parquet to save disk (~50–70% smaller).
Updates data/fireant_exports/summary.json paths. Removes original CSV after success.
Run from repo root: python scripts/compact_fireant_financials_to_parquet.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTS = REPO_ROOT / "data" / "fireant_exports"
FINANCIALS_DIR = EXPORTS / "financials"
SUMMARY_PATH = EXPORTS / "summary.json"


def main() -> int:
    if not FINANCIALS_DIR.exists():
        print("data/fireant_exports/financials/ not found; nothing to compact.")
        return 0

    summary_path = SUMMARY_PATH
    if not summary_path.exists():
        print("summary.json not found; run fetch_fireant_full_coverage first.")
        return 1

    try:
        import pandas as pd
    except ImportError:
        print("pandas required: pip install pandas")
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    financials = summary.get("financials") or {}
    q_file = financials.get("quarterly_file") or ""
    a_file = financials.get("annual_file") or ""

    if not q_file or not a_file:
        print("summary.json financials.quarterly_file / annual_file missing.")
        return 1

    # Normalize path (summary may use backslash)
    q_path = REPO_ROOT / q_file.replace("\\", "/")
    a_path = REPO_ROOT / a_file.replace("\\", "/")

    if not q_path.exists() or not a_path.exists():
        print("CSV paths from summary not found; skip compact.")
        return 0

    # Convert CSV → Parquet
    parquet_ext = ".parquet"
    q_parquet = q_path.with_suffix(parquet_ext)
    a_parquet = a_path.with_suffix(parquet_ext)

    print("Reading quarterly CSV...")
    q_df = pd.read_csv(q_path, low_memory=False)
    print("Writing quarterly Parquet...")
    q_df.to_parquet(q_parquet, index=False)
    del q_df

    print("Reading annual CSV...")
    a_df = pd.read_csv(a_path, low_memory=False)
    print("Writing annual Parquet...")
    a_df.to_parquet(a_parquet, index=False)
    del a_df

    # Update summary to point to .parquet (relative path, forward slash)
    def rel(p: Path) -> str:
        return str(p.relative_to(REPO_ROOT)).replace("\\", "/")

    financials["quarterly_file"] = rel(q_parquet)
    financials["annual_file"] = rel(a_parquet)
    summary["financials"] = financials
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Updated summary.json to Parquet paths.")

    # Remove original CSVs
    q_path.unlink()
    a_path.unlink()
    print("Removed original CSV files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
