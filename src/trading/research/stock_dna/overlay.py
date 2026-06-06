"""
Stock DNA A3 Overlay — Research Annotations
=============================================
Variant 1: T2 Support Gate annotation (annotation-only, research CSV only)
Variant 4: Danger Line Exit Warning annotation (annotation-only, research CSV only)

HARD CONSTRAINTS (enforced by design — this module NEVER touches):
  - final_action
  - a3_rank_score
  - position sizing
  - OMS payload
  - DNSE routing
  - Production daily scan CSV (data/decision/ and data/scan/)

Annotations go to research CSV only under data/research/stock_dna/.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.trading.research.stock_dna.schema import (
    COL_DNA_CONTEXT_SCORE,
    COL_DNA_DANGER_ACTIVE,
    COL_DNA_DANGER_LINE,
    COL_DNA_DANGER_NOTE,
    COL_DNA_T2_ACTIVE,
    COL_DNA_T2_CONFIDENCE,
    COL_DNA_T2_LINE,
    COL_DNA_T2_NOTE,
    DNA_ANNOTATION_COLS,
    DNA_DIR,
    PROTECTED_PRODUCTION_COLS,
    RESEARCH_ONLY_LABEL,
    assert_output_path_safe,
    DNAConfidence,
)

logger = logging.getLogger(__name__)

# Volume ratio threshold for danger line warning
DANGER_VOL_RATIO_THRESHOLD: float = 1.2

# Tolerance for "near support line" check in T2 annotation
T2_SUPPORT_TOLERANCE_PCT: float = 0.03   # within 3% of the primary support line


# ── Production column safety guard ───────────────────────────────────────────

def _verify_production_columns_intact(
    original: pd.DataFrame,
    enriched: pd.DataFrame,
) -> None:
    """
    Assert that all protected production columns are unchanged after annotation.
    Raises AssertionError on any violation.
    """
    for col in PROTECTED_PRODUCTION_COLS:
        if col not in original.columns:
            continue
        if col not in enriched.columns:
            raise AssertionError(
                f"[Stock DNA overlay] Protected column '{col}' was removed after annotation! "
                "Safety violation."
            )
        if not original[col].reset_index(drop=True).equals(
            enriched[col].reset_index(drop=True)
        ):
            raise AssertionError(
                f"[Stock DNA overlay] Protected column '{col}' was modified after annotation! "
                "This is a critical safety violation."
            )

    missing = [c for c in original.columns if c not in enriched.columns]
    if missing:
        raise AssertionError(
            f"[Stock DNA overlay] Original columns dropped after annotation: {missing}"
        )


# ── Variant 1: T2 Support Gate Annotation ────────────────────────────────────

def annotate_t2_support(
    scan_df: pd.DataFrame,
    profiles: pd.DataFrame,
    as_of_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Variant 1: T2 Support Gate (annotation-only).

    For each symbol in scan_df:
      - If A3 T2 condition would be active (assumed via 'a3_t2_eligible' col or all rows)
      - And symbol has a DNA profile with MEDIUM/HIGH confidence
      - And current price is within T2_SUPPORT_TOLERANCE_PCT of primary_support_line
      - Then annotate: stock_dna_t2_note, stock_dna_t2_line, stock_dna_t2_confidence, stock_dna_t2_active

    Does NOT modify final_action, a3_rank_score, or any production column.
    """
    if scan_df.empty:
        return scan_df

    original = scan_df.copy()

    # Drop pre-existing DNA annotation columns to prevent duplicates
    existing_dna = [c for c in scan_df.columns if c in DNA_ANNOTATION_COLS]
    if existing_dna:
        scan_df = scan_df.drop(columns=existing_dna)

    if profiles.empty:
        for col in DNA_ANNOTATION_COLS:
            scan_df[col] = pd.NA
        return scan_df

    # Build lookup: symbol -> profile row
    med_plus = profiles[
        profiles["confidence"].isin([DNAConfidence.MEDIUM.value, DNAConfidence.HIGH.value])
    ].set_index("symbol")

    t2_notes, t2_lines, t2_confs, t2_actives = [], [], [], []
    danger_notes, danger_lines, danger_actives = [], [], []
    context_scores = []

    for _, row in scan_df.iterrows():
        symbol = row.get("symbol")
        close  = row.get("close", np.nan)

        if symbol not in med_plus.index or pd.isna(close):
            t2_notes.append("")
            t2_lines.append(None)
            t2_confs.append(DNAConfidence.NONE.value)
            t2_actives.append(0)
            danger_notes.append("")
            danger_lines.append(None)
            danger_actives.append(0)
            context_scores.append(np.nan)
            continue

        profile = med_plus.loc[symbol]
        primary_line = profile.get("primary_support_line")
        danger_line  = profile.get("danger_line")
        confidence   = profile.get("confidence", DNAConfidence.NONE.value)
        score        = profile.get("line_obedience_score_raw", np.nan)

        context_scores.append(float(score) if pd.notna(score) else np.nan)

        # T2 support check: is price near primary support line?
        line_val = row.get(primary_line) if primary_line and primary_line in row.index else np.nan

        if primary_line and pd.notna(line_val) and pd.notna(close) and float(line_val) > 0:
            dist = abs(float(close) - float(line_val)) / float(line_val)
            near_support = dist <= T2_SUPPORT_TOLERANCE_PCT

            if near_support:
                t2_notes.append(
                    f"RESEARCH: Price near {primary_line.upper()} ({dist:.1%} away) — "
                    f"DNA confidence {confidence}. T2 add near historical support. "
                    f"Line obedience score: {score:.2f}. NOT A TRADE SIGNAL."
                )
                t2_lines.append(primary_line)
                t2_confs.append(confidence)
                t2_actives.append(1)
            else:
                t2_notes.append(
                    f"RESEARCH: Price {dist:.1%} from {primary_line.upper()} — "
                    f"not near support (threshold {T2_SUPPORT_TOLERANCE_PCT:.0%})."
                )
                t2_lines.append(primary_line)
                t2_confs.append(confidence)
                t2_actives.append(0)
        else:
            t2_notes.append("")
            t2_lines.append(primary_line)
            t2_confs.append(confidence)
            t2_actives.append(0)

        # Danger line check (Variant 4): price lost danger line?
        danger_val = row.get(danger_line) if danger_line and danger_line in row.index else np.nan
        vol_ratio  = row.get("volume_ratio", 1.0) or 1.0

        if danger_line and pd.notna(danger_val) and pd.notna(close) and float(danger_val) > 0:
            below_danger = float(close) < float(danger_val)
            vol_confirm  = float(vol_ratio) >= DANGER_VOL_RATIO_THRESHOLD

            if below_danger and vol_confirm:
                danger_notes.append(
                    f"RESEARCH: STOCK_DNA_DANGER_LINE_BREAK — price lost {danger_line.upper()} "
                    f"on {float(vol_ratio):.1f}x volume. Historical: breakdown at this level "
                    f"leads to weak forward returns. NOT A TRADE SIGNAL — operator review only."
                )
                danger_lines.append(danger_line)
                danger_actives.append(1)
            elif below_danger:
                danger_notes.append(
                    f"RESEARCH: Price below {danger_line.upper()} (no volume confirm yet)."
                )
                danger_lines.append(danger_line)
                danger_actives.append(0)
            else:
                danger_notes.append("")
                danger_lines.append(danger_line)
                danger_actives.append(0)
        else:
            danger_notes.append("")
            danger_lines.append(danger_line)
            danger_actives.append(0)

    scan_df[COL_DNA_T2_NOTE]       = t2_notes
    scan_df[COL_DNA_T2_LINE]       = t2_lines
    scan_df[COL_DNA_T2_CONFIDENCE] = t2_confs
    scan_df[COL_DNA_T2_ACTIVE]     = t2_actives
    scan_df[COL_DNA_DANGER_NOTE]   = danger_notes
    scan_df[COL_DNA_DANGER_LINE]   = danger_lines
    scan_df[COL_DNA_DANGER_ACTIVE] = danger_actives
    scan_df[COL_DNA_CONTEXT_SCORE] = context_scores

    _verify_production_columns_intact(original, scan_df)

    logger.info(
        "[Stock DNA overlay] Annotated %d rows. T2-active: %d, Danger-active: %d",
        len(scan_df),
        int(sum(t2_actives)),
        int(sum(danger_actives)),
    )

    return scan_df


# ── Walk-forward overlay metric computation ───────────────────────────────────

def compute_overlay_metrics(
    touch_df: pd.DataFrame,
    profiles: pd.DataFrame,
    panel: pd.DataFrame,
) -> dict:
    """
    Compute overlay performance metrics across walk-forward years.

    Measures:
      - Baseline: all touch events in OOS
      - V1 (T2 support gate): touch events for MEDIUM/HIGH symbols near their primary line
      - V4 (danger line): breakdown events below danger line for MEDIUM/HIGH symbols

    Returns dict of metric tables.
    """
    from src.trading.research.stock_dna.profiles import _oos_cutoff_date

    if touch_df.empty or profiles.empty:
        return {}

    oos_start = _oos_cutoff_date(panel)
    oos_touch = touch_df[pd.to_datetime(touch_df["date"]) >= oos_start].copy()
    # Drop events without a complete 20d forward window (parquet tail — no future bars yet)
    if "fwd_ret_20d" in oos_touch.columns:
        oos_touch = oos_touch[oos_touch["fwd_ret_20d"].notna()]

    if oos_touch.empty or "fwd_ret_20d" not in oos_touch.columns:
        logger.warning("No OOS touch events for overlay metric computation")
        return {}

    med_plus = profiles[
        profiles["confidence"].isin([DNAConfidence.MEDIUM.value, DNAConfidence.HIGH.value])
    ].set_index("symbol")

    # Baseline: all touch events
    baseline_br = (oos_touch["fwd_ret_20d"].dropna() > 0).mean()
    baseline_n  = len(oos_touch["fwd_ret_20d"].dropna())

    # V1: touches by DNA-profiled symbols near their primary support line
    v1_rows = []
    for symbol in oos_touch["symbol"].unique():
        if symbol not in med_plus.index:
            continue
        profile = med_plus.loc[symbol]
        primary = profile.get("primary_support_line")
        best_tol = profile.get("best_tolerance", "2pct")
        sym_oos = oos_touch[
            (oos_touch["symbol"] == symbol) &
            (oos_touch["line_name"] == primary) &
            (oos_touch["tol_name"] == best_tol)
        ] if primary else pd.DataFrame()
        if not sym_oos.empty:
            v1_rows.append(sym_oos)

    if v1_rows:
        v1_df = pd.concat(v1_rows, ignore_index=True)
        v1_br = (v1_df["fwd_ret_20d"].dropna() > 0).mean()
        v1_n  = len(v1_df["fwd_ret_20d"].dropna())
        v1_lift = float(v1_br - baseline_br)
    else:
        v1_br, v1_n, v1_lift = np.nan, 0, np.nan

    metrics = {
        "baseline_bounce_rate_20d": float(baseline_br),
        "baseline_n_events": int(baseline_n),
        "v1_t2_gate_bounce_rate_20d": float(v1_br) if pd.notna(v1_br) else np.nan,
        "v1_t2_gate_n_events": int(v1_n),
        "v1_t2_gate_lift": float(v1_lift) if pd.notna(v1_lift) else np.nan,
        "oos_start": str(oos_start.date()),
        "n_dna_profiled_symbols": len(med_plus),
        "research_label": RESEARCH_ONLY_LABEL,
    }

    return metrics


# ── Save research annotation CSV ──────────────────────────────────────────────

def save_research_annotation_csv(
    annotated_df: pd.DataFrame,
    output_dir: Path = DNA_DIR,
    filename: str = "stock_dna_daily_scan_annotations_sample.csv",
) -> Path:
    """
    Save research annotation CSV to data/research/stock_dna/ only.
    Raises if output path overlaps with production directories.
    """
    output_dir = Path(output_dir)
    assert_output_path_safe(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / filename
    dna_cols = ["symbol"] + [c for c in DNA_ANNOTATION_COLS if c in annotated_df.columns]
    annotated_df[dna_cols].to_csv(out_path, index=False)
    logger.info("Research annotation CSV saved: %s", out_path)
    return out_path
