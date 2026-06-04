"""
CLI: Group Rotation Dashboard Integration.
Generates dashboard snapshot, writes CSV/JSON/MD, packages review zip.

Usage:
    python -m scripts.research.group_rotation.run_group_rotation [--date YYYY-MM-DD]

DASHBOARD ONLY. No A3/OMS/Phase36/DNSE/S3 changes.
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from .group_rotation_daily import build_group_rotation_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

_REPO_ROOT    = Path(__file__).resolve().parents[3]
_OUT_CSV      = _REPO_ROOT / "data/research/group_rotation/group_rotation_latest.csv"
_OUT_JSON     = _REPO_ROOT / "data/research/group_rotation/group_rotation_latest.json"
_OUT_CARD     = _REPO_ROOT / "data/research/reports/group_rotation_card_latest.md"
_REVIEW_DIR   = _REPO_ROOT / "outputs/review_packages"
_P1_DIR       = _REPO_ROOT / "data/research/sector_l4_causality"


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("CSV written: %s (%d rows)", path, len(df))


def _write_json(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for _, row in df.iterrows():
        rec = row.to_dict()
        # Ensure execution_allowed_flag is JSON boolean
        rec["execution_allowed_flag"] = False
        # Convert NaN to None for valid JSON
        rec = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in rec.items()}
        records.append(rec)
    payload = {
        "snapshot_date": df["snapshot_date"].iloc[0] if len(df) else str(date.today()),
        "execution_allowed_flag_all_rows": False,
        "n_groups": len(df),
        "groups": records,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info("JSON written: %s", path)


def _write_card(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    today_str = df["snapshot_date"].iloc[0] if len(df) else str(date.today())

    tiers_a = df[df["tier"] == "A"]
    tiers_b = df[df["tier"] == "B"]

    lines = [
        f"# Group Rotation Dashboard Card\n",
        f"\n**Snapshot date:** {today_str}  \n",
        f"**DASHBOARD ONLY — execution_allowed_flag = false for all rows**\n",
        "\n---\n",
        "\n## Signal Summary\n",
        f"\n| Badge | Count |\n|---|---|\n",
        f"| GROUP_STRONG_ROTATION | {(df['signal_badge']=='GROUP_STRONG_ROTATION').sum()} |\n",
        f"| GROUP_MODERATE_ROTATION | {(df['signal_badge']=='GROUP_MODERATE_ROTATION').sum()} |\n",
        f"| GROUP_WEAK_ROTATION | {(df['signal_badge']=='GROUP_WEAK_ROTATION').sum()} |\n",
        f"| GROUP_RESEARCH_ONLY | {(df['signal_badge']=='GROUP_RESEARCH_ONLY').sum()} |\n",
        f"| GROUP_NO_SIGNAL | {(df['signal_badge']=='GROUP_NO_SIGNAL').sum()} |\n",
        "\n---\n",
        "\n## Tier A Groups (Broad-based + G2 pass)\n",
    ]
    if tiers_a.empty:
        lines.append("\n_No Tier A groups today._\n")
    else:
        lines.append("\n| Group | Layer | Score | Badge | Breadth EW | Sessions Since Turn |\n")
        lines.append("|---|---|---|---|---|---|\n")
        for _, r in tiers_a.iterrows():
            lines.append(
                f"| {r['group_name']} | {r['grouping_layer']} "
                f"| {r['group_rotation_score']:.2f} | {r['signal_badge']} "
                f"| {r['breadth_equal_weight']:.1%} | {r['sessions_since_turn']} |\n"
            )

    lines.append("\n## Tier B Groups (Coincident + G2 pass)\n")
    if tiers_b.empty:
        lines.append("\n_No Tier B groups today._\n")
    else:
        lines.append("\n| Group | Layer | Score | Badge | Breadth EW | Sessions Since Turn |\n")
        lines.append("|---|---|---|---|---|---|\n")
        for _, r in tiers_b.iterrows():
            lines.append(
                f"| {r['group_name']} | {r['grouping_layer']} "
                f"| {r['group_rotation_score']:.2f} | {r['signal_badge']} "
                f"| {r['breadth_equal_weight']:.1%} | {r['sessions_since_turn']} |\n"
            )

    lines.append("\n## Top 10 by Score\n")
    lines.append("\n| Rank | Group | Layer | Tier | Score | Badge | Breadth EW | Last Turn |\n")
    lines.append("|---|---|---|---|---|---|---|---|\n")
    for i, (_, r) in enumerate(df.head(10).iterrows(), 1):
        lines.append(
            f"| {i} | {r['group_name']} | {r['grouping_layer']} | {r['tier']} "
            f"| {r['group_rotation_score']:.2f} | {r['signal_badge']} "
            f"| {r['breadth_equal_weight']:.1%} | {r['last_turn_date'] or 'N/A'} |\n"
        )

    lines.append("\n---\n")
    lines.append("\n## No-Production-Change Confirmation\n\n")
    lines.append("- A3 production logic: **UNCHANGED**\n")
    lines.append("- OMS: **UNCHANGED**\n")
    lines.append("- Phase36 final_action: **UNCHANGED**\n")
    lines.append("- S3 status: **UNCHANGED**\n")
    lines.append("- DNSE routing: **UNCHANGED**\n")
    lines.append("- execution_allowed_flag: **false for ALL rows**\n")

    path.write_text("".join(lines), encoding="utf-8")
    log.info("MD card written: %s", path)


def _write_impl_report(df: pd.DataFrame, today_str: str) -> Path:
    rpt_path = _REPO_ROOT / "data/research/group_rotation/GROUP_ROTATION_IMPL_REPORT.md"
    rpt_path.parent.mkdir(parents=True, exist_ok=True)
    tier_counts = df["tier"].value_counts().to_dict()
    badge_counts = df["signal_badge"].value_counts().to_dict()
    lines = [
        "# Group Rotation Dashboard Integration — Implementation Report\n",
        f"\n**Date:** {today_str}\n",
        "\n## Verdict\n\nGROUP_ROTATION_DASHBOARD_RANKING_ONLY\n",
        "\n## Output Files\n\n",
        f"- `data/research/group_rotation/group_rotation_latest.csv` — {len(df)} groups\n",
        "- `data/research/group_rotation/group_rotation_latest.json`\n",
        "- `data/research/reports/group_rotation_card_latest.md`\n",
        "\n## Snapshot Statistics\n\n| Item | Value |\n|---|---|\n",
        f"| Total groups | {len(df)} |\n",
        f"| Snapshot date | {df['snapshot_date'].iloc[0]} |\n",
    ]
    for tier in ["A", "B", "C", "D"]:
        lines.append(f"| Tier {tier} | {tier_counts.get(tier, 0)} |\n")
    for badge in ["GROUP_STRONG_ROTATION", "GROUP_MODERATE_ROTATION", "GROUP_WEAK_ROTATION",
                  "GROUP_RESEARCH_ONLY", "GROUP_NO_SIGNAL"]:
        lines.append(f"| {badge} | {badge_counts.get(badge, 0)} |\n")
    lines.append("\n## No-Production-Change Confirmation\n\n")
    lines.append("- A3 production logic: UNCHANGED\n")
    lines.append("- OMS: UNCHANGED\n")
    lines.append("- Phase36 final_action: UNCHANGED\n")
    lines.append("- S3 status: UNCHANGED\n")
    lines.append("- DNSE routing: UNCHANGED\n")
    lines.append("- execution_allowed_flag = false for ALL rows (assertion checked at runtime)\n")
    lines.append("\n## Open Issues\n\n")
    lines.append("- OI-GR-1 (HIGH): No daily NAV series — scores are not portfolio-MAR-validated\n")
    lines.append("- OI-GR-2 (MEDIUM): follower_score uses last-5-session cloud transitions from cached panel; needs live daily refresh for production\n")
    lines.append("- OI-GR-3 (LOW): Leader classification uses historical data; LEADER_DRIVEN groups may be BROAD_BASED in current market conditions\n")
    lines.append("- OI-GR-4 (LOW): Only 1 group (theme_tag: rubber) passes A3 hard gate — group filter must not be used as A3 hard filter\n")
    lines.append("\n## Patch Fixes Applied (chatgpt_review_20260525)\n\n")
    lines.append("- Fix 1: Tier D badge cap — score>=0.5 -> GROUP_RESEARCH_ONLY, else GROUP_NO_SIGNAL\n")
    lines.append("- Fix 2: follower_score = min(n/3, 1.0) * 0.30 (explicit formula per spec)\n")
    lines.append("- Fix 3: Added alias columns group_tier, dashboard_badge, a3_gate_status, operator_note; added delta_mean_60d from P1 filter_value (available, not null)\n")
    lines.append("- No production files changed\n")
    rpt_path.write_text("".join(lines), encoding="utf-8")
    log.info("Implementation report: %s", rpt_path)
    return rpt_path


def _create_review_zip(today_str: str, impl_report: Path) -> Path:
    _REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = _REVIEW_DIR / f"group_rotation_dashboard_integration_patch_chatgpt_review_{today_str}.zip"

    output_files = [
        (_OUT_CSV,    "outputs/group_rotation_latest.csv"),
        (_OUT_JSON,   "outputs/group_rotation_latest.json"),
        (_OUT_CARD,   "outputs/group_rotation_card_latest.md"),
        (impl_report, "outputs/GROUP_ROTATION_IMPL_REPORT.md"),
    ]
    p1_outputs = [
        "group_breadth_turn_events.csv",
        "group_stock_lead_lag_summary.csv",
        "group_filter_value_ablation.csv",
        "a3_group_gate_replay.csv",
        "group_leader_follower_classification.csv",
        "group_regime_stability_summary.csv",
        "GROUP_BREADTH_RANKING_FEATURE_PROPOSAL.md",
        "P1_IMPLEMENTATION_REPORT.md",
    ]
    code_files = [
        "scripts/research/group_rotation/group_rotation_daily.py",
        "scripts/research/group_rotation/run_group_rotation.py",
        "scripts/research/sector_l4_causality/p1_config.py",
        "scripts/research/sector_l4_causality/p1_group_breadth.py",
    ]

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in output_files:
            if src.exists():
                zf.write(src, arcname=arcname)
            else:
                log.warning("Missing from zip: %s", src)
        for fname in p1_outputs:
            fpath = _P1_DIR / fname
            if fpath.exists():
                zf.write(fpath, arcname=f"p1_inputs/{fname}")
            else:
                log.warning("P1 input missing: %s", fpath)
        for rel in code_files:
            fpath = _REPO_ROOT / rel
            if fpath.exists():
                zf.write(fpath, arcname=f"code/{fpath.name}")

    log.info("Review zip: %s (%.1f KB)", zip_path, zip_path.stat().st_size / 1024)
    return zip_path


def refresh_group_rotation_snapshot(snapshot_date: Optional[str] = None) -> pd.DataFrame:
    """Build snapshot and write CSV/JSON/card (no review zip). For EOD/scan pipeline."""
    df = build_group_rotation_snapshot(snapshot_date=snapshot_date)
    assert (df["execution_allowed_flag"] == False).all(), \
        "CRITICAL: execution_allowed_flag must be False for all rows"
    _write_csv(df, _OUT_CSV)
    _write_json(df, _OUT_JSON)
    _write_card(df, _OUT_CARD)
    return df


def main(argv=None):
    parser = argparse.ArgumentParser(description="Group Rotation Dashboard Integration")
    parser.add_argument("--date", default=None, help="Snapshot date YYYY-MM-DD (default: latest)")
    args = parser.parse_args(argv)

    today_str = date.today().strftime("%Y%m%d")
    log.info("=" * 60)
    log.info("Group Rotation Dashboard Integration")
    log.info("DASHBOARD ONLY — no production changes")
    log.info("=" * 60)

    df = refresh_group_rotation_snapshot(snapshot_date=args.date)
    log.info("Safety check passed: execution_allowed_flag = false for all %d rows", len(df))
    impl_report = _write_impl_report(df, today_str)

    # Validation summary
    log.info("--- Validation ---")
    log.info("Groups: %d | Snapshot: %s", len(df), df["snapshot_date"].iloc[0])
    log.info("Tier A: %d | Tier B: %d | Tier C: %d | Tier D: %d",
             (df["tier"] == "A").sum(), (df["tier"] == "B").sum(),
             (df["tier"] == "C").sum(), (df["tier"] == "D").sum())
    log.info("STRONG: %d | MODERATE: %d | WEAK: %d | RESEARCH_ONLY: %d | NO_SIGNAL: %d",
             (df["signal_badge"] == "GROUP_STRONG_ROTATION").sum(),
             (df["signal_badge"] == "GROUP_MODERATE_ROTATION").sum(),
             (df["signal_badge"] == "GROUP_WEAK_ROTATION").sum(),
             (df["signal_badge"] == "GROUP_RESEARCH_ONLY").sum(),
             (df["signal_badge"] == "GROUP_NO_SIGNAL").sum())
    log.info("No A3/OMS/Phase36/DNSE/S3 files changed.")

    # Package review zip
    log.info("Packaging review zip ...")
    zip_path = _create_review_zip(today_str, impl_report)

    log.info("=" * 60)
    log.info("Done. Review zip: %s", zip_path)
    log.info("=" * 60)
    return str(zip_path)


if __name__ == "__main__":
    main()
