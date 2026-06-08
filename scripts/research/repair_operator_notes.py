"""
Operator Note Parity Repair — Stock DNA Close-Out Fix (P0)

Council ruling 2026-06-07:
  The current on-disk CSV/JSON have stale operator_note values: all 83
  RESEARCH_ANNOTATION_ONLY rows carry WATCHLIST_ONLY notes because
  operator_note was generated before the post-step updated production_status.

  This script applies build_operator_note(..., production_status=<FINAL>)
  against each existing row and writes back CSV + JSON in one pass.

  Guardrails (council-mandated):
  1. Reads existing CSV; mutates ONLY the operator_note column.
  2. Sources production_status from the existing row (final value on disk).
  3. Asserts row count and production_status distribution unchanged.
  4. Regenerates CSV and JSON from the SAME in-memory frame in one pass.

  5-check verification gate (council Q3):
  A. RAA rows with WATCHLIST_ONLY note = 0
  B. WL/REJECT rows with bullish note = 0
  C. REJECT rows with bullish note = 0
  D. Determinism: every row's operator_note == build_operator_note(...) recomputed live
  E. Non-empty / NONE-consistency: RAA rows non-empty; NONE-confidence rows carry CAUTION sentinel

RESEARCH ONLY — no production_status, edge_confidence, tier, or line changes.
STOCK_DNA_ANNOTATION_ENABLED stays false.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.schema import DNA_DIR, RESEARCH_ONLY_LABEL, assert_output_path_safe
from src.trading.research.stock_dna.profiles import build_operator_note

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("dna.repair_operator_notes")

PROFILES_CSV  = DNA_DIR / "stock_dna_symbol_profiles.csv"
PROFILES_JSON = DNA_DIR / "stock_dna_symbol_profiles.json"


def _recompute_note(row: pd.Series) -> str:
    return build_operator_note(
        primary_line=row.get("primary_support_line") or None,
        danger_line=row.get("danger_line") or None,
        confidence=str(row.get("confidence", "NONE")),
        bull_obedience=float(row.get("regime_obedience_bull") or float("nan")),
        bear_obedience=float(row.get("regime_obedience_bear") or float("nan")),
        symbol=str(row.get("symbol", "")),
        production_status=str(row.get("production_status", "")),
    )


def repair_csv(df_orig: pd.DataFrame) -> pd.DataFrame:
    """Apply build_operator_note with final production_status to every row."""
    df = df_orig.copy()
    df["operator_note"] = df.apply(_recompute_note, axis=1)
    return df


def verify(df_orig: pd.DataFrame, df_new: pd.DataFrame) -> None:
    """Run 5-check verification gate. Raises AssertionError on any failure."""
    log.info("Running 5-check verification gate...")

    # Guard: row count and production_status distribution unchanged
    assert len(df_new) == len(df_orig), (
        f"Row count changed: {len(df_orig)} → {len(df_new)}"
    )
    orig_dist = df_orig["production_status"].value_counts().to_dict()
    new_dist  = df_new["production_status"].value_counts().to_dict()
    assert orig_dist == new_dist, (
        f"production_status distribution changed: {orig_dist} → {new_dist}"
    )
    log.info("  Guard: row count=%d, production_status distribution unchanged ✓", len(df_new))

    raa  = df_new[df_new["production_status"] == "RESEARCH_ANNOTATION_ONLY"]
    wl   = df_new[df_new["production_status"] == "WATCHLIST_ONLY"]
    rej  = df_new[df_new["production_status"] == "REJECT"]

    # Check A: RAA rows must not have WATCHLIST_ONLY note
    raa_stale = raa[raa["operator_note"].str.startswith("WATCHLIST_ONLY", na=False)]
    assert len(raa_stale) == 0, (
        f"Check A FAILED: {len(raa_stale)} RAA rows still have WATCHLIST_ONLY note: "
        f"{raa_stale['symbol'].tolist()}"
    )
    log.info("  Check A: RAA rows with WATCHLIST_ONLY note = %d ✓", len(raa_stale))

    # Check B: WATCHLIST_ONLY rows must not have bullish note
    wl_bullish = wl[wl["operator_note"].str.contains(
        "FACT: Historically respects|respects.*bull", na=False, regex=True
    )]
    assert len(wl_bullish) == 0, (
        f"Check B FAILED: {len(wl_bullish)} WL rows have bullish note"
    )
    log.info("  Check B: WL rows with bullish note = %d ✓", len(wl_bullish))

    # Check C: REJECT rows must not have bullish note
    rej_bullish = rej[rej["operator_note"].str.contains(
        "FACT: Historically respects|respects.*bull", na=False, regex=True
    )]
    assert len(rej_bullish) == 0, (
        f"Check C FAILED: {len(rej_bullish)} REJECT rows have bullish note"
    )
    log.info("  Check C: REJECT rows with bullish note = %d ✓", len(rej_bullish))

    # Check D: Determinism — recompute live and compare
    live_notes = df_new.apply(_recompute_note, axis=1)
    mismatch = (df_new["operator_note"] != live_notes).sum()
    assert mismatch == 0, (
        f"Check D FAILED: {mismatch} rows differ between written note and live recompute"
    )
    log.info("  Check D: Determinism — all %d notes match live recompute ✓", len(df_new))

    # Check E: Non-empty + NONE-consistency
    raa_empty = raa[raa["operator_note"].fillna("").str.strip() == ""]
    assert len(raa_empty) == 0, (
        f"Check E FAILED: {len(raa_empty)} RAA rows have empty operator_note"
    )
    none_conf = df_new[df_new["confidence"] == "NONE"]
    none_without_caution = none_conf[
        ~none_conf["operator_note"].str.startswith("CAUTION", na=False)
    ]
    assert len(none_without_caution) == 0, (
        f"Check E FAILED: {len(none_without_caution)} NONE-confidence rows lack CAUTION sentinel"
    )
    log.info(
        "  Check E: RAA non-empty=%d, NONE-confidence CAUTION sentinel: %d/%d ✓",
        len(raa), len(none_conf), len(none_conf),
    )

    log.info("ALL 5 CHECKS PASSED ✓")


def write_json(df: pd.DataFrame) -> None:
    """Update operator_note in JSON SSOT. Same frame as CSV (no divergence possible)."""
    if not PROFILES_JSON.exists():
        log.warning("JSON not found — skipping JSON update: %s", PROFILES_JSON)
        return
    with open(PROFILES_JSON, encoding="utf-8") as f:
        root = json.load(f)

    profiles_list = root["profiles"] if isinstance(root, dict) else root
    note_lookup = df.set_index("symbol")["operator_note"].to_dict()

    updated = 0
    for entry in profiles_list:
        if not isinstance(entry, dict):
            continue
        sym = entry.get("symbol", "")
        if sym in note_lookup:
            entry["operator_note"] = note_lookup[sym]
            updated += 1

    with open(PROFILES_JSON, "w", encoding="utf-8") as f:
        json.dump(root, f, indent=2, ensure_ascii=False, default=str)
    log.info("JSON updated: %d operator_notes written (P0-1 parity)", updated)

    # Spot-check JSON↔CSV parity for 3 random symbols
    sample_syms = df["symbol"].sample(3, random_state=42).tolist() if len(df) >= 3 else df["symbol"].tolist()
    for entry in profiles_list:
        if isinstance(entry, dict) and entry.get("symbol") in sample_syms:
            csv_note = df.set_index("symbol").loc[entry["symbol"], "operator_note"]
            assert entry["operator_note"] == csv_note, (
                f"JSON↔CSV mismatch for {entry['symbol']}"
            )
    log.info("JSON↔CSV spot-check passed for %s ✓", sample_syms)


def main() -> None:
    assert_output_path_safe(DNA_DIR)

    log.info("=" * 60)
    log.info("Operator Note Parity Repair — %s", RESEARCH_ONLY_LABEL)
    log.info("=" * 60)

    df_orig = pd.read_csv(PROFILES_CSV)
    log.info("Loaded %d rows from %s", len(df_orig), PROFILES_CSV)

    raa_before = (df_orig["production_status"] == "RESEARCH_ANNOTATION_ONLY").sum()
    stale_before = (
        df_orig[df_orig["production_status"] == "RESEARCH_ANNOTATION_ONLY"]
        ["operator_note"].str.startswith("WATCHLIST_ONLY", na=False).sum()
    )
    log.info("Before repair: %d RAA rows, %d with stale WATCHLIST_ONLY note", raa_before, stale_before)

    df_new = repair_csv(df_orig)

    verify(df_orig, df_new)

    # Write CSV
    df_new.to_csv(PROFILES_CSV, index=False)
    log.info("CSV written: %s", PROFILES_CSV)

    # Write JSON (same frame — no divergence)
    write_json(df_new)

    raa_after = (df_new["production_status"] == "RESEARCH_ANNOTATION_ONLY").sum()
    stale_after = (
        df_new[df_new["production_status"] == "RESEARCH_ANNOTATION_ONLY"]
        ["operator_note"].str.startswith("WATCHLIST_ONLY", na=False).sum()
    )
    log.info("After repair: %d RAA rows, %d with stale note (target=0)", raa_after, stale_after)
    log.info("Done. %s", RESEARCH_ONLY_LABEL)


if __name__ == "__main__":
    main()
