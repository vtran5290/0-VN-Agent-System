"""
Markdown section for Phase36 operator / daily_scan reports.
Dashboard-only — does not change final_action or OMS.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CSV = _REPO_ROOT / "data/research/group_rotation/group_rotation_latest.csv"
_P1_DIR = _REPO_ROOT / "data/research/sector_l4_causality"
_STOCK_PANEL = _P1_DIR / "stock_daily_cloud_panel.parquet"
_TURN_EVENTS = _P1_DIR / "group_breadth_turn_events.csv"


def _cache_freshness_lines() -> list[str]:
    lines: list[str] = []
    if _STOCK_PANEL.exists():
        try:
            sp = pd.read_parquet(_STOCK_PANEL, columns=["date"])
            lines.append(f"- **stock_daily_cloud_panel** last date: `{pd.Timestamp(sp['date'].max()).date()}`")
        except Exception:
            lines.append("- **stock_daily_cloud_panel:** unreadable")
    else:
        lines.append("- **stock_daily_cloud_panel:** missing")
    if _TURN_EVENTS.exists():
        try:
            te = pd.read_csv(_TURN_EVENTS, usecols=["date"])
            te["date"] = pd.to_datetime(te["date"])
            lines.append(f"- **group_breadth_turn_events** last date: `{te['date'].max().date()}`")
        except Exception:
            lines.append("- **group_breadth_turn_events:** unreadable")
    else:
        lines.append("- **group_breadth_turn_events:** missing")
    return lines


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines) + "\n"


def render_group_rotation_context_md(
    csv_path: Optional[Path] = None,
    *,
    max_validated: int = 5,
    max_research_only: int = 10,
) -> str:
    """
    Tier A/B validated context first (score >= 0.5, max N).
    Tier D research-only table below (score >= 0.5).
    """
    path = csv_path or _DEFAULT_CSV
    lines = [
        "## Group Rotation Context (dashboard only)\n\n",
        "> **DASHBOARD ONLY** — does not change `final_action`, OMS, or order routing. "
        "`execution_allowed_flag=false` for all groups.\n\n",
    ]
    if not path.is_file():
        lines.append(f"_Snapshot not found (`{path.relative_to(_REPO_ROOT)}`). "
                     "Run `python -m scripts.research.group_rotation.run_group_rotation`._\n\n")
        return "".join(lines)

    df = pd.read_csv(path)
    if df.empty:
        lines.append("_Group rotation snapshot empty._\n\n")
        return "".join(lines)

    snap = str(df["snapshot_date"].iloc[0])
    lines.append(f"- **Snapshot date:** {snap}\n")
    try:
        ssot_rel = path.relative_to(_REPO_ROOT)
    except ValueError:
        ssot_rel = path
    lines.append(f"- **SSOT:** `{ssot_rel}`\n")
    lines.append("- **P1 cache freshness:**\n")
    for fl in _cache_freshness_lines():
        lines.append(f"  {fl}\n")
    lines.append("\n")

    score = pd.to_numeric(df["group_rotation_score"], errors="coerce")
    validated = df[df["tier"].isin(["A", "B"]) & (score >= 0.5)].copy()
    validated = validated.sort_values("group_rotation_score", ascending=False).head(max_validated)

    lines.append("### Validated groups (Tier A/B, score ≥ 0.5)\n\n")
    if validated.empty:
        lines.append("_No Tier A/B groups with score ≥ 0.5 today._\n\n")
    else:
        rows = []
        for _, r in validated.iterrows():
            bew = r.get("breadth_equal_weight")
            bew_s = f"{float(bew):.1%}" if pd.notna(bew) else "—"
            rows.append([
                str(r["group_name"]),
                str(r["grouping_layer"]),
                str(r["tier"]),
                f"{float(r['group_rotation_score']):.2f}",
                str(r["signal_badge"]),
                bew_s,
                str(r.get("a3_gate_status", "")),
            ])
        lines.append(_md_table(
            ["Group", "Layer", "Tier", "Score", "Badge", "Breadth EW", "A3 gate"],
            rows,
        ))
        lines.append("\n")

    research = df[(df["tier"] == "D") & (score >= 0.5)].copy()
    research = research.sort_values("group_rotation_score", ascending=False).head(max_research_only)

    lines.append("### Research-only (Tier D — not validated rotation signals)\n\n")
    if research.empty:
        lines.append("_No Tier D groups with score ≥ 0.5._\n\n")
    else:
        rows = []
        for _, r in research.iterrows():
            bew = r.get("breadth_equal_weight")
            bew_s = f"{float(bew):.1%}" if pd.notna(bew) else "—"
            note = str(r.get("operator_note", ""))[:72]
            rows.append([
                str(r["group_name"]),
                str(r["grouping_layer"]),
                f"{float(r['group_rotation_score']):.2f}",
                str(r["signal_badge"]),
                bew_s,
                note,
            ])
        lines.append(_md_table(
            ["Group", "Layer", "Score", "Badge", "Breadth EW", "Note"],
            rows,
        ))
        lines.append("\n")

    lines.append(
        "_Full card:_ `data/research/reports/group_rotation_card_latest.md` · "
        "_Do not use group breadth as an A3 hard filter (OI-GR-4)._\n\n"
    )
    return "".join(lines)
