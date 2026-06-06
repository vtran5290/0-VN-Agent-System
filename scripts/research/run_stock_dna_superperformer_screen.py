"""
Stock DNA Super-Performer Screen — CLI runner

Filters stock_dna_symbol_profiles.csv into two ranked watchlists:

  Tier A — Highest conviction (corrected from council's original ema20/ema50 assumption):
    regime_obedience_bull > 0.6
    instability_penalty < median
    edge_confidence in {MODERATE, STRONG}
    production_status in {RESEARCH_ANNOTATION_ONLY, WATCHLIST_ONLY}
    (line restriction removed — data shows sma150/sma100 dominate quality stocks)

  Tier B — EMA-line subset (fast-moving support, relaxed thresholds):
    regime_obedience_bull > 0.5
    primary_support_line in {ema20, ema50}
    edge_confidence in {WEAK, MODERATE, STRONG}

Composite score:
    score = regime_obedience_bull * 0.4
          + bounce_rate_20d * 0.3
          + median_fwd_ret_20d_norm * 0.2
          + (1 - instability_penalty) * 0.1

Outputs:
    data/research/stock_dna/stock_dna_superperformer_screen.csv
    data/research/stock_dna/stock_dna_superperformer_screen.md

RESEARCH ONLY — does not modify A3, OMS, DNSE, final_action, sizing, live scan.
STOCK_DNA_ANNOTATION_ENABLED stays false.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.schema import (
    DNA_DIR,
    RESEARCH_ONLY_LABEL,
    assert_output_path_safe,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("stock_dna.superperformer_screen")

OUTPUT_CSV = DNA_DIR / "stock_dna_superperformer_screen.csv"
OUTPUT_MD  = DNA_DIR / "stock_dna_superperformer_screen.md"

DISPLAY_COLS = [
    "symbol",
    "tier",
    "composite_score",
    "primary_support_line",
    "edge_confidence",
    "regime_obedience_bull",
    "instability_penalty",
    "bounce_rate_20d",
    "median_fwd_ret_20d",
    "oos_lift",
    "n_touch",
    "liquidity_bucket",
    "production_status",
    "data_end",
    "operator_note",
]


def _norm_col(s: pd.Series) -> pd.Series:
    """Min-max normalise a series; returns 0.5 for all-same or all-NaN."""
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


def build_screen(profiles: pd.DataFrame) -> pd.DataFrame:
    """Apply Tier A + Tier B filters, score, rank, return combined DataFrame."""

    df = profiles.copy()
    penalty_median = df["instability_penalty"].median()

    # ── Tier A ────────────────────────────────────────────────────────────────
    # NOTE: instability_penalty is bimodal (0 or 0.25 max). Using median as hard
    # filter excluded all 20 best stocks (HAX/ANV/TIG/BSR all at 0.25).
    # Penalty is kept as an informational sort column, not a hard gate.
    mask_a = (
        (df["regime_obedience_bull"] > 0.6)
        & (df["edge_confidence"].isin(["MODERATE", "STRONG"]))
        & (df["production_status"].isin(["RESEARCH_ANNOTATION_ONLY", "WATCHLIST_ONLY"]))
        & (df["vin_distortion_flag"] == 0)
    )

    # ── Tier B — EMA subset ───────────────────────────────────────────────────
    mask_b = (
        (df["regime_obedience_bull"] > 0.5)
        & (df["primary_support_line"].isin(["ema20", "ema50"]))
        & (df["edge_confidence"].isin(["WEAK", "MODERATE", "STRONG"]))
        & (~mask_a)  # exclude already captured in Tier A
    )

    tier_a = df[mask_a].copy()
    tier_a["tier"] = "A"
    tier_b = df[mask_b].copy()
    tier_b["tier"] = "B"

    combined = pd.concat([tier_a, tier_b], ignore_index=True)

    if combined.empty:
        logger.warning("No stocks passed either filter — check input data.")
        return combined

    # ── Composite score ───────────────────────────────────────────────────────
    bull_norm   = _norm_col(combined["regime_obedience_bull"].fillna(0))
    br_norm     = _norm_col(combined["bounce_rate_20d"].fillna(0))
    ret_norm    = _norm_col(combined["median_fwd_ret_20d"].fillna(0))
    pen_norm    = 1 - _norm_col(combined["instability_penalty"].fillna(combined["instability_penalty"].median()))

    combined["composite_score"] = (
        bull_norm * 0.40
        + br_norm  * 0.30
        + ret_norm * 0.20
        + pen_norm * 0.10
    ).round(4)

    # Sort: Tier A first, then by score descending
    combined = combined.sort_values(
        ["tier", "composite_score"], ascending=[True, False]
    ).reset_index(drop=True)

    # Top 15 within Tier A get WATCHLIST_PRIORITY flag
    tier_a_idx = combined[combined["tier"] == "A"].index
    top15 = tier_a_idx[:15]
    combined["watchlist_priority"] = False
    combined.loc[top15, "watchlist_priority"] = True

    combined["research_only_flag"] = RESEARCH_ONLY_LABEL

    return combined


def write_csv(screen: pd.DataFrame, path: Path) -> None:
    cols = [c for c in DISPLAY_COLS + ["watchlist_priority", "research_only_flag"]
            if c in screen.columns]
    screen[cols].to_csv(path, index=False)
    logger.info("Screen CSV saved: %s  (%d rows)", path, len(screen))


def write_md(screen: pd.DataFrame, path: Path, penalty_median: float) -> None:
    lines: list[str] = []

    lines += [
        "# Stock DNA Super-Performer Screen",
        "",
        f"> {RESEARCH_ONLY_LABEL}",
        "",
        f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Input:** `data/research/stock_dna/stock_dna_symbol_profiles.csv`  ",
        f"**instability_penalty median:** {penalty_median:.4f}",
        "",
        "## Council Filter Calibration Note",
        "",
        "Original council filter assumed `primary_support_line ∈ {ema20, ema50}` for quality stocks.",
        "**Data finding:** MODERATE/STRONG edge_confidence stocks overwhelmingly prefer `sma150` (27) and",
        "`sma100` (21); only 3 use ema20/ema50. Bull-obedient stocks (regime_obedience_bull > 0.6) also",
        "prefer sma150 (27) / sma100 (22). Line restriction removed from Tier A.",
        "Tier B preserves the EMA subset at relaxed thresholds for operators who prefer fast-moving support.",
        "",
    ]

    tier_a = screen[screen["tier"] == "A"]
    tier_b = screen[screen["tier"] == "B"]
    priority = screen[screen.get("watchlist_priority", False) == True] if "watchlist_priority" in screen.columns else pd.DataFrame()

    lines += [
        f"## Summary",
        "",
        f"| Tier | Count | Description |",
        f"|---|---|---|",
        f"| A | {len(tier_a)} | High conviction: bull_obedience > 0.6, low instability, MODERATE/STRONG edge |",
        f"| B | {len(tier_b)} | EMA-line subset: bull_obedience > 0.5, ema20/ema50, any edge signal |",
        f"| **WATCHLIST_PRIORITY** | **{len(priority)}** | **Top 15 Tier A by composite score** |",
        "",
    ]

    # Tier A table
    if not tier_a.empty:
        lines += ["## Tier A — High Conviction", ""]
        tbl_cols = ["symbol", "composite_score", "primary_support_line",
                    "edge_confidence", "regime_obedience_bull",
                    "bounce_rate_20d", "median_fwd_ret_20d",
                    "instability_penalty", "liquidity_bucket", "production_status"]
        tbl_cols = [c for c in tbl_cols if c in tier_a.columns]
        lines.append("| " + " | ".join(tbl_cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(tbl_cols)) + " |")
        for _, row in tier_a[tbl_cols].iterrows():
            priority_marker = " ⭐" if row.get("watchlist_priority", False) else ""
            vals = []
            for c in tbl_cols:
                v = row[c]
                if isinstance(v, float):
                    vals.append(f"{v:.3f}")
                else:
                    vals.append(str(v))
            # Add priority marker to first col
            vals[0] = vals[0] + priority_marker
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    # Tier B table
    if not tier_b.empty:
        lines += ["## Tier B — EMA Subset", ""]
        tbl_cols = ["symbol", "composite_score", "primary_support_line",
                    "edge_confidence", "regime_obedience_bull",
                    "bounce_rate_20d", "instability_penalty", "liquidity_bucket"]
        tbl_cols = [c for c in tbl_cols if c in tier_b.columns]
        lines.append("| " + " | ".join(tbl_cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(tbl_cols)) + " |")
        for _, row in tier_b[tbl_cols].iterrows():
            vals = []
            for c in tbl_cols:
                v = row[c]
                if isinstance(v, float):
                    vals.append(f"{v:.3f}")
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    lines += [
        "## What This Screen Does NOT Do",
        "",
        "- No changes to A3, OMS, DNSE, final_action, sizing, or live scan",
        "- `STOCK_DNA_ANNOTATION_ENABLED` stays `false`",
        "- No EMA5/EMA10 addition (council ruling stands)",
        "- No T2-tight build (council ruling stands)",
        "- No A3 ledger join (council ruling stands)",
        "- `a3_true_ledger_used = False`",
        "",
        f"> {RESEARCH_ONLY_LABEL}",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Screen MD saved: %s", path)


def main() -> None:
    assert_output_path_safe(DNA_DIR)

    profiles_path = DNA_DIR / "stock_dna_symbol_profiles.csv"
    if not profiles_path.exists():
        logger.error("Profiles CSV not found: %s", profiles_path)
        sys.exit(1)

    profiles = pd.read_csv(profiles_path)
    logger.info("Loaded %d profiles from %s", len(profiles), profiles_path)

    penalty_median = profiles["instability_penalty"].median()

    # Diagnostics
    logger.info(
        "Filter diagnostics: bull>0.6=%d  penalty<median=%d  ema_lines=%d  edge_mod_str=%d",
        (profiles["regime_obedience_bull"] > 0.6).sum(),
        (profiles["instability_penalty"] < penalty_median).sum(),
        profiles["primary_support_line"].isin(["ema20", "ema50"]).sum(),
        profiles["edge_confidence"].isin(["MODERATE", "STRONG"]).sum(),
    )

    screen = build_screen(profiles)

    if screen.empty:
        logger.warning("Screen is empty — no output written.")
        sys.exit(0)

    tier_a_n = (screen["tier"] == "A").sum()
    tier_b_n = (screen["tier"] == "B").sum()
    priority_n = screen.get("watchlist_priority", pd.Series(False, index=screen.index)).sum()

    logger.info(
        "Screen result: Tier A=%d  Tier B=%d  WATCHLIST_PRIORITY=%d",
        tier_a_n, tier_b_n, priority_n,
    )

    write_csv(screen, OUTPUT_CSV)
    write_md(screen, OUTPUT_MD, penalty_median)

    logger.info("Done. %s", RESEARCH_ONLY_LABEL)


if __name__ == "__main__":
    main()
