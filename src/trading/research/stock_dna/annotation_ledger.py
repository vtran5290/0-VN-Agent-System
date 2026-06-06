"""
Stock DNA Annotation Ledger — Research-only parallel output.

Writes stock_dna_annotation_ledger.csv to data/research/stock_dna/ ONLY.
Never writes to data/decision, data/scan, data/state, or data/paper_trade.

This module implements the daily/reporting annotation layer approved by ChatGPT
on 2026-06-05 for RESEARCH_ANNOTATION_ONLY status.

Hard constraints (enforced by assert_output_path_safe + design):
  - Does NOT modify final_action, a3_rank_score, OMS, DNSE, sizing
  - Does NOT write to production scan/decision directories
  - Does NOT perform price fetches or OHLCV reads (uses close already on scan row)
  - Does NOT surface stock_dna_null_z in operator-facing notes (A6: nan/proxy context)
  - Feature flag STOCK_DNA_ANNOTATION_ENABLED must be True to write the ledger

Display note semantics:
  RAA + aligned    → DNA_SUPPORT_ALIGNED: [line]@[tol], edge=[ec]
  RAA + off        → DNA_OFF_SUPPORT
  RAA + danger     → appended: | DNA_DANGER_LINE_BREAK: [line]
  WATCHLIST_ONLY   → DNA_WATCHLIST_NO_EDGE  (explicit caution, not silence)
  REJECT           → DNA_REJECT_NO_EDGE
  No profile       → (empty — symbol not covered)
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.trading.research.stock_dna.schema import (
    DNA_DIR,
    INTEGRATION_STATUS_LABEL,
    RESEARCH_ONLY_LABEL,
    STOCK_DNA_ANNOTATION_ENABLED,
    assert_output_path_safe,
)

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()

LEDGER_FILENAME = "stock_dna_annotation_ledger.csv"

# Supported support-line column names (must match panel/scan column naming)
_LINE_COLS = frozenset({"ema20", "ema50", "sma100", "sma150"})

# Within 3% of support line = DNA-aligned
_SUPPORT_TOLERANCE_PCT = 0.03

# Ledger column order
LEDGER_COLS = [
    "scan_date",
    "symbol",
    "stock_dna_status",
    "stock_dna_primary_support_line",
    "stock_dna_support_tolerance",
    "stock_dna_distance_to_support_pct",
    "stock_dna_aligned_flag",
    "stock_dna_edge_confidence",
    "stock_dna_sample_confidence",
    "stock_dna_null_z",           # diagnostic only — not surfaced in operator notes (A6)
    "stock_dna_danger_line",
    "stock_dna_danger_flag",
    "stock_dna_operator_note",
]


def _note_for_raa(
    aligned: bool,
    primary_line: Optional[str],
    best_tol: Optional[str],
    edge_conf: str,
    danger_line: Optional[str],
    danger_flag: int,
) -> str:
    """Build operator-note string for RESEARCH_ANNOTATION_ONLY symbols."""
    if aligned and primary_line:
        tol_str = best_tol or "—"
        note = f"DNA_SUPPORT_ALIGNED: {primary_line.upper()}@{tol_str}, edge={edge_conf}"
    else:
        note = "DNA_OFF_SUPPORT"

    if danger_flag and danger_line:
        note += f" | DNA_DANGER_LINE_BREAK: {danger_line.upper()}"

    return note


def build_annotation_ledger(
    scan_df: pd.DataFrame,
    profiles: pd.DataFrame,
    scan_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Build the Stock DNA annotation ledger for one scan date.

    Parameters
    ----------
    scan_df   : daily scan DataFrame (must contain 'symbol' and 'close'; support-line
                columns optional but used for distance computation if present).
                No price fetches are performed — close must already be on the row.
    profiles  : stock_dna_symbol_profiles DataFrame (from discovery pipeline).
    scan_date : ISO date string (default: today).

    Returns
    -------
    DataFrame with LEDGER_COLS columns. Never modifies scan_df.
    """
    as_of = scan_date or TODAY

    if scan_df.empty:
        logger.warning("[DNA ledger] Empty scan_df — returning empty ledger.")
        return pd.DataFrame(columns=LEDGER_COLS)

    if profiles.empty:
        logger.warning("[DNA ledger] No profiles available — ledger will have no annotations.")

    # Build profile lookup keyed by symbol
    prof_lookup: dict = {}
    if not profiles.empty:
        for _, prow in profiles.iterrows():
            prof_lookup[prow["symbol"]] = prow.to_dict()

    rows = []
    for _, srow in scan_df.iterrows():
        sym   = str(srow.get("symbol", ""))
        close = srow.get("close", np.nan)

        if sym not in prof_lookup:
            rows.append({
                "scan_date": as_of, "symbol": sym,
                "stock_dna_status": "UNPROFILED",
                "stock_dna_primary_support_line": None,
                "stock_dna_support_tolerance": None,
                "stock_dna_distance_to_support_pct": None,
                "stock_dna_aligned_flag": 0,
                "stock_dna_edge_confidence": None,
                "stock_dna_sample_confidence": None,
                "stock_dna_null_z": None,
                "stock_dna_danger_line": None,
                "stock_dna_danger_flag": 0,
                "stock_dna_operator_note": "",
            })
            continue

        p = prof_lookup[sym]
        status       = p.get("production_status", "REJECT")
        primary_line = p.get("primary_support_line")
        best_tol     = p.get("best_tolerance")
        edge_conf    = p.get("edge_confidence", "NONE")
        sample_conf  = p.get("sample_confidence", "NONE")
        null_z       = p.get("per_symbol_null_z")          # stored in ledger, not in notes (A6)
        danger_line  = p.get("danger_line")

        # Distance to support — uses close already on scan row, no fetch
        dist_pct: Optional[float] = None
        aligned_flag = 0
        if primary_line and pd.notna(close):
            line_val = srow.get(primary_line, np.nan)
            if pd.notna(line_val) and float(line_val) > 0:
                dist_pct = abs(float(close) - float(line_val)) / float(line_val)
                aligned_flag = int(dist_pct <= _SUPPORT_TOLERANCE_PCT)

        # Danger flag: price below danger line
        danger_flag = 0
        if danger_line:
            dl_val = srow.get(danger_line, np.nan)
            if pd.notna(dl_val) and pd.notna(close) and float(close) < float(dl_val):
                danger_flag = 1

        # Operator note — varies by production_status
        if status == "RESEARCH_ANNOTATION_ONLY":
            note = _note_for_raa(
                aligned=bool(aligned_flag),
                primary_line=primary_line,
                best_tol=best_tol,
                edge_conf=edge_conf,
                danger_line=danger_line,
                danger_flag=danger_flag,
            )
        elif status == "WATCHLIST_ONLY":
            # Explicit caution marker — no bullish/aligned language (council A5)
            note = "DNA_WATCHLIST_NO_EDGE"
            if danger_flag and danger_line:
                note += f" | DNA_DANGER_LINE_BREAK: {danger_line.upper()}"
        elif status == "REJECT":
            note = "DNA_REJECT_NO_EDGE"
        else:
            note = ""

        rows.append({
            "scan_date": as_of,
            "symbol": sym,
            "stock_dna_status": status,
            "stock_dna_primary_support_line": primary_line,
            "stock_dna_support_tolerance": best_tol,
            "stock_dna_distance_to_support_pct": round(dist_pct, 5) if dist_pct is not None else None,
            "stock_dna_aligned_flag": aligned_flag,
            "stock_dna_edge_confidence": edge_conf,
            "stock_dna_sample_confidence": sample_conf,
            "stock_dna_null_z": round(float(null_z), 4) if null_z is not None and pd.notna(null_z) else None,
            "stock_dna_danger_line": danger_line,
            "stock_dna_danger_flag": danger_flag,
            "stock_dna_operator_note": note,
        })

    return pd.DataFrame(rows, columns=LEDGER_COLS)


def write_annotation_ledger(
    ledger_df: pd.DataFrame,
    output_dir: Path = DNA_DIR,
) -> Optional[Path]:
    """
    Write the annotation ledger to data/research/stock_dna/stock_dna_annotation_ledger.csv.
    Raises if output path overlaps with any production directory.
    Returns the written path, or None if feature flag is OFF.
    """
    if not STOCK_DNA_ANNOTATION_ENABLED:
        logger.debug("[DNA ledger] Feature flag OFF — ledger not written.")
        return None

    output_dir = Path(output_dir)
    assert_output_path_safe(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / LEDGER_FILENAME
    ledger_df.to_csv(out_path, index=False)
    logger.info(
        "[DNA ledger] %s — %d rows written to %s",
        INTEGRATION_STATUS_LABEL,
        len(ledger_df),
        out_path,
    )
    return out_path


def maybe_write_annotation_ledger(
    scan_df: pd.DataFrame,
    output_dir: Path = DNA_DIR,
    scan_date: Optional[str] = None,
) -> Optional[Path]:
    """
    Load profiles from the research output dir and write the annotation ledger,
    but only if STOCK_DNA_ANNOTATION_ENABLED=true.

    Designed to be called from daily_scan_report.py at the very end, after
    daily_scan.md and daily_scan.json have already been written.
    scan_df must be the same DataFrame used for the scan — this function
    never modifies it (no return value for scan_df).

    Safe to call even if profiles CSV does not exist.
    """
    if not STOCK_DNA_ANNOTATION_ENABLED:
        return None

    profiles_path = Path(output_dir) / "stock_dna_symbol_profiles.csv"
    if not profiles_path.exists():
        logger.warning(
            "[DNA ledger] Profiles CSV not found at %s — run discovery pipeline first. "
            "Ledger not written.",
            profiles_path,
        )
        return None

    profiles = pd.read_csv(profiles_path)
    ledger_df = build_annotation_ledger(scan_df, profiles, scan_date=scan_date)
    return write_annotation_ledger(ledger_df, output_dir=output_dir)
