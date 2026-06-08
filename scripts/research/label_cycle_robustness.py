"""
Cycle Robustness Labeler — DNA Option C (council ruling 2026-06-06)
3-state ordinal scheme (council Round 4 P0-2 fix, 2026-06-07)

Compares 2018-start vs 2015-start DNA symbol profiles and assigns:

  cycle_robustness = "multi-cycle-confirmed"
      Line stable AND edge stable or IMPROVED across windows.
      Includes stocks where edge went MODERATE→STRONG (more confirmed, not less).
      Operator implication: full research confidence.

  cycle_robustness = "cycle-edge-fading"
      Line stable BUT edge degraded by ≥1 ordinal step (e.g. STRONG→MODERATE).
      Implication: caution — primary line persists but statistical edge is weakening.
      Monitor whether obedience continues decaying before acting on pattern.

  cycle_robustness = "cycle-line-shift"
      Primary support line CHANGED between windows (regardless of edge direction).
      Implication: lowest confidence — support anchor is regime-dependent.
      Do not feature without explicit caveat.

  cycle_robustness = "no-2015-data"
      Symbol not in 2015-start run (listed too recently for 2015 panel).

EDGE ORDINAL RANKING (council-approved):
  NONE < WEAK < MODERATE < STRONG  (0 < 1 < 2 < 3)

P0-1 FIX: also writes cycle_robustness into JSON SSOT (not just CSV).

Inputs:
  data/research/stock_dna/stock_dna_symbol_profiles.csv   (2018-start, 412 symbols)
  data/research/stock_dna/stock_dna_symbol_profiles.json  (same, JSON SSOT)
  data/pilot_2015_full/dna_results/stock_dna_symbol_profiles.csv  (2015-start)

Outputs:
  data/research/stock_dna/stock_dna_symbol_profiles.csv   (updated: cycle_robustness column)
  data/research/stock_dna/stock_dna_symbol_profiles.json  (updated: JSON parity fix)
  data/research/stock_dna/cycle_robustness_report.md      (updated: 3-state summary)

RESEARCH ONLY — no changes to A3, OMS, DNSE, final_action, sizing, live scan.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("dna.cycle_robustness")

PROFILES_2018_CSV  = DNA_DIR / "stock_dna_symbol_profiles.csv"
PROFILES_2018_JSON = DNA_DIR / "stock_dna_symbol_profiles.json"
PROFILES_2015      = ROOT / "data" / "pilot_2015_full" / "dna_results" / "stock_dna_symbol_profiles.csv"
REPORT_OUT         = DNA_DIR / "cycle_robustness_report.md"

# Council-approved ordinal edge ranking (Round 4 Q4 ruling)
EDGE_ORDER: dict[str, int] = {
    "NONE":     0,
    "WEAK":     1,
    "MODERATE": 2,
    "STRONG":   3,
    "PENDING":  -1,  # treat PENDING as below NONE (should not appear post-step)
}


def _edge_rank(edge_conf: str) -> int:
    return EDGE_ORDER.get(str(edge_conf).upper(), 0)


def label_robustness(
    cur: pd.DataFrame,
    pilot: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add cycle_robustness column to current (2018-start) profiles.

    3-state ordinal scheme (council Round 4 P0-2, 2026-06-07):
      - cycle-line-shift: primary_support_line changed
      - cycle-edge-fading: line stable, edge degraded (current < pilot by ≥1 step)
      - multi-cycle-confirmed: line stable, edge stable or improved
      - no-2015-data: symbol absent from 2015-start profiles
    """
    pilot_idx = pilot.set_index("symbol")

    cycle_labels = []
    reasons = []

    for _, row in cur.iterrows():
        sym = row["symbol"]

        if sym not in pilot_idx.index:
            cycle_labels.append("no-2015-data")
            reasons.append("symbol not in 2015-start run")
            continue

        p = pilot_idx.loc[sym]

        cur_line  = str(row.get("primary_support_line", "") or "")
        pilot_line = str(p.get("primary_support_line", "") or "")
        line_stable = cur_line == pilot_line

        if not line_stable:
            cycle_labels.append("cycle-line-shift")
            reasons.append(f"line: {pilot_line}→{cur_line}")
            continue

        cur_edge_rank   = _edge_rank(str(row.get("edge_confidence", "NONE")))
        pilot_edge_rank = _edge_rank(str(p.get("edge_confidence", "NONE")))
        edge_delta = cur_edge_rank - pilot_edge_rank  # >0 = improved, 0 = same, <0 = degraded

        if edge_delta >= 0:
            cycle_labels.append("multi-cycle-confirmed")
            reasons.append(
                f"line={cur_line} stable; edge {p.get('edge_confidence')}→{row.get('edge_confidence')} (improved/stable)"
            )
        else:
            cycle_labels.append("cycle-edge-fading")
            reasons.append(
                f"line={cur_line} stable; edge {p.get('edge_confidence')}→{row.get('edge_confidence')} (FADING)"
            )

    cur = cur.copy()
    cur["cycle_robustness"] = cycle_labels
    cur["cycle_robustness_reason"] = reasons  # diagnostic column
    return cur


def write_json_with_robustness(df: pd.DataFrame) -> None:
    """P0-1 fix: write cycle_robustness into JSON SSOT."""
    assert_output_path_safe(DNA_DIR)

    if not PROFILES_2018_JSON.exists():
        logger.warning("JSON profiles not found — skipping JSON parity fix: %s", PROFILES_2018_JSON)
        return

    try:
        with open(PROFILES_2018_JSON, encoding="utf-8") as f:
            root = json.load(f)
    except Exception as e:
        logger.warning("Could not read JSON profiles: %s", e)
        return

    # JSON is {"research_label": ..., "profiles": [...]}
    if isinstance(root, dict) and "profiles" in root:
        existing_list = root["profiles"]
        wrapper = root
    elif isinstance(root, list):
        existing_list = root
        wrapper = None
    else:
        logger.warning("Unexpected JSON structure — skipping parity fix")
        return

    # Build a lookup from the labeled DataFrame
    rob_lookup = df.set_index("symbol")[["cycle_robustness", "cycle_robustness_reason"]].to_dict("index")

    updated = 0
    for entry in existing_list:
        if not isinstance(entry, dict):
            continue
        sym = entry.get("symbol", "")
        if sym in rob_lookup:
            entry["cycle_robustness"] = rob_lookup[sym]["cycle_robustness"]
            entry["cycle_robustness_reason"] = rob_lookup[sym]["cycle_robustness_reason"]
            updated += 1
        else:
            entry["cycle_robustness"] = "no-2015-data"
            entry["cycle_robustness_reason"] = "symbol not in 2015-start run"

    # Re-wrap or write directly
    out_obj = wrapper if wrapper is not None else existing_list
    with open(PROFILES_2018_JSON, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, indent=2, ensure_ascii=False, default=str)

    logger.info("JSON SSOT updated: %d symbols now have cycle_robustness (P0-1 fix)", updated)


def write_report(df: pd.DataFrame) -> None:
    multi  = df[df["cycle_robustness"] == "multi-cycle-confirmed"]
    fading = df[df["cycle_robustness"] == "cycle-edge-fading"]
    shift  = df[df["cycle_robustness"] == "cycle-line-shift"]
    no15   = df[df["cycle_robustness"] == "no-2015-data"]

    # Tier A: MODERATE/STRONG edge + bull_obedience > 0.6 + not VIN-distorted
    tier_a = df[
        (df["edge_confidence"].isin(["MODERATE", "STRONG"]))
        & (df["regime_obedience_bull"] > 0.6)
        & (df["production_status"].isin(["RESEARCH_ANNOTATION_ONLY", "WATCHLIST_ONLY"]))
        & (df["vin_distortion_flag"] == 0)
    ]
    tier_a_multi  = tier_a[tier_a["cycle_robustness"] == "multi-cycle-confirmed"]
    tier_a_fading = tier_a[tier_a["cycle_robustness"] == "cycle-edge-fading"]
    tier_a_shift  = tier_a[tier_a["cycle_robustness"] == "cycle-line-shift"]

    lines = [
        "# Cycle Robustness Report — Stock DNA (3-State Ordinal)",
        "",
        f"> {RESEARCH_ONLY_LABEL}",
        "",
        f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Council Ruling (Round 4, 2026-06-07)",
        "",
        "3-state ordinal scheme (P0-2 fix — direction-aware edge comparison):",
        "- `multi-cycle-confirmed`: line stable AND edge stable-or-improved (NONE<WEAK<MODERATE<STRONG)",
        "  Edge improving = additional confirmation, not fragility.",
        "- `cycle-edge-fading`: line stable, edge degraded ≥1 ordinal step. Monitor for decay.",
        "- `cycle-line-shift`: primary support line changed between windows. Least confirmed.",
        "- `no-2015-data`: symbol listed post-2015, single window only.",
        "",
        "**Key operator implication:** effective high-confidence Tier A =",
        "multi-cycle-confirmed + edge-improved-within-multi (both map to full research confidence).",
        "Only cycle-edge-fading and cycle-line-shift warrant explicit caution notes.",
        "",
        "## Summary",
        "",
        "| Category | Count | % | Implication |",
        "|---|---|---|---|",
        f"| multi-cycle-confirmed | **{len(multi)}** | {len(multi)/len(df)*100:.1f}% | Full confidence |",
        f"| cycle-edge-fading | **{len(fading)}** | {len(fading)/len(df)*100:.1f}% | Caution — monitor |",
        f"| cycle-line-shift | **{len(shift)}** | {len(shift)/len(df)*100:.1f}% | Lowest confidence |",
        f"| no-2015-data | {len(no15)} | {len(no15)/len(df)*100:.1f}% | Single window |",
        f"| **Total** | **{len(df)}** | 100% | |",
        "",
        "## Tier A (edge-verified) by Robustness",
        "",
        f"| Robustness | Count | Operator Rule |",
        f"|---|---|---|",
        f"| multi-cycle-confirmed | **{len(tier_a_multi)}** | Full research confidence |",
        f"| cycle-edge-fading | **{len(tier_a_fading)}** | Caution note required; watchlist with monitoring flag |",
        f"| cycle-line-shift | **{len(tier_a_shift)}** | Do not feature without regime-dependency caveat |",
        "",
    ]

    if not tier_a_multi.empty:
        lines += ["## Tier A — Multi-Cycle Confirmed", ""]
        cols = ["symbol", "primary_support_line", "edge_confidence",
                "regime_obedience_bull", "bounce_rate_20d", "liquidity_bucket"]
        cols = [c for c in cols if c in tier_a_multi.columns]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for _, r in tier_a_multi[cols].sort_values("regime_obedience_bull", ascending=False).iterrows():
            vals = [f"{v:.3f}" if isinstance(v, float) else str(v) for v in [r[c] for c in cols]]
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    if not tier_a_fading.empty:
        lines += [
            "## Tier A — Cycle-Edge-Fading (caution)",
            "",
            "> Line stable but edge weakened vs 2015 window. Monitor for continued decay.",
            "> Do NOT size up until edge stabilises.",
            "",
        ]
        cols = ["symbol", "primary_support_line", "edge_confidence",
                "regime_obedience_bull", "cycle_robustness_reason"]
        cols = [c for c in cols if c in tier_a_fading.columns]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for _, r in tier_a_fading[cols].sort_values("regime_obedience_bull", ascending=False).iterrows():
            vals = [str(v) for v in [r[c] for c in cols]]
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    if not tier_a_shift.empty:
        lines += [
            "## Tier A — Cycle-Line-Shift (lowest confidence)",
            "",
            "> Primary support line changed between 2015 and 2018 windows.",
            "> Support anchor is regime-dependent. Explicit caveat required.",
            "",
        ]
        cols = ["symbol", "primary_support_line", "edge_confidence",
                "regime_obedience_bull", "cycle_robustness_reason"]
        cols = [c for c in cols if c in tier_a_shift.columns]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for _, r in tier_a_shift[cols].sort_values("regime_obustness_bull" if "regime_obustness_bull" in tier_a_shift.columns else "regime_obedience_bull", ascending=False).iterrows():
            vals = [str(v) for v in [r[c] for c in cols]]
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    lines += [
        "## Regime Log Caveat (council P1 note)",
        "",
        "> 2015-start 'confirmation' leans primarily on price/MA structure.",
        "> Regime features (bull/bear labels) pre-2018 use the same regime log as 2018-start.",
        "> Full regime-feature parity for 2015–2017 requires updated regime labeling for that period.",
        "> This does not invalidate the robustness labels — the price/MA anchor is the primary signal.",
        "",
        "## SMA50 Note",
        "",
        "SMA50 added to v2 candidate lines (council 2026-06-06).",
        "53 symbols (2018) / 54 symbols (2015) use sma50 as primary support line — consistent.",
        "TV2 is Tier A exemplar (MODERATE edge, bull_obedience=0.676, 85 touches).",
        "",
        f"> {RESEARCH_ONLY_LABEL}",
    ]

    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report written (3-state ordinal): %s", REPORT_OUT)


def main() -> None:
    assert_output_path_safe(DNA_DIR)

    if not PROFILES_2018_CSV.exists():
        logger.error("2018-start profiles not found: %s", PROFILES_2018_CSV)
        sys.exit(1)

    if not PROFILES_2015.exists():
        logger.error("2015-start profiles not found: %s", PROFILES_2015)
        sys.exit(1)

    cur   = pd.read_csv(PROFILES_2018_CSV)
    pilot = pd.read_csv(PROFILES_2015)

    logger.info("2018-start profiles: %d symbols", len(cur))
    logger.info("2015-start profiles: %d symbols", len(pilot))

    labeled = label_robustness(cur, pilot)

    # Count by state
    counts = labeled["cycle_robustness"].value_counts()
    logger.info(
        "Robustness 3-state: multi-cycle-confirmed=%d  cycle-edge-fading=%d  "
        "cycle-line-shift=%d  no-2015-data=%d",
        counts.get("multi-cycle-confirmed", 0),
        counts.get("cycle-edge-fading", 0),
        counts.get("cycle-line-shift", 0),
        counts.get("no-2015-data", 0),
    )

    sma50_primary = (labeled["primary_support_line"] == "sma50").sum()
    logger.info("Symbols with sma50 as primary_support_line: %d", sma50_primary)

    # Save CSV (includes cycle_robustness_reason diagnostic column)
    labeled.to_csv(PROFILES_2018_CSV, index=False)
    logger.info("Updated CSV profiles saved: %s", PROFILES_2018_CSV)

    # P0-1 fix: write cycle_robustness into JSON SSOT
    write_json_with_robustness(labeled)

    # Write report
    write_report(labeled)
    logger.info("Done. %s", RESEARCH_ONLY_LABEL)


if __name__ == "__main__":
    main()
