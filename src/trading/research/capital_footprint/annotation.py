"""
Capital Footprint Daily Scan Annotator
=======================================
Non-binding research annotations for the daily Phase36 scan output.

HARD CONSTRAINTS (enforced by design — this module NEVER touches):
  - final_action
  - a3_rank_score
  - position sizing
  - OMS payload (except optional nested cf_annotation field)
  - DNSE routing

Feature flag: config/trading.yaml → research.cf_annotation_enabled: false (default)

Annotation logic (Phase 3 findings):
  SUPPLY_ABSORPTION_SETUP + BULL_BROAD regime  → active, positive note
  SUPPLY_ABSORPTION_SETUP + other regime       → active, warning note
  EXTENSION_DISTRIBUTION_RISK + event_age >= 5 → active, caution note
  EXTENSION_DISTRIBUTION_RISK + event_age < 5  → inactive, observe note
  FAILED_BREAKOUT                              → inactive, research note (bounce behavior)
  BREAKOUT_CONFIRMED / PENDING                 → inactive, research note
  NEUTRAL or not in CF panel                   → no annotation

Source: capital_footprint_phase3_decision_memo.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── Operator note constants ───────────────────────────────────────────────────

_SA_BULL_BROAD  = "✓ Dry-up setup in BULL_BROAD — constructive watchlist setup"
_SA_OTHER       = "✗ Dry-up outside BULL_BROAD — weak/avoid as entry signal"
_EXT_CAUTION    = "⚠ Extended 5+ bars — do not add / review distribution risk"
_EXT_OBSERVE    = "Extension started — observe only"
_FB_RESEARCH    = "Research-only failed breakout label — possible bounce/reclaim; verify manually"
_BC_RESEARCH    = "Research-only: breakout confirmed — not yet production-ready"
_BP_RESEARCH    = "Research-only: breakout pending volume confirm — not yet production-ready"


def _operator_note(
    phase_label: Optional[str],
    breadth_regime: Optional[str],
    event_age: Optional[float],
) -> tuple[str, int]:
    """
    Returns (cf_operator_note, cf_annotation_active).
    cf_annotation_active = 1 means the operator should review this row.
    """
    if pd.isna(phase_label) or phase_label is None:
        return "", 0

    age = float(event_age) if (event_age is not None and not pd.isna(event_age)) else 0.0
    regime = str(breadth_regime) if (breadth_regime is not None and not pd.isna(breadth_regime)) else ""

    if phase_label == "SUPPLY_ABSORPTION_SETUP":
        if regime == "BULL_BROAD":
            return _SA_BULL_BROAD, 1
        else:
            return _SA_OTHER, 1

    if phase_label == "EXTENSION_DISTRIBUTION_RISK":
        if age >= 5:
            return _EXT_CAUTION, 1
        return _EXT_OBSERVE, 0

    if phase_label == "FAILED_BREAKOUT":
        return _FB_RESEARCH, 0

    if phase_label == "BREAKOUT_CONFIRMED":
        return _BC_RESEARCH, 0

    if phase_label == "BREAKOUT_FOLLOW_THROUGH_PENDING":
        return _BP_RESEARCH, 0

    return "", 0   # NEUTRAL


def build_cf_annotation_for_date(as_of_date: str) -> pd.DataFrame:
    """
    Build a per-symbol CF annotation table for one specific date.

    Returns a DataFrame with columns:
      symbol, cf_phase_label, cf_event_age, cf_event_cooldown_flag,
      cf_breadth_regime_bucket, cf_annotation_active, cf_operator_note

    Rows only exist for symbols covered by the CF panel (min_adv50=100mn VND).
    Symbols not in CF get no rows — they will be NaN after left-join.

    Runtime: ~25-30s (CF panel build + event detection).
    """
    # Lazy imports — only loaded when CF annotation is enabled
    from src.trading.research.capital_footprint.features import build_feature_panel
    from src.trading.research.capital_footprint.classifier import (
        assign_phase_labels,
        detect_label_entry_events,
    )

    print("  [CF annotation] Building feature panel...")
    panel = build_feature_panel(min_adv50_vnd=1e8, include_fa=False)
    print("  [CF annotation] Assigning phase labels...")
    panel = assign_phase_labels(panel)
    print("  [CF annotation] Detecting entry events...")
    panel = detect_label_entry_events(panel, cooldown_days=20)

    # Slice to the requested date
    target_ts = pd.Timestamp(as_of_date)
    today = panel[panel["date"] == target_ts].copy()

    if today.empty:
        # Try normalizing in case of time component mismatch
        panel["date_norm"] = pd.to_datetime(panel["date"]).dt.normalize()
        today = panel[panel["date_norm"] == target_ts.normalize()].copy()
        if today.empty:
            print(f"  [CF annotation] WARN: No CF rows for {as_of_date}. Annotation skipped.")
            return pd.DataFrame(columns=[
                "symbol", "cf_phase_label", "cf_event_age", "cf_event_cooldown_flag",
                "cf_breadth_regime_bucket", "cf_annotation_active", "cf_operator_note",
            ])

    # Determine regime column (may be named differently across versions)
    regime_col = next(
        (c for c in ["breadth_regime_bucket", "regime_bucket", "market_regime"] if c in today.columns),
        None,
    )

    # Apply annotation logic row-by-row via vectorised apply
    def _apply_row(row: pd.Series) -> pd.Series:
        regime = row[regime_col] if regime_col else None
        note, active = _operator_note(
            row.get("phase_label"),
            regime,
            row.get("event_age"),
        )
        return pd.Series({
            "cf_phase_label":         row.get("phase_label"),
            "cf_event_age":           row.get("event_age"),
            "cf_event_cooldown_flag": int(row.get("event_cooldown_flag", 0)),
            "cf_breadth_regime_bucket": regime,
            "cf_annotation_active":   active,
            "cf_operator_note":       note,
        })

    ann = today.apply(_apply_row, axis=1)
    ann.insert(0, "symbol", today["symbol"].values)
    ann = ann.reset_index(drop=True)

    print(
        f"  [CF annotation] {len(ann)} CF symbols annotated for {as_of_date}. "
        f"Active: {int(ann['cf_annotation_active'].sum())}"
    )
    return ann


def annotate_scan_df(
    scan_df: pd.DataFrame,
    as_of_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Left-join CF annotations to scan_df.

    GUARANTEES:
      - scan_df columns that existed before remain UNCHANGED (values and dtype)
      - final_action, a3_rank_score, and all other production columns are untouched
      - Only cf_* columns are added (they'll be NaN for symbols not in CF panel)

    Returns scan_df with additional cf_* columns appended.
    """
    if as_of_date is None:
        if "as_of_date" in scan_df.columns and not scan_df.empty:
            as_of_date = str(scan_df["as_of_date"].iloc[0])
        else:
            print("  [CF annotation] WARN: as_of_date unknown — skipping annotation.")
            return scan_df

    cf_cols = [
        "cf_phase_label", "cf_event_age", "cf_event_cooldown_flag",
        "cf_breadth_regime_bucket", "cf_annotation_active", "cf_operator_note",
    ]

    # Drop any pre-existing cf_* columns to prevent duplicates on re-run
    existing_cf = [c for c in scan_df.columns if c in cf_cols]
    if existing_cf:
        scan_df = scan_df.drop(columns=existing_cf)

    # Preserve exact original dtypes for all non-cf columns
    original_dtypes = scan_df.dtypes.to_dict()

    ann = build_cf_annotation_for_date(as_of_date)

    if ann.empty:
        for col in cf_cols:
            scan_df[col] = pd.NA
        return scan_df

    enriched = scan_df.merge(ann[["symbol"] + cf_cols], on="symbol", how="left")

    # Verify no production column was accidentally altered
    _verify_production_columns_intact(scan_df, enriched, original_dtypes)

    return enriched


def _verify_production_columns_intact(
    original: pd.DataFrame,
    enriched: pd.DataFrame,
    original_dtypes: dict,
) -> None:
    """
    Assert that final_action and all original columns are unchanged after annotation.
    Raises AssertionError if any production column was modified.
    """
    protected = ["final_action", "a3_rank_score", "symbol", "as_of_date"]

    for col in protected:
        if col not in original.columns:
            continue
        if col not in enriched.columns:
            raise AssertionError(f"[CF annotation] Protected column '{col}' was removed after annotation!")
        if not original[col].equals(enriched[col]):
            raise AssertionError(
                f"[CF annotation] Protected column '{col}' was modified after annotation! "
                f"This is a critical safety violation."
            )

    # All original columns must still be present
    missing = [c for c in original.columns if c not in enriched.columns]
    if missing:
        raise AssertionError(
            f"[CF annotation] Original columns were dropped after annotation: {missing}"
        )


# ── Config helper ─────────────────────────────────────────────────────────────

def is_cf_annotation_enabled(config_path: Optional[Path] = None) -> bool:
    """
    Read CF_ANNOTATION_ENABLED from config/trading.yaml.
    Returns False if the flag is absent or the file is unreadable.
    Default: False (annotation is opt-in).
    """
    if config_path is None:
        # annotation.py lives at src/trading/research/capital_footprint/
        # parents[4] = repo root (D:\V\0. VN Agent System)
        config_path = Path(__file__).resolve().parents[4] / "config" / "trading.yaml"

    try:
        import yaml  # type: ignore
    except ImportError:
        return False

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        research = cfg.get("research", {}) or {}
        return bool(research.get("cf_annotation_enabled", False))
    except Exception:
        return False


# ── Markdown section builder ──────────────────────────────────────────────────

def build_cf_annotation_section(enriched: pd.DataFrame) -> str:
    """
    Build a markdown section for the CF annotations in daily_scan.md.
    Only shows rows with cf_annotation_active == 1 or with a non-NEUTRAL label.
    """
    cf_cols = ["symbol", "cf_phase_label", "cf_operator_note", "cf_event_age",
               "cf_breadth_regime_bucket", "cf_annotation_active"]

    missing = [c for c in cf_cols if c not in enriched.columns]
    if missing:
        return "\n## Capital Footprint Annotations (research, non-binding)\n\n_CF annotation columns not present._\n"

    annotated = enriched[enriched["cf_annotation_active"] == 1][cf_cols].copy()
    passive   = enriched[
        (enriched["cf_annotation_active"] != 1) &
        enriched["cf_phase_label"].notna() &
        (enriched["cf_phase_label"] != "NEUTRAL") &
        (enriched["cf_phase_label"] != "")
    ][cf_cols].copy()

    lines = [
        "\n## Capital Footprint Annotations (research, non-binding)\n\n",
        "> These are Phase 3 research-only labels. They do NOT change `final_action`, "
        "sizing, OMS, or DNSE logic. Operator review only.\n\n",
        f"> CF panel covers ~366 liquid symbols (adv50 ≥ 100mn VND). "
        f"Symbols not in CF panel show no annotation.\n\n",
    ]

    if annotated.empty:
        lines.append("_No active CF annotations for today's scan symbols._\n")
    else:
        lines.append(f"### Active annotations ({len(annotated)})\n\n")
        header = ["Symbol", "CF Label", "Operator Note", "Event Age", "Regime"]
        sep    = "| " + " | ".join(["---"] * len(header)) + " |"
        lines.append("| " + " | ".join(header) + " |\n")
        lines.append(sep + "\n")
        for _, r in annotated.iterrows():
            age_str = f"{int(r['cf_event_age'])}" if pd.notna(r.get("cf_event_age")) else "—"
            lines.append(
                f"| {r['symbol']} | {r['cf_phase_label']} | {r['cf_operator_note']} "
                f"| {age_str} | {r.get('cf_breadth_regime_bucket', '—')} |\n"
            )

    if not passive.empty:
        lines.append(f"\n### Passive / observe-only ({len(passive)})\n\n")
        header2 = ["Symbol", "CF Label", "Note"]
        sep2    = "| " + " | ".join(["---"] * len(header2)) + " |"
        lines.append("| " + " | ".join(header2) + " |\n")
        lines.append(sep2 + "\n")
        for _, r in passive.iterrows():
            note = str(r.get("cf_operator_note", "—"))[:80]
            lines.append(f"| {r['symbol']} | {r['cf_phase_label']} | {note} |\n")

    return "".join(lines)


# ── JSON payload builder ──────────────────────────────────────────────────────

def build_cf_annotation_json(
    enriched: pd.DataFrame,
    as_of_date: Optional[str] = None,
) -> dict:
    """
    Build the cf_annotation dict for inclusion in daily_scan.json.
    Contains only annotation metadata — no production fields.
    """
    cf_annotation_col = "cf_annotation_active"
    if cf_annotation_col not in enriched.columns:
        return {"enabled": True, "error": "cf_annotation_active column missing"}

    active_rows = enriched[enriched[cf_annotation_col] == 1]

    active_list = []
    for _, r in active_rows.iterrows():
        entry: dict = {
            "symbol":                  str(r["symbol"]),
            "cf_phase_label":          str(r.get("cf_phase_label", "")),
            "cf_operator_note":        str(r.get("cf_operator_note", "")),
            "cf_event_age":            (
                int(r["cf_event_age"]) if pd.notna(r.get("cf_event_age")) else None
            ),
            "cf_breadth_regime_bucket": str(r.get("cf_breadth_regime_bucket", "")),
            "cf_annotation_active":    1,
        }
        active_list.append(entry)

    return {
        "enabled":       True,
        "as_of_date":    as_of_date,
        "n_cf_symbols":  int(enriched["cf_phase_label"].notna().sum()),
        "n_active":      len(active_list),
        "active_annotations": active_list,
    }
