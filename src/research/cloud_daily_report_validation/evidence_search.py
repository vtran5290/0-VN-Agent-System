"""Real repo-wide evidence search for cloud daily report validation.

Searches across src/, scripts/, tests/, docs/, data/research/, Makefile
for references to key dashboard terms. Results feed cloud_dashboard_evidence_registry.csv.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator

import pandas as pd

from .schema import OUTPUT_DIR, RESEARCH_ONLY_LABEL, _REPO

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Search targets
# ---------------------------------------------------------------------------

_SEARCH_QUERIES: list[str] = [
    "cloud_daily_report",
    "phase36",
    "daily_scan",
    "final_action",
    "NEW_T1",
    "NEW_T1_MANUAL_REVIEW_BREADTH",
    "NO_T2_BREADTH",
    "TRAIL_EXIT",
    "TP1_PARTIAL",
    "WATCH_ONLY",
    "HOLD_T1",
    "ADD_T2",
    "WAIT_PB",
    "a3_rank_score",
    "breadth_zone",
    "breadth_t1_permission",
    "breadth_t2_permission",
    "T1 permission",
    "T2 permission",
    "distribution risk",
    "distribution_risk",
    "RS correction",
    "rs_correction",
    "RS C3",
    "c3_rating",
    "S3 lead",
    "s3_lead_bucket",
    "sector L4",
    "sector_l4",
    "liquidity warnings",
    "liq_warn",
    "rank score",
    "a3_rank",
    "GK5",
    "GK10",
    "gk5",
    "gk10",
    "VNINDEX regime",
    "regime_bull",
    "ex-VIN",
    "ex_vin",
    "VIN basket",
    "portfolio overlay",
    "A3",
    "S3",
]

# Directories to search — relative to repo root
_SEARCH_DIRS: list[str] = [
    "src",
    "scripts",
    "tests",
    "docs",
    "data/research/reports",
    "data/research/portfolio_optimization",
    "data/research/group_rotation",
    "data/research/rs_rating",
    "data/research/institutional_accumulation",
]

_SEARCH_FILES_DIRECT: list[str] = [
    "Makefile",
]

# File extensions to include
_INCLUDE_EXTS: set[str] = {".py", ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ""}

# Max line length to capture
_MAX_LINE = 200


def _infer_module(file_path: Path) -> str:
    """Infer the module/area from a file path."""
    parts = file_path.parts
    if "institutional_accumulation_backtest" in parts:
        return "institutional_accumulation_backtest"
    if "distribution_risk" in str(file_path):
        return "distribution_risk_lens"
    if "rs_correction" in str(file_path) or "rs_c3" in str(file_path):
        return "rs_correction_lens"
    if "cloud_daily_report" in str(file_path):
        return "cloud_daily_report"
    if "phase36" in str(file_path) or "daily_scan" in str(file_path):
        return "phase36_daily_scan"
    if "group_rotation" in str(file_path):
        return "group_rotation"
    if "sector_l4" in str(file_path) or "sector_causality" in str(file_path):
        return "sector_l4"
    if "tests" in parts:
        return "test_suite"
    if "src" in parts:
        return "src"
    if "scripts" in parts:
        return "scripts"
    if "docs" in parts:
        return "docs"
    return "other"


def _infer_evidence_type(query: str, file_path: Path) -> str:
    """Infer what type of evidence a hit represents."""
    fp = str(file_path)
    if "test_" in fp and ".py" in fp:
        if any(q in ("forward_ret", "event_study", "backtest", "ablation") for q in [query]):
            return "RETURN_BACKTEST"
        return "BEHAVIORAL_TEST"
    if "backtest" in fp.lower() or "ablation" in fp.lower():
        return "RETURN_BACKTEST"
    if "forward_returns" in fp:
        return "FORWARD_RETURN_DATA"
    if any(q in query for q in ("TRAIL_EXIT", "TP1_PARTIAL", "TRAIL", "exit")):
        return "EXIT_LOGIC_REFERENCE"
    if any(q in query for q in ("breadth", "T1 permission", "T2 permission")):
        return "BREADTH_GATE_REFERENCE"
    if "distribution_risk" in fp or "distribution risk" in query.lower():
        return "RISK_LENS_REFERENCE"
    if any(q in query for q in ("RS correction", "rs_correction", "RS C3", "c3_rating")):
        return "RS_REFERENCE"
    if any(q in query for q in ("final_action", "NEW_T1", "ADD_T2", "WAIT_PB")):
        return "ACTION_SIGNAL_REFERENCE"
    if query in ("phase36", "daily_scan", "cloud_daily_report"):
        return "PIPELINE_REFERENCE"
    return "GENERAL_REFERENCE"


def _search_file(
    file_path: Path,
    query: str,
    pattern: re.Pattern,
) -> Iterator[dict]:
    """Yield hit dicts for a single file and query."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            yield {
                "query": query,
                "file_path": str(file_path.relative_to(_REPO)),
                "line_number": lineno,
                "matched_line": line.strip()[:_MAX_LINE],
                "inferred_module": _infer_module(file_path),
                "inferred_evidence_type": _infer_evidence_type(query, file_path),
                "research_label": RESEARCH_ONLY_LABEL,
                "notes": "",
            }


def _iter_search_paths() -> Iterator[Path]:
    """Yield all files to search."""
    seen: set[Path] = set()
    for dir_str in _SEARCH_DIRS:
        d = _REPO / dir_str
        if not d.is_dir():
            continue
        for fp in d.rglob("*"):
            if not fp.is_file():
                continue
            if fp.suffix not in _INCLUDE_EXTS and fp.suffix != "":
                continue
            if "__pycache__" in fp.parts:
                continue
            if fp.stat().st_size > 5_000_000:  # skip files >5MB (large parquet etc.)
                continue
            if fp not in seen:
                seen.add(fp)
                yield fp
    for fname in _SEARCH_FILES_DIRECT:
        fp = _REPO / fname
        if fp.is_file() and fp not in seen:
            seen.add(fp)
            yield fp


def run_evidence_search(
    queries: list[str] | None = None,
    max_hits_per_query: int = 200,
) -> pd.DataFrame:
    """Run a real repo-wide evidence search.

    Parameters
    ----------
    queries: list of search terms (defaults to _SEARCH_QUERIES)
    max_hits_per_query: cap hits per query to avoid huge DataFrames on common terms

    Returns
    -------
    DataFrame with columns: query, file_path, line_number, matched_line,
    inferred_module, inferred_evidence_type, research_label, notes
    """
    if queries is None:
        queries = _SEARCH_QUERIES

    # Pre-compile patterns (case-sensitive for signal names, case-insensitive for prose)
    patterns: dict[str, re.Pattern] = {}
    for q in queries:
        # Use word boundary for short/common terms to avoid noise
        if len(q) <= 2:
            patterns[q] = re.compile(re.escape(q))
        else:
            patterns[q] = re.compile(re.escape(q), re.IGNORECASE)

    all_hits: list[dict] = []
    files = list(_iter_search_paths())
    logger.info("Evidence search: %d files to scan for %d queries", len(files), len(queries))

    for q in queries:
        pat = patterns[q]
        hits_this_query = 0
        for fp in files:
            if hits_this_query >= max_hits_per_query:
                break
            for hit in _search_file(fp, q, pat):
                all_hits.append(hit)
                hits_this_query += 1
                if hits_this_query >= max_hits_per_query:
                    break
        logger.debug("Query %r: %d hits", q, hits_this_query)

    df = pd.DataFrame(all_hits) if all_hits else pd.DataFrame(columns=[
        "query", "file_path", "line_number", "matched_line",
        "inferred_module", "inferred_evidence_type", "research_label", "notes",
    ])
    logger.info("Evidence search complete: %d total hits across %d queries", len(df), len(queries))
    return df


def run_evidence_search_full() -> pd.DataFrame:
    """Run evidence search and write results to evidence_search_hits.csv."""
    result = run_evidence_search()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "evidence_search_hits.csv"
    result.to_csv(out, index=False)
    logger.info("Evidence search hits written to %s (%d rows)", out, len(result))
    return result
