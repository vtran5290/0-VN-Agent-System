"""
Stock DNA Current-Cycle Obedience Screen — CLI runner

Panel: 2018-01-16 → 2026-06-05 (one full bull-bear-bull cycle).
NOT a "decade winners" screen — rebrand per council ruling 2026-06-06.

Tiers:

  Tier A — Highest conviction (statistically verified edge):
    regime_obedience_bull > 0.6
    edge_confidence in {MODERATE, STRONG}
    production_status in {RESEARCH_ANNOTATION_ONLY, WATCHLIST_ONLY}
    vin_distortion_flag == 0
    (line restriction removed — sma150/sma100 dominate quality stocks)

  Tier B — EMA-line subset (fast-moving support, relaxed thresholds):
    regime_obedience_bull > 0.5
    primary_support_line in {ema20, ema50}
    edge_confidence in {WEAK, MODERATE, STRONG}

  Tier BC — Blue-Chip Obedience (council addition 2026-06-06):
    confidence == HIGH (strong touch-count sample)
    regime_obedience_bull > 0.8
    vin_distortion_flag == 0
    edge_confidence MAY be NONE — "obedience-confirmed, edge unverified"
    Rationale: z-test is under-powered on liquid/arbitraged names;
    high bull_obedience on large sample is meaningful despite NONE edge_confidence.
    NOT merged with Tier A — kept separate and labelled.

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

# Council watchlist — known blue-chips / institution favourites to diagnose
COUNCIL_WATCHLIST_SYMBOLS = [
    "ACP", "FPT", "HPG", "VCB", "MWG", "MSN", "ACB", "VNM",
    "VIC", "VHM", "SSI", "VND", "HDB", "TCB", "MBB",
]

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

    # ── Tier BC — Blue-Chip Obedience (council addition 2026-06-06) ──────────
    # HIGH sample confidence + strong bull obedience — edge_confidence may be NONE.
    # Council ruling: z-test is under-powered on liquid/arbitraged names; the
    # obedience signal is real (e.g., MWG 0.867 bull_obedience) even when the
    # per-symbol null z-test fails. Shown SEPARATELY — do not merge with Tier A.
    mask_bc = (
        (df["confidence"] == "HIGH")
        & (df["regime_obedience_bull"] > 0.8)
        & (df["vin_distortion_flag"] == 0)
        & (~mask_a)  # exclude already in Tier A
        & (~mask_b)  # exclude already in Tier B
    )

    tier_a = df[mask_a].copy()
    tier_a["tier"] = "A"
    tier_b = df[mask_b].copy()
    tier_b["tier"] = "B"
    tier_bc = df[mask_bc].copy()
    tier_bc["tier"] = "BC"

    combined = pd.concat([tier_a, tier_b, tier_bc], ignore_index=True)

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

    # Top 15 within Tier A get WATCHLIST_PRIORITY flag (Tier BC/B excluded)
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


def diagnose_exclusions(profiles: pd.DataFrame) -> list[str]:
    """Return MD lines diagnosing why council watchlist symbols were excluded."""
    lines: list[str] = [
        "## Exclusion Diagnostics — Council Watchlist Symbols",
        "",
        "> Council ruling 2026-06-06: log exclusion reasons per-symbol to diagnose ACP class gaps.",
        "",
        "| Symbol | In Profiles | Confidence | EdgeConf | Bull_Obedience | Tier A | Tier BC | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sym in COUNCIL_WATCHLIST_SYMBOLS:
        row = profiles[profiles["symbol"] == sym]
        if row.empty:
            lines.append(
                f"| {sym} | ❌ MISSING | — | — | — | ✗ | ✗ | Not in 412-symbol universe — check SSOT parquet |"
            )
            continue
        r = row.iloc[0]
        conf  = str(r.get("confidence", "?"))
        edge  = str(r.get("edge_confidence", "?"))
        bull  = float(r.get("regime_obedience_bull", 0))
        vin   = int(r.get("vin_distortion_flag", 0))
        prod  = str(r.get("production_status", "?"))

        # Tier A gate
        a_fails: list[str] = []
        if bull <= 0.6:
            a_fails.append(f"bull={bull:.3f}≤0.6")
        if edge not in ("MODERATE", "STRONG"):
            a_fails.append(f"edge={edge}")
        if prod not in ("RESEARCH_ANNOTATION_ONLY", "WATCHLIST_ONLY"):
            a_fails.append(f"status={prod}")
        if vin != 0:
            a_fails.append(f"VIN={vin}")
        tier_a_ok = len(a_fails) == 0

        # Tier BC gate
        bc_fails: list[str] = []
        if conf != "HIGH":
            bc_fails.append(f"conf={conf}≠HIGH")
        if bull <= 0.8:
            bc_fails.append(f"bull={bull:.3f}≤0.8")
        if vin != 0:
            bc_fails.append(f"VIN={vin}")
        tier_bc_ok = len(bc_fails) == 0

        tier_a_str  = "✓" if tier_a_ok  else "✗"
        tier_bc_str = "✓" if tier_bc_ok else "✗"

        if tier_a_ok:
            verdict = "QUALIFIES Tier A"
        elif tier_bc_ok:
            verdict = f"Tier A fails ({'; '.join(a_fails)}) | Qualifies BC (edge unverified)"
        else:
            reason_parts = [f"Tier A: {'; '.join(a_fails)}"] if a_fails else []
            reason_parts += [f"Tier BC: {'; '.join(bc_fails)}"] if bc_fails else []
            verdict = " | ".join(reason_parts)

        lines.append(
            f"| {sym} | ✓ | {conf} | {edge} | {bull:.3f} | {tier_a_str} | {tier_bc_str} | {verdict} |"
        )
    lines.append("")
    return lines


def write_md(screen: pd.DataFrame, path: Path, penalty_median: float,
             profiles: pd.DataFrame | None = None) -> None:
    lines: list[str] = []

    lines += [
        "# Stock DNA Current-Cycle Obedience Screen",
        "",
        f"> {RESEARCH_ONLY_LABEL}",
        "",
        f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Panel:** 2018-01-16 → 2026-06-05 (one bull-bear-bull cycle — NOT a decade screen)  ",
        f"**Input:** `data/research/stock_dna/stock_dna_symbol_profiles.csv`  ",
        f"**instability_penalty median:** {penalty_median:.4f}",
        "",
        "## Council Notes (2026-06-06)",
        "",
        "**Timeframe:** 2018–2026 covers ~8.4 years and one complete bull-bear-bull cycle. "
        "Rebrand as 'current-cycle obedience' — not a decade screen.",
        "",
        "**Blue-chip absence:** FPT/HPG/MWG/MSN have `edge_confidence=NONE` despite `confidence=HIGH`. "
        "Council ruling: z-test is under-powered on liquid/arbitraged names — the null is harder to beat "
        "when price paths are more arbitraged. MWG (bull_obedience=0.867) is the key tell: real pattern "
        "failing z-test, not a weak pattern. **Tier BC** added as separate track — do not merge with Tier A.",
        "",
        "**Line calibration:** MODERATE/STRONG edge_confidence stocks overwhelmingly prefer `sma150` (27) "
        "and `sma100` (21); only 3 use ema20/ema50. Line restriction removed from Tier A. "
        "Tier B preserves the EMA subset at relaxed thresholds.",
        "",
    ]

    tier_a  = screen[screen["tier"] == "A"]
    tier_b  = screen[screen["tier"] == "B"]
    tier_bc = screen[screen["tier"] == "BC"]
    priority = (
        screen[screen["watchlist_priority"] == True]
        if "watchlist_priority" in screen.columns
        else pd.DataFrame()
    )

    lines += [
        "## Summary",
        "",
        "| Tier | Count | Description |",
        "|---|---|---|",
        f"| A | {len(tier_a)} | High conviction: bull_obedience > 0.6, MODERATE/STRONG edge, statistically verified |",
        f"| B | {len(tier_b)} | EMA-line subset: bull_obedience > 0.5, ema20/ema50, any edge signal |",
        f"| BC | {len(tier_bc)} | Blue-Chip Obedience: HIGH conf + bull_obedience > 0.8 — edge UNVERIFIED (z-test under-powered) |",
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

    # Tier BC table
    if not tier_bc.empty:
        lines += [
            "## Tier BC — Blue-Chip Obedience ⚠️ Edge Unverified",
            "",
            "> Council ruling: z-test is under-powered on liquid/arbitraged names. "
            "HIGH confidence + bull_obedience > 0.8 is meaningful despite NONE edge_confidence. "
            "Do NOT treat as statistically equivalent to Tier A.",
            "",
        ]
        tbl_cols = ["symbol", "composite_score", "primary_support_line", "confidence",
                    "edge_confidence", "regime_obedience_bull",
                    "bounce_rate_20d", "instability_penalty", "liquidity_bucket"]
        tbl_cols = [c for c in tbl_cols if c in tier_bc.columns]
        lines.append("| " + " | ".join(tbl_cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(tbl_cols)) + " |")
        for _, row in tier_bc[tbl_cols].iterrows():
            vals = []
            for c in tbl_cols:
                v = row[c]
                if isinstance(v, float):
                    vals.append(f"{v:.3f}")
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    # Exclusion diagnostics
    if profiles is not None:
        lines += diagnose_exclusions(profiles)

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

    tier_a_n  = (screen["tier"] == "A").sum()
    tier_b_n  = (screen["tier"] == "B").sum()
    tier_bc_n = (screen["tier"] == "BC").sum()
    priority_n = screen.get("watchlist_priority", pd.Series(False, index=screen.index)).sum()

    logger.info(
        "Screen result: Tier A=%d  Tier B=%d  Tier BC=%d  WATCHLIST_PRIORITY=%d",
        tier_a_n, tier_b_n, tier_bc_n, priority_n,
    )

    # Log council watchlist exclusion summary
    missing = [s for s in COUNCIL_WATCHLIST_SYMBOLS if profiles[profiles["symbol"] == s].empty]
    if missing:
        logger.warning("Council watchlist symbols NOT IN PROFILES (check SSOT): %s", missing)

    write_csv(screen, OUTPUT_CSV)
    write_md(screen, OUTPUT_MD, penalty_median, profiles=profiles)

    logger.info("Done. %s", RESEARCH_ONLY_LABEL)


if __name__ == "__main__":
    main()
